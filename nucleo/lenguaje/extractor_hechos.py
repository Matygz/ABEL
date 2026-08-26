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
from nucleo.memoria.afirmaciones import Afirmaciones, VINCULOS_UNICOS
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
- Las relaciones de vínculo van de quien tiene el rol hacia quien lo
  recibe, no de quien habla: en "madre_de", el sujeto es la madre, no
  necesariamente quien cuenta.
  "mi vieja se llama Marta" →
  {"sujeto": "Marta", "predicado": "madre_de", "objeto": "yo"}
  {"sujeto": "Marta", "predicado": "se_llama", "objeto": "Marta"}
  "soy hijo de Julio" →
  {"sujeto": "yo", "predicado": "hijo_de", "objeto": "Julio"}
  Las dos formas son válidas: el sistema las normaliza a una sola. Lo
  importante es que el predicado describa correctamente quién es qué del
  otro, nunca lo contrario de lo que pasa.
- Si el mensaje habla de otra persona por su vínculo ("mi vieja",
  "mi hermano", "mi jefe"), devolvé DOS hechos: uno con el vínculo (el
  sujeto es esa persona, el predicado es el vínculo desde su rol —
  madre_de, hermano_de, jefe_de — y el objeto es quien habla, "yo") y otro
  con lo que se cuenta de esa persona (el sujeto sigue siendo ella). Si el
  mensaje da su nombre, usalo como sujeto de los dos hechos. Si no da el
  nombre, usá el vínculo tal cual ("mi hermano") como sujeto en los dos
  lugares.
  Ejemplo sin nombre — "mi hermano vive en Mendoza":
  {"sujeto": "mi hermano", "predicado": "hermano_de", "objeto": "yo"}
  {"sujeto": "mi hermano", "predicado": "vive_en", "objeto": "Mendoza"}
- Un posesivo ("su taller", "su hijo") solo tiene sentido si el mensaje
  ya dijo de quién es. Resolvelo contra eso: en "trabajo con mi papá, en
  su empresa", "su taller" es "el taller de mi papá". Si no podés
  resolverlo con lo que dice el mensaje, no inventes a quién se refiere:
  omití ese hecho entero. Es mejor no registrar nada que registrar algo
  ambiguo.
- Un posesivo se resuelve contra la persona mencionada en el mismo mensaje:
  "trabajo con mi papá, en su taller" →
  {"sujeto": "mi papá", "predicado": "padre_de", "objeto": "yo"}
  {"sujeto": "yo", "predicado": "trabaja_en", "objeto": "taller de mi papá"}
    Nunca dejes un posesivo sin resolver: "su taller" a secas no significa
    nada. Si no hay a quién referirlo, omití el hecho.
