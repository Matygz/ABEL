"""Tiempo de uso por aplicación."""

from __future__ import annotations

from datetime import timedelta

from nucleo.memoria.consultas import Memoria, hoy, ultimos_dias
from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "actividad_por_aplicacion"
TIPO = "consultar_memoria"
DESCRIPCION = "Cuánto tiempo se usó cada aplicación."
NIVEL = "lectura"
NECESITA = ("memoria",)

EJEMPLOS = (
    "¿cuánto tiempo estuve en Code hoy?",
    "cuánto usé el editor",
    "en qué aplicaciones gasté el tiempo",
    "qué programas usé hoy",
    "cuánto tiempo pasé en el navegador",
    "dame el tiempo por aplicación",
    "en qué se me fue el día",
    "cuánto estuve laburando",
    "qué apps abrí esta semana",
    "tiempo de uso de WhatsApp",
    "cuánto estuve en el chat",
    "en qué anduve ayer",
)


def _rango(crudo: str | None):
    """Traduce un rango en palabras a fechas concretas."""
    texto = str(crudo or "hoy").lower().strip()

    if texto.startswith("dias:"):
        try:
            return ultimos_dias(int(texto.split(":", 1)[1]))
        except (ValueError, IndexError):
            pass
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
    filtro = parametros.get("filtro") or None

    datos = await memoria.actividad_por_aplicacion(desde, hasta)

    if filtro:
        buscado = str(filtro).lower()
        datos = [d for d in datos if buscado in d["aplicacion"].lower()]

    total = sum(d["segundos"] for d in datos)

    return Resultado(
        tipo="actividad",
        procedencia=Procedencia.OBSERVADO,
        datos={
            "aplicaciones": datos,
            "total_segundos": total,
            "desde": desde,
            "hasta": hasta,
            "filtro": filtro,
        },
        pasos=(
            f"Sesiones de ventana entre {desde:%d/%m %H:%M} y {hasta:%d/%m %H:%M}",
            "Agrupadas por aplicación"
            + (f", filtrando por {filtro}" if filtro else ""),
        ),
    )