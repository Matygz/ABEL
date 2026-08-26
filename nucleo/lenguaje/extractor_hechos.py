"""De una frase contada a una o más afirmaciones estructuradas.

EL PRINCIPIO QUE ORDENA ESTE MÓDULO: el LLM traduce, no concluye.

    "Mi vieja se llama Elena" → estructura      El LLM
    Mirar 3.000 eventos y sacar conclusiones     Nunca el LLM
    Detectar regularidades en los datos          Consultas SQL con umbrales
                                                  (ver nucleo/memoria/inferencia.py)

Si el LLM concluye desde datos crudos, inventa —ya se lo vio inventar una
ensalada de quinoa que nadie mencionó— y no hay forma de saber por qué
concluyó eso. Contradice el principio 7: si ABEL afirma algo, debe poder
citar su fuente.

Acá la conclusión ya estaba en la frase de la persona: el modelo solo la
pasa a formato. Eso es lenguaje puro, y es su trabajo. El prompt es corto y
sin ejemplos de clasificación a propósito — un modelo chico tiende a
completar los ejemplos del prompt en vez de responder a lo que se le pidió
(ya pasó con el analizador de intenciones).
"""

from __future__ import annotations

import logging
import unicodedata
from uuid import UUID

from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.preguntas import Preguntas

logger = logging.getLogger(__name__)

INSTRUCCIONES = """\
Extraé los hechos del mensaje. Devolvé JSON:
{"hechos": [
  {"sujeto": "quién", "predicado": "qué se afirma", "objeto": "el valor"}
]}

- "sujeto" es de quién es el hecho, no quién escribe. Si no se nombra a
  nadie más, el sujeto es "yo".
- "predicado" describe la relación en una o dos palabras con guión bajo:
  se_llama, trabaja_en, vive_en, estudia, le_gusta, tiene.
- Si el mensaje habla de otra persona por su vínculo ("mi vieja",
  "mi hermano", "mi jefe"), devolvé DOS hechos: uno con el vínculo (el
  sujeto sos "yo", el predicado es el vínculo — madre_de, hermano_de,
  jefe_de — y el objeto es esa persona) y otro con lo que se cuenta de esa
  persona (el sujeto es esa persona). Si el mensaje da su nombre, usá el
  nombre como objeto del vínculo y como sujeto del segundo hecho. Si no da
  el nombre, usá el vínculo tal cual ("mi hermano") en los dos lugares.
  Ejemplo con nombre — "mi vieja se llama Marta":
  {"sujeto": "yo", "predicado": "madre_de", "objeto": "Marta"}
  {"sujeto": "Marta", "predicado": "se_llama", "objeto": "Marta"}
  Ejemplo sin nombre — "mi hermano vive en Mendoza":
  {"sujeto": "yo", "predicado": "hermano_de", "objeto": "mi hermano"}
  {"sujeto": "mi hermano", "predicado": "vive_en", "objeto": "Mendoza"}
- Un posesivo ("su taller", "su hijo") solo tiene sentido si el mensaje
  ya dijo de quién es. Resolvelo contra eso: en "trabajo con mi papá, en
  su empresa", "su taller" es "el taller de mi papá". Si no podés
  resolverlo con lo que dice el mensaje, no inventes a quién se refiere:
  omití ese hecho entero. Es mejor no registrar nada que registrar algo
  ambiguo.
- Un posesivo se resuelve contra la persona mencionada en el mismo mensaje:
  "trabajo con mi papá, en su taller" →
  {"sujeto": "yo", "predicado": "padre_de", "objeto": "mi papá"}
  {"sujeto": "yo", "predicado": "trabaja_en", "objeto": "taller de mi papá"}
    Nunca dejes un posesivo sin resolver: "su taller" a secas no significa
    nada. Si no hay a quién referirlo, omití el hecho.
- Si el mensaje no afirma ningún hecho, devolvé {"hechos": []}.
- No inventes nada que no esté en el mensaje.
"""

