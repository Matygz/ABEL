"""El ciclo interno de ABEL.

Gira aunque no entre nada. Lee la sangre, calcula cuánta presión hay, y
decide si algo merece atención.

No es un manejador de eventos: nadie lo dispara. Corre porque ABEL existe, y
lo que encuentra depende de cómo está — no de lo que le mandaron.

Hoy solo mide y registra. Cuando existan los motores (modelo de personas,
memoria asociativa, atención), la presión los va a activar.

Ver docs/filosofia/arquitectura-v1.md, sección "Temperamento".
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from comun.sangre import Sangre
from nucleo.config import INTERVALO_CICLO_SEGUNDOS, UMBRAL_HABLAR, UMBRAL_PENSAR
from nucleo.datos.repositorio import Repositorio

logger = logging.getLogger(__name__)

# No repetir un registro por la misma causa antes de que pase esto, aunque
# la presión se mantenga alta. Sin este límite, una presión sostenida llena
# la memoria de eventos idénticos.
REPETICION_MINIMA_SEGUNDOS = 600.0

# Cada cuánto se deja una instantánea completa, haya o no presión. Es lo que
# permite reconstruir la noche después.
INTERVALO_ESTADO_SEGUNDOS = 3600.0


class Ciclo:
    """El bucle interno: lee la sangre, calcula presión, registra lo que encuentra.

    Restricciones deliberadas: no le habla a nadie más que al repositorio de
    eventos. No publica avisos dirigidos ni llama a otros componentes — eso
    es trabajo de los motores que todavía no existen.
    """

    def __init__(
        self,
        sangre: Sangre,
        repositorio: Repositorio,
        actor_id: UUID,
        run_id: UUID,
    ) -> None:
        self._sangre = sangre
        self._repo = repositorio
        self._actor_id = actor_id
        self._run_id = run_id

        # Para no repetir el mismo motivo dos veces seguidas.
        self._causa_anterior: str | None = None
        self._momento_anterior: datetime | None = None

        self._ultimo_estado: datetime | None = None

    async def girar(self) -> None:
        """El bucle en sí. Registrado como servicio: corre indefinidamente."""
        while True:
            await asyncio.sleep(INTERVALO_CICLO_SEGUNDOS)
            await self._latir()

    async def _latir(self) -> None:
        await self._incertidumbre_provisoria()

        instantanea = self._sangre.instantanea()
        presion, presion_hablar, desglose, causa = self._calcular_presion(instantanea)
        ahora = datetime.now(timezone.utc)

        if presion > UMBRAL_PENSAR:
            if self._debe_registrar(causa, ahora):
                impulso_hablar = presion_hablar > UMBRAL_HABLAR
                await self._repo.registrar_evento(
                    event_type="internal_pressure",
                    actor_id=self._actor_id,
                    run_id=self._run_id,
                    payload={
                        "presion": round(presion, 4),
                        "desglose": desglose,
                        "causa_dominante": causa,
                        "impulso_hablar": impulso_hablar,
                    },
                    occurred_at=ahora,
                )
                if impulso_hablar:
                    # Solo se registra el impulso. Todavía no hay qué decir:
                    # eso depende de los motores que faltan.
                    logger.info(
                        "Presión interna %.2f (%s). Impulso de hablar, sin hablar.",
                        presion, causa,
                    )
                else:
                    logger.info("Presión interna %.2f (%s).", presion, causa)

                self._causa_anterior = causa
                self._momento_anterior = ahora
        else:
            # Al caer por debajo del umbral, la próxima subida es una
            # ocurrencia nueva, no una continuación de la anterior.
            self._causa_anterior = None
            self._momento_anterior = None

        await self._registrar_estado_si_corresponde(ahora, instantanea)

    def _debe_registrar(self, causa: str, ahora: datetime) -> bool:
        """Evita registrar dos veces seguidas por el mismo motivo.

        Solo se registra de nuevo si cambió la causa dominante o pasó el
        tiempo mínimo de repetición.
        """
        if self._causa_anterior is None or self._momento_anterior is None:
            return True
        if causa != self._causa_anterior:
            return True
        transcurrido = (ahora - self._momento_anterior).total_seconds()
        return transcurrido > REPETICION_MINIMA_SEGUNDOS

    @staticmethod
    def _calcular_presion(instantanea: dict) -> tuple[float, float, dict, str]:
        """Devuelve (presion_pensar, presion_hablar, desglose, causa).

        Son dos presiones distintas y no una sola con umbrales distintos.

        Pensar no tiene costo para nadie: se piensa con lo que hay, esté o
        no la persona. Hablar interrumpe, y ahí sí el freno corresponde.

        Verificado por omisión: con el freno sobre las dos, una noche entera
        sin una sola presión registrada, porque `conexion` en cero anulaba
        todo.

        coherencia pesa doble: es lo único que corrompe todo lo que se apoye
        en ello. El freno multiplica en vez de restar: un freno alto debe
        anular, no descontar un poco.
        """
        incertidumbre = instantanea["incertidumbre"]["nivel"]
        novedad = instantanea["novedad"]["nivel"]
        coherencia = instantanea["coherencia"]["nivel"]
        conexion = instantanea["conexion"]["nivel"]
        saturacion = instantanea["saturacion"]["nivel"]

        # 1 - conexion: interrumpir a alguien que no está tiene otro costo.
        # saturacion: un sistema saturado debería dudar más de sí mismo.
        freno = max(1.0 - conexion, saturacion)

        aportes = {
            "incertidumbre": incertidumbre,
            "novedad": novedad,
            "coherencia": coherencia * 2.0,
        }

        presion_pensar = sum(aportes.values())
        presion_hablar = presion_pensar * (1.0 - freno)
        causa = max(aportes, key=aportes.get)

        desglose = {
            "incertidumbre": round(incertidumbre, 4),
            "novedad": round(novedad, 4),
            "coherencia": round(coherencia, 4),
            "freno": round(freno, 4),
            "presion_hablar": round(presion_hablar, 4),
        }
        return presion_pensar, presion_hablar, desglose, causa

    async def _registrar_estado_si_corresponde(
        self, ahora: datetime, instantanea: dict
    ) -> None:
        """Deja una instantánea completa cada hora, haya o no presión."""
        if (
            self._ultimo_estado is not None
            and (ahora - self._ultimo_estado).total_seconds() < INTERVALO_ESTADO_SEGUNDOS
        ):
            return

        await self._repo.registrar_evento(
            event_type="internal_state",
            actor_id=self._actor_id,
            run_id=self._run_id,
            payload={"sangre": instantanea},
            occurred_at=ahora,
        )
        self._ultimo_estado = ahora

    async def _incertidumbre_provisoria(self) -> None:
        """PROVISORIO — se elimina en la Fase 3.

        La incertidumbre real viene del modelo de personas: qué no sé de
        alguien que me importa. Eso todavía no existe.

        Mientras tanto se aproxima con los huecos de percepción: si pasaron
        horas sin observaciones, ABEL efectivamente no sabe qué pasó. Es
        pobre pero no es falso, y permite que el bucle tenga algo que leer.
        """
        fila = await self._repo.consultar_una(
            "SELECT MAX(occurred_at) AS ultima FROM events "
            "WHERE event_type = 'window_session'"
        )
        if fila is None or fila["ultima"] is None:
            return

        horas = (datetime.now(timezone.utc) - fila["ultima"]).total_seconds() / 3600
        # Cuatro horas sin percibir nada es incertidumbre alta.
        self._sangre.fijar("incertidumbre", min(1.0, 0.25 + horas / 4))
