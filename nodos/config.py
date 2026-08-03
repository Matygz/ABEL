"""Configuración de un Nodo.

Un Nodo no comparte configuración con el Núcleo: en otra máquina ese archivo
no existe. Lee su identidad y su destino de un JSON propio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
from protocolos.firma import LARGO_CLAVE, ErrorFirma, desde_texto

ARCHIVO_POR_DEFECTO = Path("nodo.config.json")


class ErrorConfigNodo(Exception):
    """Falta configuración del Nodo, o es inválida."""


@dataclass(frozen=True)
class ConfigNodo:
    device_id: UUID
    nombre: str
    servidor_url: str
    capabilities: tuple[str, ...]
    clave_privada: bytes
    certificado_nucleo: str
    cola_db: str = "datos/cola.db"
    durabilidad: str = "normal"


def cargar_config(ruta: Path = ARCHIVO_POR_DEFECTO) -> ConfigNodo:
    if not ruta.exists():
        raise ErrorConfigNodo(
            f"No existe {ruta}. Copiá nodo.config.example.json y completalo "
            f"con el UUID que devolvió 'python -m scripts.dispositivos autorizar'."
        )

    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ErrorConfigNodo(f"{ruta} no es JSON válido: {exc}") from None

    faltantes = {"device_id", "nombre", "servidor_url"} - datos.keys()
    if faltantes:
        raise ErrorConfigNodo(f"Faltan campos en {ruta}: {', '.join(sorted(faltantes))}.")

    try:
        device_id = UUID(datos["device_id"])
    except (ValueError, TypeError):
        raise ErrorConfigNodo(f"device_id inválido: {datos['device_id']!r}.") from None

    ruta_clave = datos.get("clave_privada")
    if not ruta_clave:
        raise ErrorConfigNodo(
            f"Falta 'clave_privada' en {ruta}. Generala con: "
            f"python -m scripts.dispositivos generar-clave"
        )

    archivo_clave = Path(ruta_clave)
    if not archivo_clave.exists():
        raise ErrorConfigNodo(f"No existe el archivo de clave: {archivo_clave}")

    try:
        clave = desde_texto(archivo_clave.read_text(encoding="ascii").strip())
    except (ErrorFirma, UnicodeDecodeError) as exc:
        raise ErrorConfigNodo(f"La clave en {archivo_clave} es inválida: {exc}") from None

    if len(clave) != LARGO_CLAVE:
        raise ErrorConfigNodo(
            f"La clave en {archivo_clave} tiene {len(clave)} bytes, "
            f"se esperaban {LARGO_CLAVE}."
        )
    
    cert_nucleo = datos.get("certificado_nucleo")
    if not cert_nucleo:
        raise ErrorConfigNodo(
            f"Falta 'certificado_nucleo' en {ruta}. Copiá certs/nucleo.crt "
            f"desde el Núcleo y apuntá a él."
        )
    if not Path(cert_nucleo).exists():
        raise ErrorConfigNodo(f"No existe el certificado del Núcleo: {cert_nucleo}")
    return ConfigNodo(
        device_id=device_id,
        nombre=datos["nombre"],
        servidor_url=datos["servidor_url"],
        capabilities=tuple(datos.get("capabilities", ["presence"])),
        clave_privada=clave,
        certificado_nucleo=cert_nucleo,
        cola_db=datos.get("cola_db", "datos/cola.db"),
        durabilidad=datos.get("durabilidad", "normal"),
    )