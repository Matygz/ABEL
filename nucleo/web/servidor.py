"""Servidor web del Núcleo.

Sirve la interfaz y su API. Corre como servicio del planificador, en el mismo
proceso que el Núcleo: comparte el repositorio y el bus de eventos sin
necesidad de comunicación entre procesos.

La autenticación no usa contraseñas: la sesión se establece porque el Nodo
del dispositivo la autorizó con su firma (ver nucleo/web/sesiones.py).
"""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from comun.eventos import BusEventos
from nucleo.datos.repositorio import Repositorio
from nucleo.memoria.consultas import Memoria
from nucleo.web.rutas import construir_rutas
from nucleo.web.sesiones import ServicioSesiones

logger = logging.getLogger(__name__)

RAIZ_ESTATICA = Path(__file__).parent / "estatico"


class ServidorWeb:
    """Sirve la interfaz de ABEL."""

    def __init__(
        self,
        repositorio: Repositorio,
        memoria: Memoria,
        sesiones: ServicioSesiones,
        bus: BusEventos,
        version: str,
        host: str = "127.0.0.1",
        puerto: int = 8080,
        conversacion=None,
    ) -> None:
        self._host = host
        self._puerto = puerto

        rutas = construir_rutas(
            repositorio, memoria, sesiones, bus, version, conversacion
        )
        # El montaje de archivos estáticos va último: Starlette evalúa las
        # rutas en orden, así que las de la API tienen prioridad y esto
        # atrapa todo lo demás.
        rutas.append(
            Mount(
                "/",
                app=StaticFiles(directory=RAIZ_ESTATICA, html=True),
                name="estatico",
            )
        )

        self._app = Starlette(routes=rutas)

    async def ejecutar(self) -> None:
        """Corre el servidor hasta que se lo cancele."""
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._puerto,
            log_level="warning",
            access_log=False,
        )
        servidor = uvicorn.Server(config)

        logger.info(
            "Interfaz disponible en http://%s:%s", self._host, self._puerto
        )
        await servidor.serve()