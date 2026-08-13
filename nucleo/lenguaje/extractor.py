"""Extracción de parámetros de un mensaje.

Una vez que se sabe qué capacidad corresponde, hay que sacar los datos: qué
rango de fechas, qué aplicación, qué enunciado.

Se hace en dos pasos. Primero patrones, que resuelven lo obvio sin costo:
"hoy", "ayer", "esta semana" son formas fijas. Después, solo si quedó algo
sin resolver y la capacidad lo declaró, el modelo de lenguaje.

Es una tarea mucho más chica que clasificar: ya se sabe qué capacidad es, así
que se le pide exactamente qué campos completar. El modelo no puede inventar
una categoría porque no se le está pidiendo una.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from nucleo.capacidades.registro import Capacidad
from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Extractores por patrón
# ----------------------------------------------------------------------

_RANGOS = (
    (r"\bhoy\b|\ben el d[ií]a\b", "hoy"),
    (r"\bayer\b", "ayer"),
    (r"\banteayer\b|\bantes de ayer\b", "dias:2"),
    (r"\besta semana\b|\bla semana\b|\b[uú]ltimos? (?:7|siete) d[ií]as\b", "semana"),
    (r"\beste mes\b|\bel mes\b|\b[uú]ltimos? (?:30|treinta) d[ií]as\b", "mes"),
    (r"\b[uú]ltimos? (\d+) d[ií]as\b", None),   # captura el número
)


def _extraer_rango(mensaje: str) -> str | None:
    """Reconoce un período en el mensaje."""
    texto = mensaje.lower()

    for patron, valor in _RANGOS:
        coincidencia = re.search(patron, texto)
        if coincidencia is None:
            continue
        if valor is not None:
            return valor
        try:
            return f"dias:{int(coincidencia.group(1))}"
        except (IndexError, ValueError):
            continue

    return None


def _extraer_aplicacion(mensaje: str, conocidas: tuple[str, ...]) -> str | None:
    """Busca una aplicación conocida mencionada en el mensaje.

    Compara contra las que ABEL registró: no tiene sentido buscar una
    aplicación que nunca vio, y adivinar nombres produce filtros que no
    coinciden con nada.
    """
    texto = mensaje.lower()

    for aplicacion in conocidas:
        # "Code.exe" se menciona como "code", "WhatsApp.Root.exe" como
        # "whatsapp": se compara contra la raíz del nombre.
        raiz = aplicacion.lower().split(".")[0]
        if len(raiz) < 3:
            continue
        if re.search(rf"\b{re.escape(raiz)}\b", texto):
            return aplicacion

    return None


# ----------------------------------------------------------------------

class Extractor:
    """Saca los parámetros que una capacidad necesita."""

    def __init__(self, motor: MotorLenguaje) -> None:
        self._motor = motor

    async def extraer(
        self,
        mensaje: str,
        capacidad: Capacidad,
        aplicaciones: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Devuelve los parámetros para ejecutar la capacidad."""
        declarados = capacidad.parametros
        if not declarados:
            return {}

        valores: dict[str, Any] = {}
        pendientes: dict[str, dict] = {}

        for nombre, definicion in declarados.items():
            if not isinstance(definicion, dict):
                # Parámetro con valor fijo: la capacidad ya lo resolvió.
                valores[nombre] = definicion
                continue

            valor = self._por_patron(
                mensaje, definicion.get("tipo", ""), aplicaciones
            )
            if valor is not None:
                valores[nombre] = valor
            elif definicion.get("preguntar_al_modelo", False):
                pendientes[nombre] = definicion
            else:
                valores[nombre] = definicion.get("default")

        if pendientes:
            valores.update(
                await self._por_modelo(mensaje, pendientes)
            )

        return valores

    # ------------------------------------------------------------------

    @staticmethod
    def _por_patron(
        mensaje: str, tipo: str, aplicaciones: tuple[str, ...]
    ) -> Any:
        """Extrae sin modelo lo que tiene forma reconocible."""
        if tipo == "rango_temporal":
            return _extraer_rango(mensaje)
        if tipo == "aplicacion":
            return _extraer_aplicacion(mensaje, aplicaciones)
        if tipo == "texto_completo":
            return mensaje
        return None

    async def _por_modelo(
        self, mensaje: str, pendientes: dict[str, dict]
    ) -> dict[str, Any]:
        """Le pide al modelo solo los campos que faltan.

        El prompt es corto a propósito: se nombran los campos y nada más. Sin
        categorías, sin ejemplos de clasificación, sin contexto — nada que el
        modelo pueda tomar como patrón para completar.
        """
        campos = "\n".join(
            f'- "{nombre}": {d.get("descripcion", nombre)}'
            for nombre, d in pendientes.items()
        )

        instrucciones = (
            "Extraé los datos pedidos del mensaje. Devolvé solo JSON con "
            "estas claves:\n\n"
            f"{campos}\n\n"
            "Si un dato no está en el mensaje, poné null. "
            "No agregues claves. No expliques nada."
        )

        try:
            datos = await self._motor.generar_json(
                instrucciones, mensaje, temperatura=0.1
            )
        except ErrorLenguaje as exc:
            logger.warning("No se pudieron extraer parámetros: %s", exc)
            return {n: d.get("default") for n, d in pendientes.items()}

        return {
            nombre: datos.get(nombre) or definicion.get("default")
            for nombre, definicion in pendientes.items()
        }