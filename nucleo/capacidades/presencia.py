"""Cuándo el usuario estuvo activo frente a la máquina."""

from __future__ import annotations

from datetime import timedelta

from nucleo.memoria.consultas import Memoria, hoy, ultimos_dias
from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "presencia"
TIPO = "consultar_memoria"
DESCRIPCION = "Cuándo estuvo activo o inactivo frente a la máquina."
NIVEL = "lectura"
NECESITA = ("memoria",)
PARAMETROS = {
    "rango": {
        "tipo": "rango_temporal",
        "descripcion": "período a consultar",
        "default": "hoy",
    },
}
EJEMPLOS = (
    "¿cuándo estuve activo?",
    "a qué hora me puse a laburar",
    "cuándo me fui de la compu",
    "mostrame mis períodos de actividad",
    "¿me estoy quedando hasta tarde?",
    "a qué hora arranqué hoy",
    "cuánto tiempo estuve sin tocar nada",
    "cuándo estuve conectado",
    "a qué hora me levanté",
    "estuve mucho rato inactivo",

    # Variantes sin acento: se escribe "cuando"/"cuanto" mucho más seguido
    # que con tilde, y la frase corta hace que la falta de tilde importe.
    "cuando estuve activo",
    "cuanto tiempo estuve sin tocar nada",
)

def _rango(crudo: str | None):
    texto = str(crudo or "hoy").lower().strip()
    if texto in ("semana", "week"):
        return ultimos_dias(7)
    if texto in ("mes", "month"):
        return ultimos_dias(30)
    if texto in ("ayer", "yesterday"):
        inicio, _ = hoy()
        return inicio - timedelta(days=1), inicio
    return hoy()


async def resolver(parametros: dict, memoria: Memoria) -> Resultado:
    desde, hasta = _rango(parametros.get("rango"))
    cambios = await memoria.periodos_de_actividad(desde, hasta)

    return Resultado(
        tipo="presencia",
        procedencia=Procedencia.OBSERVADO,
        datos={"cambios": cambios, "desde": desde, "hasta": hasta},
        pasos=(f"Transiciones de estado entre {desde:%d/%m} y {hasta:%d/%m}",),
        salvedades=(
            "'inactivo' significa sin entrada de teclado ni mouse, "
            "no que no hubiera nadie.",
        ),
    )