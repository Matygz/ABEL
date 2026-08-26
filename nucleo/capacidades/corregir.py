"""Reconocer cuándo la persona corrige algo que ABEL cree.

Existe para que el clasificador tenga con qué comparar, igual que afirmar.py.
No corrige nada acá: solo reconoce que el mensaje es una corrección. El
trabajo de identificar qué se corrige y aplicarlo lo hace
nucleo/lenguaje/corrector.py, llamado desde nucleo/lenguaje/conversacion.py
cuando esta capacidad gana el análisis — igual que afirmar, necesita el
mensaje completo y el contexto de la sesión, cosas que el despachador no le
pasa a una capacidad común.

Por qué importa: una corrección es la evidencia más fuerte que ABEL puede
tener sobre algo — más que una observación propia, más que una inferencia.
Si la persona dice que algo está mal, está mal. No hay margen para pesarla
contra otra fuente, como sí pasa entre dos afirmaciones told que difieren.
"""

from __future__ import annotations

from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "corregir"
TIPO = "corregir"
DESCRIPCION = "Enmendar algo que ABEL cree y está equivocado."
NIVEL = "lectura"
NECESITA = ("llm", "afirmaciones", "repositorio")

EJEMPLOS = (
    # Solo la marca de corrección, sin repetir el hecho: "no, mi vieja se
    # llama Marta" quedaba a 0.928 de "mi vieja se llama Marta" y se
    # comía las afirmaciones normales. El "no" pesa poco en el vector de
    # una frase larga — lo que distingue es la frase corta y explícita.
    "eso está mal",
    "eso esta mal",
    "te equivocaste",
    "no es así",
    "no es asi",
    "nada que ver",
    "estás equivocado",
    "estas equivocado",
    "me confundí",
    "me confundi",
    "no dije eso",
    "eso es falso",
    "eso ya no vale",
    "ya no es así",
    "corregí eso",
    "corregi eso",
    "está mal lo que anotaste",
    "no, eso no",
    "eso cambió",
    "eso cambio",
    "ya no",
    "no, mentira",
    "mentira",
    "mentira, no es así",
    "no mentira",
    "pará, mentira",
    "para, mentira",
)


async def resolver(parametros: dict, llm, afirmaciones, repositorio) -> Resultado:
    # Solo marca que se reconoció una corrección. No escribe nada: el
    # despachador solo le pasa a esta capacidad los parámetros declarados
    # (ninguno) y las dependencias de NECESITA — no el mensaje completo, ni
    # el id del turno, ni la sesión, que es lo que hace falta para saber
    # qué se está corrigiendo. Eso lo hace nucleo/lenguaje/corrector.py,
    # llamado directamente desde conversacion.py.
    return Resultado(
        tipo="corregir",
        procedencia=Procedencia.NINGUNA,
        datos={},
    )
