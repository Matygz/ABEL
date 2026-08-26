"""Decide si ABEL responde, qué responde, y con cuánto.

Tener un dato no obliga a decirlo. Un sistema que siempre contesta algo, y
siempre con todo lo que sabe, es un chatbot. La diferencia con un compañero
está en lo que elige callar.

El criterio es código, no modelo: tiene que ser predecible y auditable. Pero
las reglas están escritas sobre qué aporta cada cosa, no sobre su forma.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from nucleo.razonamiento.despachador import Respuesta, Resuelto

logger = logging.getLogger(__name__)

# Por debajo de esto, una intención no conversacional no vale la pena.
CONFIANZA_MINIMA = 0.35


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

    def decidir(
        self, respuesta: Respuesta, previos: list | None = None
    ) -> Decision:
        if not respuesta.resueltos:
            return Decision(Postura.CALLAR, motivo="nada que resolver")

        if self._ya_lo_dijo(respuesta, previos):
            return Decision(
                Postura.ACUSAR,
                motivo="ya dijo lo mismo y ya le contesté",
            )

        relevantes = self._filtrar(respuesta)

        if not relevantes:
            return Decision(Postura.ACUSAR, motivo="nada que aportar sobre eso")

        return Decision(Postura.RESPONDER, resueltos=relevantes)

    # ------------------------------------------------------------------

    def _filtrar(self, respuesta: Respuesta) -> tuple[Resuelto, ...]:
        """Descarta lo que no vale la pena decir."""
        candidatos = list(respuesta.resueltos)

        desahogo = self._desahogo(candidatos)
        if desahogo is not None:
            return (desahogo,)

        # Un límite se dice solo, sin acompañarlo de datos parciales que
        # parezcan una respuesta a medias.
        sin_alcance = [
            r for r in candidatos if r.intencion.tipo == "fuera_de_alcance"
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

        actual = respuesta.analisis.texto_original.strip().lower()
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
        """El desahogo domina, salvo que la persona haya pedido el dato.

        "Estuve todo el día en el código y estoy quemado" no pide datos: la
        consulta la infirió ABEL, y responder con estadísticas sería contestar
        la pregunta literal e ignorar la real.

        "Estoy quemado de Code, ¿cuánto tiempo estuve?" sí los pide. Ahí
        callar el dato es no responder lo que se preguntó.
        """
        emocional = None
        for resuelto in candidatos:
            if resuelto.intencion.tipo != "conversar":
                continue
            registro = resuelto.intencion.parametros.get("registro", "")
            if registro in ("desahogo", "malestar"):
                emocional = resuelto
                break

        if emocional is None:
            return None

        # Si alguna otra intención vino de una parte propia del mensaje, la
        # persona la pidió: no se descarta.
        hay_pedido_explicito = any(
            r is not emocional and r.intencion.explicita for r in candidatos
        )
        return None if hay_pedido_explicito else emocional

    @staticmethod
    def _aporta(resuelto: Resuelto) -> bool:
        """Si vale la pena mencionar este resultado."""
        intencion, resultado = resuelto.intencion, resuelto.resultado

        # Contar algo no pide respuesta. Que ABEL conteste "entendido" cada
        # vez que le contás un dato lo vuelve un formulario. El gesto de la
        # interfaz alcanza para que se sepa que quedó registrado. Esto
        # deja el mensaje sin nada que aportar, así que decidir() cae en
        # ACUSAR — salvo que el mismo mensaje traiga además una consulta o
        # conversación, que sí se responde (ese Resuelto es otro, y a ese
        # sí llega este chequeo).
        if intencion.tipo == "afirmar":
            return False

        # Corregir sí merece respuesta: quien corrige quiere saber que se
        # aplicó. Pero sin disculparse ni explicar — "ah, Marta entonces"
        # alcanza. Un sistema que se disculpa cada vez que se equivoca es
        # agotador. Nunca se descarta por confianza ni por estar "vacío":
        # el trabajo real ya lo hizo nucleo/lenguaje/corrector.py antes de
        # llegar acá (ver conversacion.py), este resultado siempre importa.
        if intencion.tipo == "corregir":
            return True

        if intencion.tipo == "conversar":
            # Una conversación nunca se descarta por confianza: la confianza
            # mide qué tan claro está de qué clase de cosa es, y ante la duda
            # responder algo es mejor que callar.
            return True

        if intencion.confianza < CONFIANZA_MINIMA:
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
