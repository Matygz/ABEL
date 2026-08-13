"""Decide qué capacidad corresponde a un mensaje.

Segunda capa de la cascada: los patrones atrapan lo determinista, esto
reconoce lo conocido, y solo lo que no encaja llega al modelo de lenguaje.

No genera nada. Compara el mensaje contra los ejemplos indexados y vota entre
los más cercanos. Un clasificador que solo puede elegir entre capacidades
existentes no puede inventarse una categoría — que es lo que hacía el
intérprete generativo ante frases raras.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from nucleo.lenguaje.indice import Coincidencia, ErrorIndice, IndiceIntenciones

logger = logging.getLogger(__name__)

# Por debajo de esto, ninguna capacidad corresponde. Calibrado con datos:
# los aciertos daban 0.93+ y los ajenos 0.64-.
UMBRAL = 0.72

# Cuántas coincidencias participan de la votación.
VOTANTES = 5


@dataclass(frozen=True)
class Clasificacion:
    """Qué capacidad corresponde, y qué tan seguro está."""

    capacidad: str | None
    tipo: str | None
    confianza: float
    coincidencias: tuple[Coincidencia, ...] = ()

    @property
    def reconocido(self) -> bool:
        return self.capacidad is not None


class Clasificador:
    """Reconoce intenciones por similitud con ejemplos conocidos."""

    def __init__(
        self,
        indice: IndiceIntenciones,
        umbral: float = UMBRAL,
        votantes: int = VOTANTES,
    ) -> None:
        self._indice = indice
        self._umbral = umbral
        self._votantes = votantes

    async def clasificar(self, mensaje: str) -> Clasificacion:
        """Devuelve la capacidad que mejor corresponde, o ninguna."""
        mensaje = mensaje.strip()
        if not mensaje:
            return Clasificacion(None, None, 0.0)

        try:
            coincidencias = await self._indice.buscar(mensaje, self._votantes)
        except ErrorIndice as exc:
            # Sin índice el mensaje sigue hacia el modelo de lenguaje: se
            # pierde velocidad, no la conversación.
            logger.warning("Sin clasificación por similitud: %s", exc)
            return Clasificacion(None, None, 0.0)

        if not coincidencias:
            return Clasificacion(None, None, 0.0)

        mejor = coincidencias[0]

        if mejor.similitud < self._umbral:
            logger.debug(
                "Nada supera el umbral: mejor %.3f (%s)",
                mejor.similitud, mejor.capacidad,
            )
            return Clasificacion(
                None, None, mejor.similitud, tuple(coincidencias)
            )

        ganadora, confianza = self._votar(coincidencias)

        return Clasificacion(
            capacidad=ganadora.capacidad,
            tipo=ganadora.tipo,
            confianza=confianza,
            coincidencias=tuple(coincidencias),
        )

    # ------------------------------------------------------------------

    def _votar(
        self, coincidencias: list[Coincidencia]
    ) -> tuple[Coincidencia, float]:
        """Elige entre las coincidencias sumando el peso de cada capacidad.

        Solo votan las que superan el umbral: una coincidencia lejana no
        aporta información, solo ruido.

        Vota el conjunto y no solo la primera porque un ejemplo suelto de otra
        capacidad puede parecerse mucho por casualidad. Si tres de cinco
        apuntan al mismo lado, eso pesa más que una coincidencia aislada.
        """
        pesos: dict[str, float] = defaultdict(float)
        mejor_de: dict[str, Coincidencia] = {}

        for coincidencia in coincidencias:
            if coincidencia.similitud < self._umbral:
                continue
            pesos[coincidencia.capacidad] += coincidencia.similitud
            if coincidencia.capacidad not in mejor_de:
                mejor_de[coincidencia.capacidad] = coincidencia

        if not pesos:
            return coincidencias[0], coincidencias[0].similitud

        nombre = max(pesos, key=pesos.get)
        ganadora = mejor_de[nombre]

        # La confianza es la similitud del mejor ejemplo de la ganadora, no
        # la suma: el peso sirve para elegir, no para medir certeza.
        return ganadora, ganadora.similitud