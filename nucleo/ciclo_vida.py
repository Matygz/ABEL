"""Ciclo de vida del Núcleo.

Registra el arranque y garantiza el cierre ordenado de la ejecución, incluso
si el Núcleo termina por interrupción o por error. Una ejecución que queda
sin cerrar es, por diseño, la señal de que el proceso murió sin avisar.
"""

from __future__ import annotations

import logging
import os
import socket
from datetime import datetime, timezone
from types import TracebackType
from uuid import UUID

from nucleo.datos.repositorio import ErrorRepositorio, Repositorio

logger = logging.getLogger(__name__)


class CicloVida:
    """Gestiona el arranque y el apagado de una ejecución del Núcleo."""

    def __init__(self, repositorio: Repositorio, version: str) -> None:
        self.inicio: datetime | None = None
        self.motivo_solicitado: str | None = None
        self._repo = repositorio
        self._version = version
        self.actor_id: UUID | None = None
        self.run_id: UUID | None = None
        self.inicio: datetime | None = None

    async def __aenter__(self) -> CicloVida:
        self.actor_id = await self._repo.obtener_actor_id("system", "core")
        self.inicio = datetime.now(timezone.utc)

        self.run_id = await self._repo.iniciar_ejecucion(
            hostname=socket.gethostname(),
            version=self._version,
            pid=os.getpid(),
        )

        await self._repo.registrar_evento(
            event_type="core_started",
            actor_id=self.actor_id,
            run_id=self.run_id,
            payload={"version": self._version, "pid": os.getpid()},
            occurred_at=self.inicio,
        )

        logger.info("Núcleo iniciado. Ejecución %s (pid %s)", self.run_id, os.getpid())
        return self

    async def __aexit__(
        self,
        tipo_exc: type[BaseException] | None,
        exc: BaseException | None,
        traza: TracebackType | None,
    ) -> bool:
        motivo = self.motivo_solicitado or self._motivo(tipo_exc)
        uptime = (datetime.now(timezone.utc) - self.inicio).total_seconds()

        try:
            await self._repo.registrar_evento(
                event_type="core_stopped",
                actor_id=self.actor_id,
                run_id=self.run_id,
                payload={"reason": motivo, "uptime_seconds": round(uptime, 1)},
            )
            await self._repo.finalizar_ejecucion(self.run_id, motivo)
        except ErrorRepositorio:
            logger.error(
                "No se pudo cerrar la ejecución %s en la base. "
                "Quedará registrada como caída.",
                self.run_id,
            )

        logger.info("Núcleo detenido (%s). Uptime: %.1fs", motivo, uptime)
        return False

    @staticmethod
    def _motivo(tipo_exc: type[BaseException] | None) -> str:
        if tipo_exc is None:
            return "clean"
        if issubclass(tipo_exc, (KeyboardInterrupt, SystemExit)):
            return "interrupted"
        return "error"