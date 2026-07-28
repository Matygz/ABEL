"""Arranque del Núcleo."""

from __future__ import annotations

import asyncio
import logging
import signal

from nucleo.ciclo_vida import CicloVida
from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.logging_setup import ajustar_nivel, configurar_logging
from nucleo.planificador import Planificador, Tarea
from nucleo.tareas.presencia import crear_tarea_presencia

logger = logging.getLogger(__name__)

VERSION = "0.0.1"
INTERVALO_PRESENCIA_POR_DEFECTO = 60.0


async def main() -> None:
    configurar_logging()

    config = cargar_config()
    repositorio = Repositorio(config)

    settings = await repositorio.leer_configuracion()
    ajustar_nivel(settings.get("log_level", "INFO"))

    intervalo = float(
        settings.get("presence_interval_seconds", INTERVALO_PRESENCIA_POR_DEFECTO)
    )

    async with CicloVida(repositorio, VERSION) as ciclo:
        planificador = Planificador()

        planificador.registrar(
            Tarea(
                nombre="presencia",
                funcion=crear_tarea_presencia(
                    repositorio, ciclo.actor_id, ciclo.run_id, ciclo.inicio
                ),
                intervalo_segundos=intervalo,
            )
        )

        _instalar_senales(planificador, ciclo)
        await planificador.iniciar()


def _instalar_senales(planificador: Planificador, ciclo: CicloVida) -> None:
    """Hace que Ctrl+C solicite una detención ordenada."""

    def manejar(signum, frame) -> None:
        logger.info("Señal recibida (%s). Deteniendo.", signum)
        ciclo.motivo_solicitado = "interrupted"
        planificador.detener()

    signal.signal(signal.SIGINT, manejar)
    signal.signal(signal.SIGTERM, manejar)