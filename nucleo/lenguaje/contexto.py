"""Contexto que ABEL le entrega al modelo junto con cada consulta.

Un modelo de lenguaje no puede traducir "lo de mi vieja" sin saber qué
lugares conoce ABEL. La solución no es analizar la oración con más detalle:
es darle la información antes de pedirle que interprete.

Hoy el contexto es magro —solo aplicaciones y dispositivos— porque ABEL no
registra lugares ni personas todavía. Cuando existan, se suman acá sin tocar
nada más.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from nucleo.datos.repositorio import ErrorRepositorio, Repositorio

logger = logging.getLogger(__name__)

CACHE_SEGUNDOS = 300.0


@dataclass
class ContextoABEL:
    """Lo que ABEL sabe, en forma utilizable por el modelo."""

    momento: datetime
    aplicaciones: tuple[str, ...] = ()
    dispositivos: tuple[str, ...] = ()
    desde: datetime | None = None
    usuario: str = ""

    def a_texto(self) -> str:
        """Formatea el contexto para incluirlo en las instrucciones.

        Se escribe en prosa breve y no en JSON: los modelos siguen mejor un
        contexto redactado que una estructura anidada.
        """
        lineas = [
            f"Fecha y hora actual: {self.momento.strftime('%A %d/%m/%Y %H:%M')}",
        ]

        if self.usuario:
            lineas.append(f"Usuario: {self.usuario}")

        if self.desde:
            dias = (self.momento - self.desde).days
            lineas.append(
                f"ABEL tiene registros desde {self.desde.strftime('%d/%m/%Y')} "
                f"({dias} días)."
            )

        if self.aplicaciones:
            lineas.append(
                "Aplicaciones registradas: " + ", ".join(self.aplicaciones)
            )

        if self.dispositivos:
            lineas.append("Dispositivos: " + ", ".join(self.dispositivos))

        lineas.append(
            "ABEL NO registra todavía: ubicación, personas, lugares, "
            "calendario, correo, ni contenido de archivos."
        )
        lineas.append(
            "ABEL NO registra todavía: ubicación, personas, lugares, "
            "calendario, correo, ni contenido de archivos."
        )
        lineas.append(
            "ABEL SÍ resuelve cálculos de probabilidad, lógica y optimización "
            "con motores propios: eso nunca es fuera_de_alcance."
        )

        return "\n".join(lineas)


class ProveedorContexto:
    """Arma el contexto consultando la memoria.

    Cachea unos minutos: las aplicaciones conocidas no cambian de un mensaje
    al siguiente, y consultarlas en cada turno sería desperdicio.
    """

    def __init__(self, repositorio: Repositorio) -> None:
        self._repo = repositorio
        self._cache: ContextoABEL | None = None
        self._vence: float = 0.0

    async def obtener(self, usuario: str = "") -> ContextoABEL:
        import asyncio

        ahora_monotonico = asyncio.get_running_loop().time()
        if self._cache is not None and ahora_monotonico < self._vence:
            return ContextoABEL(
                momento=datetime.now(timezone.utc).astimezone(),
                aplicaciones=self._cache.aplicaciones,
                dispositivos=self._cache.dispositivos,
                desde=self._cache.desde,
                usuario=usuario or self._cache.usuario,
            )

        contexto = await self._construir(usuario)
        self._cache = contexto
        self._vence = ahora_monotonico + CACHE_SEGUNDOS
        return contexto

    async def _construir(self, usuario: str) -> ContextoABEL:
        ahora = datetime.now(timezone.utc).astimezone()
        aplicaciones: tuple[str, ...] = ()
        dispositivos: tuple[str, ...] = ()
        desde: datetime | None = None

        try:
            aplicaciones = tuple(
                f["app"] for f in await self._repo.consultar(
                    """
                    SELECT DISTINCT payload->>'application' AS app
                      FROM events
                     WHERE event_type = 'window_session'
                       AND occurred_at > now() - INTERVAL '30 days'
                       AND payload->>'application' IS NOT NULL
                     ORDER BY app
                     LIMIT 40
                    """
                )
            )

            fila = await self._repo.consultar_una(
                "SELECT MIN(occurred_at) AS d FROM events"
            )
            desde = fila["d"] if fila else None

            activos = await self._repo.listar_dispositivos()
            dispositivos = tuple(d["name"] for d in activos)

        except ErrorRepositorio as exc:
            logger.warning("No se pudo armar el contexto completo: %s", exc)
            
        return ContextoABEL(
            momento=ahora,
            aplicaciones=aplicaciones,
            dispositivos=dispositivos,
            desde=desde,
            usuario=usuario,
        )