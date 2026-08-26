"""El ciclo completo de una conversación con ABEL.

Reúne las piezas: analizar, ejecutar, decidir si vale la pena hablar, y
expresar. Es la puerta única — la interfaz web, un script o cualquier otra
entrada llaman acá.

Que ABEL no responda es un resultado válido, no un fallo.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from nucleo.lenguaje.analizador import Analizador
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.expresador import Expresador
from nucleo.lenguaje.extractor_hechos import ExtractorHechos
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
        sangre=None,
        extractor_hechos: ExtractorHechos | None = None,
    ) -> None:
        self._repo = repositorio
        self._modelo = modelo
        self._contexto = contexto
        self._analizador = analizador
        self._despachador = despachador
        self._criterio = criterio
        self._expresador = expresador
        self._turnos = turnos_recordados
        self._sangre = sangre
        self._extractor_hechos = extractor_hechos

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

        turno_event_id = None
        if user_id is not None:
            turno_event_id = await self._repo.registrar_turno(
                user_id, "user", mensaje, session_id=session_id
            )

        contexto = await self._contexto.obtener(usuario=usuario)
        analisis = await self._analizador.analizar(mensaje, contexto)

        # La extracción no depende de qué capacidad ganó: contar algo es a la
        # vez un hecho y un acto conversacional. Si dependiera del
        # clasificador, un hecho se perdería entero porque la frase no se
        # parece lo suficiente a los ejemplos — pasó con "mi papa se llama
        # Julio" sin tilde, que quedaba fuera de alcance por 0.699. Un
        # piso de palabras evita gastar una llamada al modelo en "ok" o
        # "dale"; no hace falta filtrar más: el extractor ya devuelve
        # {"hechos": []} cuando no hay nada que sacar.
        if (
            self._extractor_hechos is not None
            and user_id is not None
            and len(mensaje.split()) >= 3
        ):
            # Sin bloquear la respuesta: la extracción ocurre en paralelo y
            # la conversación sigue su curso normal. Si falla, se registra
            # y no se entera nadie más — no es lo que la persona vino a
            # escuchar.
            asyncio.create_task(
                self._extraer_hechos_en_segundo_plano(
                    mensaje, user_id, turno_event_id
                )
            )

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

        if self._sangre is not None:
            # Hablar acerca. El decaimiento se encarga de alejar.
            self._sangre.empujar("conexion", 0.4)

        return Turno(
            texto=texto,
            postura=decision.postura.value,
            intenciones=tuple(
                i.capacidad or "fuera_de_alcance" for i in analisis.intenciones
            ),
            origenes=tuple(i.origen for i in analisis.intenciones),
            descartadas=len(resultados.resueltos) - len(decision.resueltos),
        )

    async def _extraer_hechos_en_segundo_plano(
        self, mensaje: str, user_id, event_id
    ) -> None:
        """Corre en su propia tarea: un fallo acá no debe tocar la conversación."""
        try:
            await self._extractor_hechos.extraer_y_registrar(
                mensaje, user_id, event_id
            )
        except Exception:
            logger.exception("Fallo al extraer hechos de un mensaje.")
