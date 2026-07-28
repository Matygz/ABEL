"""Capa de acceso a datos del Núcleo.

Encapsula todo el SQL del proyecto. El resto del código llama métodos de
esta clase y nunca escribe consultas.

Interfaz asíncrona: todos los métodos son corrutinas y no bloquean el bucle
de eventos mientras esperan a la base de datos.

Estrategia de conexión: se abre y se cierra una conexión por operación
(ver docs/decisiones). A la carga de la Fase 1 el costo es irrelevante, y
cada operación queda aislada: si la base estuvo caída, el siguiente intento
parte de cero sin estado corrupto.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


from nucleo.config import ConfigEntorno
from nucleo.errores import ErrorOperativo

logger = logging.getLogger(__name__)

class ErrorRepositorio(ErrorOperativo):
    """Fallo al acceder a la base de datos."""
    
class Repositorio:
    """Acceso asíncrono a la base de datos de ABEL."""

    def __init__(self, config: ConfigEntorno) -> None:
        self._conninfo = config.conninfo

    @asynccontextmanager
    async def _conexion(self) -> AsyncIterator[psycopg.AsyncConnection]:
        """Abre una conexión, la entrega, y la cierra al salir.

        Al salir sin excepción se confirma la transacción; si hubo excepción,
        se deshace. Las dos cosas las hace psycopg automáticamente.
        """
        try:
            async with await psycopg.AsyncConnection.connect(
                self._conninfo, row_factory=dict_row
            ) as conn:
                yield conn
        except psycopg.Error as exc:
            logger.debug("Fallo de base de datos: %s", exc)
            raise ErrorRepositorio(str(exc)) from exc

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    async def obtener_actor_id(self, actor_type: str, name: str) -> UUID:
        """Devuelve el id de un actor por tipo y nombre."""
        async with self._conexion() as conn:
            cur = await conn.execute(
                "SELECT id FROM actors WHERE actor_type = %s AND name = %s",
                (actor_type, name),
            )
            fila = await cur.fetchone()

        if fila is None:
            raise ErrorRepositorio(
                f"No existe el actor {actor_type}/{name}. "
                f"¿Se ejecutó db/schema/002_seed_base.sql?"
            )
        return fila["id"]

    async def leer_configuracion(self) -> dict[str, Any]:
        """Devuelve la configuración vigente como diccionario clave -> valor."""
        async with self._conexion() as conn:
            cur = await conn.execute("SELECT key, value FROM current_settings")
            filas = await cur.fetchall()

        return {fila["key"]: fila["value"] for fila in filas}

    # ------------------------------------------------------------------
    # Ejecuciones
    # ------------------------------------------------------------------

    async def iniciar_ejecucion(
        self, hostname: str, version: str, pid: int
    ) -> UUID:
        """Registra el arranque del Núcleo. Devuelve el id de la ejecución."""
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                INSERT INTO runs (hostname, version, pid)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (hostname, version, pid),
            )
            fila = await cur.fetchone()

        logger.info("Ejecución iniciada: %s", fila["id"])
        return fila["id"]

    async def finalizar_ejecucion(
        self, run_id: UUID, motivo: str = "clean"
    ) -> None:
        """Cierra una ejecución. Si nunca se llama, queda registrada como caída."""
        async with self._conexion() as conn:
            await conn.execute(
                """
                UPDATE runs
                   SET ended_at = now(), stop_reason = %s
                 WHERE id = %s AND ended_at IS NULL
                """,
                (motivo, run_id),
            )

        logger.info("Ejecución finalizada: %s (%s)", run_id, motivo)

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    async def registrar_evento(
        self,
        event_type: str,
        actor_id: UUID,
        run_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> UUID:
        """Registra un evento. Devuelve su id."""
        if occurred_at is None:
            occurred_at = datetime.now(timezone.utc)

        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                INSERT INTO events
                    (occurred_at, event_type, actor_id, run_id, payload)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    occurred_at,
                    event_type,
                    actor_id,
                    run_id,
                    Jsonb(payload or {}),
                ),
            )
            fila = await cur.fetchone()

        return fila["id"]