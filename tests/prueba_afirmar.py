import asyncio
from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.clasificador import Clasificador
from nucleo.lenguaje.indice import IndiceIntenciones
from nucleo.lenguaje.vectorizador import Vectorizador

FRASES = ["Mi mamá se llama Marta", "trabajo en una fábrica",
          "mi hermano vive en Mendoza", "hola"]

async def main():
    r = RegistroCapacidades({"memoria": object(), "llm": object(),
                             "repositorio": object(), "afirmaciones": object()})
    r.descubrir()
    print("capacidades:", [c.nombre for c in r.todas()])
    i = IndiceIntenciones(Vectorizador())
    await i.sincronizar(r)
    c = Clasificador(i)
    for f in FRASES:
        x = await c.clasificar(f)
        print(f"{f:<30} -> {x.capacidad or 'fuera de alcance':<20} {x.confianza:.3f}")
    await i.cerrar()

asyncio.run(main())
