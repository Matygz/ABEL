"""Operaciones aritméticas, evaluadas de forma exacta.

Llega acá por la capa de patrones, que reconoce expresiones sin modelo.
"""

from __future__ import annotations

from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.razonamiento.motor_calculo import MotorCalculo
from nucleo.razonamiento.resultado import Resultado

NOMBRE = "aritmetica"
TIPO = "calcular"
DESCRIPCION = "Operaciones aritméticas exactas."
NIVEL = "lectura"
NECESITA = ("llm",)
PARAMETROS = {
    "enunciado": {"tipo": "texto_completo"},
}
EJEMPLOS = (
    "cuánto es 4 por 29",
    "sumame 145 más 78",
    "cuánto da 1200 dividido 15",
    "calculá 17 al cuadrado",
    "cuánto es el 20 por ciento de 350",
)

async def resolver(parametros: dict, llm: MotorLenguaje) -> Resultado:
    return await MotorCalculo(llm).resolver(
        "aritmetica", parametros.get("enunciado", "")
    )