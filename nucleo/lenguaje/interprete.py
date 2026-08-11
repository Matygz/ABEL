"""Interpretación de lo que el usuario dice.

Convierte texto libre en una lista de intenciones estructuradas. No decide
qué hacer con ellas: eso es del despachador.

Un mensaje puede contener varias cosas. "Estuve todo el día en el código y
estoy quemado" es una consulta y algo emocional a la vez. El intérprete
devuelve las dos; qué se responde —y si se responde— se decide después.

El modelo traduce, no razona. Reconoce de qué se trata y extrae los datos;
resolver es de los motores del Núcleo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from nucleo.lenguaje.contexto import ContextoABEL
from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje

logger = logging.getLogger(__name__)

CONFIANZA_MINIMA = 0.35


class TipoIntencion:
    """Qué clase de cosa quiere el usuario.

    Viven en el código, no en la base: cada tipo necesita un motor que lo
    resuelva, y un tipo sin motor no sirve de nada.
    """

    CONSULTAR_MEMORIA = "consultar_memoria"
    CONVERSAR = "conversar"
    CALCULAR = "calcular"
    FUERA_DE_ALCANCE = "fuera_de_alcance"

    TODOS = frozenset({
        CONSULTAR_MEMORIA, CONVERSAR, CALCULAR, FUERA_DE_ALCANCE,
    })


@dataclass(frozen=True)
class Intencion:
    """Una cosa que el usuario quiere, con qué tan seguro está ABEL."""

    tipo: str
    confianza: float
    parametros: dict[str, Any] = field(default_factory=dict)

    @property
    def dudosa(self) -> bool:
        return self.confianza < CONFIANZA_MINIMA


@dataclass(frozen=True)
class Interpretacion:
    """El resultado completo de interpretar un mensaje."""

    intenciones: tuple[Intencion, ...]
    ambiguedades: tuple[str, ...] = ()
    texto_original: str = ""

    @property
    def vacia(self) -> bool:
        return not self.intenciones

    @property
    def principal(self) -> Intencion | None:
        return self.intenciones[0] if self.intenciones else None


INSTRUCCIONES = """\
Sos el componente de interpretación de ABEL, un sistema de memoria personal.

Tu única tarea: convertir el mensaje del usuario en intenciones estructuradas.
NO respondas al usuario. NO inventes datos. NO resuelvas nada.

{contexto}

REGLA CRÍTICA: si el usuario pide datos que ABEL no registra (ubicación,
personas, mensajes) o acciones que no puede hacer, el tipo es
"fuera_de_alcance". Pero un problema de cálculo NUNCA es fuera_de_alcance:
ABEL tiene motores propios para resolverlos.

Tipos:

- "consultar_memoria": pide datos que ABEL SÍ registró: tiempo de uso de
  aplicaciones, cuándo estuvo activo o inactivo, estado del sistema.
  parametros: {{"metrica": "tiempo_por_aplicacion|actividad|presencia|sistema",
                "rango": "hoy|semana|mes|dias:N", "filtro": "nombre.exe o vacío"}}

- "conversar": comentario, desahogo, opinión, saludo, o pregunta sobre ABEL
  mismo. No pide datos.
  parametros: {{"registro": "casual|desahogo|pregunta|saludo", "tono": "..."}}

- "calcular": problema de probabilidad, optimización, lógica o acertijo que
  requiere cómputo exacto.
  parametros: {{"clase": "probabilidad|optimizacion|logica", "enunciado": "..."}}

- "fuera_de_alcance": pide algo que ABEL no registra ni puede hacer.
  parametros: {{"que_falta": "qué le haría falta a ABEL, en pocas palabras"}}

EJEMPLOS:

Mensaje: "si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?"
{{"intenciones": [{{"tipo": "calcular", "confianza": 0.95,
  "parametros": {{"clase": "probabilidad",
  "enunciado": "si tiro 3 dados, ¿cuál es la probabilidad de sacar más de 15?"}}}}],
  "ambiguedades": []}}
  
Mensaje: "¿cuánto estuve en Code hoy?"
{{"intenciones": [{{"tipo": "consultar_memoria", "confianza": 0.95,
  "parametros": {{"metrica": "tiempo_por_aplicacion", "rango": "hoy",
  "filtro": "Code.exe"}}}}], "ambiguedades": []}}

Mensaje: "¿dónde estuve ayer a las 6?"
{{"intenciones": [{{"tipo": "fuera_de_alcance", "confianza": 0.9,
  "parametros": {{"que_falta": "registro de ubicación"}}}}], "ambiguedades": []}}

Mensaje: "prendé la luz del living"
{{"intenciones": [{{"tipo": "fuera_de_alcance", "confianza": 0.95,
  "parametros": {{"que_falta": "control de dispositivos del hogar"}}}}],
  "ambiguedades": []}}

Mensaje: "mandale un mensaje a Tomi"
{{"intenciones": [{{"tipo": "fuera_de_alcance", "confianza": 0.95,
  "parametros": {{"que_falta": "acceso a mensajería y contactos"}}}}],
  "ambiguedades": []}}

Mensaje: "estuve todo el día en el código y estoy quemado"
{{"intenciones": [
  {{"tipo": "conversar", "confianza": 0.85,
    "parametros": {{"registro": "desahogo", "tono": "agotamiento"}}}},
  {{"tipo": "consultar_memoria", "confianza": 0.6,
    "parametros": {{"metrica": "tiempo_por_aplicacion", "rango": "hoy",
    "filtro": "Code.exe"}}}}
], "ambiguedades": []}}

