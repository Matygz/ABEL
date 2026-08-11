"""Ciclo completo: interpretar y resolver.
Ejecutar: python -m tests.test_despacho
"""

import asyncio

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.interprete import Interprete
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.memoria.consultas import Memoria
from nucleo.razonamiento.despachador import Despachador
from nucleo.razonamiento.motor_calculo import MotorCalculo
from nucleo.razonamiento.motor_memoria import MotorMemoria

MENSAJES = [
    "¿cuánto tiempo estuve en Code hoy?",
    "si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?",
    "estuve todo el día en el código y estoy quemado",
    "¿dónde estuve ayer a las 6?",
    "me siento como el orto",
]


async def main():
    config = cargar_config()
    motor_llm = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")
    servidor = ServidorModelo(
        ejecutable=config.llm_ejecutable,
        modelo=config.llm_modelo,
        motor=motor_llm,
        puerto=config.llm_puerto,
    )
    await servidor.asegurar_disponible()

    repo = Repositorio(config)
    memoria = Memoria(repo)
    contexto = await ProveedorContexto(repo).obtener(usuario="Maty")

    interprete = Interprete(motor_llm)
    despachador = Despachador(MotorMemoria(memoria), MotorCalculo(motor_llm))

    for mensaje in MENSAJES:
        interpretacion = await interprete.interpretar(mensaje, contexto)
        respuesta = await despachador.despachar(interpretacion)

        print(f"\n{'─' * 60}")
        print(f"> {mensaje}")

        for r in respuesta.resueltos:
            res = r.resultado
            print(f"\n  [{r.intencion.tipo}]  confianza {r.intencion.confianza:.2f}")

            if not res.resuelto:
                print(f"    no puedo: {res.falta}")
            elif res.vacio:
                print(f"    sin datos")
            else:
                print(f"    procedencia: {res.procedencia}")
                print(f"    {_resumir(res)}")

            for paso in res.pasos:
                print(f"      · {paso}")
            for s in res.salvedades:
                print(f"    nota: {s}")

    await servidor.cerrar()


def _resumir(resultado):
    d = resultado.datos
    if resultado.tipo == "actividad":
        apps = d.get("aplicaciones", [])
        if not apps:
            return "sin actividad en el rango"
        total = d["total_segundos"] / 60
        return f"{len(apps)} app(s), {total:.1f} min en total"
    if resultado.tipo == "calculo":
        return f"{d['porcentaje']:.2f}% ({d['fraccion']})"
    if resultado.tipo == "presencia":
        return f"{len(d.get('cambios', []))} cambio(s) de estado"
    return str(d)[:80]


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)