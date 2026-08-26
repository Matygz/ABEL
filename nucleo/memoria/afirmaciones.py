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
from nucleo.memoria.relaciones import INVERSAS, SIMETRICAS, equivalentes_de, normalizar

# Dentro de un grupo de equivalentes (ver relaciones.EQUIVALENTES), cuál es
# el genérico que cede ante uno específico si las dos terminan apuntando al
# mismo par de personas. Solo padre_de lo es: es el destino de hijo_de
# cuando no se sabe el género del progenitor (ver relaciones.INVERSAS). Los
# demás grupos no tienen un miembro genérico — ahí gana la que ya estaba,
# sin más, como en cualquier otro afirmar repetido.
GENERICOS = frozenset({"padre_de"})

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

# Vínculos que solo pueden apuntar a una persona. Los que no están acá
# —hermano_de, amigo_de, conoce_a— admiten varios y dos objetos distintos
# no son un duplicado, son dos personas.
#
# Es una lista y no una regla porque el criterio es del mundo, no del
# sistema: más adelante debería salir del propio catálogo de predicados.
VINCULOS_UNICOS = frozenset({
    "padre_de", "madre_de", "esposo_de", "esposa_de",
})

# Saltos máximos al seguir una cadena de merged_into. No debería hacer
# falta más de uno o dos, pero una fusión mal hecha podría dejar dos
# personas apuntándose entre sí — esto corta en vez de colgar el sistema.
LIMITE_SALTOS_FUSION = 20


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
        subject_id = await self.resolver(subject_id)

        # Cuando el objeto es un actor, dos afirmaciones son la misma si
        # apuntan al mismo actor aunque el texto difiera: "mi papá" y
        # "Julio" son la misma persona y el vínculo es uno solo. Sin
        # esto quedaban dos padre_de activos apuntando al mismo padre.
        if object_actor_id is not None:
            object_actor_id = await self.resolver(object_actor_id)

            # Una relación se guarda siempre en la misma dirección, sin
            # importar cómo se dijo. Si no, "soy hijo de Julio" y
            # "Julio es mi papá" entran como dos afirmaciones distintas
            # y ninguna consulta las junta (ver nucleo/memoria/relaciones.py).
            nuevo_subject_id, predicate, object_actor_id = normalizar(
                subject_id, predicate, object_actor_id
            )
            if nuevo_subject_id != subject_id:
                # Se invirtieron sujeto y objeto: el texto que se había
                # dicho ("Julio") describía a quien ahora es sujeto, no
                # al nuevo objeto. Se recalcula desde el nombre actual en
                # vez de dejar una etiqueta que ya no describe a nadie.
                actor_objeto = await self._repo.consultar_una(
                    "SELECT name FROM actors WHERE id = %s", (object_actor_id,)
                )
                if actor_objeto is not None:
                    object_text = actor_objeto["name"]
                subject_id = nuevo_subject_id

            equivalentes = equivalentes_de(predicate)
            if len(equivalentes) > 1:
                # Puede haber otra fila que diga el mismo vínculo con un
                # predicado equivalente (padre_de/madre_de, hermano_de/
                # hermana_de, esposo_de/esposa_de) sobre el mismo par de
                # personas: es la misma relación contada de otra forma, no
                # una nueva (ver nucleo/memoria/relaciones.py).
                conflicto = await self._repo.consultar_una(
                    """
                    SELECT id, predicate FROM assertions
                     WHERE subject_id = %s AND predicate = ANY(%s)
                       AND object_actor_id = %s AND retired_at IS NULL
                    """,
                    (subject_id, list(equivalentes), object_actor_id),
                )
                if conflicto is not None and conflicto["predicate"] != predicate:
                    if predicate in GENERICOS and conflicto["predicate"] not in GENERICOS:
                        # Lo nuevo es el genérico y ya había algo más
                        # específico: se confirma lo específico y no se
                        # toca su predicado.
                        await self.confirmar(
                            conflicto["id"], CONFIRMACION_REPETIDA,
                            "se volvió a afirmar el mismo vínculo, de forma más genérica",
                        )
                        return conflicto["id"]
                    if conflicto["predicate"] in GENERICOS and predicate not in GENERICOS:
                        # Lo nuevo es más específico que lo que había: gana
                        # lo nuevo. Se retira el genérico —con su historia,
                        # como cualquier retiro— y sigue el flujo normal,
                        # que va a crear la fila específica.
                        await self.retirar(
                            conflicto["id"],
                            f"reemplazada por una forma más específica del mismo vínculo ({predicate})",
                        )
                    else:
                        # Ninguna es más genérica que la otra: gana la que
                        # ya estaba, igual que un afirmar repetido normal.
                        await self.confirmar(
                            conflicto["id"], CONFIRMACION_REPETIDA,
                            "se volvió a afirmar el mismo vínculo, de otra forma",
                        )
                        return conflicto["id"]

            existente = await self._repo.consultar_una(
                """
                SELECT id FROM assertions
                 WHERE subject_id = %s AND predicate = %s
                   AND object_actor_id = %s AND retired_at IS NULL
                """,
                (subject_id, predicate, object_actor_id),
            )
        else:
            existente = await self._repo.consultar_una(
                """
                SELECT id FROM assertions
                 WHERE subject_id = %s AND predicate = %s AND object_text = %s
                   AND object_actor_id IS NULL AND retired_at IS NULL
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

    async def resolver(self, actor_id: UUID) -> UUID:
        """Sigue merged_into hasta la persona real. Sin persons, no hay nada que seguir.

        Cortada contra ciclos (LIMITE_SALTOS_FUSION): una fusión mal hecha
        podría dejar dos personas apuntándose entre sí, y sin este límite
        eso cuelga cualquier consulta en vez de fallar visiblemente.
        """
        vistos = {actor_id}
        actual = actor_id
        for _ in range(LIMITE_SALTOS_FUSION):
            fila = await self._repo.consultar_una(
                "SELECT merged_into FROM persons WHERE id = %s", (actual,)
            )
            if fila is None or fila["merged_into"] is None:
                return actual
            siguiente = fila["merged_into"]
            if siguiente in vistos:
                logger.error(
                    "Ciclo de fusión detectado siguiendo %s; se corta en %s",
                    actor_id, actual,
                )
                return actual
            vistos.add(siguiente)
            actual = siguiente

        logger.error(
            "Cadena de fusión de %s superó %d saltos; se corta en %s",
            actor_id, LIMITE_SALTOS_FUSION, actual,
        )
        return actual

    async def fusionar(self, duplicada_id: UUID, real_id: UUID, motivo: str) -> None:
        """Marca a duplicada_id como la misma persona que real_id.

        No se borra nada (regla del módulo, ver docstring de arriba): la
        duplicada queda con merged_into apuntando a la real, y sus
        afirmaciones se reapuntan — no se copian, para que la historia de
        cada una no quede partida entre dos sujetos.

        Idempotente: fusionar una persona ya fusionada no hace nada.
        """
        if duplicada_id == real_id:
            return

        real_id = await self.resolver(real_id)
        if duplicada_id == real_id:
            return

        fila = await self._repo.consultar_una(
            "SELECT merged_into FROM persons WHERE id = %s", (duplicada_id,)
        )
        if fila is None or fila["merged_into"] is not None:
            return

        await self._repo.ejecutar(
            """
            UPDATE persons SET merged_into = %s, merged_at = now(), merged_reason = %s
             WHERE id = %s
            """,
            (real_id, motivo, duplicada_id),
        )

        # Reapuntar, no copiar: tanto lo que la duplicada afirmaba (subject_id)
        # como lo que otras afirmaciones decían sobre ella (object_actor_id).
        await self._repo.ejecutar(
            "UPDATE assertions SET subject_id = %s, updated_at = now() WHERE subject_id = %s",
            (real_id, duplicada_id),
        )
        await self._repo.ejecutar(
            "UPDATE assertions SET object_actor_id = %s, updated_at = now() "
            "WHERE object_actor_id = %s",
            (real_id, duplicada_id),
        )

        await self._fusionar_equivalentes(real_id)
        await self._sincronizar_nombre(real_id)

        await self._repo.registrar_evento(
            event_type="persons_merged",
            actor_id=real_id,
            payload={
                "duplicada_id": str(duplicada_id),
                "real_id": str(real_id),
                "motivo": motivo,
            },
        )

    async def _fusionar_equivalentes(self, subject_id: UUID) -> None:
        """Tras reapuntar, dos afirmaciones pueden haber quedado diciendo lo mismo.

        Mismo sujeto, predicado y objeto, ambas activas: en vez de sostener
        dos filas iguales, se confirma la de mayor confianza (regla 3: sube
        saturando, no se clava) y la otra se retira — con su historia, como
        cualquier retiro.
        """
        grupos = await self._repo.consultar(
            """
            SELECT array_agg(id ORDER BY confidence DESC) AS ids
              FROM assertions
             WHERE subject_id = %s AND retired_at IS NULL
             GROUP BY predicate, object_text
            HAVING count(*) > 1
            """,
            (subject_id,),
        )
        for grupo in grupos:
            ids = grupo["ids"]
            await self.confirmar(
                ids[0], CONFIRMACION_REPETIDA, "fusión: ya se sostenía en la persona real"
            )
            for otro in ids[1:]:
                await self.retirar(
                    otro, "fusión: quedó duplicada con una afirmación equivalente"
                )

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
        """Todo lo que ABEL cree sobre alguien, por confianza, sin lo retirado.

        Con la canónica `Julio / padre_de / Maty`, la afirmación está
        guardada sobre Julio. Consultar "qué sé de Maty" solo por
        subject_id no la traería — y eso sería peor que el problema
        original (ver nucleo/memoria/relaciones.py). Se guarda una vez y se
        lee desde los dos lados: duplicar la fila invertida sería más
        rápido de consultar, pero una fuente permanente de
        desincronización, porque dos filas que dicen lo mismo pueden
        divergir con el tiempo.

        Las que vienen de leer desde el otro lado quedan marcadas con
        "derivada": True, para que quien las use sepa que no son filas
        propias — importa al editar o corregir (esa operación tiene que
        apuntar a la fila real, no a la lectura invertida).
        """
        subject_id = await self.resolver(subject_id)

        propias = await self._repo.consultar(
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
        for fila in propias:
            fila["derivada"] = False

        derivadas_crudas = await self._repo.consultar(
            """
            SELECT a.id, a.predicate, s.name AS object_text, a.subject_id AS object_actor_id,
                   a.raw_text, a.confidence, a.source_type, a.source_actor_id,
                   a.source_event_id, a.created_at, a.updated_at, a.confirmed_at
              FROM assertions a
              JOIN actors s ON s.id = a.subject_id
             WHERE a.object_actor_id = %s AND a.retired_at IS NULL
             ORDER BY a.confidence DESC
            """,
            (subject_id,),
        )

        derivadas = []
        for fila in derivadas_crudas:
            if fila["predicate"] in SIMETRICAS:
                predicado_derivado = fila["predicate"]
            else:
                predicado_derivado = INVERSAS.get(fila["predicate"])
                if predicado_derivado is None:
                    # Fuera del catálogo: no se sabe cómo se llama la
                    # relación desde este lado, así que no se inventa.
                    continue
            fila["predicate"] = predicado_derivado
            fila["derivada"] = True
            derivadas.append(fila)

        return sorted(propias + derivadas, key=lambda f: f["confidence"], reverse=True)

    async def buscar_contradicciones(self, subject_id: UUID) -> list[dict[str, Any]]:
        """Mismo sujeto y predicado (o equivalente), objeto distinto, sobre el piso.

        No toda discrepancia es contradicción: trabaja_en puede tener varios
        valores legítimos (ver PREDICADOS_MULTIPLES). fecha_nacimiento no.

        Se agrupa por conjunto de equivalentes, no por predicado exacto:
        padre_de y madre_de con el mismo objeto son el mismo rol dicho de
        otra forma (ver nucleo/memoria/relaciones.py), no dos hechos que se
        contradicen. afirmar() ya evita que las dos queden activas a la
        vez, pero agrupar así igual, en vez de confiar en que nunca haya
        una excepción — un dato viejo, una fila tocada a mano.
        """
        subject_id = await self.resolver(subject_id)
        filas = await self._repo.consultar(
            """
            SELECT id, predicate, object_text, confidence
              FROM assertions
             WHERE subject_id = %s AND retired_at IS NULL
             ORDER BY predicate
            """,
            (subject_id,),
        )

        por_grupo: dict[frozenset[str], list[dict[str, Any]]] = {}
        for fila in filas:
            if fila["predicate"] in PREDICADOS_MULTIPLES:
                continue
            clave = equivalentes_de(fila["predicate"])
            por_grupo.setdefault(clave, []).append(fila)

        contradicciones = []
        for grupo_predicados, grupo in por_grupo.items():
            if len({f["object_text"] for f in grupo}) > 1:
                # El nombre que se muestra es el del predicado más
                # frecuente en el grupo — a efectos de reportar, alcanza
                # con cualquiera de los equivalentes.
                contradicciones.append({
                    "predicate": grupo[0]["predicate"], "afirmaciones": grupo,
                })
        return contradicciones

    async def buscar_duplicados_por_vinculo(self, subject_id: UUID) -> list[dict[str, Any]]:
        """Dos o más afirmaciones activas de un vínculo único con objetos distintos.

        Se compara por object_actor_id, no por object_text: dos etiquetas
        de texto distintas para el mismo actor ("mi papa" y "Julio") no
        son dos personas, son un nombre sin sincronizar todavía (ver
        _sincronizar_nombre). Dos actores distintos sí lo son.
        """
        subject_id = await self.resolver(subject_id)
        filas = await self._repo.consultar(
            """
            SELECT id, predicate, object_text, object_actor_id, confidence
              FROM assertions
             WHERE subject_id = %s AND retired_at IS NULL
               AND predicate = ANY(%s)
             ORDER BY predicate, confidence DESC
            """,
            (subject_id, list(VINCULOS_UNICOS)),
        )

        por_predicado: dict[str, list[dict[str, Any]]] = {}
        for fila in filas:
            por_predicado.setdefault(fila["predicate"], []).append(fila)

        duplicados = []
        for predicado, grupo in por_predicado.items():
            actores = {f["object_actor_id"] for f in grupo if f["object_actor_id"] is not None}
            if len(actores) > 1:
                duplicados.append({"predicate": predicado, "afirmaciones": grupo})
        return duplicados

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
