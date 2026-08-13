"""Estado del sistema: dispositivos, eventos, ejecuciones."""

from __future__ import annotations

from nucleo.memoria.consultas import Memoria
from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "estado_del_sistema"
TIPO = "consultar_memoria"
DESCRIPCION = "Estado de ABEL: dispositivos, eventos y ejecuciones."
NIVEL = "lectura"
NECESITA = ("memoria",)

EJEMPLOS = (
    "¿cómo está el sistema?",
    "cuántos eventos tenés registrados",
    "qué dispositivos hay conectados",
    "mostrame el estado del núcleo",
    "cuánta memoria tenés",
    "estás funcionando bien",
    "cuánto hace que estás corriendo",
    "qué tenés guardado",
)


async def resolver(parametros: dict, memoria: Memoria) -> Resultado:
    estado = await memoria.estado_del_sistema()
    return Resultado(
        tipo="sistema",
        procedencia=Procedencia.OBSERVADO,
        datos=estado,
    )