- Si el mensaje no afirma ningún hecho, devolvé {"hechos": []}.
- No inventes nada que no esté en el mensaje.
"""

TEMPERATURA = 0.1

# Predicados de vínculo: el objeto de estos hechos no es un dato suelto,
# es otra persona — o el propio hablante ("yo"), que es el caso más común
# ("mi papá" visto desde el rol de "mi papá" tiene como objeto a quien
# habla). Acá solo se usa la lista para saber cuándo el objeto hay que
# resolverlo a un actor en vez de guardarlo como texto suelto.
PREDICADOS_DE_VINCULO = {
    "madre_de", "padre_de", "hermano_de", "hermana_de", "pareja_de",
    "jefe_de", "jefa_de", "amigo_de", "amiga_de", "hijo_de",
}

# Peso de la pregunta que queda abierta cuando dos personas con nombre
# propio compiten por el mismo vínculo único. Alto: que ABEL no pueda
# decidir solo cuál de las dos es la correcta es algo que vale la pena que
# note y, eventualmente, pregunte.
PESO_PREGUNTA_DUPLICADO = 0.85


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

            # En un hecho de vínculo el objeto no es un dato suelto: es
            # otra persona, o el propio hablante si el objeto es "yo" (el
            # caso más común: "mi papá" tiene a quien habla como objeto de
            # padre_de). Se resuelve igual que un sujeto — mismo criterio
            # para "yo" y para un nombre — para que la relación quede
            # enlazada y no como texto libre sin referencia.
            object_actor_id = None
            if predicado in PREDICADOS_DE_VINCULO:
                object_actor_id = await self._resolver_sujeto(
                    objeto_texto, hablante_id, cache
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

            # Un vínculo único (padre_de, madre_de...) con dos objetos
            # distintos no es una contradicción legítima como sí lo sería
            # trabaja_en: nadie tiene dos padres biológicos. Es la misma
            # persona vista dos veces — por ejemplo, "mi papá" provisorio
            # de un mensaje y "Julio" con nombre de otro.
            if predicado in VINCULOS_UNICOS:
                await self._resolver_posible_duplicado(subject_id, predicado)

        return registradas

    async def _resolver_sujeto(
        self, sujeto_texto: str, hablante_id: UUID, cache: dict[str, UUID]
    ) -> UUID:
        """"yo"/"mí" es quien habla. Cualquier otro texto es una persona."""
        clave = _normalizar(sujeto_texto)

        if clave in ("yo", "mi", "mi mismo", "yo mismo"):
            return hablante_id

        return await self._resolver_persona(sujeto_texto, cache)

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

    async def _resolver_posible_duplicado(self, subject_id: UUID, predicado: str) -> None:
        """Tras afirmar un vínculo único, ver si quedaron dos personas para el mismo rol.

        Solo mira el predicado recién afirmado: si hubiera otro vínculo
        único duplicado sin relación con este mensaje, se detecta la
        próxima vez que se toque (acá o desde scripts/fusionar.py).
        """
        duplicados = await self._af.buscar_duplicados_por_vinculo(subject_id)
        for grupo in duplicados:
            if grupo["predicate"] != predicado:
                continue

            por_actor: dict[UUID, dict] = {}
            for afirmacion in grupo["afirmaciones"]:
                actor_id = afirmacion["object_actor_id"]
                if actor_id is not None:
                    por_actor.setdefault(actor_id, afirmacion)

            ids_actores = list(por_actor.keys())
            if len(ids_actores) < 2:
                continue

            # Puede haber más de dos si el vínculo se afirmó tres veces con
            # objetos distintos; se resuelve el primer par y, si sigue
            # habiendo duplicado tras la fusión, la próxima pasada lo agarra.
            a_id, b_id = ids_actores[0], ids_actores[1]
            origen_id = por_actor[a_id]["id"]
            await self._fusionar_o_preguntar(subject_id, predicado, a_id, b_id, origen_id)

    async def _fusionar_o_preguntar(
        self, subject_id: UUID, predicado: str, a_id: UUID, b_id: UUID, origen_id: UUID,
    ) -> None:
        """Decide cuál de las dos personas sobrevive, o si no se puede decidir solo.

        Gana la que tiene nombre propio: una etiqueta de vínculo ("mi papa")
        es provisoria por definición. Si las dos tienen nombre propio y son
        distintos, no se fusiona a ciegas — puede que se haya extraído mal,
        o que la persona se haya confundido. Se registra una pregunta.
        """
        a_tiene = await self._tiene_nombre_propio(a_id)
        b_tiene = await self._tiene_nombre_propio(b_id)

        if a_tiene and b_tiene:
            await self._preguntas.abrir(
                subject_id,
                f"dijiste dos personas distintas para '{predicado}': "
                "no está claro cuál es la correcta",
                origen_id,
                PESO_PREGUNTA_DUPLICADO,
            )
            return

        if a_tiene:
            duplicada, real = b_id, a_id
        elif b_tiene:
            duplicada, real = a_id, b_id
        else:
            # Ninguna tiene nombre propio todavía: no hay base para decidir
            # cuál sobrevive. Se deja para cuando alguna lo tenga.
            return

        await self._af.fusionar(
            duplicada, real, f"duplicado detectado por vínculo único {predicado}"
        )

    async def _tiene_nombre_propio(self, actor_id: UUID) -> bool:
        """Si tiene una afirmación se_llama activa, no es solo una etiqueta de vínculo."""
        fila = await self._repo.consultar_una(
            """
            SELECT 1 FROM assertions
             WHERE subject_id = %s AND predicate = 'se_llama' AND retired_at IS NULL
             LIMIT 1
            """,
            (actor_id,),
        )
        return fila is not None
