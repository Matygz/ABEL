"""Definición del sobre y los tipos de mensaje del protocolo ABEL.

Este es el único código compartido entre Núcleo y Nodo. Define el contrato
entre ambos: qué forma tiene un mensaje y cómo se serializa.

No importa nada de nucleo/ ni de nodos/. La dependencia va en un solo
sentido: los dos extremos dependen del protocolo, el protocolo no depende
de ninguno.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid7

VERSION_PROTOCOLO = 1

class CodigoError:
    """Códigos que viajan por el cable.

    El detalle de un error queda en el log local; al otro extremo solo se le
    envía el código. Un mensaje de error verboso convierte al servidor en un
    oráculo: el atacante prueba variantes y el sistema le indica qué corregir.
    """

    MALFORMED = "malformed"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNAUTHORIZED = "unauthorized"
    REJECTED = "rejected"
    INTERNAL = "internal"

class ErrorProtocolo(Exception):
    """Un mensaje no cumple el contrato del protocolo.

    `detalle` es para el log local. `codigo` es lo único que se envía al otro
    extremo.
    """

    def __init__(self, detalle: str, codigo: str = "malformed") -> None:
        super().__init__(detalle)
        self.detalle = detalle
        self.codigo = codigo


class TipoMensaje:
    """Tipos de mensaje válidos.

    Son un contrato entre programas, no datos que ABEL manipule: viven en el
    código y se versionan con el protocolo. Distinto de `event_types`, que sí
    es un catálogo en base de datos ampliable en caliente (ver decisión 0005).
    """

    HELLO = "hello"
    CHALLENGE = "challenge"
    WELCOME = "welcome"
    REJECT = "reject"
    PRESENCE_MARK = "presence_mark"
    OBSERVATION = "observation"
    ACK = "ack"
    ERROR = "error"

    TODOS = frozenset({
        HELLO, CHALLENGE, WELCOME, REJECT,
        PRESENCE_MARK, OBSERVATION, ACK, ERROR,
    })


@dataclass(frozen=True)
class Sobre:
    """Envoltorio común a todos los mensajes del protocolo."""

    tipo: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid7)
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    protocol_version: int = VERSION_PROTOCOLO

    def __post_init__(self) -> None:
        if self.tipo not in TipoMensaje.TODOS:
            raise ErrorProtocolo(f"Tipo de mensaje desconocido: {self.tipo!r}.")
        if self.sent_at.tzinfo is None:
            raise ErrorProtocolo(
                "sent_at debe tener zona horaria. Usá datetime.now(timezone.utc)."
            )

    def a_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "id": str(self.id),
            "type": self.tipo,
            "sent_at": self.sent_at.isoformat(),
            "payload": self.payload,
        }

    def serializar(self) -> str:
        """Convierte el sobre en el texto que viaja por el cable."""
        return json.dumps(self.a_dict(), separators=(",", ":"), ensure_ascii=False)


def deserializar(crudo: str | bytes) -> Sobre:
    """Convierte texto recibido en un Sobre validado.

    Todo lo que llega de la red es hostil hasta que se demuestre lo contrario:
    puede venir mal formado, incompleto, o construido a propósito para romper
    al receptor. Esta función es la frontera donde eso se detiene.
    """
    try:
        datos = json.loads(crudo)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ErrorProtocolo(f"El mensaje no es JSON válido: {exc}") from None

    if not isinstance(datos, dict):
        raise ErrorProtocolo("El mensaje debe ser un objeto JSON.")

    faltantes = {"protocol_version", "id", "type", "sent_at"} - datos.keys()
    if faltantes:
        raise ErrorProtocolo(
            f"Faltan campos obligatorios: {', '.join(sorted(faltantes))}."
        )

    version = datos["protocol_version"]
    if not isinstance(version, int):
        raise ErrorProtocolo("protocol_version debe ser un entero.")
    if version != VERSION_PROTOCOLO:
        raise ErrorProtocolo(
            f"Versión de protocolo {version} no soportada. "
            f"Esta implementación habla la versión {VERSION_PROTOCOLO}.",
            codigo=CodigoError.UNSUPPORTED_VERSION,
        )

    payload = datos.get("payload", {})
    if not isinstance(payload, dict):
        raise ErrorProtocolo("payload debe ser un objeto.")

    try:
        identificador = UUID(datos["id"])
    except (ValueError, AttributeError, TypeError):
        raise ErrorProtocolo(f"id inválido: {datos['id']!r}.") from None

    try:
        sent_at = datetime.fromisoformat(datos["sent_at"])
    except (ValueError, TypeError):
        raise ErrorProtocolo(f"sent_at inválido: {datos['sent_at']!r}.") from None

    if sent_at.tzinfo is None:
        raise ErrorProtocolo("sent_at debe incluir zona horaria.")

    return Sobre(
        tipo=datos["type"],
        payload=payload,
        id=identificador,
        sent_at=sent_at,
        protocol_version=version,
    )