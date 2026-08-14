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
import os
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

RAIZ = Path(__file__).parent
PYTHON = RAIZ / ".venv" / "Scripts" / "python.exe"
URL_INTERFAZ = "http://127.0.0.1:8080"

SIN_VENTANA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

def logger_print(mensaje: str) -> None:
    """Mensaje a consola si la hay. Con pythonw no hay, y no importa."""
    try:
        print(mensaje, flush=True)
    except Exception:
        pass

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

    def _matar_huerfanos(self) -> None:
        """Termina procesos de ABEL que hayan quedado de una sesión anterior.

        Un Nodo huérfano compite con el nuevo: los dos se conectan, los dos
        abren conexiones a la base, y se agotan. Pasó.

        Solo mata Núcleos y Nodos, nunca otros lanzadores: matar un `abel.py`
        incluiría al proceso actual y a su padre.
        """
        try:
            import psutil
        except ImportError:
            return

        propio = os.getpid()
        try:
            padre = psutil.Process(propio).ppid()
        except psutil.Error:
            padre = -1

        for proceso in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proceso.info["pid"] in (propio, padre):
                    continue

                nombre = (proceso.info["name"] or "").lower()
                if not nombre.startswith("python"):
                    continue

                argumentos = proceso.info["cmdline"] or []
                # Solo los módulos: `python -m nucleo`, `python -m nodos`.
                if "-m" not in argumentos:
                    continue
                if not any(a in ("nucleo", "nodos") for a in argumentos):
                    continue

                logger_print(f"Terminando proceso huérfano: {proceso.info['pid']}")
                proceso.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _esperar_base(self, limite: float = 120.0) -> bool:
        """Espera a que PostgreSQL acepte conexiones.

        Docker arranca en paralelo con la sesión del usuario y puede tardar
        más. El Núcleo no arranca sin base —falla en la primera consulta— así
        que esperar acá evita un arranque fallido.
        """
        import socket

        limite_tiempo = time.monotonic() + limite
        while time.monotonic() < limite_tiempo:
            if self._detener.is_set():
                return False
            with socket.socket() as s:
                s.settimeout(2.0)
                if s.connect_ex(("127.0.0.1", 5432)) == 0:
                    return True
            time.sleep(2.0)

        logger_print("La base no respondió. ABEL arranca igual y reintenta.")
        return False

    def _esperar_nucleo(self, limite: float = 90.0) -> bool:
        """Espera a que el Núcleo escuche en su puerto.

        El Núcleo carga el modelo de embeddings al arrancar, y eso tarda unos
        segundos. Lanzar el Nodo antes solo produce reintentos en el log.
        """
        import socket

        limite_tiempo = time.monotonic() + limite
        while time.monotonic() < limite_tiempo:
            if self._detener.is_set():
                return False
            with socket.socket() as s:
                s.settimeout(2.0)
                if s.connect_ex(("127.0.0.1", 8765)) == 0:
                    return True
            time.sleep(1.0)
        return False

    def arrancar(self) -> None:
        self._matar_huerfanos()
        self._esperar_base()

        self._nucleo = self._lanzar("nucleo")
        self._esperar_nucleo()
        self._nodo = self._lanzar("nodos")

    def _vivo(self, proceso: subprocess.Popen[bytes] | None) -> bool:
        return proceso is not None and proceso.poll() is None

    def vigilar(self) -> None:
        """Reinicia lo que se caiga. Corre en un hilo aparte."""
        while not self._detener.wait(10.0):
            if not self._vivo(self._nucleo):
                logger_print("El Núcleo se cayó. Reiniciando.")
                if self._vivo(self._nodo):
                    self._nodo.terminate()
                self._nucleo = self._lanzar("nucleo")
                self._esperar_nucleo()
                self._nodo = self._lanzar("nodos")
            elif not self._vivo(self._nodo):
                logger_print("El Nodo se cayó. Reiniciando.")
                self._nodo = self._lanzar("nodos")

    def detener(self) -> None:
        self._detener.set()
        for proceso in (self._nodo, self._nucleo):
            if self._vivo(proceso):
                proceso.terminate()
                try:
                    proceso.wait(timeout=15)
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