"""Lo que produce un motor al resolver una intención.

Datos estructurados, nunca texto formateado. El expresador decide cómo
decirlo; el motor solo dice qué encontró.

Un resultado lleva su procedencia: si fue observado, calculado o inferido.
Esa distinción no es decorativa — es la regla de que lo inferido nunca debe
ser indistinguible de lo observado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Procedencia:
    """De dónde sale un resultado.

    Determina cómo debe presentarse: un dato observado se afirma, uno
    inferido se matiza.
    """

    OBSERVADO = "observado"      # Registrado por un sensor
    CALCULADO = "calculado"      # Derivado con exactitud de lo observado
    INFERIDO = "inferido"        # Deducido, con margen de error
    NINGUNA = "ninguna"          # No hay dato


@dataclass(frozen=True)
class Resultado:
    """Lo que un motor encontró al resolver una intención."""

    tipo: str
    procedencia: str
    datos: Any = None
    confianza: float = 1.0

    # Cómo se llegó. Para poder explicar el razonamiento cuando se pida.
    pasos: tuple[str, ...] = ()

    # Qué le faltó a ABEL, si no pudo resolver.
    falta: str | None = None

    # Advertencias sobre el resultado: ambigüedades, datos parciales.
    salvedades: tuple[str, ...] = ()

    @property
    def resuelto(self) -> bool:
        return self.falta is None

    @property
    def vacio(self) -> bool:
        return self.datos is None or (
            isinstance(self.datos, (list, tuple, dict)) and not self.datos
        )


def sin_alcance(que_falta: str) -> Resultado:
    """Resultado para lo que ABEL no puede hacer.

    No es un error: es una respuesta legítima y honesta.
    """
    return Resultado(
        tipo="fuera_de_alcance",
        procedencia=Procedencia.NINGUNA,
        falta=que_falta,
    )