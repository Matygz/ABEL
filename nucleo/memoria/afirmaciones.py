"""Memoria semántica: qué es cierto, no qué pasó.

Un evento tiene fecha porque ocurrió en un momento: "Maty abrió VS Code a
las 23:40". Una afirmación no: "Maty programa de noche" es una regularidad,
no un instante. Es la misma distinción que en una persona — recordar haber
almorzado ayer (episódico) contra saber que París es la capital de Francia
sin recordar cuándo lo aprendiste (semántico).

CASO TESTIGO — por qué se guarda así

Si el usuario dice que su madre tiene 52 años y ella misma dice 53, ABEL no
puede saber quién acierta. Este módulo registra las dos afirmaciones, cada
una con su fuente (afirmar() confirma en vez de sobrescribir solo cuando
sujeto, predicado Y objeto coinciden — objetos distintos quedan como dos
filas). Sobrescribir perdería justamente la información de que hay
desacuerdo; buscar_contradicciones() la deja visible en vez de ocultarla.

Y lo que se guarda es la fecha de nacimiento, no la edad: "52 años" queda
viejo en un año y hay que recalcularlo en todos lados donde se usó. Un
hecho no es una derivación — se guarda lo mínimo de lo que todo lo demás se
puede calcular, no el cálculo.

ADVERTENCIA — lo que pasó en V.0.2

Todos los valores de aquel grafo terminaron cerca de 1 y nunca bajaban:
subir es fácil de programar, bajar hay que diseñarlo aparte y nada lo
dispara, así que no se nota que falta hasta que todo pesa igual — es decir,
nada pesa. Cuatro reglas de este módulo existen específicamente por eso:

1. Todo lo que sube (confirmar, afirmar) tiene su bajada escrita al lado
   (contradecir, decaer). No hay un mecanismo de aumento sin su contrario.
2. El descenso por defecto es el tiempo: decaer() baja lo que hace mucho
   que nadie confirma, sin que haga falta una contradicción explícita.
3. Los aumentos saturan contra el techo (confidence += (1 - confidence) *
   cuanto), igual que la sangre: tres confirmaciones no clavan nada en 1.
4. Las afirmaciones compiten por un presupuesto (presupuesto_reequilibrar):
   sostener algo con fuerza implica soltar otra cosa del mismo predicado.
   Sin esto no hay diferencia entre lo central y lo periférico.

Restricción de diseño: este módulo no le habla a nadie. No llama al ciclo
ni al expresador — el ciclo es quien lee afirmaciones y empuja la sangre,
nunca al revés (ver nucleo/ciclo.py).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from comun.errores import ErrorOperativo
from nucleo.datos.repositorio import Repositorio

logger = logging.getLogger(__name__)


class ErrorAfirmaciones(ErrorOperativo):
    """Se pidió operar sobre una afirmación que no existe."""


# Confianza con la que nace una afirmación, según de dónde vino.
CONFIANZA_INICIAL = {
    "told": 0.75,      # Lo dijo alguien. Alto, pero no certeza:
                        # las personas se equivocan y cambian.
    "observed": 0.85,  # Lo vio ABEL. Alto porque es directo, no 1.0
                        # porque una observación puede interpretarse mal.
    "inferred": 0.35,  # Lo dedujo. Bajo a propósito: una inferencia
                        # sin confirmar es una sospecha.
}

# Cuánto sube una afirmación que se repite en vez de duplicarse. Menor que
# una confirmación explícita: que alguien vuelva a decir lo mismo pesa,
# pero no tanto como una confirmación deliberada (regla 3: saturar, no
# clavar).
CONFIRMACION_REPETIDA = 0.3

# Por debajo de esto una afirmación se retira: sostenerla activa ya no
# aporta. No es cero — cero significaría que no queda rastro, y sí queda
# (retired_at no borra).
PISO_RETIRO = 0.15

# Días sin confirmar antes de que decaer() empiece a tocar una afirmación.
# Confirmar no es solo el llamado explícito: sobre() y las consultas del
# día a día no cuentan como confirmación — solo confirmar()/afirmar() sí.
UMBRAL_DECAIMIENTO_DIAS = {
    "told": 14.0,
    "observed": 14.0,
    "inferred": 2.0,   # una sospecha sin confirmar envejece rápido
}

# Tiempo en que, pasado el umbral, una afirmación recorre la mitad del
# camino hacia su piso de decaimiento. Más chico, más volátil.
VIDA_MEDIA_DECAIMIENTO_DIAS = {
    "told": 60.0,
    "observed": 90.0,
    "inferred": 7.0,
}

# Hacia dónde decae, no hasta dónde. told/observed nunca llegan a un nivel
# que las retire solas (PISO_RETIRO = 0.15): un hecho que alguien dijo no
# se vuelve falso por el tiempo, solo menos vigente. Una inferencia sí
# puede decaer por debajo del piso y retirarse: una sospecha vieja sin
# confirmar deja de sostenerse.
PISO_DECAIMIENTO = {
    "told": 0.3,
    "observed": 0.3,
    "inferred": 0.05,
}

# Suma máxima de confianza entre las afirmaciones activas de un mismo
# sujeto y predicado. Ver presupuesto_reequilibrar().
PRESUPUESTO_POR_PREDICADO = 1.5

# Predicados donde varios valores simultáneos son legítimos (alguien puede
# trabajar en más de un lugar). Todo lo que no está acá se trata como de
# valor único: dos afirmaciones con objetos distintos son una
# contradicción. Hardcodeado a propósito — más adelante debería
# aprenderse de los datos en vez de mantenerse a mano acá.
PREDICADOS_MULTIPLES = {
    "trabaja_en",
    "vive_en",
    "le_gusta",
    "estudia",
    "tiene",
    # De la inferencia sobre conducta (nucleo/memoria/inferencia.py): cada
    # fila es sobre una aplicación distinta, así que varias activas a la vez
    # con el mismo predicado son normales, no una contradicción.
    "usa_mucho",
    "usa_de_manana",
    "usa_de_tarde",
    "usa_de_noche",
    "usa_de_madrugada",
}


class Afirmaciones:
    """Lo que ABEL cree: registrarlo, sostenerlo, y dejar que se desvanezca."""

    def __init__(self, repositorio: Repositorio) -> None:
        self._repo = repositorio

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    async def afirmar(
        self,
        subject_id: UUID,
        predicate: str,
        object_text: str,
        raw_text: str,
        source_type: str,
        source_actor_id: UUID,
        object_actor_id: UUID | None = None,
        source_event_id: UUID | None = None,
    ) -> UUID:
        """Registra algo nuevo. Si ya existe igual, lo confirma en vez de duplicar.

        "Igual" es mismo sujeto, predicado Y objeto. Si el objeto difiere
        (45 contra 46), son dos afirmaciones distintas: sobrescribir
        perdería la contradicción, que es información (ver docstring del
        módulo).
        """
        existente = await self._repo.consultar_una(
            """
            SELECT id FROM assertions
             WHERE subject_id = %s AND predicate = %s AND object_text = %s
               AND retired_at IS NULL
            """,
            (subject_id, predicate, object_text),
        )
        if existente is not None:
            await self.confirmar(
                existente["id"], CONFIRMACION_REPETIDA, "se volvió a afirmar lo mismo"
            )
            return existente["id"]

        confianza = CONFIANZA_INICIAL[source_type]
        filas = await self._repo.ejecutar(
            """
            INSERT INTO assertions
                (subject_id, predicate, object_text, object_actor_id,
                 raw_text, confidence, source_type, source_actor_id,
                 source_event_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                subject_id, predicate, object_text, object_actor_id,
                raw_text, confianza, source_type, source_actor_id,
                source_event_id,
            ),
        )
        assertion_id = filas[0]["id"]

        await self._registrar_cambio(
            assertion_id, "created", confianza, confianza, "afirmación nueva"
        )
        await self.presupuesto_reequilibrar(subject_id, predicate)
        if predicate == "se_llama":
            await self._sincronizar_nombre(subject_id)
        return assertion_id

    async def confirmar(self, assertion_id: UUID, cuanto: float, motivo: str) -> float:
        """Sube la confianza, saturando contra el techo (regla 3).

        Si la afirmación estaba retirada y la confianza vuelve a superar el
        piso, revive sola: no hace falta un revivir() aparte para el caso
        más común, que es "confirmaron de nuevo algo que se había dejado
        de sostener".
        """
        fila = await self._repo.consultar_una(
            "SELECT subject_id, predicate, confidence, retired_at "
            "FROM assertions WHERE id = %s",
            (assertion_id,),
        )
        if fila is None:
            raise ErrorAfirmaciones(f"No existe la afirmación {assertion_id}.")

        vieja = fila["confidence"]
        nueva = max(0.0, min(1.0, vieja + (1.0 - vieja) * cuanto))

        await self._repo.ejecutar(
            """
            UPDATE assertions
               SET confidence = %s, updated_at = now(), confirmed_at = now()
             WHERE id = %s
            """,
            (nueva, assertion_id),
        )
        await self._registrar_cambio(assertion_id, "confirmed", nueva - vieja, nueva, motivo)

        if fila["retired_at"] is not None and nueva > PISO_RETIRO:
            await self._revivir_interno(assertion_id, nueva, "recuperó confianza al confirmarse")

        await self.presupuesto_reequilibrar(fila["subject_id"], fila["predicate"])
        if fila["predicate"] == "se_llama":
            await self._sincronizar_nombre(fila["subject_id"])
        return nueva

    async def contradecir(self, assertion_id: UUID, cuanto: float, motivo: str) -> float:
        """Baja la confianza. Por debajo del piso, retira (regla 1: espejo de confirmar)."""
        fila = await self._repo.consultar_una(
            "SELECT subject_id, predicate, confidence FROM assertions "
            "WHERE id = %s AND retired_at IS NULL",
            (assertion_id,),
        )
        if fila is None:
            raise ErrorAfirmaciones(
                f"No existe (o ya está retirada) la afirmación {assertion_id}."
            )

        vieja = fila["confidence"]
        nueva = max(0.0, vieja - vieja * cuanto)

        await self._repo.ejecutar(
            "UPDATE assertions SET confidence = %s, updated_at = now() WHERE id = %s",
            (nueva, assertion_id),
        )
        await self._registrar_cambio(assertion_id, "contradicted", nueva - vieja, nueva, motivo)

        if nueva < PISO_RETIRO:
            await self.retirar(
                assertion_id, f"confianza bajo el piso tras contradicción ({motivo})"
            )

        if fila["predicate"] == "se_llama":
            await self._sincronizar_nombre(fila["subject_id"])
        return nueva

    async def decaer(self) -> int:
        """Baja la confianza de lo que hace mucho no se confirma (regla 2).

        Es el descenso por defecto: no hace falta que algo contradiga una
        afirmación, basta con que nadie la sostenga. Devuelve cuántas se
        tocaron.
        """
        ahora = datetime.now(timezone.utc)
        filas = await self._repo.consultar(
            """
            SELECT id, subject_id, predicate, confidence, source_type,
                   COALESCE(confirmed_at, created_at) AS referencia
              FROM assertions
             WHERE retired_at IS NULL
            """
        )

        tocadas = 0
        for fila in filas:
            tipo = fila["source_type"]
            umbral = UMBRAL_DECAIMIENTO_DIAS[tipo]
            dias = (ahora - fila["referencia"]).total_seconds() / 86400.0
            if dias <= umbral:
                continue

            piso = PISO_DECAIMIENTO[tipo]
            vida_media = VIDA_MEDIA_DECAIMIENTO_DIAS[tipo]
            factor = 0.5 ** ((dias - umbral) / vida_media)
            vieja = fila["confidence"]
            nueva = piso + (vieja - piso) * factor
            if nueva >= vieja:
                continue

            await self._repo.ejecutar(
                "UPDATE assertions SET confidence = %s, updated_at = now() WHERE id = %s",
                (nueva, fila["id"]),
            )
            await self._registrar_cambio(
                fila["id"], "decayed", nueva - vieja, nueva,
                f"{dias:.0f} días sin confirmarse",
            )
            tocadas += 1

            if nueva < PISO_RETIRO:
                await self.retirar(fila["id"], "confianza bajo el piso por decaimiento")

        return tocadas

    async def retirar(self, assertion_id: UUID, motivo: str) -> None:
        """Marca retired_at. No borra: la historia queda (ver docstring del módulo)."""
        fila = await self._repo.consultar_una(
            "SELECT subject_id, predicate, confidence FROM assertions "
            "WHERE id = %s AND retired_at IS NULL",
            (assertion_id,),
        )
        if fila is None:
            return  # ya retirada, o no existe: retirar es idempotente

        await self._repo.ejecutar(
            "UPDATE assertions SET retired_at = now(), updated_at = now() WHERE id = %s",
            (assertion_id,),
        )
        await self._registrar_cambio(assertion_id, "retired", 0.0, fila["confidence"], motivo)
        if fila["predicate"] == "se_llama":
            await self._sincronizar_nombre(fila["subject_id"])

    async def revivir(self, assertion_id: UUID, motivo: str) -> bool:
        """Limpia retired_at si la confianza volvió a subir. Devuelve si revivió."""
        fila = await self._repo.consultar_una(
            "SELECT subject_id, predicate, confidence, retired_at "
            "FROM assertions WHERE id = %s",
            (assertion_id,),
        )
        if fila is None or fila["retired_at"] is None or fila["confidence"] <= PISO_RETIRO:
            return False

        await self._revivir_interno(assertion_id, fila["confidence"], motivo)
        await self.presupuesto_reequilibrar(fila["subject_id"], fila["predicate"])
        if fila["predicate"] == "se_llama":
            await self._sincronizar_nombre(fila["subject_id"])
        return True

    async def _revivir_interno(self, assertion_id: UUID, confidence: float, motivo: str) -> None:
        await self._repo.ejecutar(
            "UPDATE assertions SET retired_at = NULL, updated_at = now() WHERE id = %s",
            (assertion_id,),
        )
        await self._registrar_cambio(assertion_id, "revived", 0.0, confidence, motivo)

    async def presupuesto_reequilibrar(self, subject_id: UUID, predicate: str) -> None:
        # Sostener algo con fuerza implica soltar otra cosa. Sin esto todas las
        # afirmaciones tienden a 1 y el modelo deja de tener forma: no hay
        # diferencia entre lo central y lo periférico.
        #
        # Solo aplica dentro de un mismo predicado: creer mucho sobre dónde
        # trabaja alguien no debería debilitar lo que se sabe de su nombre.
        filas = await self._repo.consultar(
            """
            SELECT id, confidence FROM assertions
             WHERE subject_id = %s AND predicate = %s AND retired_at IS NULL
            """,
            (subject_id, predicate),
        )
        if not filas:
            return

        total = sum(f["confidence"] for f in filas)
        if total <= PRESUPUESTO_POR_PREDICADO:
            return

        # No se registra en assertion_events: es un efecto de contabilidad
        # del cambio que lo disparó (confirmar/afirmar/revivir), no una
        # creencia nueva que cambió por sí misma.
        factor = PRESUPUESTO_POR_PREDICADO / total
        for fila in filas:
            nueva = fila["confidence"] * factor
            await self._repo.ejecutar(
                "UPDATE assertions SET confidence = %s, updated_at = now() WHERE id = %s",
                (nueva, fila["id"]),
            )

    async def _sincronizar_nombre(self, subject_id: UUID) -> None:
        """El nombre visible de una persona sigue a lo que ABEL cree.

        `actors.name` es la etiqueta operativa y la afirmación `se_llama` es
        la creencia. Si no se sincronizan, quedan contradiciéndose: se vio a
        alguien llamado "Elena" con una afirmación activa que decía que se
        llamaba Marta.

        Se trata como vista materializada: se recalcula acá y en ningún otro
        lado, para que no haya dos caminos que puedan desfasarse.

        Solo se toca a las personas. Los usuarios y el sistema tienen nombre
        propio que no depende de lo que ABEL crea.
        """
        actor = await self._repo.consultar_una(
            "SELECT actor_type, name FROM actors WHERE id = %s", (subject_id,)
        )
        if actor is None or actor["actor_type"] != "person":
            return

        activa = await self._repo.consultar_una(
            """
            SELECT object_text FROM assertions
             WHERE subject_id = %s AND predicate = 'se_llama' AND retired_at IS NULL
             ORDER BY confidence DESC LIMIT 1
            """,
            (subject_id,),
        )
        # Si no queda ninguna activa (todas retiradas), no se toca el
        # nombre: es preferible conservar la última etiqueta conocida a
        # dejar a alguien sin nombre.
        if activa is None or activa["object_text"] == actor["name"]:
            return

        await self._repo.ejecutar(
            "UPDATE actors SET name = %s WHERE id = %s",
            (activa["object_text"], subject_id),
        )

    async def _registrar_cambio(
        self, assertion_id: UUID, kind: str, delta: float, confidence_after: float, reason: str
    ) -> None:
        await self._repo.ejecutar(
            """
            INSERT INTO assertion_events
                (assertion_id, kind, delta, confidence_after, reason)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (assertion_id, kind, delta, confidence_after, reason),
        )

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    async def sobre(self, subject_id: UUID) -> list[dict[str, Any]]:
        """Todo lo que ABEL cree sobre alguien, por confianza, sin lo retirado."""
        return await self._repo.consultar(
            """
            SELECT id, predicate, object_text, object_actor_id, raw_text,
                   confidence, source_type, source_actor_id, source_event_id,
                   created_at, updated_at, confirmed_at
              FROM assertions
             WHERE subject_id = %s AND retired_at IS NULL
             ORDER BY confidence DESC
            """,
            (subject_id,),
        )

    async def buscar_contradicciones(self, subject_id: UUID) -> list[dict[str, Any]]:
        """Mismo sujeto y predicado, objeto distinto, ambas por encima del piso.

        No toda discrepancia es contradicción: trabaja_en puede tener varios
        valores legítimos (ver PREDICADOS_MULTIPLES). fecha_nacimiento no.
        """
        filas = await self._repo.consultar(
            """
            SELECT id, predicate, object_text, confidence
              FROM assertions
             WHERE subject_id = %s AND retired_at IS NULL
             ORDER BY predicate
            """,
            (subject_id,),
        )

        por_predicado: dict[str, list[dict[str, Any]]] = {}
        for fila in filas:
            if fila["predicate"] in PREDICADOS_MULTIPLES:
                continue
            por_predicado.setdefault(fila["predicate"], []).append(fila)

        contradicciones = []
        for predicado, grupo in por_predicado.items():
            if len({f["object_text"] for f in grupo}) > 1:
                contradicciones.append({"predicate": predicado, "afirmaciones": grupo})
        return contradicciones

    async def todas(self, incluir_retiradas: bool = False) -> list[dict[str, Any]]:
        """Todas las afirmaciones con el nombre del sujeto. Para scripts.creencias."""
        condicion = "" if incluir_retiradas else "WHERE a.retired_at IS NULL"
        return await self._repo.consultar(
            f"""
            SELECT a.id, s.name AS sujeto, a.predicate, a.object_text,
                   a.confidence, a.source_type, a.confirmed_at, a.created_at,
                   a.retired_at
              FROM assertions a
              JOIN actors s ON s.id = a.subject_id
              {condicion}
             ORDER BY s.name, a.confidence DESC
            """
        )

    async def historial(self, assertion_id: UUID) -> list[dict[str, Any]]:
        """Por qué cambió la confianza de una afirmación, en orden."""
        return await self._repo.consultar(
            """
            SELECT kind, delta, confidence_after, occurred_at, reason
              FROM assertion_events
             WHERE assertion_id = %s
             ORDER BY occurred_at
            """,
            (assertion_id,),
        )
