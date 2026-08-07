"""Primitivas de firma digital del protocolo ABEL.

Ed25519: el Nodo firma con su clave privada, el Núcleo verifica con la
pública. La privada nunca sale del dispositivo ni viaja por la red.

Firmar no es cifrar. Un mensaje firmado se lee perfectamente; lo que no se
puede es falsificarlo ni alterarlo sin invalidar la firma. El cifrado del
canal es responsabilidad de TLS (Fase 2.4).

Este módulo no implementa criptografía: envuelve `cryptography`, que a su vez
usa OpenSSL. Implementar primitivas criptográficas a mano es la forma más
confiable de introducir vulnerabilidades sutiles.
"""

from __future__ import annotations

import base64
import secrets
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

LARGO_CLAVE = 32
LARGO_FIRMA = 64
LARGO_DESAFIO = 32


class ErrorFirma(Exception):
    """Una clave o firma es inválida."""


# ----------------------------------------------------------------------
# Generación
# ----------------------------------------------------------------------

def generar_par_de_claves() -> tuple[bytes, bytes]:
    """Genera un par nuevo. Devuelve (privada, pública), 32 bytes cada una."""
    privada = Ed25519PrivateKey.generate()
    return (
        privada.private_bytes(
            encoding=Encoding.Raw,
            format=PrivateFormat.Raw,
            encryption_algorithm=NoEncryption(),
        ),
        privada.public_key().public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        ),
    )


def generar_desafio() -> bytes:
    """Genera un valor aleatorio de un solo uso para el saludo.

    Usa `secrets`, no `random`: este último es predecible a partir de
    suficientes salidas y no sirve para nada relacionado con seguridad.
    """
    return secrets.token_bytes(LARGO_DESAFIO)


# ----------------------------------------------------------------------
# Firma y verificación
# ----------------------------------------------------------------------

def material_a_firmar(desafio: bytes, device_id: UUID) -> bytes:
    """Arma el material exacto que se firma.

    Incluye el device_id además del desafío: así una firma obtenida para un
    dispositivo no puede reutilizarse declarando ser otro.
    """
    return b"ABEL-auth-v1|" + desafio + b"|" + device_id.bytes


def firmar(clave_privada: bytes, mensaje: bytes) -> bytes:
    """Firma un mensaje. Devuelve 64 bytes."""
    if len(clave_privada) != LARGO_CLAVE:
        raise ErrorFirma(
            f"La clave privada debe tener {LARGO_CLAVE} bytes, tiene {len(clave_privada)}."
        )
    return Ed25519PrivateKey.from_private_bytes(clave_privada).sign(mensaje)


def verificar(clave_publica: bytes, mensaje: bytes, firma: bytes) -> bool:
    """Verifica una firma. Devuelve True o False; nunca lanza por firma inválida.

    Una firma inválida no es un error del programa: es el resultado normal
    de un intento fallido, y el llamador decide qué hacer con él.
    """
    if len(clave_publica) != LARGO_CLAVE or len(firma) != LARGO_FIRMA:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(clave_publica).verify(firma, mensaje)
        return True
    except (InvalidSignature, ValueError):
        return False


# ----------------------------------------------------------------------
# Codificación para transporte y archivos
# ----------------------------------------------------------------------

def a_texto(datos: bytes) -> str:
    """Codifica bytes en base64 para viajar en JSON o guardarse en archivo."""
    return base64.b64encode(datos).decode("ascii")


def desde_texto(texto: str) -> bytes:
    """Decodifica base64. Falla con mensaje claro si el texto es inválido."""
    try:
        return base64.b64decode(texto, validate=True)
    except (ValueError, TypeError):
        raise ErrorFirma("El valor no es base64 válido.") from None

def material_sesion(desafio: bytes, solicitud_id: UUID, device_id: UUID) -> bytes:
    """Material a firmar para autorizar una sesión de interfaz.

    Prefijo distinto del de autenticación: una firma obtenida en el saludo
    no debe servir para abrir una sesión web, ni al revés. Es la misma
    separación de dominio de material_a_firmar, en otro contexto.
    """
    return (
        b"ABEL-session-v1|"
        + desafio
        + b"|" + solicitud_id.bytes
        + b"|" + device_id.bytes
    )