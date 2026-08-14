"""De un mensaje a una intención ejecutable.

Cascada de tres capas. Cada una resuelve lo que puede y solo pasa hacia abajo
lo que no reconoce:

    patrones       lo determinista — una expresión aritmética no es lenguaje
                   ambiguo, es una expresión aritmética
    similitud      lo conocido — se compara contra ejemplos indexados
    modelo         lo que no encaja en nada — solo entonces

El modelo pasa de atender todos los mensajes a atender los que ninguna otra
capa reconoció. Y en esos casos no clasifica entre categorías: solo decide si
es charla o un límite, que es una pregunta mucho más chica.

Un clasificador que solo puede elegir entre capacidades existentes no puede
inventarse una categoría. Eso resuelve el modo de fallo del intérprete
generativo, que ante frases raras se ponía a completar los ejemplos del
prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from nucleo.capacidades.registro import Capacidad, RegistroCapacidades
from nucleo.lenguaje import particion, patrones
from nucleo.lenguaje.clasificador import Clasificador
from nucleo.lenguaje.contexto import ContextoABEL
from nucleo.lenguaje.extractor import Extractor
from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje

logger = logging.getLogger(__name__)


class Origen:
    """Qué capa reconoció el mensaje. Sirve para medir la cascada."""

    PATRON = "patron"
    SIMILITUD = "similitud"
    MODELO = "modelo"
    RESPALDO = "respaldo"


@dataclass(frozen=True)
class Intencion:
    capacidad: str | None
    tipo: str
    confianza: float
    parametros: dict = field(default_factory=dict)
    origen: str = Origen.SIMILITUD
    # Si vino de una parte propia del mensaje o si ABEL la dedujo del
    # conjunto. Un pedido explícito no se descarta por criterio.
    explicita: bool = True

    @property
    def fuera_de_alcance(self) -> bool:
        return self.capacidad is None


@dataclass(frozen=True)
class Analisis:
    """El resultado de analizar un mensaje."""

    intenciones: tuple[Intencion, ...]
    texto_original: str = ""
    ambiguedades: tuple[str, ...] = ()

    @property
    def vacio(self) -> bool:
        return not self.intenciones

    @property
    def principal(self) -> Intencion | None:
        return self.intenciones[0] if self.intenciones else None


INSTRUCCIONES_ULTIMO_RECURSO = """\
Decidí si el mensaje del usuario es conversación o pide algo que ABEL no puede
hacer.

ABEL puede: consultar el tiempo de uso de aplicaciones, cuándo el usuario
estuvo activo, su propio estado, cálculos de probabilidad y aritmética.

ABEL NO puede: ubicación, mensajes, calendario, correo, música, dispositivos
del hogar, ni nada fuera de esta computadora.

Devolvé JSON:
{"tipo": "conversar"} si es charla, desahogo, saludo, opinión o algo sin pedido
concreto.
{"tipo": "fuera_de_alcance", "que_falta": "..."} si pide algo que ABEL no puede.

