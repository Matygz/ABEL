"""Interpretación de mensajes. Ejecutar: python -m tests.test_interprete"""

import asyncio

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.contexto import ProveedorContexto
from nucleo.lenguaje.interprete import Interprete
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo

MENSAJES = [
    "¿cuánto tiempo estuve en Code hoy?",
    "me siento como el orto",
    "estuve todo el día en el código y estoy quemado",
    "¿dónde estuve ayer a las 6?",
    "si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?",
    "hola",
    "prendé la luz del living",
    "che, ¿me estoy quedando hasta tarde últimamente?",
]


async def main():
    config = cargar_config()
    motor = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")
    servidor = ServidorModelo(
        ejecutable=config.llm_ejecutable,
        modelo=config.llm_modelo,
        motor=motor,
        puerto=config.llm_puerto,
    )
    await servidor.asegurar_disponible()

    repo = Repositorio(config)
    proveedor = ProveedorContexto(repo)
    contexto = await proveedor.obtener(usuario="Maty")
    interprete = Interprete(motor)

    print("=" * 70)
    print(contexto.a_texto())
    print("=" * 70)

    for mensaje in MENSAJES:
        r = await interprete.interpretar(mensaje, contexto)
        print(f"\n> {mensaje}")
        for i in r.intenciones:
            print(f"   {i.tipo:<20} {i.confianza:.2f}  {i.parametros}")
        for a in r.ambiguedades:
            print(f"   ambiguo: {a}")

    await servidor.cerrar()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)