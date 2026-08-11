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

import hashlib
import secrets

from comun.eventos import BusEventos
from nucleo.config import ConfigEntorno
from comun.errores import ErrorOperativo

from typing import Any, AsyncIterator, Sequence

from protocolos.contenidos import Observacion

logger = logging.getLogger(__name__)


class ErrorRepositorio(ErrorOperativo):
    """Fallo al acceder a la base de datos."""
    
class Repositorio:
    """Acceso asíncrono a la base de datos de ABEL."""

    def __init__(self, config: ConfigEntorno, bus: "BusEventos | None" = None) -> None:
        self._config = config
        self._conninfo = config.conninfo
        self._bus = bus

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
            
        if self._bus is not None:
            from comun.eventos import Aviso
            self._bus.publicar(
                Aviso(
                    tipo_evento=event_type,
                    actor_id=actor_id,
                    occurred_at=occurred_at or datetime.now(timezone.utc),
                    resumen=payload or {},
                )
            )
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

    async def listar_usuarios(self) -> list[dict[str, Any]]:
        """Lista los usuarios registrados."""
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT u.id, u.username, u.full_name, u.role, a.name
                  FROM users u JOIN actors a ON a.id = u.id
                 ORDER BY u.username
                """
            )
            return await cur.fetchall()

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

        # ------------------------------------------------------------------
    # Observaciones de Nodos
    # ------------------------------------------------------------------

    async def obtener_dispositivo_activo(self, device_id: UUID) -> dict[str, Any] | None:
        """Devuelve un dispositivo solo si está autorizado y no revocado.

        Es la consulta que decide si un Nodo puede conectarse. Un dispositivo
        revocado o desactivado devuelve None: la revocación es permanente
        hasta que un admin la levante (ver decisión 0011).
        """
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT d.id, d.platform, d.trust_level, a.name
                  FROM devices d
                  JOIN actors a ON a.id = d.id
                 WHERE d.id = %s
                   AND d.revoked_at IS NULL
                   AND a.active = true
                """,
                (device_id,),
            )
            return await cur.fetchone()

    async def obtener_tipos_de_evento(self) -> set[str]:
        """Devuelve los tipos de evento válidos del catálogo."""
        async with self._conexion() as conn:
            cur = await conn.execute("SELECT name FROM event_types")
            return {fila["name"] for fila in await cur.fetchall()}

    async def persistir_observaciones(
        self,
        device_id: UUID,
        observaciones: Sequence[Observacion],
        run_id: UUID | None = None,
    ) -> tuple[list[UUID], list[tuple[UUID, str]]]:
        """Persiste un lote de observaciones. Devuelve (confirmadas, rechazadas).

        Idempotente: el id de cada observación lo genera el Nodo y se usa como
        events.id. Un reenvío por ack perdido no duplica nada — el INSERT
        choca con la clave primaria y se ignora (ver decisión 0002).

        El lote entero va en una transacción: o se escribe todo lo válido, o
        no se escribe nada. Solo entonces se confirma.
        """
        if not observaciones:
            return [], []

        tipos_validos = await self.obtener_tipos_de_evento()

        aceptadas: list[Observacion] = []
        rechazadas: list[tuple[UUID, str]] = []
        for obs in observaciones:
            if obs.event_type not in tipos_validos:
                rechazadas.append((obs.id, "unknown_event_type"))
            else:
                aceptadas.append(obs)

        if aceptadas:
            filas = [
                (
                    obs.id,
                    obs.occurred_at,
                    obs.event_type,
                    device_id,
                    run_id,
                    Jsonb(obs.data),
                )
                for obs in aceptadas
            ]
            async with self._conexion() as conn:
                async with conn.transaction():
                    await conn.cursor().executemany(
                        """
                        INSERT INTO events
                            (id, occurred_at, event_type, actor_id, run_id, payload)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        filas,
                    )

        if rechazadas:
            logger.warning(
                "Dispositivo %s: %d observación(es) rechazada(s) por tipo desconocido.",
                device_id, len(rechazadas),
            )

        return [obs.id for obs in aceptadas], rechazadas

# ------------------------------------------------------------------
    # Claves de dispositivos
    # ------------------------------------------------------------------

    async def registrar_clave(
        self,
        device_id: UUID,
        clave_publica: bytes,
        creada_por: UUID,
        etiqueta: str | None = None,
    ) -> UUID:
        """Registra una clave pública para un dispositivo."""
        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    INSERT INTO device_keys
                        (device_id, public_key, created_by, label)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (device_id, clave_publica, creada_por, etiqueta),
                )
                key_id = (await cur.fetchone())["id"]

                await conn.execute(
                    """
                    INSERT INTO events (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'device_key_registered', %s, %s)
                    """,
                    (
                        creada_por,
                        Jsonb({
                            "device_id": str(device_id),
                            "key_id": str(key_id),
                            "label": etiqueta,
                        }),
                    ),
                )

        logger.info("Clave registrada para %s: %s", device_id, key_id)
        return key_id

    async def obtener_claves_activas(self, device_id: UUID) -> list[bytes]:
        """Devuelve las claves públicas vigentes de un dispositivo.

        Un dispositivo puede tener más de una durante una rotación.
        """
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT public_key FROM device_keys
                 WHERE device_id = %s AND revoked_at IS NULL
                 ORDER BY created_at DESC
                """,
                (device_id,),
            )
            return [bytes(fila["public_key"]) for fila in await cur.fetchall()]

    async def revocar_clave(
        self, key_id: UUID, revocada_por: UUID, motivo: str
    ) -> None:
        """Revoca una clave. El dispositivo conserva su identidad."""
        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    UPDATE device_keys
                       SET revoked_at = now(),
                           revoked_by = %s,
                           revocation_reason = %s
                     WHERE id = %s AND revoked_at IS NULL
                    RETURNING device_id
                    """,
                    (revocada_por, motivo, key_id),
                )
                fila = await cur.fetchone()
                if fila is None:
                    raise ErrorRepositorio(
                        f"La clave {key_id} no existe o ya estaba revocada."
                    )

                await conn.execute(
                    """
                    INSERT INTO events (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'device_key_revoked', %s, %s)
                    """,
                    (
                        revocada_por,
                        Jsonb({
                            "device_id": str(fila["device_id"]),
                            "key_id": str(key_id),
                            "reason": motivo,
                        }),
                    ),
                )

        logger.info("Clave revocada: %s (%s)", key_id, motivo)

    async def listar_claves(self, device_id: UUID) -> list[dict[str, Any]]:
        """Lista las claves de un dispositivo, incluidas las revocadas."""
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT id, label, algorithm, created_at, revoked_at,
                       revocation_reason
                  FROM device_keys
                 WHERE device_id = %s
                 ORDER BY created_at DESC
                """,
                (device_id,),
            )
            return await cur.fetchall()

    # ------------------------------------------------------------------
    # Sesiones de interfaz
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_token(token: str) -> bytes:
        """Hash del token de sesión.

        SHA-256 alcanza: el token es aleatorio de 32 bytes, no un secreto
        elegido por una persona. Argon2 está diseñado para resistir fuerza
        bruta contra contraseñas débiles, y acá no hay nada que adivinar.
        """
        return hashlib.sha256(token.encode("ascii")).digest()

    async def abrir_sesion(
        self,
        user_id: UUID,
        device_id: UUID,
        duracion_horas: int = 720,
    ) -> str:
        """Crea una sesión y devuelve su token.

        El token se devuelve una sola vez: en la base queda solo su hash.
        """
        token = secrets.token_urlsafe(32)

        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    INSERT INTO sessions
                        (user_id, device_id, token_hash, expires_at)
                    VALUES (%s, %s, %s, now() + (%s * INTERVAL '1 hour'))
                    RETURNING id
                    """,
                    (user_id, device_id, self._hash_token(token), duracion_horas),
                )
                session_id = (await cur.fetchone())["id"]

                await conn.execute(
                    """
                    INSERT INTO events (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'session_opened', %s, %s)
                    """,
                    (
                        user_id,
                        Jsonb({
                            "session_id": str(session_id),
                            "device_id": str(device_id),
                        }),
                    ),
                )

        logger.info("Sesión abierta: %s en dispositivo %s", session_id, device_id)
        return token

    async def validar_sesion(self, token: str) -> dict[str, Any] | None:
        """Devuelve los datos de la sesión si el token es válido.

        Actualiza `last_seen_at` en el mismo paso: permite saber qué sesiones
        están realmente en uso y cuáles quedaron abandonadas.
        """
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                UPDATE sessions
                   SET last_seen_at = now()
                 WHERE token_hash = %s
                   AND revoked_at IS NULL
                   AND expires_at > now()
                RETURNING id, user_id, device_id, created_at, expires_at
                """,
                (self._hash_token(token),),
            )
            sesion = await cur.fetchone()

            if sesion is None:
                return None

            cur = await conn.execute(
                """
                SELECT u.username, u.full_name, u.role, a.name AS display_name,
                       d.trust_level, da.name AS device_name
                  FROM users u
                  JOIN actors a ON a.id = u.id
                  JOIN devices d ON d.id = %s
                  JOIN actors da ON da.id = d.id
                 WHERE u.id = %s
                   AND d.revoked_at IS NULL
                """,
                (sesion["device_id"], sesion["user_id"]),
            )
            contexto = await cur.fetchone()

        if contexto is None:
            return None

        return {**sesion, **contexto}

    async def cerrar_sesion(self, token: str, cerrada_por: UUID | None = None) -> None:
        """Revoca una sesión."""
        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    UPDATE sessions
                       SET revoked_at = now(), revoked_by = %s
                     WHERE token_hash = %s AND revoked_at IS NULL
                    RETURNING id, user_id
                    """,
                    (cerrada_por, self._hash_token(token)),
                )
                fila = await cur.fetchone()
                if fila is None:
                    return

                await conn.execute(
                    """
                    INSERT INTO events (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'session_closed', %s, %s)
                    """,
                    (fila["user_id"], Jsonb({"session_id": str(fila["id"])})),
                )

    async def listar_sesiones(self, solo_activas: bool = True) -> list[dict[str, Any]]:
        """Lista las sesiones registradas, para poder cerrarlas a distancia."""
        condicion = (
            "WHERE s.revoked_at IS NULL AND s.expires_at > now()"
            if solo_activas else ""
        )
        async with self._conexion() as conn:
            cur = await conn.execute(
                f"""
                SELECT s.id, s.created_at, s.last_seen_at, s.expires_at,
                       s.revoked_at,
                       ua.name AS usuario, da.name AS dispositivo
                  FROM sessions s
                  JOIN actors ua ON ua.id = s.user_id
                  JOIN actors da ON da.id = s.device_id
                  {condicion}
                 ORDER BY s.last_seen_at DESC
                """
            )
            return await cur.fetchall()

    async def revocar_sesion_por_id(
        self, session_id: UUID, revocada_por: UUID
    ) -> None:
        """Cierra una sesión sin conocer su token. Para cerrar a distancia."""
        async with self._conexion() as conn:
            async with conn.transaction():
                cur = await conn.execute(
                    """
                    UPDATE sessions
                       SET revoked_at = now(), revoked_by = %s
                     WHERE id = %s AND revoked_at IS NULL
                    RETURNING user_id
                    """,
                    (revocada_por, session_id),
                )
                fila = await cur.fetchone()
                if fila is None:
                    raise ErrorRepositorio(
                        f"La sesión {session_id} no existe o ya estaba cerrada."
                    )

                await conn.execute(
                    """
                    INSERT INTO events (occurred_at, event_type, actor_id, payload)
                    VALUES (now(), 'session_closed', %s, %s)
                    """,
                    (
                        fila["user_id"],
                        Jsonb({"session_id": str(session_id), "reason": "revoked"}),
                    ),
                )
# ------------------------------------------------------------------
# Conversación
# ------------------------------------------------------------------

    async def registrar_turno(
        self,
        actor_id: UUID,
        hablante: str,
        texto: str,
        metadatos: dict[str, Any] | None = None,
    ) -> None:
        """Registra un turno de conversación.

        Los turnos son eventos como cualquier otro: quedan en el registro
        append-only y se pueden consultar junto con el resto de la memoria.
        """
        payload = {"speaker": hablante, "text": texto}
        if metadatos:
            payload.update(metadatos)

        await self.registrar_evento(
            event_type="utterance",
            actor_id=actor_id,
            payload=payload,
        )

    async def ultimos_turnos(
        self, user_id: UUID, cantidad: int = 8, minutos: int = 45
    ) -> list[dict[str, Any]]:
        """Devuelve los últimos turnos, del más viejo al más nuevo.

        Solo los de la sesión de conversación en curso: un intercambio de hace
        horas no es contexto, es otra conversación. Un saludo repetido en el
        mismo minuto es raro; repetido al otro día es lo normal.
        """
        async with self._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT occurred_at,
                       payload->>'speaker' AS hablante,
                       payload->>'text' AS texto
                  FROM events
                 WHERE event_type = 'utterance'
                   AND occurred_at > now() - (%s * INTERVAL '1 minute')
                   AND (actor_id = %s OR payload->>'addressee' = %s)
                 ORDER BY occurred_at DESC
                 LIMIT %s
                """,
                (minutos, user_id, str(user_id), cantidad),
            )
            filas = await cur.fetchall()

        return list(reversed(filas))