"""Qué es ABEL y qué puede hacer.

Se responde consultando el registro de capacidades: la respuesta sale de lo
que efectivamente está cargado, no de una lista escrita a mano que puede
quedar desactualizada.
"""

from __future__ import annotations

from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "sobre_si_mismo"
TIPO = "consultar_memoria"
DESCRIPCION = "Qué es ABEL y qué capacidades tiene."
NIVEL = "lectura"
NECESITA = ("registro",)

EJEMPLOS = (
    "¿quién sos?",
    "qué sos exactamente",
    "qué podés hacer",
    "sabés resolver ecuaciones",
    "qué cosas registrás",
    "cómo funcionás",
    "de qué te acordás",
    "qué información tenés mía",
    "para qué servís",
    "qué sabés hacer",
    "podés acceder a mi ubicación",
    "tenés acceso a mis mensajes",
)


async def resolver(parametros: dict, registro) -> Resultado:
    capacidades = [
        {"nombre": c.nombre, "descripcion": c.descripcion, "tipo": c.tipo}
        for c in registro.todas()
    ]

    return Resultado(
        tipo="capacidades",
        procedencia=Procedencia.OBSERVADO,
        datos={"capacidades": capacidades, "cantidad": len(capacidades)},
        pasos=("Consultado el registro de capacidades cargadas",),
    )