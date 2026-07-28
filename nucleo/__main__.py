"""Punto de entrada del Núcleo.

Se ejecuta con: python -m nucleo
"""

import asyncio

from nucleo.arranque import main

if __name__ == "__main__":
    # psycopg3 en modo asíncrono no es compatible con ProactorEventLoop,
    # el bucle por defecto en Windows. SelectorEventLoop sí lo es.
    # Ver docs/decisiones/0008-psycopg3-como-driver.md
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)