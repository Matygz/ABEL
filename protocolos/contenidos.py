"""Contenido de cada tipo de mensaje del protocolo ABEL.

`mensajes.py` valida el sobre: estructura común, versión, tipos conocidos.
Este módulo valida el payload de cada tipo en particular.

Cada tipo tiene un constructor (crear_*) que arma el Sobre, y un lector
(leer_*) que valida y devuelve un objeto tipado. El lector es la frontera:
después de él, el código puede confiar en los datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from protocolos.mensajes import (
    CodigoError,
    ErrorProtocolo,
    Sobre,
    TipoMensaje,
)

MAX_OBSERVACIONES_POR_LOTE = 500
MAX_LARGO_TEXTO = 256


# ----------------------------------------------------------------------
# Extractores tipados
# ----------------------------------------------------------------------

def _texto(payload: dict[str, Any], campo: str, requerido: bool = True) -> str | None:
    valor = payload.get(campo)
    if valor is None:
        if requerido:
            raise ErrorProtocolo(f"Falta el campo {campo!r}.")
        return None
    if not isinstance(valor, str):
        raise ErrorProtocolo(f"{campo!r} debe ser texto.")
    if len(valor) > MAX_LARGO_TEXTO:
        raise ErrorProtocolo(f"{campo!r} excede {MAX_LARGO_TEXTO} caracteres.")
    return valor


def _uuid(payload: dict[str, Any], campo: str) -> UUID:
    crudo = _texto(payload, campo)
    try:
        return UUID(crudo)
    except ValueError:
        raise ErrorProtocolo(f"{campo!r} no es un UUID válido.") from None


def _entero(payload: dict[str, Any], campo: str, minimo: int = 0) -> int:
    valor = payload.get(campo)
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise ErrorProtocolo(f"{campo!r} debe ser un entero.")
    if valor < minimo:
        raise ErrorProtocolo(f"{campo!r} debe ser al menos {minimo}.")
    return valor


def _lista(payload: dict[str, Any], campo: str, maximo: int) -> list:
    valor = payload.get(campo)
    if not isinstance(valor, list):
        raise ErrorProtocolo(f"{campo!r} debe ser una lista.")
    if len(valor) > maximo:
        raise ErrorProtocolo(f"{campo!r} excede el máximo de {maximo} elementos.")
    return valor


def _momento(payload: dict[str, Any], campo: str) -> datetime:
    crudo = _texto(payload, campo)
    try:
        momento = datetime.fromisoformat(crudo)
    except ValueError:
        raise ErrorProtocolo(f"{campo!r} no es una fecha ISO válida.") from None
    if momento.tzinfo is None:
        raise ErrorProtocolo(f"{campo!r} debe incluir zona horaria.")
    return momento


# ----------------------------------------------------------------------
# hello
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Hello:
    device_id: UUID
    capabilities: tuple[str, ...]
    client_version: str
    credential: str | None


def crear_hello(
    device_id: UUID,
    capabilities: list[str],
    client_version: str,
    credential: str | None = None,
) -> Sobre:
    return Sobre(
        tipo=TipoMensaje.HELLO,
        payload={
            "device_id": str(device_id),
            "capabilities": list(capabilities),
            "client_version": client_version,
            "credential": credential,
        },
    )


def leer_hello(sobre: Sobre) -> Hello:
    p = sobre.payload
    capacidades = _lista(p, "capabilities", maximo=64)
    if not all(isinstance(c, str) for c in capacidades):
        raise ErrorProtocolo("capabilities debe ser una lista de textos.")

    return Hello(
        device_id=_uuid(p, "device_id"),
        capabilities=tuple(capacidades),
        client_version=_texto(p, "client_version"),
        credential=_texto(p, "credential", requerido=False),
    )

# ----------------------------------------------------------------------
# challenge
# ----------------------------------------------------------------------

def crear_challenge(desafio_texto: str) -> Sobre:
    """Desafío de un solo uso que el Nodo debe firmar."""
    return Sobre(
        tipo=TipoMensaje.CHALLENGE,
        payload={"challenge": desafio_texto},
    )


def leer_challenge(sobre: Sobre) -> str:
    return _texto(sobre.payload, "challenge")

# ----------------------------------------------------------------------
# welcome
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Welcome:
    session_id: UUID
    server_version: str
    presence_interval_seconds: int
    max_batch_size: int


def crear_welcome(
    session_id: UUID,
    server_version: str,
    presence_interval_seconds: int,
    max_batch_size: int = MAX_OBSERVACIONES_POR_LOTE,
) -> Sobre:
    return Sobre(
        tipo=TipoMensaje.WELCOME,
        payload={
            "session_id": str(session_id),
            "server_version": server_version,
            "presence_interval_seconds": presence_interval_seconds,
            "max_batch_size": max_batch_size,
        },
    )


def leer_welcome(sobre: Sobre) -> Welcome:
    p = sobre.payload
    return Welcome(
        session_id=_uuid(p, "session_id"),
        server_version=_texto(p, "server_version"),
        presence_interval_seconds=_entero(p, "presence_interval_seconds", minimo=1),
        max_batch_size=_entero(p, "max_batch_size", minimo=1),
    )


# ----------------------------------------------------------------------
# observation
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Observacion:
    """Un hecho captado por un Nodo.

    El Nodo declara qué clase de dato es (event_type), pero nunca lo
    interpreta. Transporta observaciones, no conclusiones.
    """

    id: UUID
    occurred_at: datetime
    event_type: str
    data: dict[str, Any]

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "occurred_at": self.occurred_at.isoformat(),
            "event_type": self.event_type,
            "data": self.data,
        }

    @classmethod
    def desde_dict(cls, crudo: Any) -> Observacion:
        if not isinstance(crudo, dict):
            raise ErrorProtocolo("Cada observación debe ser un objeto.")
        datos = crudo.get("data", {})
        if not isinstance(datos, dict):
            raise ErrorProtocolo("data debe ser un objeto.")
        return cls(
            id=_uuid(crudo, "id"),
            occurred_at=_momento(crudo, "occurred_at"),
            event_type=_texto(crudo, "event_type"),
            data=datos,
        )


def crear_observation(observaciones: list[Observacion]) -> Sobre:
    if not observaciones:
        raise ErrorProtocolo("Un mensaje de observación no puede ir vacío.")
    return Sobre(
        tipo=TipoMensaje.OBSERVATION,
        payload={"observations": [o.a_dict() for o in observaciones]},
    )


def leer_observation(
    sobre: Sobre, maximo: int = MAX_OBSERVACIONES_POR_LOTE
) -> tuple[Observacion, ...]:
    crudas = _lista(sobre.payload, "observations", maximo=maximo)
    if not crudas:
        raise ErrorProtocolo("observations no puede estar vacío.")
    return tuple(Observacion.desde_dict(c) for c in crudas)


# ----------------------------------------------------------------------
# ack
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class Ack:
    acknowledged: tuple[UUID, ...]
    rejected: tuple[tuple[UUID, str], ...]


def crear_ack(
    acknowledged: list[UUID],
    rejected: list[tuple[UUID, str]] | None = None,
) -> Sobre:
    return Sobre(
        tipo=TipoMensaje.ACK,
        payload={
            "acknowledged": [str(i) for i in acknowledged],
            "rejected": [
                {"id": str(i), "code": codigo} for i, codigo in (rejected or [])
            ],
        },
    )


def leer_ack(sobre: Sobre, maximo: int = MAX_OBSERVACIONES_POR_LOTE) -> Ack:
    p = sobre.payload
    confirmados = _lista(p, "acknowledged", maximo=maximo)
    rechazados = _lista(p, "rejected", maximo=maximo)

    try:
        ids = tuple(UUID(i) for i in confirmados)
    except (ValueError, AttributeError, TypeError):
        raise ErrorProtocolo("acknowledged debe contener UUIDs.") from None

    fallidos = tuple(
        (_uuid(r, "id"), _texto(r, "code")) for r in rechazados
        if isinstance(r, dict)
    )
    return Ack(acknowledged=ids, rejected=fallidos)


# ----------------------------------------------------------------------
# reject / error
# ----------------------------------------------------------------------

def crear_reject(codigo: str) -> Sobre:
    """Rechazo de conexión. Solo el código: nada de detalle por el cable."""
    return Sobre(tipo=TipoMensaje.REJECT, payload={"code": codigo})


def crear_error(codigo: str = CodigoError.MALFORMED) -> Sobre:
    return Sobre(tipo=TipoMensaje.ERROR, payload={"code": codigo})