"""Carga y descarga del modelo. Ejecutar: python -m tests.test_modelo"""

import asyncio
import time

from nucleo.config import cargar_config
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

    print("disponible antes:", await motor.disponible())

    inicio = time.monotonic()
    await servidor.asegurar_disponible()
    print(f"cargado en {time.monotonic() - inicio:.1f}s")

    r = await motor.generar(
        "Respondé en una línea, en español rioplatense.",
        "¿Qué sos?",
        temperatura=0.7,
    )
    print(f"\n{r.texto}")
    print(f"\n{r.velocidad:.0f} tokens/s")

    inicio = time.monotonic()
    await servidor.asegurar_disponible()
    print(f"\nsegunda llamada: {time.monotonic() - inicio:.2f}s (ya estaba caliente)")

    await servidor.cerrar()
    print("descargado:", not await motor.disponible())


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)