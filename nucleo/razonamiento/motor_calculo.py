"""Resolución exacta de problemas de cálculo.

El modelo de lenguaje reconoce que algo es un cálculo y extrae el enunciado.
Resolver es de acá: enumeración exacta, no estimación.

Es la diferencia que importa. Un modelo de lenguaje, ante "probabilidad de
sacar más de 15 con tres dados", devuelve un número que suena razonable y
suele estar mal. Este motor cuenta los casos y da el número correcto — y
puede mostrar cómo llegó.

El LLM no calcula nunca. Traduce el enunciado a una estructura; el cómputo
ocurre en Python.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Any

from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje
from nucleo.razonamiento.resultado import Procedencia, Resultado, sin_alcance

logger = logging.getLogger(__name__)

MAX_COMBINACIONES = 2_000_000


INSTRUCCIONES_DADOS = """\
Convertí el enunciado en una estructura de cálculo. NO resuelvas el problema.
NO calcules nada. Solo extraé los datos.

Devolvé JSON con esta forma:

{
  "clase": "dados",
  "cantidad": <cuántos dados>,
  "caras": <cuántas caras tiene cada dado>,
  "comparador": "mayor|mayor_igual|menor|menor_igual|igual",
  "objetivo": <número>
}

Si el enunciado NO es un problema de dados, devolvé:
{"clase": "desconocida"}

Ejemplos:

"si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?"
{"clase": "dados", "cantidad": 3, "caras": 6, "comparador": "mayor",
 "objetivo": 15}

"probabilidad de sacar al menos 8 con dos dados"
{"clase": "dados", "cantidad": 2, "caras": 6, "comparador": "mayor_igual",
 "objetivo": 8}

"tiro 4 dados de 20 caras, ¿qué chance hay de sacar exactamente 50?"
{"clase": "dados", "cantidad": 4, "caras": 20, "comparador": "igual",
 "objetivo": 50}
