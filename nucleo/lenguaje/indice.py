"""Índice de ejemplos para reconocer intenciones por similitud.

Cada capacidad declara ejemplos de cómo se le pide. Se vectorizan y se
guardan en Qdrant; cuando llega un mensaje, se busca cuál queda más cerca.

Buscar por similitud no se degrada con la cantidad: la diferencia entre siete
capacidades y dos mil es irrelevante para el índice. Un prompt, en cambio, se
degrada — cada ejemplo nuevo compite por atención con los anteriores.

Y el índice crece con el uso: un mensaje bien clasificado se puede sumar como
ejemplo, y el reconocimiento mejora para esa persona en particular. Eso es la
memoria mejorando la cognición, no un modelo más grande.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient, models

from comun.errores import ErrorOperativo
from nucleo.capacidades.registro import RegistroCapacidades
from nucleo.lenguaje.vectorizador import Vectorizador

logger = logging.getLogger(__name__)

COLECCION = "intenciones"


class ErrorIndice(ErrorOperativo):
    """Fallo al indexar o buscar."""


@dataclass(frozen=True)
class Coincidencia:
    """Un ejemplo parecido al mensaje, con qué tan parecido es."""

    capacidad: str
    tipo: str
    ejemplo: str
    similitud: float


class IndiceIntenciones:
    """Guarda los ejemplos y busca el más parecido a un mensaje."""

    def __init__(
        self,
        vectorizador: Vectorizador,
        url: str = "http://127.0.0.1:6333",
    ) -> None:
        self._vectorizador = vectorizador
        self._cliente = AsyncQdrantClient(url=url)

    async def cerrar(self) -> None:
        await self._cliente.close()

    # ------------------------------------------------------------------

    async def disponible(self) -> bool:
        try:
            await self._cliente.get_collections()
            return True
        except Exception:
            return False

    async def sincronizar(self, registro: RegistroCapacidades) -> bool:
        """Carga los ejemplos si cambiaron. Devuelve True si hubo que cargar.

        Se compara una huella del catálogo con la guardada: vectorizar 76
        ejemplos tarda unos segundos, y hacerlo en cada arranque sería
        desperdicio. Si nada cambió, no se toca nada.
        """
        await self._vectorizador.cargar()
        huella = self._huella(registro)

        if await self._al_dia(huella):
            logger.info("Índice al día.")
            return False

        await self._crear_coleccion()
        await self._cargar(registro, huella)
        return True

    @staticmethod
    def _huella(registro: RegistroCapacidades) -> str:
        """Resumen del catálogo. Cambia si cambia cualquier ejemplo."""
        partes = []
        for capacidad in sorted(registro.todas(), key=lambda c: c.nombre):
            partes.append(capacidad.nombre)
            partes.extend(capacidad.ejemplos)
        return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()[:16]

    async def _al_dia(self, huella: str) -> bool:
        try:
            info = await self._cliente.get_collection(COLECCION)
        except Exception:
            return False

        if info.points_count == 0:
            return False

        # La huella se guarda en un punto reservado, con el id 0.
        try:
            puntos = await self._cliente.retrieve(COLECCION, ids=[0])
        except Exception:
            return False

        return bool(puntos) and puntos[0].payload.get("huella") == huella

    async def _crear_coleccion(self) -> None:
        dimensiones = self._vectorizador.dimensiones

        try:
            await self._cliente.delete_collection(COLECCION)
        except Exception:
            pass

        await self._cliente.create_collection(
            collection_name=COLECCION,
            vectors_config=models.VectorParams(
                size=dimensiones,
                distance=models.Distance.COSINE,
            ),
        )
        logger.debug("Colección creada: %d dimensiones", dimensiones)

    async def _cargar(self, registro: RegistroCapacidades, huella: str) -> None:
        """Vectoriza todos los ejemplos y los guarda."""
        textos: list[str] = []
        metadatos: list[dict] = []

        for capacidad in registro.todas():
            for ejemplo in capacidad.ejemplos:
                textos.append(ejemplo)
                metadatos.append({
                    "capacidad": capacidad.nombre,
                    "tipo": capacidad.tipo,
                    "ejemplo": ejemplo,
                })

        if not textos:
            raise ErrorIndice("No hay ejemplos que indexar.")

        vectores = await self._vectorizador.vectorizar_lote(textos)

        # El punto 0 guarda la huella; los ejemplos van desde el 1.
        puntos = [
            models.PointStruct(
                id=0,
                vector=[0.0] * self._vectorizador.dimensiones,
                payload={"huella": huella, "reservado": True},
            )
        ]
        puntos += [
            models.PointStruct(id=i + 1, vector=vector, payload=meta)
            for i, (vector, meta) in enumerate(zip(vectores, metadatos))
        ]

        await self._cliente.upsert(collection_name=COLECCION, points=puntos)
        logger.info("Índice cargado: %d ejemplos.", len(textos))

    # ------------------------------------------------------------------

    async def buscar(self, mensaje: str, cantidad: int = 5) -> list[Coincidencia]:
        """Devuelve los ejemplos más parecidos, del más cercano al menos."""
        vector = await self._vectorizador.vectorizar(mensaje)

        try:
            resultados = await self._cliente.query_points(
                collection_name=COLECCION,
                query=vector,
                limit=cantidad + 1,   # +1 por si aparece el punto reservado
                with_payload=True,
            )
        except Exception as exc:
            raise ErrorIndice(f"Fallo al buscar: {exc}") from None

        coincidencias = []
        for punto in resultados.points:
            if punto.payload.get("reservado"):
                continue
            coincidencias.append(
                Coincidencia(
                    capacidad=punto.payload["capacidad"],
                    tipo=punto.payload["tipo"],
                    ejemplo=punto.payload["ejemplo"],
                    similitud=punto.score,
                )
            )

        return coincidencias[:cantidad]