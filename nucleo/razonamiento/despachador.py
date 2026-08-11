"""Enruta cada intención al motor que sabe resolverla.

No resuelve nada por sí mismo: decide quién lo hace. Agregar una clase nueva
de problema es registrar un motor más, no modificar esta pieza.

Devuelve resultados, no texto. Cómo se dicen —y si se dicen— lo decide el
expresador (5.3) y el criterio de habla (5.4).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from nucleo.lenguaje.interprete import Intencion, Interpretacion, TipoIntencion
from nucleo.razonamiento.motor_calculo import MotorCalculo
from nucleo.razonamiento.motor_memoria import MotorMemoria
from nucleo.razonamiento.resultado import Procedencia, Resultado, sin_alcance

logger = logging.getLogger(__name__)

TIMEOUT_MOTOR = 45.0


@dataclass(frozen=True)
class Resuelto:
    """Una intención junto con lo que produjo."""

    intencion: Intencion
    resultado: Resultado


@dataclass(frozen=True)
class Respuesta:
    """Todo lo que ABEL tiene para responder a un mensaje."""

    resueltos: tuple[Resuelto, ...]
    interpretacion: Interpretacion

    @property
    def hay_conversacion(self) -> bool:
        return any(
            r.intencion.tipo == TipoIntencion.CONVERSAR for r in self.resueltos
        )

    @property
    def datos_utiles(self) -> tuple[Resuelto, ...]:
        """Resultados con contenido real, descartando los vacíos."""
        return tuple(
            r for r in self.resueltos
            if r.resultado.resuelto and not r.resultado.vacio
        )


class Despachador:
    """Manda cada intención al motor correspondiente."""

    def __init__(
        self,
        motor_memoria: MotorMemoria,
        motor_calculo: MotorCalculo,
    ) -> None:
        self._motores = {
            TipoIntencion.CONSULTAR_MEMORIA: motor_memoria.resolver,
            TipoIntencion.CALCULAR: motor_calculo.resolver,
        }

    async def despachar(self, interpretacion: Interpretacion) -> Respuesta:
        """Resuelve todas las intenciones de un mensaje.

        Se resuelven en paralelo: son independientes entre sí, y una consulta
        lenta no debería retrasar a las demás.
        """
        if interpretacion.vacia:
            return Respuesta(resueltos=(), interpretacion=interpretacion)

        tareas = [
            self._resolver_una(intencion)
            for intencion in interpretacion.intenciones
        ]
        resueltos = await asyncio.gather(*tareas)

        return Respuesta(
            resueltos=tuple(resueltos),
            interpretacion=interpretacion,
        )

    # ------------------------------------------------------------------

    async def _resolver_una(self, intencion: Intencion) -> Resuelto:
        motor = self._motores.get(intencion.tipo)

        if motor is None:
            # Conversar y fuera_de_alcance no necesitan motor: el resultado
            # es la intención misma. Uno lo maneja el expresador, el otro
            # es una respuesta honesta sobre un límite.
            return Resuelto(intencion, self._sin_motor(intencion))

        try:
            resultado = await asyncio.wait_for(
                motor(intencion), timeout=TIMEOUT_MOTOR
            )
        except TimeoutError:
            logger.warning(
                "El motor de %s superó %ss.", intencion.tipo, TIMEOUT_MOTOR
            )
            resultado = Resultado(
                tipo=intencion.tipo,
                procedencia=Procedencia.NINGUNA,
                falta="resolver eso en un tiempo razonable",
            )
        except Exception:
            # Un motor que revienta no debe tumbar la respuesta entera: las
            # demás intenciones del mensaje pueden haberse resuelto bien.
            logger.exception("Fallo inesperado en el motor de %s.", intencion.tipo)
            resultado = Resultado(
                tipo=intencion.tipo,
                procedencia=Procedencia.NINGUNA,
                falta="resolver eso ahora",
            )

        return Resuelto(intencion, resultado)

    @staticmethod
    def _sin_motor(intencion: Intencion) -> Resultado:
        if intencion.tipo == TipoIntencion.FUERA_DE_ALCANCE:
            return sin_alcance(
                str(intencion.parametros.get("que_falta", "esa capacidad"))
            )

        return Resultado(
            tipo=TipoIntencion.CONVERSAR,
            procedencia=Procedencia.NINGUNA,
            datos=intencion.parametros,
        )