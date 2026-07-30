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

from nucleo.errores import ErrorOperativo

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
        """Arranca todas las tareas y espera hasta que se pida detener."""
        if not self._tareas:
            logger.warning("El planificador arrancó sin tareas registradas.")

        self._detener.clear()
        self._corriendo = [
            asyncio.create_task(self._ejecutar_periodica(t), name=t.nombre)
            for t in self._tareas
        ]

        logger.info("Planificador en marcha con %d tarea(s).", len(self._corriendo))
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