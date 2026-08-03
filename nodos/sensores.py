"""Sensores de un Nodo.

Un sensor produce observaciones y las encola. No decide qué significan, no
las transmite, no habla con el Núcleo: eso es del cliente.

La estructura no impone cómo se obtienen los datos. Un sensor de muestreo
periódico pregunta el estado cada N segundos; uno reactivo espera a que el
sistema le avise. Los dos cumplen la misma interfaz.

Un sensor que falla al iniciarse no impide que el Nodo arranque: queda
deshabilitado y su capacidad no se declara al Núcleo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol
from uuid import uuid7

from protocolos.contenidos import Observacion

logger = logging.getLogger(__name__)


class Emisor(Protocol):
    """Lo que un sensor recibe para entregar lo que capta."""

    def __call__(self, event_type: str, data: dict) -> None: ...


@dataclass
class Sensor:
    """Una fuente de observaciones.

    `iniciar` se ejecuta una vez al arrancar el Nodo. Si lanza una excepción,
    el sensor queda deshabilitado y el resto del Nodo sigue funcionando.

    `capturar` se ejecuta con la cadencia declarada. Si falla, se registra y
    se reintenta en el próximo turno.
    """

    nombre: str
    capacidad: str
    intervalo_segundos: float
    capturar: Callable[[Emisor], Awaitable[None]]
    iniciar: Callable[[], Awaitable[None]] | None = None
    detener: Callable[[], Awaitable[None]] | None = None

    habilitado: bool = field(default=False, init=False)
    motivo_deshabilitado: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.intervalo_segundos <= 0:
            raise ValueError(
                f"El intervalo de {self.nombre} debe ser mayor a cero."
            )


class RegistroSensores:
    """Sensores disponibles en un Nodo y su estado."""

    def __init__(self) -> None:
        self._sensores: dict[str, Sensor] = {}

    def registrar(self, sensor: Sensor) -> None:
        if sensor.nombre in self._sensores:
            raise ValueError(f"Ya existe un sensor llamado {sensor.nombre!r}.")
        self._sensores[sensor.nombre] = sensor

    def todos(self) -> list[Sensor]:
        return list(self._sensores.values())

    def habilitados(self) -> list[Sensor]:
        return [s for s in self._sensores.values() if s.habilitado]

    def capacidades(self) -> list[str]:
        """Capacidades que el Nodo declara al Núcleo.

        Solo las de sensores efectivamente habilitados: declarar una
        capacidad que no funciona haría que el Núcleo cuente con datos que
        nunca van a llegar.
        """
        return sorted({s.capacidad for s in self.habilitados()})

    async def iniciar_todos(self, solicitados: list[str]) -> None:
        """Inicia los sensores solicitados en la configuración.

        Un fallo deshabilita ese sensor y no detiene a los demás: es
        preferible un Nodo que funciona parcialmente a uno que no arranca.
        """
        for sensor in self._sensores.values():
            if sensor.nombre not in solicitados:
                sensor.motivo_deshabilitado = "no_solicitado"
                continue

            try:
                if sensor.iniciar is not None:
                    await sensor.iniciar()
                sensor.habilitado = True
                logger.info(
                    "Sensor habilitado: %s (cada %ss)",
                    sensor.nombre, sensor.intervalo_segundos,
                )
            except Exception as exc:
                sensor.habilitado = False
                sensor.motivo_deshabilitado = type(exc).__name__
                logger.warning(
                    "Sensor %s no disponible (%s): %s",
                    sensor.nombre, type(exc).__name__, exc,
                )

        desconocidos = set(solicitados) - set(self._sensores)
        if desconocidos:
            logger.warning(
                "Sensores solicitados que no existen: %s",
                ", ".join(sorted(desconocidos)),
            )

    async def detener_todos(self) -> None:
        for sensor in self.habilitados():
            if sensor.detener is None:
                continue
            try:
                await sensor.detener()
            except Exception:
                logger.exception("Fallo al detener el sensor %s.", sensor.nombre)

    def estado(self) -> list[dict]:
        """Estado de todos los sensores, para reportar al Núcleo."""
        return [
            {
                "nombre": s.nombre,
                "capacidad": s.capacidad,
                "habilitado": s.habilitado,
                "motivo": s.motivo_deshabilitado,
                "intervalo_segundos": s.intervalo_segundos,
            }
            for s in self._sensores.values()
        ]


def crear_emisor(cola) -> Emisor:
    """Devuelve la función que los sensores usan para entregar lo que captan.

    El sensor no conoce la cola ni el protocolo: solo llama a esta función.
    """

    def emitir(event_type: str, data: dict) -> None:
        cola.agregar(
            Observacion(
                id=uuid7(),
                occurred_at=datetime.now(timezone.utc),
                event_type=event_type,
                data=data,
            )
        )

    return emitir