Ante la duda, "conversar".
"""


class Analizador:
    """Convierte mensajes en intenciones ejecutables."""

    def __init__(
        self,
        registro: RegistroCapacidades,
        clasificador: Clasificador,
        extractor: Extractor,
        motor: MotorLenguaje,
    ) -> None:
        self._registro = registro
        self._clasificador = clasificador
        self._extractor = extractor
        self._motor = motor

    async def analizar(self, mensaje: str, contexto: ContextoABEL) -> Analisis:
        mensaje = mensaje.strip()
        if not mensaje:
            return Analisis(intenciones=())

        partes = particion.partir(mensaje)
        explicitas = len(partes) > 1

        intenciones: list[Intencion] = []
        for parte in partes:
            intencion = await self._analizar_parte(
                parte, mensaje, contexto, explicitas
            )
            if intencion is not None:
                intenciones.append(intencion)

        if not intenciones:
            intenciones = [await self._ultimo_recurso(mensaje)]

        # Sin duplicados: dos partes pueden caer en la misma capacidad, y
        # ejecutarla dos veces no aporta nada.
        vistas: set[str] = set()
        unicas: list[Intencion] = []
        for intencion in intenciones:
            clave = intencion.capacidad or "fuera_de_alcance"
            if clave in vistas:
                continue
            vistas.add(clave)
            unicas.append(intencion)

        return Analisis(tuple(unicas), texto_original=mensaje)

    async def _analizar_parte(
        self,
        parte: str,
        completo: str,
        contexto: ContextoABEL,
        explicita: bool,
    ) -> Intencion | None:
        """Aplica la cascada a una parte del mensaje.

        La clasificación usa la parte; la extracción, el mensaje entero. Un
        parámetro puede estar en cualquier lado: "estoy quemado de Code,
        ¿cuánto estuve?" nombra la aplicación en la primera mitad y pregunta
        en la segunda.
        """
        directo = self._por_patron(parte)
        if directo is not None:
            return directo

        por_similitud = await self._por_similitud(
            parte, completo, contexto, explicita
        )
        if por_similitud is not None:
            return por_similitud

        return None
    
    def _por_patron(self, mensaje: str) -> Intencion | None:
        """Primera capa: lo que se reconoce sin ningún modelo."""
        reconocido = patrones.reconocer(mensaje)
        if reconocido is None:
            return None

        _, parametros = reconocido
        capacidad = self._registro.obtener("aritmetica")
        if capacidad is None:
            return None

        return Intencion(
            capacidad=capacidad.nombre,
            tipo=capacidad.tipo,
            confianza=1.0,
            parametros={"enunciado": parametros["enunciado"]},
            origen=Origen.PATRON,
        )
    
    async def _por_similitud(
        self,
        parte: str,
        completo: str,
        contexto: ContextoABEL,
        explicita: bool = True,
    ) -> Intencion | None:
        """Segunda capa: comparación contra ejemplos conocidos."""
        clasificacion = await self._clasificador.clasificar(parte)
        if not clasificacion.reconocido:
            return None

        capacidad = self._registro.obtener(clasificacion.capacidad)
        if capacidad is None:
            logger.warning(
                "El índice devolvió una capacidad que no existe: %s. "
                "¿Quedó desincronizado?", clasificacion.capacidad,
            )
            return None

        parametros = await self._extractor.extraer(
            completo, capacidad, contexto.aplicaciones
        )

        return Intencion(
            capacidad=capacidad.nombre,
            tipo=capacidad.tipo,
            confianza=clasificacion.confianza,
            parametros=parametros,
            origen=Origen.SIMILITUD,
            explicita=explicita,
        )

    async def _ultimo_recurso(self, mensaje: str) -> Intencion:
        """Tercera capa: charla o límite.

        No se le pide clasificar entre capacidades — para eso está el índice.
        Solo si esto es conversación o algo que ABEL no puede hacer.
        """
        try:
            datos = await self._motor.generar_json(
                INSTRUCCIONES_ULTIMO_RECURSO,
                f"Mensaje a clasificar: {mensaje}",
                temperatura=0.1,
            )
        except ErrorLenguaje as exc:
            logger.debug("Sin decisión del modelo: %s", exc)
            return self._como_charla(Origen.RESPALDO)

        if datos.get("tipo") == "fuera_de_alcance":
            return Intencion(
                capacidad=None,
                tipo="fuera_de_alcance",
                confianza=0.7,
                parametros={
                    "que_falta": str(
                        datos.get("que_falta") or "esa capacidad"
                    )
                },
                origen=Origen.MODELO,
            )

        return self._como_charla(Origen.MODELO)

    def _como_charla(self, origen: str) -> Intencion:
        """Conversación: la salida más segura ante la duda.

        No consulta datos ni ejecuta nada, y deja que la persona reformule.
        Un mensaje que no se entendió merece una respuesta, no un silencio.
        """
        capacidad = self._registro.obtener("conversar")
        return Intencion(
            capacidad="conversar" if capacidad else None,
            tipo="conversar",
            confianza=0.5,
            parametros={},
            origen=origen,
        )