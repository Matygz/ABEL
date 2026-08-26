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
    # Con el dato correcto adentro.
    "no, se llama Marta",
    "no, mi vieja se llama Marta",
    "no, es Julio",
    "no, ya no trabajo ahí",
    "no, ya no trabajo ahi",
    "cambió, ahora vivo en Quilmes",
    "cambio, ahora vivo en Quilmes",
    "me confundí, es al revés",

    # Sin el dato: señalan el error sin decir cuál es el valor correcto.
    "eso está mal",
    "eso esta mal",
    "te equivocaste",
    "no es así",
    "no es asi",
    "nada que ver",
    "ya no es así",
    "ya no es asi",
    "eso ya no vale",
    "no dije eso",
    "estás equivocado",
    "estas equivocado",
    "corregí eso",
    "corregi eso",
    "borrá eso",
    "borra eso",
    "eso es falso",
    "ya no",
    "no, para nada",
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
