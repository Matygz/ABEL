"""Arranque del Núcleo."""

from __future__ import annotations

import asyncio
import logging
import signal

from nucleo.ciclo_vida import CicloVida
from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.logging_setup import ajustar_nivel, configurar_logging
from comun.planificador import Planificador, Tarea
from nucleo.tareas.presencia import crear_tarea_presencia
from nucleo.red.servidor import ServidorNodos
from comun.eventos import BusEventos
from nucleo.memoria.consultas import Memoria
from nucleo.web.servidor import ServidorWeb
from nucleo.web.sesiones import ServicioSesiones

logger = logging.getLogger(__name__)

VERSION = "0.0.1"
INTERVALO_PRESENCIA_POR_DEFECTO = 60.0


async def main() -> None:
    configurar_logging()

    config = cargar_config()
    bus = BusEventos()
    repositorio = Repositorio(config, bus=bus)

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
        servidor = ServidorNodos(
            repositorio=repositorio,
            version=VERSION,
            host=config.ws_host,
            puerto=config.ws_puerto,
            intervalo_presencia=int(intervalo),
            tls_cert=config.tls_cert,
            tls_clave=config.tls_clave,
        )
        planificador.registrar_servicio("servidor_nodos", servidor.ejecutar)
        servidor_web = ServidorWeb(
            repositorio=repositorio,
            memoria=Memoria(repositorio),
            sesiones=ServicioSesiones(repositorio, servidor),
            bus=bus,
            version=VERSION,
            host=config.web_host,
            puerto=config.web_puerto,
        )
        planificador.registrar_servicio("servidor_web", servidor_web.ejecutar)

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