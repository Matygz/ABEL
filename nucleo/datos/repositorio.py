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
    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    async def obtener_usuario_por_username(self, username: str) -> dict[str, Any]:
        """Devuelve un usuario por su username. Falla si no existe."""
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT u.id, u.username, u.full_name, u.role, a.name AS display_name
                  FROM users u
                  JOIN actors a ON a.id = u.id
                 WHERE u.username = %s
                """,
                (username,),
            )
            fila = await cur.fetchone()

        if fila is None:
            raise ErrorRepositorio(f"No existe el usuario {username!r}.")
        return fila

    # ------------------------------------------------------------------
    # Dispositivos
    # ------------------------------------------------------------------

    async def obtener_dispositivo(self, device_id: UUID) -> dict[str, Any] | None:
        """Devuelve un dispositivo por su id, o None si no existe."""
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT d.*, a.name, a.active
                  FROM devices d
                  JOIN actors a ON a.id = d.id
                 WHERE d.id = %s
                """,
                (device_id,),
            )
            return await cur.fetchone()

    async def listar_dispositivos(self, incluir_revocados: bool = False) -> list[dict[str, Any]]:
        """Lista los dispositivos registrados."""
        condicion = "" if incluir_revocados else "WHERE d.revoked_at IS NULL"
        async with self._conexion() as conn:
            cur = await conn.execute(
                f"""
                SELECT a.name, d.id, d.platform, d.trust_level,
                       d.authorized_at, d.revoked_at
                  FROM devices d
                  JOIN actors a ON a.id = d.id
                  {condicion}
                 ORDER BY d.authorized_at
                """
            )
            return await cur.fetchall()

    async def autorizar_dispositivo(
        self,
        nombre: str,
        platform: str,
        autorizado_por: UUID,
        trust_level: str = "restricted",
        politica: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Registra un dispositivo nuevo. Devuelve su id.

        Inserta en `actors` y en `devices` dentro de una misma transacción:
        una fila en `devices` sin su fila en `actors` sería inconsistente.
        """
        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    INSERT INTO actors (actor_type, name)
                    VALUES ('device', %s)
                    RETURNING id
                    """,
                    (nombre,),
                )
                device_id = (await cur.fetchone())["id"]

                await conn.execute(
                    """
                    INSERT INTO devices
                        (id, platform, trust_level, authorized_by,
                         authorization_policy, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        device_id,
                        platform,
                        trust_level,
                        autorizado_por,
                        politica,
                        Jsonb(metadata or {}),
                    ),
                )

                await conn.execute(
                    """
                    INSERT INTO events
                        (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'device_authorized', %s, %s)
                    """,
                    (
                        autorizado_por,
                        Jsonb({
                            "device_id": str(device_id),
                            "device_name": nombre,
                            "platform": platform,
                            "trust_level": trust_level,
                            "policy": politica,
                        }),
                    ),
                )

        logger.info(
            "Dispositivo autorizado: %s (%s, %s) por %s",
            nombre, device_id, trust_level, autorizado_por,
        )
        return device_id

    async def revocar_dispositivo(
        self, device_id: UUID, revocado_por: UUID, motivo: str
    ) -> None:
        """Revoca un dispositivo. No se borra: sus eventos históricos persisten."""
        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    UPDATE devices
                       SET revoked_at = now(),
                           revoked_by = %s,
                           revocation_reason = %s
                     WHERE id = %s AND revoked_at IS NULL
                    RETURNING id
                    """,
                    (revocado_por, motivo, device_id),
                )
                if await cur.fetchone() is None:
                    raise ErrorRepositorio(
                        f"El dispositivo {device_id} no existe o ya estaba revocado."
                    )

                await conn.execute(
                    "UPDATE actors SET active = false WHERE id = %s",
                    (device_id,),
                )

                await conn.execute(
                    """
                    INSERT INTO events
                        (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'device_revoked', %s, %s)
                    """,
                    (
                        revocado_por,
                        Jsonb({"device_id": str(device_id), "reason": motivo}),
                    ),
                )

        logger.info("Dispositivo revocado: %s (%s)", device_id, motivo)