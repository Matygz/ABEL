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
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.conversacion import Conversacion
from nucleo.lenguaje.expresador import Expresador
from nucleo.lenguaje.interprete import Interprete
from nucleo.razonamiento.criterio import Criterio
from nucleo.razonamiento.despachador import Despachador
from nucleo.razonamiento.motor_calculo import MotorCalculo
from nucleo.razonamiento.motor_memoria import MotorMemoria

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

        motor = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")
        modelo = ServidorModelo(
            ejecutable=config.llm_ejecutable,
            modelo=config.llm_modelo,
            motor=motor,
            puerto=config.llm_puerto,
            inactividad_segundos=config.llm_inactividad_segundos,
        )
        planificador.registrar_servicio("vigilante_modelo", modelo.vigilar)

        memoria = Memoria(repositorio)

        conversacion = None
        if config.llm_ejecutable and config.llm_modelo:
            conversacion = Conversacion(
                repositorio=repositorio,
                modelo=modelo,
                contexto=ProveedorContexto(repositorio),
                interprete=Interprete(motor),
                despachador=Despachador(
                    MotorMemoria(memoria), MotorCalculo(motor)
                ),
                criterio=Criterio(),
                expresador=Expresador(motor),
            )
        else:
            logger.warning(
                "Sin modelo de lenguaje configurado. La conversación no estará "
                "disponible."
            )

        servidor_web = ServidorWeb(
            repositorio=repositorio,
            memoria=memoria,
            sesiones=ServicioSesiones(repositorio, servidor),
            bus=bus,
            version=VERSION,
            host=config.web_host,
            puerto=config.web_puerto,
            conversacion=conversacion,
        )
        planificador.registrar_servicio("servidor_web", servidor_web.ejecutar)

        _instalar_senales(planificador, ciclo)
        try:
            await planificador.iniciar()
        finally:
            await modelo.cerrar()
        
def _instalar_senales(planificador: Planificador, ciclo: CicloVida) -> None:
    """Hace que Ctrl+C solicite una detención ordenada."""
    ya_pedido = False

    def manejar(signum, frame) -> None:
        nonlocal ya_pedido
        if ya_pedido:
            return
        ya_pedido = True
        # Directo a la consola: el sistema de logging pasa por manejadores
        # y formateo, y acá lo que importa es que se vea ya.
        print("\nDeteniendo ABEL…", flush=True)
        logger.info("Señal recibida (%s). Deteniendo.", signum)
        ciclo.motivo_solicitado = "interrupted"
        planificador.detener()

    signal.signal(signal.SIGINT, manejar)
    signal.signal(signal.SIGTERM, manejar)