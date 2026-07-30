"""Cola local de observaciones pendientes.

Un Nodo captura aunque no haya enlace. Lo captado espera acá hasta que el
Núcleo confirme por escrito que lo persistió — recién entonces se descarta.

Fase 2.2: implementación en memoria. Se pierde al reiniciar el proceso.
La 2.5 la reemplaza por SQLite conservando esta misma interfaz.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from uuid import UUID

from protocolos.contenidos import Observacion

logger = logging.getLogger(__name__)

MAX_PENDIENTES = 10_000


class ColaObservaciones:
    """Almacena observaciones hasta que el Núcleo las confirme."""

    def __init__(self, maximo: int = MAX_PENDIENTES) -> None:
        self._pendientes: OrderedDict[UUID, Observacion] = OrderedDict()
        self._maximo = maximo
        self._descartadas = 0

    def __len__(self) -> int:
        return len(self._pendientes)

    def agregar(self, observacion: Observacion) -> None:
        """Encola una observación. Si la cola está llena, descarta la más vieja."""
        if len(self._pendientes) >= self._maximo:
            vieja, _ = self._pendientes.popitem(last=False)
            self._descartadas += 1
            if self._descartadas % 100 == 1:
                logger.warning(
                    "Cola llena (%d). Descartadas %d observaciones antiguas.",
                    self._maximo, self._descartadas,
                )
        self._pendientes[observacion.id] = observacion

    def pendientes(self, limite: int) -> list[Observacion]:
        """Devuelve hasta `limite` observaciones, las más antiguas primero."""
        return [obs for _, obs in list(self._pendientes.items())[:limite]]

    def confirmar(self, ids: list[UUID]) -> None:
        """Descarta las observaciones que el Núcleo confirmó haber persistido."""
        for identificador in ids:
            self._pendientes.pop(identificador, None)

    def descartar(self, ids: list[UUID]) -> None:
        """Descarta observaciones que el Núcleo rechazó. Reintentarlas no sirve."""
        for identificador in ids:
            self._pendientes.pop(identificador, None)