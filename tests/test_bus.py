"""Bus de eventos. Ejecutar: python -m tests.test_bus"""

import asyncio
from datetime import datetime, timezone

from comun.eventos import Aviso, BusEventos


async def main():
    bus = BusEventos()

    def aviso(n):
        return Aviso("presence_mark", None, datetime.now(timezone.utc), {"n": n})

    # Un suscriptor recibe lo que se publica mientras está suscrito.
    async with bus.suscribirse() as cola:
        bus.publicar(aviso(1))
        bus.publicar(aviso(2))
        assert cola.qsize() == 2
        primero = await cola.get()
        assert primero.resumen["n"] == 1
    print("ok  recibe lo publicado")

    # Fuera del contexto, ya no está suscrito.
    bus.publicar(aviso(3))
    assert bus.cantidad_suscriptores == 0
    print("ok  la suscripción se limpia sola")

    # Dos suscriptores reciben cada uno su copia.
    async with bus.suscribirse() as a, bus.suscribirse() as b:
        bus.publicar(aviso(9))
        assert a.qsize() == 1 and b.qsize() == 1
    print("ok  cada suscriptor recibe su copia")

    # Un suscriptor lleno descarta sin romper.
    async with bus.suscribirse() as cola:
        for i in range(300):
            bus.publicar(aviso(i))
        assert cola.qsize() <= 256
    print("ok  descarta si se llena, sin romper")

    print("\n4 pruebas pasaron.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)