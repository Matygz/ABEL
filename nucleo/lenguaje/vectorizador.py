"""Conversión de texto a vectores.

Un vector es la forma en que ABEL puede comparar significados sin generar
texto. Dos frases que quieren decir lo mismo caen cerca aunque no compartan
ninguna palabra — y eso permite reconocer una intención sin pedirle a un
modelo de lenguaje que la clasifique.

Corre en CPU a propósito: vectorizar una frase corta tarda milisegundos, y la
GPU hace falta para generar. Cada uno donde rinde.

El modelo se carga una vez y queda residente: son unos 600 MB de RAM, contra
32 disponibles. No hay carga bajo demanda como con el modelo de lenguaje
porque acá el costo es de RAM, no de VRAM.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from comun.errores import ErrorOperativo

logger = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "Qwen/Qwen3-Embedding-0.6B"


class ErrorVectorizador(ErrorOperativo):
    """No se pudo convertir texto a vectores."""


class Vectorizador:
    """Convierte texto en vectores comparables."""

    def __init__(self, modelo: str = MODELO_POR_DEFECTO) -> None:
        self._nombre = modelo
        self._modelo = None
        self._dimensiones: int | None = None
        self._cargando = asyncio.Lock()

    # ------------------------------------------------------------------

    async def cargar(self) -> None:
        """Carga el modelo. Tarda unos segundos la primera vez.

        Se hace en un hilo aparte: importar y cargar el modelo bloquea, y el
        bucle de eventos tiene que seguir atendiendo mientras tanto.
        """
        async with self._cargando:
            if self._modelo is not None:
                return

            def _cargar():
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(
                    self._nombre, device="cpu"
                )

            try:
                self._modelo = await asyncio.to_thread(_cargar)
            except Exception as exc:
                raise ErrorVectorizador(
                    f"No se pudo cargar el modelo {self._nombre}: {exc}"
                ) from None

            self._dimensiones = self._modelo.get_embedding_dimension()
            logger.info(
                "Vectorizador listo: %s (%d dimensiones)",
                self._nombre, self._dimensiones,
            )

    @property
    def dimensiones(self) -> int:
        """Cuántos números tiene cada vector. Debe coincidir con la colección."""
        if self._dimensiones is None:
            raise ErrorVectorizador("El vectorizador no está cargado.")
        return self._dimensiones

    @property
    def cargado(self) -> bool:
        return self._modelo is not None

    # ------------------------------------------------------------------

    async def vectorizar(self, texto: str) -> list[float]:
        """Convierte un texto en un vector."""
        vectores = await self.vectorizar_lote([texto])
        return vectores[0]

    async def vectorizar_lote(self, textos: Sequence[str]) -> list[list[float]]:
        """Convierte varios textos de una vez.

        En lote es bastante más rápido que uno por uno: el modelo procesa
        todos juntos en vez de pagar el costo fijo por cada uno. Importa al
        cargar el catálogo de capacidades, no al clasificar un mensaje.
        """
        if not textos:
            return []

        if self._modelo is None:
            await self.cargar()

        def _codificar():
            return self._modelo.encode(
                list(textos),
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist()

        try:
            return await asyncio.to_thread(_codificar)
        except Exception as exc:
            raise ErrorVectorizador(f"Fallo al vectorizar: {exc}") from None