"""Tarea diaria de inferencia.

No corre en cada ciclo: son consultas pesadas sobre toda la memoria
observada, y los patrones de uso no cambian en minutos. Una vez por día
alcanza.
"""

from __future__ import annotations

import logging

from comun.sangre import Sangre
from nucleo.memoria.inferencia import Inferencia

logger = logging.getLogger(__name__)

# Por debajo de esto se considera "poca actividad": buen momento para correr
# consultas pesadas sin competir por atención con nada que esté pasando.
UMBRAL_ACTIVIDAD_BAJA = 0.3


def crear_tarea_inferencia(inferencia: Inferencia, sangre: Sangre):
    """Arma la tarea con su contexto ya resuelto."""

    async def correr_inferencia() -> None:
        # Preferentemente en un momento de baja actividad: si no lo es
        # ahora, no pasa nada — la tarea vuelve a intentar en su próximo
        # turno (una vez por día), no hay urgencia en forzarla.
        if sangre.leer("actividad") > UMBRAL_ACTIVIDAD_BAJA:
            logger.debug("Inferencia pospuesta: actividad alta.")
            return

        tocadas = await inferencia.correr()
        logger.info("Inferencia diaria: %d afirmación(es) tocada(s).", tocadas)

    return correr_inferencia
