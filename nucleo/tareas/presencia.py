"""Marca de presencia.

Registro periódico que deja constancia de que el Núcleo existía en un
momento dado. No inspecciona nada: su valor está en la ausencia, no en la
presencia. Un hueco entre marcas indica que el Núcleo estuvo caído, y
delimita cuándo.

Ver docs/desarrollo/glosario.md — no confundir con el "latido" de V.0.2.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from nucleo.datos.repositorio import Repositorio

logger = logging.getLogger(__name__)


def crear_tarea_presencia(
    repositorio: Repositorio,
    actor_id: UUID,
    run_id: UUID,
    inicio: datetime,
):
    """Arma la tarea de presencia con su contexto ya resuelto."""

    async def marcar_presencia() -> None:
        ahora = datetime.now(timezone.utc)
        uptime = (ahora - inicio).total_seconds()

        await repositorio.registrar_evento(
            event_type="presence_mark",
            actor_id=actor_id,
            run_id=run_id,
            payload={"uptime_seconds": round(uptime, 1)},
            occurred_at=ahora,
        )
        logger.debug("Marca de presencia. Uptime: %.1fs", uptime)

    return marcar_presencia