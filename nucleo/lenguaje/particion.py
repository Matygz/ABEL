"""Corte de un mensaje en partes con intención propia.

"Estoy quemado de Code, ¿cuánto tiempo estuve?" son dos cosas: un desahogo y
una pregunta. Cada una merece su intención.

El corte importa por algo más que reconocer las dos: distingue lo que la
persona pidió de lo que ABEL dedujo. Una parte propia del mensaje es un
pedido explícito y no se descarta por criterio; una capacidad que aparece
como segunda coincidencia sin corte es inferencia.

Se corta por señales fuertes —signos de pregunta, puntuación— y no por
cualquier conector: "estuve todo el día en el código y estoy quemado" es una
sola cosa dicha de corrido, aunque tenga un "y".
"""

from __future__ import annotations

import re

# Un mensaje muy corto no se parte: "hola, ¿qué onda?" es un saludo, no dos.
MINIMO_POR_PARTE = 12

# Conectores que sí separan intenciones cuando unen dos partes sustanciales.
_CONECTORES = re.compile(
    r"\s+(?:y\s+de\s+paso|y\s+tambi[eé]n|adem[aá]s|por\s+cierto|"
    r"a\s+prop[oó]sito|otra\s+cosa)\s+",
    re.IGNORECASE,
)


def partir(mensaje: str) -> list[str]:
    """Devuelve las partes con intención propia."""
    texto = mensaje.strip()
    if not texto:
        return []

    texto = _sin_apertura(texto)

    partes = _por_pregunta(texto)
    if len(partes) > 1:
        return partes

    partes = _por_conector(texto)
    if len(partes) > 1:
        return partes

    return [texto]


def _sin_apertura(texto: str) -> str:
    """Quita el saludo inicial si lo acompaña algo con contenido.

    "Hola, ¿cuánto estuve en Code?" es una consulta con un saludo adelante,
    no dos intenciones. Sacarlo evita partir por una fórmula de cortesía.

    Si el saludo es todo lo que hay —"hola" a secas— se conserva: ahí sí es
    la intención del mensaje.
    """
    coincidencia = _APERTURAS_INICIALES.match(texto)
    if coincidencia is None:
        return texto

    resto = texto[coincidencia.end():].strip(" ,;")
    return resto if len(resto) >= MINIMO_POR_PARTE else texto


_APERTURAS_INICIALES = re.compile(
    r"^(?:hola|buenas|buen d[ií]a|buenas tardes|buenas noches|"
    r"ey|hey|holis|che)\b[,\s]*",
    re.IGNORECASE,
)


def _por_pregunta(texto: str) -> list[str]:
    """Separa una pregunta del resto del mensaje.

    Es la señal más confiable: un signo de interrogación marca un pedido
    explícito, y lo que viene antes suele ser otra cosa.
    """
    # Corta después de un cierre de interrogación o antes de una apertura.
    crudas = re.split(r"(?<=\?)\s+|\s+(?=¿)", texto)

    # También separa una cláusula que termina en coma y sigue con pregunta.
    if len(crudas) == 1 and "?" in texto:
        coincidencia = re.search(r"^(.{%d,}?)[,;]\s+(.*\?)\s*$" % MINIMO_POR_PARTE,
                                 texto, re.DOTALL)
        if coincidencia:
            crudas = [coincidencia.group(1), coincidencia.group(2)]

    return _limpiar(crudas)


def _por_conector(texto: str) -> list[str]:
    """Separa por conectores que marcan un cambio de tema."""
    return _limpiar(_CONECTORES.split(texto))


def _limpiar(partes: list[str]) -> list[str]:
    """Descarta las partes vacías o demasiado cortas para tener intención."""
    utiles = [p.strip(" ,;") for p in partes]
    utiles = [p for p in utiles if len(p) >= MINIMO_POR_PARTE]
    return utiles if len(utiles) > 1 else []