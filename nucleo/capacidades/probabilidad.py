"""Probabilidad con dados, resuelta por enumeración exacta.

El modelo de lenguaje extrae la estructura del enunciado; el cómputo ocurre
en Python. Los modelos son notoriamente malos con probabilidades: producen un
número plausible y equivocado. Acá se cuentan los casos.
"""

from __future__ import annotations

from nucleo.lenguaje.interprete import Intencion, TipoIntencion
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.razonamiento.motor_calculo import MotorCalculo
from nucleo.razonamiento.resultado import Resultado

NOMBRE = "probabilidad"
TIPO = "calcular"
DESCRIPCION = "Probabilidad con dados, por enumeración exacta."
NIVEL = "lectura"
NECESITA = ("llm",)

EJEMPLOS = (
    "si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?",
    "probabilidad de sacar 7 con dos dados",
    "qué chance hay de sacar al menos 10",
    "cuál es la probabilidad de que salga par",
    "tiro cuatro dados de veinte caras, chance de pasar 50",
    "qué tan probable es sacar doble seis",
    "chances de sacar menos de 5 con dos dados",
)


async def resolver(parametros: dict, llm: MotorLenguaje) -> Resultado:
    intencion = Intencion(
        tipo=TipoIntencion.CALCULAR,
        confianza=1.0,
        parametros={
            "clase": "probabilidad",
            "enunciado": parametros.get("enunciado", ""),
        },
    )
    return await MotorCalculo(llm).resolver(intencion)