"""Motor de cálculo. Ejecutar: python -m tests.test_calculo"""

import asyncio

from nucleo.config import cargar_config
from nucleo.lenguaje.interprete import Intencion, TipoIntencion
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.razonamiento.motor_calculo import MotorCalculo

ENUNCIADOS = [
    "si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?",
    "probabilidad de sacar al menos 8 con dos dados",
    "con 2 dados, ¿qué chance hay de sacar exactamente 7?",
    "tiro 3 dados, probabilidad de sacar más de 30",
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

    motor = MotorCalculo(motor_llm)

    for enunciado in ENUNCIADOS:
        intencion = Intencion(
            tipo=TipoIntencion.CALCULAR,
            confianza=0.9,
            parametros={"clase": "probabilidad", "enunciado": enunciado},
        )
        r = await motor.resolver(intencion)

        print(f"\n> {enunciado}")
        if not r.resuelto:
            print(f"   no pude: {r.falta}")
        else:
            d = r.datos
            print(f"   {d['porcentaje']:.2f}%  ({d['fraccion']})")
            for paso in r.pasos:
                print(f"     · {paso}")
        for s in r.salvedades:
            print(f"   nota: {s}")

    await servidor.cerrar()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)