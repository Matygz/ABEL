"""Ejecuta las capacidades que el analizador identificó.

No decide nada: el analizador ya eligió qué capacidad corresponde y con qué
parámetros. Acá solo se ejecutan y se juntan los resultados.

Las intenciones se resuelven en paralelo porque son independientes: si un
mensaje pide un dato y además un cálculo, no hay razón para hacerlos en fila.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from nucleo.capacidades.registro import ErrorCapacidad, RegistroCapacidades
from nucleo.lenguaje.analizador import Analisis, Intencion
from nucleo.razonamiento.resultado import Procedencia, Resultado, sin_alcance

logger = logging.getLogger(__name__)

TIMEOUT_CAPACIDAD = 45.0


@dataclass(frozen=True)
class Resuelto:
    """Una intención junto con lo que produjo."""

    intencion: Intencion
    resultado: Resultado


@dataclass(frozen=True)
class Respuesta:
    """Todo lo que ABEL tiene para responder a un mensaje."""

    resueltos: tuple[Resuelto, ...]
    analisis: Analisis

    @property
    def hay_conversacion(self) -> bool:
        return any(r.intencion.tipo == "conversar" for r in self.resueltos)

    @property
    def datos_utiles(self) -> tuple[Resuelto, ...]:
        """Resultados con contenido real, descartando los vacíos."""
        return tuple(
            r for r in self.resueltos
            if r.resultado.resuelto and not r.resultado.vacio
        )


class Despachador:
    """Ejecuta capacidades y junta lo que produjeron."""

    def __init__(self, registro: RegistroCapacidades) -> None:
        self._registro = registro

    async def despachar(self, analisis: Analisis) -> Respuesta:
        """Ejecuta todas las intenciones de un mensaje."""
        if analisis.vacio:
            return Respuesta(resueltos=(), analisis=analisis)

        resueltos = await asyncio.gather(
            *(self._ejecutar(i) for i in analisis.intenciones)
        )
        return Respuesta(resueltos=tuple(resueltos), analisis=analisis)

    # ------------------------------------------------------------------

    async def _ejecutar(self, intencion: Intencion) -> Resuelto:
        if intencion.fuera_de_alcance:
            return Resuelto(
                intencion,
                sin_alcance(
                    str(intencion.parametros.get("que_falta", "esa capacidad"))
                ),
            )

        try:
            resultado = await asyncio.wait_for(
                self._registro.ejecutar(
                    intencion.capacidad, intencion.parametros
                ),
                timeout=TIMEOUT_CAPACIDAD,
            )
        except TimeoutError:
            logger.warning(
                "La capacidad %s superó %ss.",
                intencion.capacidad, TIMEOUT_CAPACIDAD,
            )
            resultado = Resultado(
                tipo=intencion.tipo,
                procedencia=Procedencia.NINGUNA,
                falta="resolver eso en un tiempo razonable",
            )
        except ErrorCapacidad as exc:
            logger.error("Capacidad %s: %s", intencion.capacidad, exc)
            resultado = Resultado(
                tipo=intencion.tipo,
                procedencia=Procedencia.NINGUNA,
                falta="resolver eso ahora",
            )
        except Exception:
            # Una capacidad que revienta no debe tumbar la respuesta entera:
            # las demás intenciones del mensaje pueden haberse resuelto bien.
            logger.exception(
                "Fallo inesperado en la capacidad %s.", intencion.capacidad
            )
            resultado = Resultado(
                tipo=intencion.tipo,
                procedencia=Procedencia.NINGUNA,
                falta="resolver eso ahora",
            )

        return Resuelto(intencion, resultado)