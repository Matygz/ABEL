"""Lanzador de ABEL: Núcleo y Nodo en background, con ícono en la bandeja.

Arranca los dos procesos sin ventanas visibles y deja un ícono al lado del
reloj para verlos, abrir la interfaz y detenerlos.

Se eligió una aplicación de bandeja y no un servicio de Windows por una
razón concreta: un servicio corre en otra sesión y no puede ver el
escritorio del usuario. El sensor de ventana activa dejaría de funcionar.

Uso:
    pythonw abel.py     (sin consola)
    python abel.py      (con consola, para depurar)
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

RAIZ = Path(__file__).parent
PYTHON = RAIZ / ".venv" / "Scripts" / "python.exe"
URL_INTERFAZ = "http://127.0.0.1:8080"

SIN_VENTANA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class Abel:
    """Supervisa los procesos de ABEL y ofrece el menú de bandeja."""

    def __init__(self) -> None:
        self._nucleo: subprocess.Popen[bytes] | None = None
        self._nodo: subprocess.Popen[bytes] | None = None
        self._icono = None  # type: ignore[assignment]
        self._detener = threading.Event()

    # ------------------------------------------------------------------

    def _lanzar(self, modulo: str) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [str(PYTHON), "-m", modulo],
            cwd=str(RAIZ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=SIN_VENTANA,
        )

    def arrancar(self) -> None:
        self._nucleo = self._lanzar("nucleo")
        # El Nodo espera un poco: si arranca antes que el servidor esté
        # escuchando, reintenta igual, pero así se evita ruido en el log.
        time.sleep(3)
        self._nodo = self._lanzar("nodos")

    def _vivo(self, proceso: subprocess.Popen[bytes] | None) -> bool:
        return proceso is not None and proceso.poll() is None

    def vigilar(self) -> None:
        """Reinicia lo que se caiga. Corre en un hilo aparte."""
        while not self._detener.wait(10.0):
            if not self._vivo(self._nucleo):
                self._nucleo = self._lanzar("nucleo")
                time.sleep(3)
                self._nodo = self._lanzar("nodos")
            elif not self._vivo(self._nodo):
                self._nodo = self._lanzar("nodos")

            if self._icono is not None:
                self._icono.icon = self._dibujar_icono(activo=True)

    def detener(self) -> None:
        self._detener.set()
        for proceso in (self._nodo, self._nucleo):
            if self._vivo(proceso):
                proceso.terminate()
                try:
                    proceso.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proceso.kill()

    # ------------------------------------------------------------------

    @staticmethod
    def _dibujar_icono(activo: bool = True) -> Image.Image:
        """El icosaedro, en miniatura."""
        lado = 64
        imagen = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        trazo = ImageDraw.Draw(imagen)
        color = (79, 209, 224, 255) if activo else (74, 85, 96, 255)

        c, r = lado / 2, lado / 2 - 6
        # Seis vértices de un hexágono: la silueta del icosaedro visto de frente.
        import math
        puntos = [
            (c + r * math.sin(math.pi / 3 * i), c - r * math.cos(math.pi / 3 * i))
            for i in range(6)
        ]

        trazo.polygon(puntos, outline=color)
        trazo.line([puntos[0], puntos[3]], fill=color)
        trazo.line([puntos[1], puntos[4]], fill=color)
        trazo.line([puntos[2], puntos[5]], fill=color)

        return imagen

    def _menu(self) -> pystray.Menu:
        def estado(_) -> str:
            partes = []
            partes.append("núcleo activo" if self._vivo(self._nucleo) else "núcleo caído")
            partes.append("nodo activo" if self._vivo(self._nodo) else "nodo caído")
            return " · ".join(partes)

        return pystray.Menu(
            pystray.MenuItem(estado, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir ABEL", lambda: webbrowser.open(URL_INTERFAZ),
                             default=True),
            pystray.MenuItem("Ver registro", self._abrir_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._salir),
        )

    def _abrir_log(self) -> None:
        registro = RAIZ / "logs" / "nucleo.log"
        if registro.exists():
            subprocess.Popen(["notepad.exe", str(registro)])

    def _salir(self) -> None:
        self.detener()
        if self._icono is not None:
            self._icono.stop()

    # ------------------------------------------------------------------

    def ejecutar(self) -> None:
        self.arrancar()

        threading.Thread(target=self.vigilar, daemon=True).start()

        self._icono = pystray.Icon(
            "abel",
            icon=self._dibujar_icono(),
            title="ABEL",
            menu=self._menu(),
        )
        self._icono.run()


if __name__ == "__main__":
    if not PYTHON.exists():
        print(f"No existe {PYTHON}. ¿Está creado el entorno virtual?")
        sys.exit(1)

    Abel().ejecutar()