"""Dónde se va el tiempo. Ejecutar: python -m tests.test_tiempos"""

import asyncio
import time

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.interprete import Interprete
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo


async def main():
    config = cargar_config()
    motor = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")
    servidor = ServidorModelo(
        ejecutable=config.llm_ejecutable,
        modelo=config.llm_modelo,
        motor=motor,
        puerto=config.llm_puerto,
    )
    await servidor.asegurar_disponible()

    # Llamada mínima: sin contexto ni ejemplos.
    t = time.monotonic()
    r = await motor.generar("Respondé en una línea.", "¿Qué hora es más o menos?")
    print(f"llamada simple:     {time.monotonic() - t:.1f}s  "
          f"({r.tokens_entrada} ent, {r.tokens_salida} sal, "
          f"{r.velocidad:.0f} t/s)")

    # Interpretación completa, con todos los ejemplos.
    repo = Repositorio(config)
    contexto = await ProveedorContexto(repo).obtener(usuario="Maty")
    interprete = Interprete(motor)

    t = time.monotonic()
    await interprete.interpretar("¿cuánto estuve en Code hoy?", contexto)
    print(f"interpretación:     {time.monotonic() - t:.1f}s")

    t = time.monotonic()
    await interprete.interpretar("me siento como el orto", contexto)
    print(f"interpretación 2:   {time.monotonic() - t:.1f}s")

    await servidor.cerrar()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)