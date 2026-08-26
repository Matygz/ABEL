"""Aplicar una corrección: identificar qué afirmación está mal y arreglarla.

EL PRINCIPIO QUE ORDENA ESTE MÓDULO: una corrección es la evidencia más
fuerte que ABEL puede tener. Más que una observación propia, más que una
inferencia. Si la persona dice que algo está mal, está mal — no hay margen
para pesarla contra otra fuente, como sí pasa entre dos afirmaciones told
que difieren (ver docstring de nucleo/memoria/afirmaciones.py).

Pero no se borra nada. La afirmación corregida queda retirada, con su
historia intacta: ABEL puede saber que antes creía eso y dejó de creerlo, y
si algún día aparece evidencia nueva, revive (regla 1 de afirmaciones.py).

Identificar qué se corrige, en orden:

    1. La corrección trae el dato correcto ("no, se llama Marta"): se
       extrae, y se busca una afirmación activa con el mismo sujeto y
       predicado pero objeto distinto. Esa es la que se corrige.
    2. La corrección no trae el dato ("eso está mal"): se corrige la
       última afirmación registrada en la conversación en curso.
    3. No se puede identificar ninguna de las dos formas: no se adivina.
       Se registra una pregunta abierta (si hay a qué afirmación
       anclarla) y ABEL responde dejando ver que no entendió qué corregir.

El LLM solo traduce el mensaje de corrección a predicado/objeto — nunca
decide qué afirmación es la correcta ni concluye nada por su cuenta.
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
La persona te está corrigiendo algo que dijiste creer. Mirá el mensaje y
decidí si trae el valor correcto.

Devolvé JSON:
{"tiene_dato": true o false,
 "sujeto": "de quién es el hecho corregido (nombre o vínculo como 'mi vieja'), o null si es sobre quien habla",
 "predicado": "la relación en una o dos palabras con guión bajo (se_llama, trabaja_en, vive_en, estudia, le_gusta, tiene), o null",
 "objeto": "el valor correcto, o null"}

- "tiene_dato" es true SOLO si el mensaje dice explícitamente cuál es el
  valor correcto: "no, se llama Marta", "vivo en Quilmes, no en Bernal".
- Si el mensaje solo señala que algo está mal sin decir cuál es el valor
  correcto ("eso está mal", "te equivocaste", "no es así"), "tiene_dato" es
  false y los demás campos van null.
- No inventes nada que no esté en el mensaje.
"""

TEMPERATURA = 0.1

# Espejo de PREDICADOS_DE_VINCULO en extractor_hechos.py, pero como mapa de
# la palabra suelta al predicado: acá no se extrae un hecho nuevo, se busca
# a quién ya se refiere ese vínculo para encontrar la afirmación a corregir.
_VINCULOS_A_PREDICADO = {
    "mama": "madre_de", "mamá": "madre_de", "vieja": "madre_de", "madre": "madre_de",
    "papa": "padre_de", "papá": "padre_de", "viejo": "padre_de", "padre": "padre_de",
    "hermano": "hermano_de", "hermana": "hermana_de",
    "pareja": "pareja_de", "novio": "pareja_de", "novia": "pareja_de",
    "jefe": "jefe_de", "jefa": "jefa_de",
    "amigo": "amigo_de", "amiga": "amiga_de",
}

# Más alto que un told normal (0.75): corregir es deliberado, no contar algo
# al pasar. Aplicado con confirmar() sobre el 0.75 inicial de afirmar():
# 0.75 + (1 - 0.75) * 0.6 = 0.9.
CUANTO_CONFIANZA_CORRECCION = 0.6

# Baja la afirmación vieja muy por debajo del piso de retiro (0.15): una
# corrección no dosifica, retira.
FUERZA_CORRECCION = 0.95

# Peso alto: que ABEL no haya entendido qué corregir es algo que vale la
# pena que ABEL mismo note y, eventualmente, pregunte.
PESO_PREGUNTA_CORRECCION = 0.9


def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def _normalizar(texto: str) -> str:
    return _sin_acentos(texto.strip().lower())


def _normalizar_predicado(texto: str) -> str:
    return _normalizar(texto).replace(" ", "_")


def _predicado_de_vinculo(texto: str) -> str | None:
    """"mi vieja" -> madre_de. Solo mira la última palabra con contenido."""
    palabras = _normalizar(texto).split()
    if not palabras:
        return None
    return _VINCULOS_A_PREDICADO.get(palabras[-1])


