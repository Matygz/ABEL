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
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.preguntas import Preguntas

logger = logging.getLogger(__name__)

# No repetir un registro por la misma causa antes de que pase esto, aunque
# la presión se mantenga alta. Sin este límite, una presión sostenida llena
# la memoria de eventos idénticos.
REPETICION_MINIMA_SEGUNDOS = 600.0

# Cada cuánto se deja una instantánea completa, haya o no presión. Es lo que
# permite reconstruir la noche después.
INTERVALO_ESTADO_SEGUNDOS = 3600.0

# Con menos afirmaciones que esto, la proporción de confianza baja no
# significa nada — es preferible un valor honesto en reposo a uno
# fabricado con dos o tres datos.
MINIMO_AFIRMACIONES_PARA_INCERTIDUMBRE = 5

# Confianza por debajo de la cual una afirmación cuenta como "poco sabido"
# para la incertidumbre.
UMBRAL_CONFIANZA_BAJA = 0.5

# Días sin una afirmación nueva sobre nadie que, por sí solos, ya son
# incertidumbre máxima por ese componente.
DIAS_SIN_APRENDER_MAXIMO = 7.0

# Cuántas contradicciones muy creídas hacen falta para saturar la
# coherencia en 1. Tres contradicciones con confianza ~1 cada una la
# saturan; una sola y dudosa apenas la mueve.
CONTRADICCIONES_PARA_SATURAR = 3.0

# Cuánto peso acumulado de preguntas pendientes satura la deuda en 1. Tres
# preguntas de peso máximo sin responder son mucha deuda; una sola y débil
# apenas la mueve.
PREGUNTAS_PARA_SATURAR_DEUDA = 3.0


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
        afirmaciones: Afirmaciones | None = None,
        preguntas: Preguntas | None = None,
    ) -> None:
        self._sangre = sangre
        self._repo = repositorio
        self._actor_id = actor_id
        self._run_id = run_id
        self._afirmaciones = afirmaciones or Afirmaciones(repositorio)
        self._preguntas = preguntas or Preguntas(repositorio)

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
        await self._coherencia_desde_contradicciones()
        await self._incertidumbre_desde_modelo()
        await self._deuda_desde_preguntas()

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

    async def _coherencia_desde_contradicciones(self) -> None:
        """coherencia: cuánto ensucian las contradicciones activas, no cuántas hay.

        Una contradicción sobre algo central pesa; una sobre un detalle
        suelto, poco. Si pesaran todas igual, ABEL insistiría con cualquier
        discrepancia trivial y sería insoportable. Se aproxima el peso con
        la confianza de las afirmaciones involucradas: dos cosas muy
        creídas que se contradicen ensucian más que dos dudosas.
        """
        # Si las afirmaciones se reapuntaron bien al fusionar (ver
        # Afirmaciones.fusionar), una persona fusionada ya no debería tener
        # afirmaciones propias — pero se excluye igual, explícito: coherencia
        # alta sin causa visible es más desconcertante que una consulta de más.
        sujetos = await self._repo.consultar(
            """
            SELECT DISTINCT a.subject_id FROM assertions a
             WHERE a.retired_at IS NULL
               AND NOT EXISTS (
                   SELECT 1 FROM persons p
                    WHERE p.id = a.subject_id AND p.merged_into IS NOT NULL
               )
            """
        )
        if not sujetos:
            return

        peso_total = 0.0
        for fila in sujetos:
            contradicciones = await self._afirmaciones.buscar_contradicciones(
                fila["subject_id"]
            )
            for c in contradicciones:
                confianzas = [a["confidence"] for a in c["afirmaciones"]]
                peso_total += sum(confianzas) / len(confianzas)

        self._sangre.fijar(
            "coherencia", min(1.0, peso_total / CONTRADICCIONES_PARA_SATURAR)
        )

    async def _incertidumbre_desde_modelo(self) -> None:
        """incertidumbre: qué tanto de lo que ABEL cree es poco firme, o viejo.

        Dos componentes: qué proporción de las afirmaciones activas tiene
        confianza baja, y hace cuánto no aparece una afirmación nueva sobre
        alguien. Con pocas afirmaciones ninguno de los dos significa nada
        todavía — es preferible dejar la incertidumbre en su reposo que
        inventar un número con dos o tres datos.
        """
        activas = await self._repo.consultar(
            "SELECT confidence, created_at FROM assertions WHERE retired_at IS NULL"
        )
        if len(activas) < MINIMO_AFIRMACIONES_PARA_INCERTIDUMBRE:
            return

        proporcion_baja = sum(
            1 for a in activas if a["confidence"] < UMBRAL_CONFIANZA_BAJA
        ) / len(activas)

        ultima = max(a["created_at"] for a in activas)
        dias_sin_aprender = (
            datetime.now(timezone.utc) - ultima
        ).total_seconds() / 86400.0
        componente_tiempo = min(1.0, dias_sin_aprender / DIAS_SIN_APRENDER_MAXIMO)

        self._sangre.fijar(
            "incertidumbre",
            min(1.0, 0.5 * proporcion_baja + 0.5 * componente_tiempo),
        )

    async def _deuda_desde_preguntas(self) -> None:
        """deuda: cuánto pesa lo que ABEL sabe que no sabe.

        ABEL va a querer preguntar porque le falta una pieza concreta, no
        porque un prompt le dijo que sea curioso. Por eso deuda no se
        empuja desde ningún otro lado: nace exclusivamente de preguntas
        abiertas (nucleo/memoria/preguntas.py) que nadie respondió todavía.
        """
        abiertas = await self._preguntas.abiertas()
        peso_total = sum(p["weight"] for p in abiertas)
        self._sangre.fijar(
            "deuda", min(1.0, peso_total / PREGUNTAS_PARA_SATURAR_DEUDA)
        )
