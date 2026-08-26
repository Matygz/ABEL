"""Charla: no requiere datos ni cómputo.

Existe como capacidad para que el clasificador tenga con qué comparar. No
resuelve nada: el resultado es el hecho de que el mensaje es conversación, y
el expresador se encarga del resto.
"""

from __future__ import annotations

from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "conversar"
TIPO = "conversar"
DESCRIPCION = "Charla, desahogo, saludo, opinión."
NIVEL = "lectura"
NECESITA = ()

EJEMPLOS = (
    "hola",
    "buenas, ¿qué onda?",
    "me siento como el orto",
    "estoy hecho mierda",
    "qué andás haciendo",
    "estoy cansado",
    "tuve un día de mierda",
    "no doy más",
    "¿vos cómo estás?",
    "che, ¿todo bien?",
    "no sé qué hacer",
    "estoy contento hoy",
    "qué opinás de esto",
    "gracias",
    "nada, no importa",
    "estaba pensando en algo",
    "me pasó una cosa rara",
    "tengo ganas de dormir",
    "qué lindo día",
    "estoy medio bajoneado",
    "buen día",
    "chau, me voy",
    "dale",
    "ok",
    "listo",
    "qué onda",
    "todo bien",
    "me parece bien",
    "cualquiera",
    "está claro",
    "bueno",
    "claro",
    "obvio",
    "y bueno",
    "ni idea",
    "puede ser",
    "ah mirá",
    "epa",
    "uh",
    "jaja",
    "posta?",
    "en serio",
    "cómo andás",
    "como andas",
    "cómo venís",
    "todo en orden",
    "qué hacés",
    "cómo va",
)


async def resolver(parametros: dict) -> Resultado:
    return Resultado(
        tipo="conversar",
        procedencia=Procedencia.NINGUNA,
        datos=parametros,
    )