class Corrector:
    """Identifica qué afirmación corregir y la aplica."""

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

    async def corregir(
        self,
        mensaje: str,
        hablante_id: UUID,
        event_id: UUID | None,
        session_id: UUID | None,
    ) -> None:
        """Identifica qué se corrige y lo aplica. No devuelve nada: solo escribe."""
        try:
            datos = await self._motor.generar_json(
                INSTRUCCIONES, mensaje, temperatura=TEMPERATURA
            )
        except ErrorLenguaje as exc:
            logger.warning("No se pudo interpretar la corrección %r: %s", mensaje, exc)
            datos = {"tiene_dato": False}

        if datos.get("tiene_dato"):
            await self._corregir_con_dato(datos, mensaje, hablante_id, event_id, session_id)
        else:
            await self._corregir_sin_dato(mensaje, hablante_id, session_id)

    # ------------------------------------------------------------------

    async def _corregir_con_dato(
        self, datos: dict, mensaje: str, hablante_id: UUID, event_id: UUID | None,
        session_id: UUID | None,
    ) -> None:
        predicado = _normalizar_predicado(str(datos.get("predicado") or ""))
        objeto = str(datos.get("objeto") or "").strip()
        subject_id = await self._resolver_sujeto(datos.get("sujeto"), hablante_id)

        vieja = None
        if subject_id is not None and predicado and objeto:
            vieja = await self._repo.consultar_una(
                """
                SELECT id FROM assertions
                 WHERE subject_id = %s AND predicate = %s AND retired_at IS NULL
                   AND object_text <> %s
                 ORDER BY confidence DESC
                 LIMIT 1
                """,
                (subject_id, predicado, objeto),
            )

        if vieja is None:
            # Trae el dato pero no hay qué reemplazar: no se puede
            # identificar con certeza qué creía ABEL antes. No se adivina.
            await self._no_identificada(mensaje, hablante_id, session_id)
            return

        await self._af.contradecir(
            vieja["id"], FUERZA_CORRECCION, f"corregido por la persona: {mensaje!r}"
        )

        nueva_id = await self._af.afirmar(
            subject_id, predicado, objeto,
            raw_text=mensaje, source_type="told",
            source_actor_id=hablante_id, source_event_id=event_id,
        )
        await self._af.confirmar(
            nueva_id, CUANTO_CONFIANZA_CORRECCION,
            "corrección: dato dado con más certeza que un told normal",
        )
        await self._preguntas.responder_por_causa(subject_id, predicado)
        await self._registrar_correccion(hablante_id, vieja["id"], nueva_id, mensaje)

    async def _corregir_sin_dato(
        self, mensaje: str, hablante_id: UUID, session_id: UUID | None,
    ) -> None:
        vieja_id = await self._ultima_afirmacion_de_la_sesion(hablante_id, session_id)
        if vieja_id is None:
            await self._no_identificada(mensaje, hablante_id, session_id)
            return

        await self._af.contradecir(
            vieja_id, FUERZA_CORRECCION, f"corregido sin dato nuevo: {mensaje!r}"
        )
        await self._registrar_correccion(hablante_id, vieja_id, None, mensaje)

    async def _no_identificada(
        self, mensaje: str, hablante_id: UUID, session_id: UUID | None,
    ) -> None:
        """No se pudo identificar qué corregir. No se retira nada al azar.

        Si hay alguna afirmación reciente de la sesión a la que anclar la
        pregunta, se registra (origin_assertion_id no admite nulo). Si no
        hay ninguna —la corrección llegó sin haberse afirmado nada antes—
        no hay dónde anclarla: queda sin registrar, pero ABEL igual
        responde dejando ver que no entendió (eso lo decide el criterio,
        no este módulo).
        """
        ancla = await self._ultima_afirmacion_de_la_sesion(hablante_id, session_id)
        if ancla is None:
            logger.info(
                "Corrección sin poder identificar qué corregir, y sin "
                "afirmación previa a la que anclar la pregunta: %r", mensaje,
            )
            return

        await self._preguntas.abrir(
            hablante_id,
            f"dijo que algo estaba mal pero no quedó claro qué: {mensaje!r}",
            ancla,
            PESO_PREGUNTA_CORRECCION,
        )

    # ------------------------------------------------------------------

    async def _resolver_sujeto(self, sujeto_texto: object, hablante_id: UUID) -> UUID | None:
        """"yo" es el hablante. Un nombre conocido o un vínculo, otra persona."""
        if not sujeto_texto or not str(sujeto_texto).strip():
            return hablante_id

        texto = str(sujeto_texto).strip()
        clave = _normalizar(texto)
        if clave in ("yo", "mi", "mi mismo", "yo mismo"):
            return hablante_id

        fila = await self._repo.consultar_una(
            """
            SELECT id FROM actors
             WHERE lower(name) = %s AND actor_type IN ('person', 'user')
             LIMIT 1
            """,
            (texto.lower(),),
        )
        if fila is not None:
            return fila["id"]

        predicado = _predicado_de_vinculo(texto)
        if predicado is None:
            return None

        # La relación es canónica desde quien tiene el rol: en madre_de, el
        # sujeto es la madre y el hablante es el objeto (ver
        # nucleo/memoria/relaciones.py). "mi vieja" busca del lado del
        # objeto, no del sujeto.
        fila = await self._repo.consultar_una(
            """
            SELECT subject_id FROM assertions
             WHERE object_actor_id = %s AND predicate = %s AND retired_at IS NULL
             ORDER BY confidence DESC
             LIMIT 1
            """,
            (hablante_id, predicado),
        )
        return fila["subject_id"] if fila is not None else None

    async def _ultima_afirmacion_de_la_sesion(
        self, hablante_id: UUID, session_id: UUID | None,
    ) -> UUID | None:
        """La afirmación activa más reciente que la persona contó en esta sesión."""
        if session_id is None:
            return None

        fila = await self._repo.consultar_una(
            """
            SELECT a.id FROM assertions a
              JOIN events e ON e.id = a.source_event_id
             WHERE a.source_actor_id = %s
               AND e.payload->>'session_id' = %s
               AND a.retired_at IS NULL
             ORDER BY a.created_at DESC
             LIMIT 1
            """,
            (hablante_id, str(session_id)),
        )
        return fila["id"] if fila is not None else None

    async def _registrar_correccion(
        self, hablante_id: UUID, vieja_id: UUID, nueva_id: UUID | None, mensaje: str,
    ) -> None:
        await self._repo.registrar_evento(
            event_type="assertion_corrected",
            actor_id=hablante_id,
            payload={
                "old_assertion_id": str(vieja_id),
                "new_assertion_id": str(nueva_id) if nueva_id else None,
                "raw_text": mensaje,
            },
        )
