"""Arranque del Núcleo."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from comun.sangre import Sangre
from nucleo.ciclo import Ciclo
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
from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.analizador import Analizador
from nucleo.lenguaje.clasificador import Clasificador
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.conversacion import Conversacion
from nucleo.lenguaje.expresador import Expresador
from nucleo.lenguaje.extractor import Extractor
from nucleo.lenguaje.indice import IndiceIntenciones
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.lenguaje.vectorizador import Vectorizador
from nucleo.razonamiento.criterio import Criterio
from nucleo.razonamiento.despachador import Despachador

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
        sangre = Sangre(Path(config.sangre_ruta))
        ausencia = sangre.cargar()
        # Una ausencia larga es tiempo propio perdido. ABEL puede saber
        # cuánto estuvo caído porque compara contra lo que guardó.
        if ausencia > 300:
            sangre.empujar("continuidad", min(1.0, ausencia / 86400))
            logger.info(
                "Ausencia previa: %.0f min. Continuidad en %.2f.",
                ausencia / 60, sangre.leer("continuidad"),
            )

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
        ciclo_interno = Ciclo(
            sangre=sangre,
            repositorio=repositorio,
            actor_id=ciclo.actor_id,
            run_id=ciclo.run_id,
        )
        planificador.registrar_servicio("ciclo", ciclo_interno.girar)

        servidor = ServidorNodos(
            repositorio=repositorio,
            version=VERSION,
            host=config.ws_host,
            puerto=config.ws_puerto,
            intervalo_presencia=int(intervalo),
            tls_cert=config.tls_cert,
            tls_clave=config.tls_clave,
            sangre=sangre,
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
            registro = RegistroCapacidades({
                "memoria": memoria,
                "llm": motor,
                "repositorio": repositorio,
            })
            registro.descubrir()

            vectorizador = Vectorizador()
            indice = IndiceIntenciones(vectorizador, url=config.qdrant_url)

            # El índice se sincroniza al arrancar: si los ejemplos no
            # cambiaron, no se re-vectoriza nada. Si Qdrant no responde, ABEL
            # funciona igual — el analizador cae al modelo de lenguaje.
            try:
                await indice.sincronizar(registro)
            except Exception as exc:
                logger.warning(
                    "Sin índice de intenciones: %s. "
                    "El reconocimiento va a depender del modelo.", exc
                )

            conversacion = Conversacion(
                repositorio=repositorio,
                modelo=modelo,
                contexto=ProveedorContexto(repositorio),
                analizador=Analizador(
                    registro=registro,
                    clasificador=Clasificador(indice),
                    extractor=Extractor(motor),
                    motor=motor,
                ),
                despachador=Despachador(registro),
                criterio=Criterio(),
                expresador=Expresador(motor),
                sangre=sangre,
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
            sangre=sangre,
        )
        planificador.registrar_servicio("servidor_web", servidor_web.ejecutar)

        _instalar_senales(planificador, ciclo)
        try:
            await planificador.iniciar()
        finally:
            sangre.guardar()
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