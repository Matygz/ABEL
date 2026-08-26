import asyncio
from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.indice import IndiceIntenciones
from nucleo.lenguaje.vectorizador import Vectorizador

async def main():
    r = RegistroCapacidades({"memoria": object(), "llm": object(),
                             "repositorio": object(), "afirmaciones": object()})
    r.descubrir()
    i = IndiceIntenciones(Vectorizador())
    await i.sincronizar(r)
    for c in await i.buscar("qué sabés hacer", 5):
        print(f"{c.similitud:.3f}  {c.capacidad:<20} {c.ejemplo}")
    await i.cerrar()

asyncio.run(main())