"""


COMPARADORES = {
    "mayor": lambda s, o: s > o,
    "mayor_igual": lambda s, o: s >= o,
    "menor": lambda s, o: s < o,
    "menor_igual": lambda s, o: s <= o,
    "igual": lambda s, o: s == o,
}

SIMBOLOS = {
    "mayor": ">", "mayor_igual": "≥",
    "menor": "<", "menor_igual": "≤", "igual": "=",
}


@dataclass(frozen=True)
class ProblemaDados:
    cantidad: int
    caras: int
    comparador: str
    objetivo: int


class MotorCalculo:
    """Resuelve problemas de cálculo de forma exacta."""

    def __init__(self, motor_lenguaje: MotorLenguaje) -> None:
        self._llm = motor_lenguaje

    async def resolver(self, clase: str, enunciado: str) -> Resultado:
        """Resuelve un problema de cálculo.

        Recibe la clase y el enunciado sueltos: el motor no tiene por qué
        conocer la estructura de intenciones del analizador.
        """
        clase = str(clase or "").lower()
        enunciado = str(enunciado or "").strip()

        if not enunciado:
            return sin_alcance("un enunciado claro para calcular")

        if clase in ("aritmetica", "aritmética"):
            return await self._resolver_aritmetica(enunciado)

        if clase != "probabilidad":
            return sin_alcance(f"resolver problemas de tipo {clase!r}")

        problema = await self._estructurar_dados(enunciado)
        if problema is None:
            return Resultado(
                tipo="calculo",
                procedencia=Procedencia.NINGUNA,
                falta="entender el enunciado como un problema que sé resolver",
                salvedades=(
                    "Hoy solo resuelvo probabilidades con dados. "
                    "Podés reformularlo o darme más detalle.",
                ),
            )

        return self._resolver_dados(problema)

    # ------------------------------------------------------------------

    async def _estructurar_dados(self, enunciado: str) -> ProblemaDados | None:
        """El modelo extrae la estructura; no calcula."""
        try:
            datos = await self._llm.generar_json(INSTRUCCIONES_DADOS, enunciado)
        except ErrorLenguaje as exc:
            logger.warning("No se pudo estructurar el problema: %s", exc)
            return None

        if datos.get("clase") != "dados":
            return None

        try:
            problema = ProblemaDados(
                cantidad=int(datos["cantidad"]),
                caras=int(datos["caras"]),
                comparador=str(datos["comparador"]),
                objetivo=int(datos["objetivo"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("Estructura de dados incompleta: %r", datos)
            return None

        if problema.comparador not in COMPARADORES:
            return None
        if not (1 <= problema.cantidad <= 20):
            return None
        if not (2 <= problema.caras <= 1000):
            return None
        if problema.caras ** problema.cantidad > MAX_COMBINACIONES:
            return None

        return problema

    # ------------------------------------------------------------------

    @staticmethod
    def _resolver_dados(p: ProblemaDados) -> Resultado:
        """Cuenta los casos favorables por enumeración exacta.

        Sin aproximaciones ni fórmulas: se generan todas las combinaciones y
        se cuentan. Con los límites impuestos es instantáneo, y el resultado
        es exacto por construcción.
        """
        cumple = COMPARADORES[p.comparador]
        caras = range(1, p.caras + 1)

        total = p.caras ** p.cantidad
        favorables = sum(
            1 for tirada in product(caras, repeat=p.cantidad)
            if cumple(sum(tirada), p.objetivo)
        )

        exacta = Fraction(favorables, total)
        minimo, maximo = p.cantidad, p.cantidad * p.caras

        salvedades = []
        if p.objetivo > maximo or p.objetivo < minimo:
            salvedades.append(
                f"Con {p.cantidad} dado(s) de {p.caras} caras la suma solo "
                f"puede ir de {minimo} a {maximo}."
            )

        return Resultado(
            tipo="calculo",
            procedencia=Procedencia.CALCULADO,
            datos={
                "probabilidad": float(exacta),
                "porcentaje": float(exacta) * 100,
                "favorables": favorables,
                "total": total,
                "fraccion": f"{exacta.numerator}/{exacta.denominator}",
                "rango_posible": (minimo, maximo),
            },
            pasos=(
                f"{p.cantidad} dado(s) de {p.caras} caras: "
                f"{total:,} combinaciones posibles",
                f"Casos con suma {SIMBOLOS[p.comparador]} {p.objetivo}: "
                f"{favorables:,}",
                f"Probabilidad = {favorables:,} / {total:,} = "
                f"{float(exacta) * 100:.2f}%",
            ),
            salvedades=tuple(salvedades),
        )
    
    async def _resolver_aritmetica(self, enunciado: str) -> Resultado:
        """Evalúa una expresión aritmética de forma exacta.

        Los modelos de lenguaje son pésimos con aritmética: producen números
        plausibles y equivocados. Acá se calcula de verdad.
        """
        import ast
        import operator

        OPERADORES = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow, ast.Mod: operator.mod,
            ast.USub: operator.neg,
        }

        def evaluar(nodo):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
                return nodo.value
            if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERADORES:
                return OPERADORES[type(nodo.op)](
                    evaluar(nodo.left), evaluar(nodo.right)
                )
            if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERADORES:
                return OPERADORES[type(nodo.op)](evaluar(nodo.operand))
            raise ValueError("expresión no permitida")

        expresion = (
            enunciado.lower()
            .replace("x", "*").replace("×", "*").replace("÷", "/")
            .replace(",", ".")
        )

        try:
            arbol = ast.parse(expresion, mode="eval")
            valor = evaluar(arbol.body)
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
            return sin_alcance(f"entender {enunciado!r} como una operación")

        return Resultado(
            tipo="calculo",
            procedencia=Procedencia.CALCULADO,
            datos={"expresion": expresion, "valor": valor},
            pasos=(f"{expresion} = {valor}",),
        )