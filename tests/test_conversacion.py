"""Flujo completo de conversación.
Ejecutar: python -m tests.test_conversacion

Necesita PostgreSQL, Qdrant y el modelo de lenguaje.
"""

import asyncio

from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.analizador import Analizador
from nucleo.lenguaje.clasificador import Clasificador
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.expresador import Expresador
from nucleo.lenguaje.extractor import Extractor
from nucleo.lenguaje.indice import IndiceIntenciones
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.lenguaje.vectorizador import Vectorizador
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.consultas import Memoria
from nucleo.razonamiento.criterio import Criterio
from nucleo.razonamiento.despachador import Despachador

# (mensaje, capacidades esperadas, orígenes esperados)
# Se verifica el enrutamiento, no el texto: la redacción varía por diseño.
CASOS = [
    ("11 x 11",
     {"aritmetica"}, {"patron"}),

    ("¿cuánto es 4 x 29?",
     {"aritmetica"}, {"patron"}),

    ("¿cuánto tiempo estuve en Code hoy?",
     {"actividad_por_aplicacion"}, {"similitud"}),

    ("a qué hora arranqué",
     {"presencia"}, {"similitud"}),

    ("hola",
     {"conversar"}, {"similitud"}),

    ("me siento como el orto",
     {"conversar"}, {"similitud"}),

    ("qué sabés hacer",
     {"sobre_si_mismo"}, {"similitud"}),

    ("cómo está el sistema",
     {"estado_del_sistema"}, {"similitud"}),

    ("prendé la luz del living",
     {"fuera_de_alcance"}, {"modelo"}),

    ("estoy quemado de code hoy, cuánto tiempo estuve?",
     {"conversar", "actividad_por_aplicacion"}, {"similitud"}),
]

# Casos donde además se verifica algo del contenido.
CONTENIDO = [
    ("11 x 11", "121"),
    ("¿cuánto es 4 x 29?", "116"),
]


async def armar():
    """Monta el pipeline igual que lo hace el Núcleo."""
    config = cargar_config()
    repositorio = Repositorio(config)
    motor = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")

    servidor = ServidorModelo(
        ejecutable=config.llm_ejecutable,
        modelo=config.llm_modelo,
        motor=motor,
        puerto=config.llm_puerto,
    )
    await servidor.asegurar_disponible()

    registro = RegistroCapacidades({
        "memoria": Memoria(repositorio),
        "llm": motor,
        "repositorio": repositorio,
        "afirmaciones": Afirmaciones(repositorio),
    })
    registro.descubrir()

    indice = IndiceIntenciones(Vectorizador(), url=config.qdrant_url)
    await indice.sincronizar(registro)

    return {
        "servidor": servidor,
        "indice": indice,
        "contexto": ProveedorContexto(repositorio),
        "analizador": Analizador(
            registro=registro,
            clasificador=Clasificador(indice),
            extractor=Extractor(motor),
            motor=motor,
        ),
        "despachador": Despachador(registro),
        "criterio": Criterio(),
        "expresador": Expresador(motor),
    }


async def main():
    piezas = await armar()
    contexto = await piezas["contexto"].obtener(usuario="Maty")

    aciertos = 0
    respuestas: dict[str, str] = {}
    print()

    for mensaje, esperadas, origenes in CASOS:
        analisis = await piezas["analizador"].analizar(mensaje, contexto)
        resultados = await piezas["despachador"].despachar(analisis)
        decision = piezas["criterio"].decidir(resultados)
        texto = await piezas["expresador"].expresar(
            resultados, decision, usuario="Maty"
        )
        respuestas[mensaje] = texto

        obtenidas = {
            i.capacidad or "fuera_de_alcance" for i in analisis.intenciones
        }
        obtenidos_origen = {i.origen for i in analisis.intenciones}

        ok = obtenidas == esperadas and obtenidos_origen <= origenes | {"patron"}
        aciertos += ok

        marca = "ok  " if ok else "MAL "
        print(f"{marca}{mensaje[:44]:<46} → {', '.join(sorted(obtenidas))}")
        if not ok:
            print(f"     esperaba: {', '.join(sorted(esperadas))}")
            print(f"     orígenes: {', '.join(sorted(obtenidos_origen))}")
        if texto:
            print(f"     «{texto[:70]}»")

    print()
    for mensaje, esperado in CONTENIDO:
        texto = respuestas.get(mensaje, "")
        ok = esperado in texto
        aciertos += ok
        marca = "ok  " if ok else "MAL "
        print(f"{marca}la respuesta a {mensaje!r} contiene {esperado!r}")

    total = len(CASOS) + len(CONTENIDO)
    print(f"\n{aciertos} de {total} correctos.")

    await piezas["indice"].cerrar()
    await piezas["servidor"].cerrar()

    if aciertos < total:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)