Mensaje: "me siento como el orto"
{{"intenciones": [{{"tipo": "conversar", "confianza": 0.95,
  "parametros": {{"registro": "desahogo", "tono": "malestar"}}}}],
  "ambiguedades": []}}

Mensaje: "¿me estoy quedando hasta tarde últimamente?"
{{"intenciones": [{{"tipo": "consultar_memoria", "confianza": 0.7,
  "parametros": {{"metrica": "actividad", "rango": "semana"}}}}],
  "ambiguedades": ["'últimamente' puede ser la última semana o el último mes"]}}

REGLAS:

1. Un mensaje puede tener VARIAS intenciones. Ordenalas por importancia: lo
   que más le importa al usuario primero, no lo más literal. Si alguien dice
   que está quemado, eso importa más que cuántas horas trabajó.
2. "confianza" debe VARIAR según qué tan claro sea el mensaje. Un pedido
   directo va 0.9-0.95; una interpretación deducida va 0.5-0.7. No pongas
   siempre el mismo número.
3. "ambiguedades" es SOLO para cuando un dato concreto admite varias lecturas
   (un rango de fechas vago, un nombre que no reconocés). NO copies el mensaje
   ahí. Si no hay ambigüedad real, dejalo vacío.
4. Ante la duda entre consultar y conversar: ¿el usuario quiere un dato, o
   quiere ser escuchado?
   5. `fuera_de_alcance` es EXCLUYENTE: si aparece, no puede haber
   `consultar_memoria` en la misma respuesta. Si ABEL no registra lo que se
   pide, no hay memoria que consultar. Devolvé solo `fuera_de_alcance`.
"""


class Interprete:
    """Traduce mensajes del usuario a intenciones."""

    def __init__(self, motor: MotorLenguaje) -> None:
        self._motor = motor

    async def interpretar(
        self, mensaje: str, contexto: ContextoABEL
    ) -> Interpretacion:
        """Convierte un mensaje en intenciones estructuradas.

        Si el modelo falla o devuelve algo inutilizable, se asume que el
        mensaje es conversación: es la degradación más segura, porque
        conversar no consulta datos ni ejecuta nada.
        """
        mensaje = mensaje.strip()
        if not mensaje:
            return Interpretacion(intenciones=())

        instrucciones = INSTRUCCIONES.format(contexto=contexto.a_texto())

        try:
            datos = await self._motor.generar_json(instrucciones, mensaje)
        except ErrorLenguaje as exc:
            logger.warning("Fallo al interpretar: %s", exc)
            return self._respaldo(mensaje)

        intenciones = self._leer_intenciones(datos)

        if not intenciones:
            logger.debug("El modelo no devolvió intenciones utilizables.")
            return self._respaldo(mensaje)

        return Interpretacion(
            intenciones=intenciones,
            ambiguedades=self._leer_ambiguedades(datos),
            texto_original=mensaje,
        )

    # ------------------------------------------------------------------

    def _leer_intenciones(self, datos: dict[str, Any]) -> tuple[Intencion, ...]:
        """Valida lo que devolvió el modelo. Descarta lo inutilizable.

        Un modelo chico inventa tipos que no existen o devuelve confianza
        fuera de rango. Se filtra en vez de confiar.
        """
        crudas = datos.get("intenciones")
        if not isinstance(crudas, list):
            return ()

        validas: list[Intencion] = []
        for cruda in crudas[:5]:
            if not isinstance(cruda, dict):
                continue

            tipo = cruda.get("tipo")
            if tipo not in TipoIntencion.TODOS:
                logger.debug("Tipo de intención desconocido: %r", tipo)
                continue

            try:
                confianza = float(cruda.get("confianza", 0.5))
            except (TypeError, ValueError):
                confianza = 0.5
            confianza = max(0.0, min(1.0, confianza))

            parametros = cruda.get("parametros")
            if not isinstance(parametros, dict):
                parametros = {}

            validas.append(
                Intencion(tipo=tipo, confianza=confianza, parametros=parametros)
            )
        # Ordenar por confianza: el modelo no siempre respeta el orden pedido.
        validas.sort(key=lambda i: i.confianza, reverse=True)

        # fuera_de_alcance es excluyente: si ABEL no registra lo que se pide,
        # no hay memoria que consultar. El modelo a veces devuelve ambas.
        fuera = [i for i in validas if i.tipo == TipoIntencion.FUERA_DE_ALCANCE]
        if fuera:
            return (fuera[0],)

        return tuple(validas)

    @staticmethod
    def _leer_ambiguedades(datos: dict[str, Any]) -> tuple[str, ...]:
        crudas = datos.get("ambiguedades")
        if not isinstance(crudas, list):
            return ()
        return tuple(
            a.strip() for a in crudas[:3]
            if isinstance(a, str) and a.strip()
        )

    @staticmethod
    def _respaldo(mensaje: str) -> Interpretacion:
        """Interpretación por defecto cuando el modelo no ayuda.

        Conversar es la opción más segura: no consulta datos, no ejecuta
        nada, y deja que el usuario reformule.
        """
        return Interpretacion(
            intenciones=(
                Intencion(
                    tipo=TipoIntencion.CONVERSAR,
                    confianza=0.2,
                    parametros={"registro": "casual"},
                ),
            ),
            texto_original=mensaje,
        )