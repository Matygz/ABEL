"""Gestión del proceso del modelo de lenguaje.

El modelo no corre siempre: ocupa VRAM permanentemente, y esa VRAM le hace
falta al resto del sistema. Se levanta cuando hace falta y se baja tras un
período de inactividad.

Costo aceptado: la primera consulta después de un rato tarda unos segundos
más mientras el modelo carga.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje

logger = logging.getLogger(__name__)

INACTIVIDAD_POR_DEFECTO = 900.0  # 15 minutos


class ServidorModelo:
    """Levanta y baja el servidor del modelo según demanda."""

    def __init__(
        self,
        ejecutable: str,
        modelo: str,
        motor: MotorLenguaje,
        puerto: int = 8090,
        capas_gpu: int = 99,
        contexto: int = 8192,
        inactividad_segundos: float = INACTIVIDAD_POR_DEFECTO,
    ) -> None:
        self._ejecutable = Path(ejecutable)
        self._modelo = Path(modelo)
        self._motor = motor
        self._puerto = puerto
        self._capas_gpu = capas_gpu
        self._contexto = contexto
        self._inactividad = inactividad_segundos

        self._proceso: subprocess.Popen | None = None
        self._ultimo_uso: float = 0.0
        self._arrancando = asyncio.Lock()

    # ------------------------------------------------------------------

    async def asegurar_disponible(self) -> None:
        """Garantiza que el modelo esté listo para responder.

        Si ya está, marca el uso y vuelve. Si no, lo levanta. El lock evita
        que dos consultas simultáneas lancen dos servidores.
        """
        self._marcar_uso()

        if await self._motor.disponible():
            return

        async with self._arrancando:
            # Otra consulta pudo haberlo levantado mientras se esperaba.
            if await self._motor.disponible():
                return
            await self._arrancar()

    def _marcar_uso(self) -> None:
        self._ultimo_uso = asyncio.get_running_loop().time()

    # ------------------------------------------------------------------

    async def _arrancar(self) -> None:
        for ruta, que in ((self._ejecutable, "ejecutable"), (self._modelo, "modelo")):
            if not ruta.exists():
                raise ErrorLenguaje(f"No existe el {que} del modelo: {ruta}")

        logger.info("Cargando el modelo %s...", self._modelo.name)

        self._proceso = subprocess.Popen(
            [
                str(self._ejecutable),
                "-m", str(self._modelo),
                "--port", str(self._puerto),
                "--gpu-layers", str(self._capas_gpu),
                "--ctx-size", str(self._contexto),
                "--log-disable",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
        )

        if not await self._motor.esperar_disponible():
            await self._detener()
            raise ErrorLenguaje("El modelo no terminó de cargar a tiempo.")

        logger.info("Modelo listo en el puerto %d.", self._puerto)

    async def _detener(self) -> None:
        if self._proceso is None:
            return

        logger.info("Descargando el modelo por inactividad.")
        self._proceso.terminate()

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._proceso.wait), timeout=10.0
            )
        except TimeoutError:
            logger.warning("El proceso del modelo no cerró; se fuerza.")
            self._proceso.kill()

        self._proceso = None

    # ------------------------------------------------------------------

    async def vigilar(self) -> None:
        """Servicio que descarga el modelo tras un período sin uso.

        Se registra en el planificador. Corre indefinidamente.
        """
        while True:
            await asyncio.sleep(30.0)

            if self._proceso is None:
                continue

            ocioso = asyncio.get_running_loop().time() - self._ultimo_uso
            if ocioso >= self._inactividad:
                await self._detener()

    async def cerrar(self) -> None:
        """Detiene el modelo al apagar el Núcleo."""
        await self._detener()
        await self._motor.cerrar()