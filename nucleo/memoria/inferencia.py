"""Regularidades detectadas en lo observado. Consultas y umbrales, nunca el LLM.

El LLM traduce, no concluye (ver docstring de
nucleo/lenguaje/extractor_hechos.py). Mirar 3.000 eventos y sacar una
conclusión sobre un hábito es exactamente el tipo de salto que un modelo de
lenguaje inventa —ya se lo vio inventar cosas que nadie dijo— y del que
después no se puede explicar el origen. Acá la fuente de cada afirmación es
una consulta SQL con un umbral, y eso sí se puede citar.

LAS TRES CONDICIONES

Una regularidad solo se afirma si cumple las tres. Sin esto ABEL infiere
cualquier cosa y llena la memoria de sospechas — y el filtro no puede ser el
modelo de lenguaje: el mismo que infiere no puede juzgar si la inferencia
tiene sentido.

    MINIMO_CASOS   No se infiere un hábito de tres observaciones.
    MINIMO_DIAS    Que cubran un período, no un fin de semana.
    FUERZA_MINIMA  55% es casi azar; hace falta que se note.

Y los contraejemplos se cuentan: no basta con que pase muchas veces, importa
cuántas veces no pasa.

GENERALIZACIÓN CUANDO EL PATRÓN FINO FALLA

Un contraejemplo no invalida la inferencia: la cambia de nivel. Programar 20
veces de noche y 15 de día no refuta "programa mucho" — refuta el horario.
Cuando una regularidad falla en un eje, se prueba el eje de arriba: si "de
noche" no explica los datos, "mucho" sí. Así un contraejemplo es informativo
en vez de solo negativo.

POR QUÉ SE PUEDE INFERIR BASTANTE

Las inferencias nacen bajas (CONFIANZA_INICIAL["inferred"] = 0.35) y decaen
rápido, y compiten por el presupuesto de su predicado. Lo que no se confirma
se cae solo. Es lo contrario de V.0.2: en vez de todo subiendo, todo cae
salvo lo que se sostiene — por eso se puede inferir con generosidad sin
saturar la memoria de sospechas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from nucleo.datos.repositorio import Repositorio
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.preguntas import CAUSAS_CONOCIDAS, Preguntas

logger = logging.getLogger(__name__)

# Sin estas tres condiciones ABEL infiere cualquier cosa y llena la memoria
# de sospechas. El filtro no puede ser el modelo de lenguaje: el mismo que
# infiere no puede juzgar si la inferencia tiene sentido.
MINIMO_CASOS = 15
MINIMO_DIAS = 10
FUERZA_MINIMA = 0.65

# Una regularidad es sobre cómo es alguien ahora, no sobre toda su historia
# con la computadora. Sin este corte, "uso intenso" se calcula contra un
# total que crece para siempre y una aplicación que se dejó de usar hace un
# año sigue pesando en el promedio.
VENTANA_DIAS = 30

# Umbral del nivel "grueso" de uso intenso: ninguna aplicación sola suele
# concentrar la mayoría del tiempo total, así que exigirle FUERZA_MINIMA
# haría que "usa_mucho" casi nunca se afirme. Es deliberadamente más laxo
# que el umbral fino.
FUERZA_MINIMA_USO_INTENSO = 0.30

# Confianza a partir de la cual una inferencia sobre conducta amerita abrir
# una pregunta si nadie explicó la causa. No es CONFIANZA_INICIAL: una
# inferencia recién nacida (0.35) es apenas una sospecha; hace falta que se
# haya sostenido un poco (alguna confirmación repetida, o simplemente que la
# regularidad sea fuerte) antes de que valga la pena marcarla como pendiente.
CONFIANZA_MINIMA_PARA_PREGUNTAR = 0.5

FRANJAS = (
    (0, 6, "madrugada"),
    (6, 12, "manana"),
    (12, 19, "tarde"),
    (19, 24, "noche"),
)

DIAS_SEMANA = (
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"
)


def _franja(hora: int) -> str:
    for inicio, fin, nombre in FRANJAS:
        if inicio <= hora < fin:
            return nombre
    return "noche"


class Inferencia:
    """Recorre lo observado y afirma las regularidades que superan el umbral."""

    def __init__(
        self,
        repositorio: Repositorio,
        afirmaciones: Afirmaciones,
        preguntas: Preguntas | None = None,
    ) -> None:
        self._repo = repositorio
        self._af = afirmaciones
        self._preguntas = preguntas or Preguntas(repositorio)

    async def correr(self) -> int:
        """Corre todas las reglas. Devuelve cuántas afirmaciones tocó."""
        sujeto = await self._sujeto_principal()
        if sujeto is None:
            return 0

        tocadas = 0
        tocadas += await self._franja_y_uso_intenso(sujeto)
        tocadas += await self._ritmo_de_actividad(sujeto)
        return tocadas

    async def _sujeto_principal(self) -> UUID | None:
        # PROVISORIO: se asume un único humano con dispositivo propio, el
        # admin. Cuando haya más de una persona con presencia propia, esto
        # debería diferenciar por actor/dispositivo en vez de asumir un
        # sujeto único. No hay forma de saber a quién pertenece una sesión
        # de ventana todavía.
        usuarios = await self._repo.listar_usuarios()
        return usuarios[0]["id"] if usuarios else None

    # ------------------------------------------------------------------
    # Regla 1 y 2: franja horaria de una app, y uso intenso.
    #
    # Van juntas porque la segunda es la generalización de la primera: se
    # calculan sobre el mismo conjunto de sesiones por aplicación.
    # ------------------------------------------------------------------

    async def _franja_y_uso_intenso(self, sujeto: UUID) -> int:
        desde = datetime.now(timezone.utc) - timedelta(days=VENTANA_DIAS)
        filas = await self._repo.consultar(
            """
            SELECT payload->>'application' AS aplicacion,
                   occurred_at,
                   (payload->>'duration_seconds')::numeric AS segundos
              FROM events
             WHERE event_type = 'window_session'
               AND occurred_at >= %s
            """,
            (desde,),
        )
        if not filas:
            return 0

        por_app: dict[str, list[dict]] = {}
        for f in filas:
            por_app.setdefault(f["aplicacion"], []).append(f)

        total_segundos = sum(float(f["segundos"] or 0) for f in filas)
        tocadas = 0

        for app, sesiones in por_app.items():
            dias = {s["occurred_at"].astimezone().date() for s in sesiones}
            casos = len(sesiones)
            if casos < MINIMO_CASOS or len(dias) < MINIMO_DIAS:
                continue

            conteo_franjas: dict[str, int] = {}
            for s in sesiones:
                franja = _franja(s["occurred_at"].astimezone().hour)
                conteo_franjas[franja] = conteo_franjas.get(franja, 0) + 1

            franja_dominante, en_franja = max(
                conteo_franjas.items(), key=lambda kv: kv[1]
            )
            fuerza_fino = en_franja / casos

            if fuerza_fino >= FUERZA_MINIMA:
                await self._af.afirmar(
                    sujeto,
                    f"usa_de_{franja_dominante}",
                    app,
                    raw_text=(
                        f"{en_franja} de {casos} sesiones de {app} caen en "
                        f"la franja {franja_dominante}"
                    ),
                    source_type="inferred",
                    source_actor_id=sujeto,
                )
                tocadas += 1
                continue

            # El fino no explicó los datos: se prueba el eje de arriba en
            # vez de descartar. Los contraejemplos de horario no dicen nada
            # sobre cuánto se usa la aplicación, solo sobre cuándo.
            if total_segundos <= 0:
                continue
            segundos_app = sum(float(s["segundos"] or 0) for s in sesiones)
            fuerza_grueso = segundos_app / total_segundos

            if fuerza_grueso >= FUERZA_MINIMA_USO_INTENSO:
                aid = await self._af.afirmar(
                    sujeto,
                    "usa_mucho",
                    app,
                    raw_text=(
                        f"{app} concentra {fuerza_grueso:.0%} del tiempo "
                        f"total registrado ({casos} sesiones)"
                    ),
                    source_type="inferred",
                    source_actor_id=sujeto,
                )
                tocadas += 1
                await self._preguntar_causa_si_hace_falta(sujeto, aid, app)

        return tocadas

    # ------------------------------------------------------------------
    # Regla 3: ritmo de actividad — a qué hora/día empieza.
    # ------------------------------------------------------------------

    async def _ritmo_de_actividad(self, sujeto: UUID) -> int:
        desde = datetime.now(timezone.utc) - timedelta(days=VENTANA_DIAS)
        filas = await self._repo.consultar(
            """
            SELECT occurred_at
              FROM events
             WHERE event_type = 'session_state'
               AND payload->>'state' = 'active'
               AND payload->>'previous' = 'idle'
               AND occurred_at >= %s
             ORDER BY occurred_at
            """,
            (desde,),
        )
        if len(filas) < MINIMO_CASOS:
            return 0

        dias = {f["occurred_at"].astimezone().date() for f in filas}
        if len(dias) < MINIMO_DIAS:
            return 0

        conteo_dia: dict[int, int] = {}
        for f in filas:
            dia = f["occurred_at"].astimezone().weekday()
            conteo_dia[dia] = conteo_dia.get(dia, 0) + 1

        total = len(filas)
        dia_dominante, en_dia = max(conteo_dia.items(), key=lambda kv: kv[1])
        fuerza_fino = en_dia / total

        if fuerza_fino >= FUERZA_MINIMA:
            await self._af.afirmar(
                sujeto,
                f"activo_los_{DIAS_SEMANA[dia_dominante]}",
                "true",
                raw_text=(
                    f"{en_dia} de {total} inicios de actividad caen en "
                    f"{DIAS_SEMANA[dia_dominante]}"
                ),
                source_type="inferred",
                source_actor_id=sujeto,
            )
            return 1

        # El día puntual no explica los datos: se prueba entre-semana /
        # fin-de-semana antes de descartar la regularidad entera.
        entre_semana = sum(c for d, c in conteo_dia.items() if d < 5)
        for predicado, en_grupo in (
            ("activo_entre_semana", entre_semana),
            ("activo_fin_de_semana", total - entre_semana),
        ):
            if en_grupo / total >= FUERZA_MINIMA:
                await self._af.afirmar(
                    sujeto,
                    predicado,
                    "true",
                    raw_text=f"{en_grupo} de {total} inicios de actividad en ese grupo",
                    source_type="inferred",
                    source_actor_id=sujeto,
                )
                return 1

        return 0

    # ------------------------------------------------------------------
    # Preguntas abiertas
    # ------------------------------------------------------------------

    async def _preguntar_causa_si_hace_falta(
        self, sujeto: UUID, assertion_id: UUID, app: str
    ) -> None:
        """De 'usa_mucho' no se sigue por qué. Si nadie lo dijo, queda pendiente.

        ABEL va a querer preguntar porque le falta una pieza concreta, no
        porque un prompt le dijo que sea curioso — esa es la diferencia
        entre curiosidad y actuación.
        """
        fila = await self._repo.consultar_una(
            "SELECT confidence FROM assertions WHERE id = %s", (assertion_id,)
        )
        if fila is None or fila["confidence"] < CONFIANZA_MINIMA_PARA_PREGUNTAR:
            return

        tiene_causa = await self._repo.consultar_una(
            """
            SELECT 1 FROM assertions
             WHERE subject_id = %s AND predicate = ANY(%s) AND retired_at IS NULL
             LIMIT 1
            """,
            (sujeto, list(CAUSAS_CONOCIDAS)),
        )
        if tiene_causa is not None:
            return

        await self._preguntas.abrir(
            subject_id=sujeto,
            question=f"¿a qué se dedica que usa tanto {app}?",
            origin_assertion_id=assertion_id,
            weight=fila["confidence"],
        )
