"""Clasificación por similitud. Ejecutar: python -m tests.test_clasificador"""

import asyncio

from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.clasificador import Clasificador
from nucleo.lenguaje.indice import IndiceIntenciones
from nucleo.lenguaje.vectorizador import Vectorizador

# (mensaje, capacidad esperada o None si debe quedar fuera de alcance)
CASOS = [
    ("¿cuánto tiempo estuve en Code hoy?", "actividad_por_aplicacion"),
    ("cuánto tiempo pasé en el chat", "actividad_por_aplicacion"),
    ("en qué se me fue la tarde", "actividad_por_aplicacion"),
    ("a qué hora arranqué", "presencia"),
    ("cuándo me fui de la máquina", "presencia"),
    ("hola", "conversar"),
    ("me siento como el orto", "conversar"),
    ("estoy re cansado hoy", "conversar"),
    ("cómo andás", "conversar"),
    ("cómo venís", "conversar"),
    ("todo en orden", "conversar"),
    ("qué hacés", "conversar"),
    ("cómo va", "conversar"),
    ("probabilidad de sacar 7 con dos dados", "probabilidad"),
    ("qué sabés hacer", "sobre_si_mismo"),
    ("cómo está el sistema", "estado_del_sistema"),
    ("estado del nucelo", "estado_del_sistema"),
    ("cuantos eventos tenes?", "estado_del_sistema"),
    ("prendé la luz del living", None),
    ("mandale un mensaje a Tomi", None),
    ("qué tengo en la agenda mañana", None),
    ("reproducí música", None),
]


async def main():
    registro = RegistroCapacidades({
        "memoria": object(), "llm": object(), "repositorio": object(), "afirmaciones": object(),
    })
    registro.descubrir()

    vectorizador = Vectorizador()
    indice = IndiceIntenciones(vectorizador)

    if not await indice.disponible():
        print("Qdrant no responde.")
        return

    await indice.sincronizar(registro)
    clasificador = Clasificador(indice)

    aciertos = 0
    print()

    for mensaje, esperado in CASOS:
        r = await clasificador.clasificar(mensaje)
        ok = r.capacidad == esperado
        aciertos += ok

        obtenido = r.capacidad or "fuera de alcance"
        marca = "ok  " if ok else "MAL "
        print(f"{marca}{r.confianza:.3f}  {mensaje[:38]:<40} → {obtenido}")

        if not ok:
            print(f"           esperaba: {esperado or 'fuera de alcance'}")

    print(f"\n{aciertos} de {len(CASOS)} correctos.")
    await indice.cerrar()


if __name__ == "__main__":
    asyncio.run(main())