"""Decide si ABEL responde, qué responde, y con cuánto.

Tener un dato no obliga a decirlo. Un sistema que siempre contesta algo, y
siempre con todo lo que sabe, es un chatbot. La diferencia con un compañero
está en lo que elige callar.

El criterio es código, no modelo: tiene que ser predecible y auditable. Pero
las reglas están escritas sobre qué aporta cada cosa, no sobre su forma.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from nucleo.lenguaje.interprete import TipoIntencion
from nucleo.razonamiento.despachador import Respuesta, Resuelto

logger = logging.getLogger(__name__)


class Postura(Enum):
    """Qué hace ABEL con un mensaje."""

    RESPONDER = "responder"      # Tiene algo que decir
    ACUSAR = "acusar"            # Registró el mensaje, no tiene nada que agregar
    CALLAR = "callar"            # No corresponde ni acusar


@dataclass(frozen=True)
class Decision:
    """Qué responde ABEL y por qué."""

    postura: Postura
    resueltos: tuple[Resuelto, ...] = ()
    motivo: str = ""

    @property
    def habla(self) -> bool:
        return self.postura is Postura.RESPONDER


class Criterio:
    """Filtra lo que ABEL va a decir."""

    def decidir(self, respuesta: Respuesta, previos: list | None = None) -> Decision:
        if not respuesta.resueltos:
            return Decision(Postura.CALLAR, motivo="nada que resolver")

        if self._ya_lo_dijo(respuesta, previos):
            return Decision(
                Postura.ACUSAR,
                motivo="ya dijo lo mismo y ya le contesté",
            )

        relevantes = self._filtrar(respuesta)
        ...

        if not relevantes:
            return Decision(
                Postura.ACUSAR,
                motivo="nada que aportar sobre eso",
            )

        return Decision(Postura.RESPONDER, resueltos=relevantes)

    # ------------------------------------------------------------------

    def _filtrar(self, respuesta: Respuesta) -> tuple[Resuelto, ...]:
        """Descarta lo que no vale la pena decir."""
        candidatos = list(respuesta.resueltos)

        # Un desahogo domina el mensaje. Cuando alguien dice que está mal,
        # contestarle con estadísticas de uso de aplicaciones es responder
        # la pregunta literal e ignorar la real.
        desahogo = self._desahogo(candidatos)
        if desahogo is not None:
            return (desahogo,)

        # Un límite se dice solo, sin acompañarlo de datos parciales que
        # parezcan una respuesta a medias.
        sin_alcance = [
            r for r in candidatos
            if r.intencion.tipo == TipoIntencion.FUERA_DE_ALCANCE
        ]
        if sin_alcance:
            return (sin_alcance[0],)

        return tuple(r for r in candidatos if self._aporta(r))

    @staticmethod
    def _ya_lo_dijo(respuesta: Respuesta, previos: list | None) -> bool:
        """Si el mensaje repite exactamente lo último que la persona dijo.

        Solo mira el intercambio inmediatamente anterior, y solo si ABEL
        respondió: repetir algo dos veces seguidas es insistencia; volver a
        decirlo cinco turnos después es otra cosa.

        Y si ABEL ya calló, no vuelve a callar — insistir con el silencio es
        peor que decir algo.
        """
        if not previos or len(previos) < 2:
            return False

        actual = respuesta.interpretacion.texto_original.strip().lower()
        if not actual:
            return False

        ultimo_usuario = previos[-2]
        ultimo_abel = previos[-1]

        if ultimo_usuario.get("hablante") == "abel":
            return False
        if ultimo_abel.get("hablante") != "abel":
            return False

        mismo = (ultimo_usuario.get("texto") or "").strip().lower() == actual
        respondio = bool((ultimo_abel.get("texto") or "").strip())

        return mismo and respondio
    
    @staticmethod
    def _desahogo(candidatos: list[Resuelto]) -> Resuelto | None:
        """El desahogo tiene prioridad sobre cualquier dato."""
        for resuelto in candidatos:
            if resuelto.intencion.tipo != TipoIntencion.CONVERSAR:
                continue
            registro = resuelto.intencion.parametros.get("registro", "")
            if registro in ("desahogo", "malestar"):
                return resuelto
        return None

    @staticmethod
    def _aporta(resuelto: Resuelto) -> bool:
        """Si vale la pena mencionar este resultado."""
        intencion, resultado = resuelto.intencion, resuelto.resultado

        # Una interpretación dudosa produce respuestas que no vienen al caso.
        if intencion.tipo == TipoIntencion.CONVERSAR:
            # Una conversación nunca se descarta por confianza: la confianza
            # mide qué tan claro está de qué clase de cosa es, y ante la duda
            # responder algo es mejor que callar.
            return True

        if intencion.dudosa:
            logger.debug(
                "Descartado por baja confianza: %s (%.2f)",
                intencion.tipo, intencion.confianza,
            )
            return False

        # Un resultado que no se pudo obtener por un fallo interno no es
        # información: es ruido. El límite declarado sí se dice.
        if not resultado.resuelto:
            return resultado.tipo == "fuera_de_alcance"

        # Un dato vacío no aporta. "No hay nada registrado" solo vale la
        # pena si el usuario preguntó explícitamente por eso.
        if resultado.vacio:
            return intencion.confianza >= 0.8

        return True