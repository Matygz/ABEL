"""El ciclo completo de una conversación con ABEL.

Reúne las piezas: analizar, ejecutar, decidir si vale la pena hablar, y
expresar. Es la puerta única — la interfaz web, un script o cualquier otra
entrada llaman acá.

Que ABEL no responda es un resultado válido, no un fallo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from nucleo.lenguaje.analizador import Analizador
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.expresador import Expresador
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.razonamiento.criterio import Criterio, Postura
from nucleo.razonamiento.despachador import Despachador

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Turno:
    """Lo que ABEL produjo ante un mensaje."""

    texto: str
    postura: str
    intenciones: tuple[str, ...]
    origenes: tuple[str, ...] = ()
    descartadas: int = 0

    @property
    def habla(self) -> bool:
        return bool(self.texto)


class Conversacion:
    """Procesa un mensaje de punta a punta, con memoria de los turnos previos."""

    def __init__(
        self,
        repositorio,
        modelo: ServidorModelo,
        contexto: ProveedorContexto,
        analizador: Analizador,
        despachador: Despachador,
        criterio: Criterio,
        expresador: Expresador,
        turnos_recordados: int = 8,
    ) -> None:
        self._repo = repositorio
        self._modelo = modelo
        self._contexto = contexto
        self._analizador = analizador
        self._despachador = despachador
        self._criterio = criterio
        self._expresador = expresador
        self._turnos = turnos_recordados

    async def responder(
        self,
        mensaje: str,
        usuario: str = "",
        user_id=None,
        abel_id=None,
        session_id=None,
    ) -> Turno:
        """Procesa un mensaje y devuelve lo que ABEL tenga para decir."""
        mensaje = mensaje.strip()
        if not mensaje:
            return Turno(texto="", postura=Postura.CALLAR.value, intenciones=())

        # El modelo se carga acá: si estaba descargado por inactividad, la
        # primera respuesta tarda unos segundos más. Muchos mensajes no lo
        # necesitan, pero el expresador sí.
        await self._modelo.asegurar_disponible()

        # El historial se lee ANTES de registrar el turno actual: si no, el
        # mensaje recién llegado aparecería como parte de lo que venían
        # hablando y se detectaría a sí mismo como repetición.
        previos = (
            await self._repo.ultimos_turnos(user_id, session_id, self._turnos)
            if user_id is not None and session_id is not None else []
        )

        if user_id is not None:
            await self._repo.registrar_turno(
                user_id, "user", mensaje, session_id=session_id
            )

        contexto = await self._contexto.obtener(usuario=usuario)
        analisis = await self._analizador.analizar(mensaje, contexto)
        resultados = await self._despachador.despachar(analisis)
        decision = self._criterio.decidir(resultados, previos)
        texto = await self._expresador.expresar(
            resultados, decision, usuario, previos
        )

        if user_id is not None and abel_id is not None:
            await self._repo.registrar_turno(
                abel_id,
                "abel",
                texto,
                session_id=session_id,
                metadatos={
                    "addressee": str(user_id),
                    "postura": decision.postura.value,
                    "capacidades": [
                        i.capacidad or "fuera_de_alcance"
                        for i in analisis.intenciones
                    ],
                },
            )

        logger.info(
            "Turno: %s | %s | postura %s",
            ", ".join(
                i.capacidad or "fuera_de_alcance" for i in analisis.intenciones
            ),
            ", ".join(i.origen for i in analisis.intenciones),
            decision.postura.value,
        )

        return Turno(
            texto=texto,
            postura=decision.postura.value,
            intenciones=tuple(
                i.capacidad or "fuera_de_alcance" for i in analisis.intenciones
            ),
            origenes=tuple(i.origen for i in analisis.intenciones),
            descartadas=len(resultados.resueltos) - len(decision.resueltos),
        )
