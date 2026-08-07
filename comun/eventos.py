"""Bus de eventos interno del proceso.

Cuando algo relevante ocurre en el Núcleo, se publica acá. Quien esté
interesado se suscribe y lo recibe. El publicador no sabe quién escucha ni
cuántos son: solo anuncia.

Es un bus en memoria, del proceso. No persiste nada —de eso se encarga la
base— ni cruza a otros procesos. Su propósito es desacoplar: registrar un
evento y reaccionar a un evento dejan de estar atados.

Primer consumidor: la interfaz web, que empuja los cambios a los navegadores
en vivo. Pero cualquier módulo futuro que deba reaccionar a lo que ocurre se
conecta del mismo modo.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Cuántos avisos puede acumular un suscriptor lento antes de que se le
# empiecen a descartar. El bus nunca se bloquea por un consumidor lento:
# es preferible que ese consumidor pierda avisos a que frene al Núcleo.
MAX_PENDIENTES_POR_SUSCRIPTOR = 256


@dataclass(frozen=True)
class Aviso:
    """Lo que se publica cuando ocurre un evento.

    No es el evento completo de la base: es la noticia de que ocurrió, con lo
    mínimo para que un suscriptor decida si le interesa y consulte el detalle
    si lo necesita.
    """

    tipo_evento: str
    actor_id: Any
    occurred_at: datetime
    resumen: dict[str, Any]


class BusEventos:
    """Publica avisos a suscriptores desacoplados."""

    def __init__(self) -> None:
        self._suscriptores: set[asyncio.Queue[Aviso]] = set()
        self._descartados = 0

    def publicar(self, aviso: Aviso) -> None:
        """Anuncia un aviso a todos los suscriptores.

        No es asíncrono a propósito: publicar no debe poder bloquear a quien
        registra un evento. Si un suscriptor tiene la cola llena, se le
        descarta el aviso y se sigue.
        """
        for cola in self._suscriptores:
            try:
                cola.put_nowait(aviso)
            except asyncio.QueueFull:
                self._descartados += 1
                # Un suscriptor lento puede descartar cientos de avisos
                # seguidos. Se informa cada 100 para no inundar el log.
                if self._descartados % 100 == 1:
                    logger.warning(
                        "Suscriptor lento: %d aviso(s) descartado(s) en total.",
                        self._descartados,
                    )

    @asynccontextmanager
    async def suscribirse(self) -> AsyncIterator[asyncio.Queue[Aviso]]:
        """Entrega una cola por la que llegan los avisos mientras dure el uso.

        Se usa como contexto: al salir, la suscripción se limpia sola. Así un
        navegador que cierra la pestaña no deja una cola huérfana creciendo.
        """
        cola: asyncio.Queue[Aviso] = asyncio.Queue(
            maxsize=MAX_PENDIENTES_POR_SUSCRIPTOR
        )
        self._suscriptores.add(cola)
        logger.debug("Nuevo suscriptor. Total: %d.", len(self._suscriptores))
        try:
            yield cola
        finally:
            self._suscriptores.discard(cola)
            logger.debug("Suscriptor retirado. Total: %d.", len(self._suscriptores))

    @property
    def cantidad_suscriptores(self) -> int:
        return len(self._suscriptores)