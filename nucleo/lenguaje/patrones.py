"""Reconocimiento de mensajes que no necesitan un modelo.

Una expresión aritmética no es lenguaje ambiguo: es una expresión aritmética.
Pasarla por un modelo generativo para que la clasifique es caro, lento, y
puede fallar — falló.

Lo que se reconoce acá sale con confianza 1.0 y no toca el LLM. Es la primera
etapa de un filtro en cascada: cada capa resuelve lo que puede y solo pasa
hacia abajo lo que no reconoce.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


# Una expresión aritmética: números, operadores y paréntesis, nada más.
# El texto alrededor ("cuánto es", "?") se descarta antes de probar.
_ARITMETICA = re.compile(
    r"^[\d\s.,+\-*/x×÷^()]+$",
    re.IGNORECASE,
)

# Lo que suele envolver a una operación en lenguaje natural.
_ENVOLTURA = re.compile(
    r"^[¿¡\s]*"
    r"(?:che,?\s*)?"
    r"(?:cu[aá]nto\s+(?:es|da|son)|calcul[aá](?:me)?|resolv[eé](?:me)?|"
    r"decime\s+cu[aá]nto\s+(?:es|da))?\s*"
    r"(.+?)"
    r"\s*[?¿!¡.]*$",
    re.IGNORECASE,

)

def reconocer(mensaje: str) -> tuple[str, dict] | None:
    """Devuelve (tipo, parámetros) si el mensaje es reconocible sin modelo.

    None significa "no sé qué es esto" — el mensaje sigue hacia la capa
    siguiente. Nunca adivina: es preferible pasar de largo a clasificar mal.

    No conoce la estructura de intenciones: devuelve datos crudos y quien
    llama los arma. Así esta capa no depende de nada.
    """
    texto = mensaje.strip()
    if not texto:
        return None

    aritmetica = _extraer_aritmetica(texto)
    if aritmetica is not None:
        logger.debug("Reconocido como aritmética: %r", aritmetica)
        return ("calcular", {"clase": "aritmetica", "enunciado": aritmetica})

    return None


def _extraer_aritmetica(texto: str) -> str | None:
    """Devuelve la expresión si el mensaje es una operación, o None.

    Requiere al menos un operador: sin eso, "42" sería una operación y no lo
    es — es un número suelto, y quién sabe qué quiso decir.
    """
    coincidencia = _ENVOLTURA.match(texto)
    if coincidencia is None:
        return None

    nucleo = coincidencia.group(1).strip()
    if not nucleo or not _ARITMETICA.match(nucleo):
        return None

    if not re.search(r"[+\-*/x×÷^]", nucleo, re.IGNORECASE):
        return None

    if not re.search(r"\d", nucleo):
        return None

    return nucleo