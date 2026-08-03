"""Sensores de estado del sistema.

Observaciones, nunca conclusiones: el Nodo reporta que hubo actividad de
teclado hace N segundos, no que "el usuario está presente". La interpretación
es del Núcleo.
"""

from __future__ import annotations

import logging
import platform
import time

import psutil

from nodos.sensores import Emisor, Sensor

logger = logging.getLogger(__name__)


class EstadoSesion:
    """Detecta transiciones entre actividad e inactividad del usuario.

    Reporta solo los cambios, no el estado en cada muestreo: emitir "sigue
    activo" cada treinta segundos llenaría la base sin agregar información.
    Un cambio de estado sí es un hecho.
    """

    def __init__(self, umbral_inactividad: float = 300.0) -> None:
        self._umbral = umbral_inactividad
        self._ultimo_estado: str | None = None
        self._ultimo_boot: float | None = None

    async def iniciar(self) -> None:
        """Verifica que el sistema exponga lo que el sensor necesita."""
        self._ultimo_boot = psutil.boot_time()

    async def capturar(self, emitir: Emisor) -> None:
        inactividad = self._segundos_inactivo()
        estado = "idle" if inactividad >= self._umbral else "active"

        if estado != self._ultimo_estado:
            emitir(
                "session_state",
                {
                    "state": estado,
                    "idle_seconds": round(inactividad, 1),
                    "previous": self._ultimo_estado,
                },
            )
            self._ultimo_estado = estado

    @staticmethod
    def _segundos_inactivo() -> float:
        """Segundos desde la última actividad de teclado o mouse.

        En Windows usa GetLastInputInfo, que devuelve el momento de la última
        entrada. En otros sistemas no está implementado todavía.
        """
        if platform.system() != "Windows":
            raise NotImplementedError(
                "La detección de inactividad solo está implementada en Windows."
            )

        import ctypes

        class ULTIMA_ENTRADA(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

        info = ULTIMA_ENTRADA()
        info.cbSize = ctypes.sizeof(ULTIMA_ENTRADA)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            raise OSError("GetLastInputInfo falló.")

        milisegundos = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return milisegundos / 1000.0


class RecursosSistema:
    """Muestrea CPU, memoria y batería.

    Sensor de bajo valor informativo, útil como banco de pruebas de la
    estructura y para diagnosticar el estado del dispositivo.
    """

    async def capturar(self, emitir: Emisor) -> None:
        inactividad = self._segundos_inactivo()
        estado = "idle" if inactividad >= self._umbral else "active"

        if estado == self._ultimo_estado:
            return

        # La primera lectura tras un reinicio no es una transición real: el
        # estado previo se perdió con el proceso. Solo se reporta si es idle,
        # que sí es informativo — arrancar con el usuario activo es lo normal.
        if self._ultimo_estado is None and estado == "active":
            self._ultimo_estado = estado
            return

        emitir(
            "session_state",
            {
                "state": estado,
                "idle_seconds": round(inactividad, 1),
                "previous": self._ultimo_estado,
            },
        )
        self._ultimo_estado = estado


def construir_sensores() -> list[Sensor]:
    """Sensores disponibles en este Nodo.

    Se construyen todos; cuáles se habilitan lo decide la configuración.
    """
    sesion = EstadoSesion()
    recursos = RecursosSistema()

    return [
        Sensor(
            nombre="sesion",
            capacidad="session",
            intervalo_segundos=30.0,
            capturar=sesion.capturar,
            iniciar=sesion.iniciar,
        ),
        Sensor(
            nombre="recursos",
            capacidad="system_resources",
            intervalo_segundos=300.0,
            capturar=recursos.capturar,
        ),
    ]