"""Consultas sobre la memoria de ABEL.

Responde preguntas, no expone filas. La diferencia con el repositorio es de
propósito: el repositorio guarda y recupera; este módulo agrega, resume y
relaciona.

Devuelve datos estructurados, nunca texto formateado. Un método que devuelve
"Usaste Chrome 3.4 minutos" sirve para una sola cosa; uno que devuelve
{"aplicacion": "chrome.exe", "segundos": 204} sirve para un script, para una
interfaz y para un modelo de lenguaje.

Acá van a vivir las capacidades de recuerdo más elaboradas: el olvido por
marca, el decaimiento por relevancia, la consolidación. Hoy son consultas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from nucleo.datos.repositorio import Repositorio

logger = logging.getLogger(__name__)


class Memoria:
    """Preguntas sobre lo que ABEL registró."""

    def __init__(self, repositorio: Repositorio) -> None:
        self._repo = repositorio

    # ------------------------------------------------------------------
    # Actividad
    # ------------------------------------------------------------------

    async def actividad_por_aplicacion(
        self, desde: datetime, hasta: datetime, minimo_segundos: float = 0.0
    ) -> list[dict[str, Any]]:
        """Tiempo total en cada aplicación dentro de un rango."""
        async with self._repo._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT
                    payload->>'application' AS aplicacion,
                    COUNT(*) AS sesiones,
                    SUM((payload->>'duration_seconds')::numeric) AS segundos,
                    MIN(occurred_at) AS primera,
                    MAX(occurred_at) AS ultima
                  FROM events
                 WHERE event_type = 'window_session'
                   AND occurred_at >= %s AND occurred_at < %s
                 GROUP BY 1
                HAVING SUM((payload->>'duration_seconds')::numeric) >= %s
                 ORDER BY segundos DESC
                """,
                (desde, hasta, minimo_segundos),
            )
            filas = await cur.fetchall()

        return [
            {
                "aplicacion": f["aplicacion"],
                "sesiones": f["sesiones"],
                "segundos": float(f["segundos"]),
                "primera": f["primera"],
                "ultima": f["ultima"],
            }
            for f in filas
        ]

    async def sesiones_de_ventana(
        self, desde: datetime, hasta: datetime, limite: int = 100
    ) -> list[dict[str, Any]]:
        """Sesiones de uso individuales, de la más reciente a la más antigua."""
        async with self._repo._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT occurred_at,
                       payload->>'application' AS aplicacion,
                       payload->>'title' AS titulo,
                       (payload->>'duration_seconds')::numeric AS segundos,
                       payload->>'reason' AS motivo
                  FROM events
                 WHERE event_type = 'window_session'
                   AND occurred_at >= %s AND occurred_at < %s
                 ORDER BY occurred_at DESC
                 LIMIT %s
                """,
                (desde, hasta, limite),
            )
            filas = await cur.fetchall()

        return [
            {
                "momento": f["occurred_at"],
                "aplicacion": f["aplicacion"],
                "titulo": f["titulo"],
                "segundos": float(f["segundos"]),
                "motivo": f["motivo"],
            }
            for f in filas
        ]

    async def que_hacia(self, momento: datetime) -> dict[str, Any] | None:
        """Qué aplicación estaba en primer plano en un momento dado.

        Busca la sesión de ventana que contiene ese instante: la que terminó
        después del momento y empezó antes.
        """
        async with self._repo._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT occurred_at,
                       payload->>'application' AS aplicacion,
                       payload->>'title' AS titulo,
                       (payload->>'duration_seconds')::numeric AS segundos
                  FROM events
                 WHERE event_type = 'window_session'
                   AND occurred_at >= %s
                   AND occurred_at - ((payload->>'duration_seconds')::numeric
                                      * INTERVAL '1 second') <= %s
                 ORDER BY occurred_at
                 LIMIT 1
                """,
                (momento, momento),
            )
            fila = await cur.fetchone()

        if fila is None:
            return None

        return {
            "aplicacion": fila["aplicacion"],
            "titulo": fila["titulo"],
            "termino": fila["occurred_at"],
            "segundos": float(fila["segundos"]),
        }

    # ------------------------------------------------------------------
    # Presencia del usuario
    # ------------------------------------------------------------------

    async def periodos_de_actividad(
        self, desde: datetime, hasta: datetime
    ) -> list[dict[str, Any]]:
        """Transiciones entre actividad e inactividad.

        Devuelve los cambios de estado, no una interpretación: `idle` significa
        que no hubo entrada de teclado ni mouse, no que el usuario no estuviera.
        """
        async with self._repo._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT occurred_at,
                       payload->>'state' AS estado,
                       payload->>'previous' AS anterior,
                       a.name AS dispositivo
                  FROM events e
                  JOIN actors a ON a.id = e.actor_id
                 WHERE event_type = 'session_state'
                   AND occurred_at >= %s AND occurred_at < %s
                 ORDER BY occurred_at
                """,
                (desde, hasta),
            )
            filas = await cur.fetchall()

        return [
            {
                "momento": f["occurred_at"],
                "estado": f["estado"],
                "anterior": f["anterior"],
                "dispositivo": f["dispositivo"],
            }
            for f in filas
        ]

    # ------------------------------------------------------------------
    # Estado del sistema
    # ------------------------------------------------------------------

    async def estado_del_sistema(self) -> dict[str, Any]:
        """Panorama de ABEL: ejecuciones, dispositivos y volumen de memoria."""
        async with self._repo._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT id, started_at, ended_at, stop_reason, pid
                  FROM runs ORDER BY started_at DESC LIMIT 5
                """
            )
            ejecuciones = await cur.fetchall()

            cur = await conn.execute(
                """
                SELECT a.name, d.trust_level, d.platform,
                       MAX(e.occurred_at) AS ultima_senal
                  FROM devices d
                  JOIN actors a ON a.id = d.id
                  LEFT JOIN events e ON e.actor_id = d.id
                 WHERE d.revoked_at IS NULL
                 GROUP BY a.name, d.trust_level, d.platform
                 ORDER BY ultima_senal DESC NULLS LAST
                """
            )
            dispositivos = await cur.fetchall()

            cur = await conn.execute(
                """
                SELECT event_type, COUNT(*) AS cantidad,
                       MIN(occurred_at) AS desde, MAX(occurred_at) AS hasta
                  FROM events GROUP BY 1 ORDER BY cantidad DESC
                """
            )
            eventos = await cur.fetchall()

        vigente = ejecuciones[0] if ejecuciones else None
        caidas = [
            e for e in ejecuciones[1:]
            if e["ended_at"] is None
        ]

        return {
            "ejecucion_vigente": (
                {
                    "id": vigente["id"],
                    "desde": vigente["started_at"],
                    "activa": vigente["ended_at"] is None,
                }
                if vigente else None
            ),
            "ejecuciones_caidas": len(caidas),
            "dispositivos": [
                {
                    "nombre": d["name"],
                    "confianza": d["trust_level"],
                    "plataforma": d["platform"],
                    "ultima_senal": d["ultima_senal"],
                }
                for d in dispositivos
            ],
            "eventos": [
                {
                    "tipo": e["event_type"],
                    "cantidad": e["cantidad"],
                    "desde": e["desde"],
                    "hasta": e["hasta"],
                }
                for e in eventos
            ],
            "total_eventos": sum(e["cantidad"] for e in eventos),
        }

    async def huecos_de_presencia(
        self, actor_id: UUID, desde: datetime, hasta: datetime,
        tolerancia_segundos: float = 180.0,
    ) -> list[dict[str, Any]]:
        """Períodos sin marcas de presencia.

        Un hueco indica que el actor estuvo caído o incomunicado. Es la
        contrapartida de la marca: su valor está en la ausencia.
        """
        async with self._repo._conexion() as conn:
            cur = await conn.execute(
                """
                SELECT anterior, occurred_at AS siguiente,
                       EXTRACT(EPOCH FROM (occurred_at - anterior)) AS segundos
                  FROM (
                    SELECT occurred_at,
                           LAG(occurred_at) OVER (ORDER BY occurred_at) AS anterior
                      FROM events
                     WHERE event_type = 'presence_mark'
                       AND actor_id = %s
                       AND occurred_at >= %s AND occurred_at < %s
                  ) t
                 WHERE anterior IS NOT NULL
                   AND occurred_at - anterior > (%s * INTERVAL '1 second')
                 ORDER BY anterior
                """,
                (actor_id, desde, hasta, tolerancia_segundos),
            )
            filas = await cur.fetchall()

        return [
            {
                "desde": f["anterior"],
                "hasta": f["siguiente"],
                "segundos": float(f["segundos"]),
            }
            for f in filas
        ]


# ----------------------------------------------------------------------
# Rangos de tiempo
# ----------------------------------------------------------------------

def hoy() -> tuple[datetime, datetime]:
    ahora = datetime.now(timezone.utc).astimezone()
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio, inicio + timedelta(days=1)


def ultimas_horas(cantidad: float) -> tuple[datetime, datetime]:
    ahora = datetime.now(timezone.utc)
    return ahora - timedelta(hours=cantidad), ahora


def ultimos_dias(cantidad: int) -> tuple[datetime, datetime]:
    ahora = datetime.now(timezone.utc).astimezone()
    fin = ahora.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return fin - timedelta(days=cantidad), fin