TEMPERATURA = 0.1

# Predicados de vínculo: el objeto de estos hechos no es un dato suelto,
# es otra persona. El prompt le pide al modelo dos hechos por vínculo (uno
# con este predicado, sujeto=hablante y objeto=la persona nombrada o el
# vínculo tal cual si no hay nombre) — acá solo se usa la lista para saber
# cuándo el objeto hay que resolverlo a un actor en vez de guardarlo como
# texto suelto.
PREDICADOS_DE_VINCULO = {
    "madre_de", "padre_de", "hermano_de", "hermana_de", "pareja_de",
    "jefe_de", "jefa_de", "amigo_de", "amiga_de",
}


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def _normalizar(texto: str) -> str:
    return _sin_acentos(texto.strip().lower())


def _normalizar_predicado(texto: str) -> str:
    return _normalizar(texto).replace(" ", "_")


def _valido(hecho: object) -> bool:
    """Descarta hechos sin los tres campos o con campos vacíos."""
    if not isinstance(hecho, dict):
        return False
    return all(
        isinstance(hecho.get(campo), str) and hecho[campo].strip()
        for campo in ("sujeto", "predicado", "objeto")
    )


class ExtractorHechos:
    """Traduce mensajes a afirmaciones. No decide si algo es cierto, solo lo registra."""

    def __init__(
        self,
        motor: MotorLenguaje,
        afirmaciones: Afirmaciones,
        preguntas: Preguntas,
        repositorio: Repositorio,
    ) -> None:
        self._motor = motor
        self._af = afirmaciones
        self._preguntas = preguntas
        self._repo = repositorio

    async def extraer_y_registrar(
        self, mensaje: str, hablante_id: UUID, event_id: UUID | None
    ) -> list[UUID]:
        """Extrae los hechos de un mensaje y los registra. Devuelve sus ids."""
        try:
            datos = await self._motor.generar_json(
                INSTRUCCIONES, mensaje, temperatura=TEMPERATURA
            )
        except ErrorLenguaje as exc:
            logger.warning("No se pudo extraer hechos de %r: %s", mensaje, exc)
            return []

        hechos = datos.get("hechos")
        if not isinstance(hechos, list) or not hechos:
            return []

        # Cache por mensaje: si el mismo vínculo o nombre aparece dos veces
        # en una frase, se resuelve una sola vez en vez de crear dos
        # personas para lo mismo.
        cache: dict[str, UUID] = {}
        registradas: list[UUID] = []

        for hecho in hechos:
            if not _valido(hecho):
                continue

            sujeto_texto = hecho["sujeto"].strip()
            subject_id = await self._resolver_sujeto(
                sujeto_texto, hablante_id, cache
            )

            predicado = _normalizar_predicado(hecho["predicado"])
            objeto_texto = hecho["objeto"].strip()

            # En un hecho de vínculo el objeto no es un dato suelto, es
            # otra persona (o el vínculo mismo si no se dio nombre): se
            # resuelve a un actor igual que el sujeto, para que la relación
            # quede enlazada y no como texto libre sin referencia.
            object_actor_id = None
            if predicado in PREDICADOS_DE_VINCULO:
                object_actor_id = await self._resolver_objeto_vinculo(
                    objeto_texto, predicado, hablante_id, cache
                )

            assertion_id = await self._af.afirmar(
                subject_id,
                predicado,
                objeto_texto,
                raw_text=mensaje,
                source_type="told",
                source_actor_id=hablante_id,
                source_event_id=event_id,
                object_actor_id=object_actor_id,
            )
            registradas.append(assertion_id)

            # Si esto es una causa conocida (trabaja_en, estudia, proyecto),
            # puede estar respondiendo una pregunta pendiente sobre esta
            # persona (ver nucleo/memoria/inferencia.py).
            await self._preguntas.responder_por_causa(subject_id, predicado)

        return registradas

    async def _resolver_sujeto(
        self, sujeto_texto: str, hablante_id: UUID, cache: dict[str, UUID]
    ) -> UUID:
        """"yo"/"mí" es quien habla. Cualquier otro texto es una persona."""
        clave = _normalizar(sujeto_texto)

        if clave in ("yo", "mi", "mi mismo", "yo mismo"):
            return hablante_id

        return await self._resolver_persona(sujeto_texto, cache)

    async def _resolver_objeto_vinculo(
        self, nombre: str, predicado: str, hablante_id: UUID, cache: dict[str, UUID]
    ) -> UUID:
        """Resuelve el objeto de un hecho de vínculo, reconciliando identidad.

        "Trabajo con mi papá" crea una persona provisoria nombrada "mi papá"
        bajo padre_de. Cuando después llega "mi papá se llama Julio", el
        objeto que llega acá ya es el nombre ("Julio"), no el vínculo —
        buscarlo por nombre exacto no encuentra a esa persona y crearía una
        segunda. Reconciliar contra la afirmación de vínculo existente del
        mismo hablante evita la duplicación (decisión 0028 pendiente).

        No actualiza actors.name acá: eso lo hace únicamente
        Afirmaciones._sincronizar_nombre, disparado por el hecho "se_llama"
        que el prompt pide como segundo hecho en este mismo mensaje. Un solo
        lugar sincroniza el nombre, para que no haya dos caminos que puedan
        desfasarse.
        """
        clave = _normalizar(nombre)
        if clave in cache:
            return cache[clave]

        existente = await self._repo.consultar_una(
            """
            SELECT object_actor_id FROM assertions
             WHERE subject_id = %s AND predicate = %s AND retired_at IS NULL
             ORDER BY confidence DESC LIMIT 1
            """,
            (hablante_id, predicado),
        )
        if existente is not None and existente["object_actor_id"] is not None:
            persona_id = existente["object_actor_id"]
            cache[clave] = persona_id
            return persona_id

        return await self._resolver_persona(nombre, cache)

    async def _resolver_persona(
        self, nombre: str, cache: dict[str, UUID]
    ) -> UUID:
        """Encuentra o crea la persona nombrada, cacheada por mensaje.

        Un nombre conocido se busca en actors. Uno desconocido crea una
        person — tanto si es un nombre propio ("Marta") como si es un
        vínculo sin nombre usado como referencia ("mi hermano"): en ambos
        casos, dos hechos del mismo mensaje que se refieren a lo mismo
        (el vínculo y lo que se cuenta de esa persona) deben resolver a la
        misma persona, por eso el cache es compartido con el sujeto.
        """
        clave = _normalizar(nombre)

        if clave in cache:
            return cache[clave]

        fila = await self._repo.consultar_una(
            """
            SELECT id FROM actors
             WHERE lower(name) = %s AND actor_type IN ('person', 'user')
             LIMIT 1
            """,
            (nombre.lower(),),
        )
        if fila is not None:
            cache[clave] = fila["id"]
            return fila["id"]

        persona_id = await self._buscar_o_crear_persona(nombre)
        cache[clave] = persona_id
        return persona_id

    async def _buscar_o_crear_persona(self, nombre: str) -> UUID:
        """Encuentra o crea una person. No crea usuarios — eso es un acto humano.

        actors.name es único por tipo (fuera de 'user'), así que dos
        vínculos iguales ("mi hermano" en dos conversaciones distintas)
        tienen que resolver a la misma persona provisoria en vez de chocar
        contra esa restricción.
        """
        fila = await self._repo.consultar_una(
            "SELECT id FROM actors WHERE actor_type = 'person' AND name = %s",
            (nombre,),
        )
        if fila is not None:
            return fila["id"]

        filas = await self._repo.ejecutar(
            """
            WITH nuevo_actor AS (
                INSERT INTO actors (actor_type, name) VALUES ('person', %s)
                RETURNING id
            )
            INSERT INTO persons (id) SELECT id FROM nuevo_actor
            RETURNING id
            """,
            (nombre,),
        )
        return filas[0]["id"]
