"""Ciclo completo con respuesta. Ejecutar: python -m tests.test_conversar"""

import asyncio

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.expresador import Expresador
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
    "hola",
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
    contexto = await ProveedorContexto(repo).obtener(usuario="Maty")

    interprete = Interprete(motor_llm)
    despachador = Despachador(
        MotorMemoria(Memoria(repo)), MotorCalculo(motor_llm)
    )
    expresador = Expresador(motor_llm)

    for mensaje in MENSAJES:
        interpretacion = await interprete.interpretar(mensaje, contexto)
        resultados = await despachador.despachar(interpretacion)
        texto = await expresador.expresar(resultados, usuario="Maty")

        print(f"\n{'─' * 60}")
        print(f"vos:  {mensaje}")
        print(f"abel: {texto}")

    await servidor.cerrar()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)