"""Planificador de tareas del Núcleo.

Mantiene un bucle de eventos asíncrono donde cada tarea registrada corre con
su propia cadencia, independiente de las demás. El planificador no conoce el
contenido de las tareas: solo las despacha.

Una tarea que falla no detiene al planificador ni a las otras tareas: el
error se registra y la tarea reintenta en su próximo turno.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from comun.errores import ErrorOperativo

logger = logging.getLogger(__name__)

FuncionTarea = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class Tarea:
    """Una unidad de trabajo periódica."""

    nombre: str
    funcion: FuncionTarea
    intervalo_segundos: float
    timeout_segundos: float | None = None

    def __post_init__(self) -> None:
        if self.intervalo_segundos <= 0:
            raise ValueError(
                f"El intervalo de {self.nombre} debe ser mayor a cero, "
                f"se recibió {self.intervalo_segundos}."
            )
        if self.timeout_segundos is not None and self.timeout_segundos <= 0:
            raise ValueError(
                f"El timeout de {self.nombre} debe ser mayor a cero, "
                f"se recibió {self.timeout_segundos}."
            )

    @property
    def timeout_efectivo(self) -> float:
        """Timeout a aplicar. Por defecto, la mitad del intervalo."""
        if self.timeout_segundos is not None:
            return self.timeout_segundos
        return max(self.intervalo_segundos / 2, 1.0)


class Planificador:
    """Ejecuta tareas periódicas sobre un bucle de eventos asíncrono."""

    def __init__(self) -> None:
        self._tareas: list[Tarea] = []
        self._corriendo: list[asyncio.Task] = []
        self._detener = asyncio.Event()
        self._tareas: list[Tarea] = []
        self._servicios: list[tuple[str, FuncionTarea]] = []

    def registrar_servicio(self, nombre: str, funcion: FuncionTarea) -> None:
        """Registra un proceso de larga duración.

        A diferencia de una tarea, un servicio arranca una vez y corre hasta
        que se lo detiene. Si termina o falla, se reinicia.
        """
        if self._corriendo:
            raise RuntimeError(
                "No se pueden registrar servicios con el planificador en marcha."
            )
        self._servicios.append((nombre, funcion))
        logger.info("Servicio registrado: %s", nombre)
        
    def registrar(self, tarea: Tarea) -> None:
        """Agrega una tarea. Debe llamarse antes de iniciar()."""
        if self._corriendo:
            raise RuntimeError(
                "No se pueden registrar tareas con el planificador en marcha."
            )
        self._tareas.append(tarea)
        logger.info(
            "Tarea registrada: %s (cada %ss, timeout %ss)",
            tarea.nombre,
            tarea.intervalo_segundos,
            tarea.timeout_efectivo,
        )

    async def iniciar(self) -> None:
        """Arranca todas las tareas y servicios, y espera hasta que se pida detener."""
        if not self._tareas and not self._servicios:
            logger.warning("El planificador arrancó sin tareas ni servicios registrados.")

        self._detener.clear()
        self._corriendo = [
            asyncio.create_task(self._ejecutar_periodica(t), name=t.nombre)
            for t in self._tareas
        ] + [
            asyncio.create_task(self._ejecutar_servicio(n, f), name=n)
            for n, f in self._servicios
        ] + [
            asyncio.create_task(self._despertar_periodicamente(), name="_despertador")
        ]

        logger.info(
            "Planificador en marcha: %d tarea(s), %d servicio(s).",
            len(self._tareas),
            len(self._servicios),
        )
        await self._detener.wait()
        await self._cancelar_tareas()

    def detener(self) -> None:
        """Solicita la detención. No bloquea; iniciar() retorna poco después."""
        logger.info("Detención solicitada.")
        self._detener.set()

    async def _cancelar_tareas(self) -> None:
        """Cancela las tareas en curso y espera a que terminen."""
        for tarea in self._corriendo:
            tarea.cancel()

        await asyncio.gather(*self._corriendo, return_exceptions=True)
        self._corriendo = []
        logger.info("Todas las tareas se detuvieron.")

    async def _ejecutar_periodica(self, tarea: Tarea) -> None:
        """Ejecuta una tarea en bucle hasta que se la cancele."""
        logger.debug("Tarea %s iniciada.", tarea.nombre)
        try:
            while True:
                try:
                    await asyncio.wait_for(
                        tarea.funcion(), timeout=tarea.timeout_efectivo
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Tarea %s superó su límite de %ss y fue cancelada. "
                        "Reintenta en %ss.",
                        tarea.nombre,
                        tarea.timeout_efectivo,
                        tarea.intervalo_segundos,
                    )
                except ErrorOperativo as exc:
                    logger.error(
                        "Tarea %s: %s. Reintenta en %ss.",
                        tarea.nombre,
                        str(exc).splitlines()[0],
                        tarea.intervalo_segundos,
                    )
                except Exception:
                    logger.exception(
                        "Fallo inesperado en la tarea %s. Reintenta en %ss.",
                        tarea.nombre,
                        tarea.intervalo_segundos,
                    )
                await asyncio.sleep(tarea.intervalo_segundos)
        except asyncio.CancelledError:
            logger.debug("Tarea %s cancelada.", tarea.nombre)
            raise

    async def _ejecutar_servicio(self, nombre: str, funcion: FuncionTarea) -> None:
        """Mantiene vivo un servicio, reiniciándolo si termina o falla.

        A diferencia de una tarea periódica, un servicio no lleva timeout: se
        espera que esté bloqueado esperando trabajo. Esa es su función.
        """
        espera_reinicio = 5.0
        try:
            while True:
                try:
                    await funcion()
                    logger.warning("El servicio %s terminó solo. Reiniciando.", nombre)
                except ErrorOperativo as exc:
                    logger.error(
                        "Servicio %s: %s. Reinicia en %ss.",
                        nombre,
                        str(exc).splitlines()[0],
                        espera_reinicio,
                    )
                except Exception:
                    logger.exception(
                        "Fallo inesperado en el servicio %s. Reinicia en %ss.",
                        nombre,
                        espera_reinicio,
                    )
                await asyncio.sleep(espera_reinicio)
        except asyncio.CancelledError:
            logger.debug("Servicio %s cancelado.", nombre)
            raise

    async def _despertar_periodicamente(self) -> None:
        """Despierta el bucle con frecuencia para que Ctrl+C se atienda rápido.

        En Windows los manejadores de señal solo corren cuando el intérprete
        recupera el control. Sin este ciclo corto, una detención puede tardar
        hasta lo que dure el sleep más largo en curso.

        El costo es un temporizador; el bucle sigue ocioso entre despertares.
        """
        try:
            while True:
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            raise