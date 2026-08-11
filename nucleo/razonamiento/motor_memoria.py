"""Resuelve consultas sobre lo que ABEL registró.

Traduce los parámetros que devolvió el intérprete a llamadas concretas al
módulo de memoria. No inventa: si la métrica pedida no existe, lo dice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from nucleo.datos.repositorio import ErrorRepositorio
from nucleo.lenguaje.interprete import Intencion
from nucleo.memoria.consultas import Memoria, hoy, ultimas_horas, ultimos_dias
from nucleo.razonamiento.resultado import Procedencia, Resultado, sin_alcance

logger = logging.getLogger(__name__)


class MotorMemoria:
    """Consulta la memoria de ABEL."""

    def __init__(self, memoria: Memoria) -> None:
        self._memoria = memoria

    async def resolver(self, intencion: Intencion) -> Resultado:
        metrica = str(intencion.parametros.get("metrica", "")).lower()
        desde, hasta = self._rango(intencion.parametros.get("rango"))
        filtro = intencion.parametros.get("filtro") or None
        if filtro in ("vacío", "vacio", ""):
            filtro = None

        try:
            if metrica in ("tiempo_por_aplicacion", "tiempo", "actividad"):
                return await self._actividad(desde, hasta, filtro)
            if metrica in ("presencia", "sesion"):
                return await self._presencia(desde, hasta)
            if metrica in ("sistema", "estado"):
                return await self._sistema()
        except ErrorRepositorio as exc:
            logger.error("Fallo al consultar la memoria: %s", exc)
            return Resultado(
                tipo="consultar_memoria",
                procedencia=Procedencia.NINGUNA,
                falta="acceso a la base de datos en este momento",
            )

        return sin_alcance(f"una consulta del tipo {metrica!r}")

    # ------------------------------------------------------------------

    async def _actividad(
        self, desde: datetime, hasta: datetime, filtro: str | None
    ) -> Resultado:
        datos = await self._memoria.actividad_por_aplicacion(desde, hasta)

        if filtro:
            buscado = filtro.lower()
            datos = [
                d for d in datos
                if buscado in d["aplicacion"].lower()
            ]

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
                f"Agrupadas por aplicación" + (f", filtrando por {filtro}" if filtro else ""),
            ),
        )

    async def _presencia(self, desde: datetime, hasta: datetime) -> Resultado:
        cambios = await self._memoria.periodos_de_actividad(desde, hasta)

        return Resultado(
            tipo="presencia",
            procedencia=Procedencia.OBSERVADO,
            datos={"cambios": cambios, "desde": desde, "hasta": hasta},
            pasos=(
                f"Transiciones de estado entre {desde:%d/%m} y {hasta:%d/%m}",
            ),
            salvedades=(
                "'inactivo' significa sin entrada de teclado ni mouse, "
                "no que no hubiera nadie.",
            ),
        )

    async def _sistema(self) -> Resultado:
        estado = await self._memoria.estado_del_sistema()
        return Resultado(
            tipo="sistema",
            procedencia=Procedencia.OBSERVADO,
            datos=estado,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _rango(crudo: str | None) -> tuple[datetime, datetime]:
        """Traduce el rango que devolvió el intérprete a fechas concretas."""
        texto = str(crudo or "hoy").lower().strip()

        if texto.startswith("dias:"):
            try:
                return ultimos_dias(int(texto.split(":", 1)[1]))
            except (ValueError, IndexError):
                pass

        if texto in ("hoy", "today"):
            return hoy()
        if texto in ("semana", "week"):
            return ultimos_dias(7)
        if texto in ("mes", "month"):
            return ultimos_dias(30)
        if texto in ("ayer", "yesterday"):
            inicio, _ = hoy()
            return inicio - timedelta(days=1), inicio

        return hoy()