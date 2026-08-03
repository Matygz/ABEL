"""Sensor de ventana activa.

Registra sesiones de uso: qué aplicación estuvo en primer plano y cuánto
tiempo. Emite el evento cuando la sesión termina, con su duración ya
calculada.

Observación, no conclusión: reporta qué ventana tuvo el foco, no qué estaba
haciendo el usuario. La interpretación es del Núcleo.

Nota sobre privacidad: el título de una ventana puede contener el nombre de
un documento, el asunto de un correo o la página que se está leyendo. Se
registra a propósito — es donde está el valor informativo — pero el filtrado
por reglas definidas por un admin es un pendiente conocido.
"""

from __future__ import annotations

import ctypes
import logging
import platform
import time
from ctypes import wintypes
from dataclasses import dataclass

from nodos.sensores import Emisor, Sensor

logger = logging.getLogger(__name__)

UMBRAL_MINIMO_SEGUNDOS = 10.0
MAXIMO_SESION_SEGUNDOS = 1800.0
INTERVALO_MUESTREO = 2.0


@dataclass
class _SesionVentana:
    """Una sesión de uso en curso."""

    aplicacion: str
    titulo: str
    inicio: float
    acumulado_parcial: float = 0.0

    @property
    def duracion(self) -> float:
        return time.monotonic() - self.inicio


class VentanaActiva:
    """Detecta qué aplicación está en primer plano y por cuánto tiempo.

    El muestreo periódico filtra ruido por construcción: un cambio de foco
    más breve que el intervalo no se observa, y eso es deseable — pasar medio
    segundo por una ventana buscando otra no es usarla.
    """

    def __init__(
        self,
        umbral: float = UMBRAL_MINIMO_SEGUNDOS,
        maximo: float = MAXIMO_SESION_SEGUNDOS,
    ) -> None:
        self._umbral = umbral
        self._maximo = maximo
        self._actual: _SesionVentana | None = None
        self._descartadas: dict[str, float] = {}

    async def iniciar(self) -> None:
        """Verifica que el sistema permita consultar la ventana activa."""
        if platform.system() != "Windows":
            raise NotImplementedError(
                "El sensor de ventana activa solo está implementado en Windows."
            )
        self._consultar()

    async def capturar(self, emitir: Emisor) -> None:
        actual = self._consultar()

        if actual is None:
            self._cerrar_sesion(emitir, "sin_foco")
            return

        aplicacion, titulo = actual

        if self._actual is None:
            self._actual = _SesionVentana(aplicacion, titulo, time.monotonic())
            return

        if aplicacion != self._actual.aplicacion:
            self._cerrar_sesion(emitir, "cambio")
            self._actual = _SesionVentana(aplicacion, titulo, time.monotonic())
            return

        if titulo != self._actual.titulo:
            self._actual.titulo = titulo

        if self._actual.duracion >= self._maximo:
            self._emitir_sesion(emitir, self._actual, "parcial")
            self._actual = _SesionVentana(aplicacion, titulo, time.monotonic())

    async def detener(self) -> None:
        """Al apagarse, la sesión en curso se pierde: no hay a quién emitirle."""
        self._actual = None

    # ------------------------------------------------------------------

    def _cerrar_sesion(self, emitir: Emisor, motivo: str) -> None:
        if self._actual is None:
            return

        sesion = self._actual
        self._actual = None
        duracion = sesion.duracion

        if duracion >= self._umbral:
            self._emitir_sesion(emitir, sesion, motivo)
            return

        # Sesiones cortas: se acumulan por aplicación. Alternar entre dos
        # ventanas cada pocos segundos durante una hora es actividad real,
        # y un umbral simple la descartaría por completo.
        acumulado = self._descartadas.get(sesion.aplicacion, 0.0) + duracion
        if acumulado >= self._umbral:
            emitir(
                "window_session",
                {
                    "application": sesion.aplicacion,
                    "title": None,
                    "duration_seconds": round(acumulado, 1),
                    "reason": "fragmentada",
                },
            )
            self._descartadas.pop(sesion.aplicacion, None)
        else:
            self._descartadas[sesion.aplicacion] = acumulado

    @staticmethod
    def _emitir_sesion(emitir: Emisor, sesion: _SesionVentana, motivo: str) -> None:
        emitir(
            "window_session",
            {
                "application": sesion.aplicacion,
                "title": sesion.titulo,
                "duration_seconds": round(sesion.duracion, 1),
                "reason": motivo,
            },
        )

    @staticmethod
    def _consultar() -> tuple[str, str] | None:
        """Devuelve (ejecutable, título) de la ventana en primer plano."""
        user32 = ctypes.windll.user32

        handle = user32.GetForegroundWindow()
        if not handle:
            return None

        largo = user32.GetWindowTextLengthW(handle)
        buffer = ctypes.create_unicode_buffer(largo + 1)
        user32.GetWindowTextW(handle, buffer, largo + 1)
        titulo = buffer.value

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))

        try:
            import psutil

            aplicacion = psutil.Process(pid.value).name()
        except Exception:
            aplicacion = "desconocido"

        return aplicacion, titulo


def construir_sensores_ventana() -> list[Sensor]:
    ventana = VentanaActiva()
    return [
        Sensor(
            nombre="ventana",
            capacidad="active_window",
            intervalo_segundos=INTERVALO_MUESTREO,
            capturar=ventana.capturar,
            iniciar=ventana.iniciar,
            detener=ventana.detener,
        )
    ]