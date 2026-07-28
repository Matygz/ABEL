"""Configuración de logging del Núcleo.

Los logs son para el programador: progreso, errores, trazas. Son distintos
de los eventos, que son el registro estructurado de lo que ABEL hace y viven
en la base de datos (ver docs/desarrollo/glosario.md).

Se configura en dos tiempos: al arrancar con un nivel por defecto, y luego
se ajusta con el valor leído de la tabla `settings`. Así, si la conexión a
la base falla, el error queda registrado igual.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMATO = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"

DIRECTORIO_LOGS = Path("logs")
ARCHIVO_LOG = DIRECTORIO_LOGS / "nucleo.log"

MAX_BYTES = 5 * 1024 * 1024
COPIAS_ANTIGUAS = 5


def configurar_logging(nivel: str = "INFO") -> None:
    """Configura el logging de la aplicación. Se llama una sola vez al arrancar."""
    DIRECTORIO_LOGS.mkdir(exist_ok=True)

    formateador = logging.Formatter(FORMATO, datefmt=FORMATO_FECHA)

    consola = logging.StreamHandler()
    consola.setFormatter(formateador)

    archivo = logging.handlers.RotatingFileHandler(
        ARCHIVO_LOG,
        maxBytes=MAX_BYTES,
        backupCount=COPIAS_ANTIGUAS,
        encoding="utf-8",
    )
    archivo.setFormatter(formateador)

    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.setLevel(_nivel_valido(nivel))
    raiz.addHandler(consola)
    raiz.addHandler(archivo)


def ajustar_nivel(nivel: str) -> None:
    """Cambia el nivel de log en ejecución, sin reconfigurar los handlers."""
    logging.getLogger().setLevel(_nivel_valido(nivel))


def _nivel_valido(nivel: str) -> int:
    """Traduce el nombre del nivel a su constante. Cae a INFO si no es válido."""
    resuelto = logging.getLevelNamesMapping().get(str(nivel).upper())
    if resuelto is None:
        logging.getLogger(__name__).warning(
            "Nivel de log desconocido: %r. Se usa INFO.", nivel
        )
        return logging.INFO
    return resuelto