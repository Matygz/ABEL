"""Índice de intenciones. Ejecutar: python -m tests.test_indice"""

import asyncio
import time

from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.indice import IndiceIntenciones
from nucleo.lenguaje.vectorizador import Vectorizador

MENSAJES = [
    "¿cuánto tiempo estuve en Code hoy?",
    "cuánto tiempo pasé en el chat",
    "hola",
    "me siento como el orto",
    "a qué hora arranqué",
    "probabilidad de sacar 7 con dos dados",
    "qué sabés hacer",
    "prendé la luz del living",
    "mandale un mensaje a Tomi",
]


async def main():
    registro = RegistroCapacidades({
        "memoria": object(), "llm": object(), "repositorio": object(),
    })
    registro.descubrir()

    vectorizador = Vectorizador()
    indice = IndiceIntenciones(vectorizador)

    if not await indice.disponible():
        print("Qdrant no responde. ¿Está levantado el contenedor?")
        return

    inicio = time.monotonic()
    cargo = await indice.sincronizar(registro)
    print(f"{'cargado' if cargo else 'al día'} en "
          f"{time.monotonic() - inicio:.1f}s\n")

    for mensaje in MENSAJES:
        inicio = time.monotonic()
        coincidencias = await indice.buscar(mensaje, cantidad=3)
        ms = (time.monotonic() - inicio) * 1000

        print(f"> {mensaje}   ({ms:.0f}ms)")
        for c in coincidencias:
            print(f"    {c.similitud:.3f}  {c.capacidad:<26} {c.ejemplo[:40]}")
        print()

    await indice.cerrar()


if __name__ == "__main__":
    asyncio.run(main())