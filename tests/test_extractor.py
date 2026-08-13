"""Extracción de parámetros. Ejecutar: python -m tests.test_extractor"""

import asyncio

from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.extractor import Extractor

# Las aplicaciones que ABEL "conoce" para esta prueba.
APLICACIONES = ("Code.exe", "opera.exe", "WhatsApp.Root.exe", "claude.exe")

CASOS = [
    ("¿cuánto tiempo estuve en Code hoy?", "actividad_por_aplicacion",
     {"rango": "hoy", "filtro": "Code.exe"}),
    ("cuánto usé opera ayer", "actividad_por_aplicacion",
     {"rango": "ayer", "filtro": "opera.exe"}),
    ("en qué se me fue esta semana", "actividad_por_aplicacion",
     {"rango": "semana", "filtro": None}),
    ("cuánto estuve en whatsapp", "actividad_por_aplicacion",
     {"rango": "hoy", "filtro": "WhatsApp.Root.exe"}),
    ("actividad de los últimos 5 días", "actividad_por_aplicacion",
     {"rango": "dias:5", "filtro": None}),
    ("a qué hora arranqué hoy", "presencia",
     {"rango": "hoy"}),
    ("cuándo estuve activo este mes", "presencia",
     {"rango": "mes"}),
]


async def main():
    registro = RegistroCapacidades({
        "memoria": object(), "llm": object(), "repositorio": object(),
    })
    registro.descubrir()

    # Sin modelo: estas extracciones son todas por patrón.
    extractor = Extractor(motor=None)

    aciertos = 0
    print()

    for mensaje, nombre, esperado in CASOS:
        capacidad = registro.obtener(nombre)
        assert capacidad is not None, f"no existe la capacidad {nombre}"

        obtenido = await extractor.extraer(mensaje, capacidad, APLICACIONES)
        ok = all(obtenido.get(k) == v for k, v in esperado.items())
        aciertos += ok

        marca = "ok  " if ok else "MAL "
        print(f"{marca}{mensaje[:36]:<38} → {obtenido}")
        if not ok:
            print(f"     esperaba: {esperado}")

    print(f"\n{aciertos} de {len(CASOS)} correctos.")


if __name__ == "__main__":
    asyncio.run(main())