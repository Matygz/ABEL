"""Punto de entrada de un Nodo.

Se ejecuta con: python -m nodos
"""

import asyncio
import logging
import sys

from nodos.cliente import ClienteNodo
from nodos.config import ErrorConfigNodo, cargar_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("nodos")
logging.getLogger("websockets").setLevel(logging.INFO)


async def main() -> int:
    try:
        config = cargar_config()
    except ErrorConfigNodo as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Nodo %s (%s)", config.nombre, config.device_id)
    cliente = ClienteNodo(config)

    try:
        await cliente.iniciar_sensores()
        await asyncio.gather(
            cliente.ejecutar_sensores(),
            cliente.ejecutar(),
        )
    except asyncio.CancelledError:
        logger.info("Nodo detenido.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop))
    except KeyboardInterrupt:
        logger.info("Detención solicitada.")
        sys.exit(0)