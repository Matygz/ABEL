"""Vectorización de texto. Ejecutar: python -m tests.test_vectorizador"""

import asyncio
import time

from nucleo.lenguaje.vectorizador import Vectorizador


def coseno(a: list[float], b: list[float]) -> float:
    """Similitud entre dos vectores normalizados: su producto escalar."""
    return sum(x * y for x, y in zip(a, b))


PARES = [
    # Deberían ser parecidos: dicen lo mismo de otra forma.
    ("¿cuánto estuve en Code hoy?", "cuánto tiempo usé el editor", True),
    ("me siento como el orto", "estoy hecho mierda", True),
    ("hola", "buenas, qué onda", True),
    # Deberían ser distintos.
    ("¿cuánto estuve en Code hoy?", "me siento como el orto", False),
    ("hola", "cuál es la probabilidad de sacar 7", False),
]


async def main():
    v = Vectorizador()

    inicio = time.monotonic()
    await v.cargar()
    print(f"cargado en {time.monotonic() - inicio:.1f}s, "
          f"{v.dimensiones} dimensiones\n")

    inicio = time.monotonic()
    await v.vectorizar("una frase cualquiera")
    print(f"vectorizar una frase: {(time.monotonic() - inicio) * 1000:.0f}ms\n")

    # Segunda vez: la primera incluye calentamiento del modelo.
    inicio = time.monotonic()
    await v.vectorizar("otra frase distinta")
    print(f"segunda vectorización: {(time.monotonic() - inicio) * 1000:.0f}ms\n")
    
    for uno, otro, esperado_parecido in PARES:
        va, vb = await v.vectorizar_lote([uno, otro])
        sim = coseno(va, vb)
        marca = "cerca " if sim > 0.5 else "lejos "
        correcto = "ok  " if (sim > 0.5) == esperado_parecido else "MAL "
        print(f"{correcto}{marca} {sim:.3f}  {uno[:32]:<34} | {otro[:32]}")


if __name__ == "__main__":
    asyncio.run(main())