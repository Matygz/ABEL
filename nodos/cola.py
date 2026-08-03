"""Cola local de observaciones pendientes, persistida en SQLite.

Un Nodo captura aunque no haya enlace. Lo captado espera acá hasta que el
Núcleo confirme por escrito que lo persistió — recién entonces se descarta.

La cola vive en un archivo: sobrevive a que el proceso se reinicie, que es
lo habitual en un dispositivo móvil. Antes vivía en memoria y se perdía.

La interfaz es la misma que la versión en memoria: `cliente.py` no sabe
dónde se guardan los datos.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

from protocolos.contenidos import Observacion

logger = logging.getLogger(__name__)

MAX_PENDIENTES = 10_000

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pendientes (
    id           TEXT PRIMARY KEY,
    occurred_at  TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    data         TEXT NOT NULL,
    encolada_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS pendientes_orden_idx ON pendientes (id);
"""


class ColaObservaciones:
    """Almacena observaciones en disco hasta que el Núcleo las confirme."""

    def __init__(
        self,
        ruta: str | Path = "datos/cola.db",
        maximo: int = MAX_PENDIENTES,
        durabilidad: str = "normal",
    ) -> None:
        self._ruta = Path(ruta)
        self._maximo = maximo
        self._descartadas = 0

        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._ruta, isolation_level=None)
        self._conn.row_factory = sqlite3.Row

        # WAL: escrituras más rápidas y lectura concurrente con escritura.
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute(f"PRAGMA synchronous = {self._pragma(durabilidad)}")
        self._conn.executescript(ESQUEMA)

        pendientes = len(self)
        if pendientes:
            logger.info("Cola recuperada del disco: %d pendiente(s).", pendientes)

    @staticmethod
    def _pragma(durabilidad: str) -> str:
        """Traduce la política de durabilidad al ajuste de SQLite.

        `full` espera confirmación física del disco en cada escritura:
        sobrevive a un corte de energía, a costa de un fsync por operación.
        `normal` sobrevive a que el proceso se reinicie, pero puede perder
        lo último escrito ante un apagón abrupto.
        """
        valores = {"normal": "NORMAL", "full": "FULL"}
        elegido = valores.get(durabilidad.lower())
        if elegido is None:
            logger.warning(
                "Durabilidad desconocida: %r. Se usa 'normal'.", durabilidad
            )
            return "NORMAL"
        return elegido

    def cerrar(self) -> None:
        """Cierra la base. Los datos ya escritos permanecen."""
        self._conn.close()

    def __len__(self) -> int:
        fila = self._conn.execute("SELECT COUNT(*) AS n FROM pendientes").fetchone()
        return fila["n"]

    # ------------------------------------------------------------------

    def agregar(self, observacion: Observacion) -> None:
        """Encola una observación. Si la cola está llena, descarta la más vieja."""
        self._podar()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO pendientes (id, occurred_at, event_type, data)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(observacion.id),
                observacion.occurred_at.isoformat(),
                observacion.event_type,
                json.dumps(observacion.data, ensure_ascii=False),
            ),
        )

    def pendientes(self, limite: int) -> list[Observacion]:
        """Devuelve hasta `limite` observaciones, las más antiguas primero.

        El orden por id es cronológico porque son UUIDv7: los primeros bits
        son un timestamp (ver decisión 0002).
        """
        filas = self._conn.execute(
            "SELECT * FROM pendientes ORDER BY id LIMIT ?", (limite,)
        ).fetchall()

        observaciones = []
        for fila in filas:
            try:
                observaciones.append(
                    Observacion(
                        id=UUID(fila["id"]),
                        occurred_at=datetime.fromisoformat(fila["occurred_at"]),
                        event_type=fila["event_type"],
                        data=json.loads(fila["data"]),
                    )
                )
            except (ValueError, TypeError, json.JSONDecodeError):
                logger.error(
                    "Fila corrupta en la cola, se descarta: %s", fila["id"]
                )
                self._conn.execute(
                    "DELETE FROM pendientes WHERE id = ?", (fila["id"],)
                )
        return observaciones

    def confirmar(self, ids: list[UUID]) -> None:
        """Descarta lo que el Núcleo confirmó haber persistido."""
        self._borrar(ids)

    def descartar(self, ids: list[UUID]) -> None:
        """Descarta lo que el Núcleo rechazó. Reintentarlo no serviría."""
        self._borrar(ids)

    # ------------------------------------------------------------------

    def _borrar(self, ids: list[UUID]) -> None:
        if not ids:
            return
        self._conn.executemany(
            "DELETE FROM pendientes WHERE id = ?", [(str(i),) for i in ids]
        )

    def _podar(self) -> None:
        """Mantiene la cola dentro del máximo, descartando lo más antiguo.

        Política: se privilegia lo reciente sobre lo completo. Discutible
        según el tipo de dato; configurable a futuro.
        """
        sobrantes = len(self) - self._maximo + 1
        if sobrantes <= 0:
            return

        self._conn.execute(
            "DELETE FROM pendientes WHERE id IN "
            "(SELECT id FROM pendientes ORDER BY id LIMIT ?)",
            (sobrantes,),
        )
        self._descartadas += sobrantes
        if self._descartadas % 100 < sobrantes:
            logger.warning(
                "Cola llena (%d). Descartadas %d observaciones antiguas.",
                self._maximo, self._descartadas,
            )