"""Configuración de un Nodo.

Un Nodo no comparte configuración con el Núcleo: en otra máquina ese archivo
no existe. Lee su identidad y su destino de un JSON propio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

ARCHIVO_POR_DEFECTO = Path("nodo.config.json")


class ErrorConfigNodo(Exception):
    """Falta configuración del Nodo, o es inválida."""


@dataclass(frozen=True)
class ConfigNodo:
    device_id: UUID
    nombre: str
    servidor_url: str
    capabilities: tuple[str, ...]


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

    return ConfigNodo(
        device_id=device_id,
        nombre=datos["nombre"],
        servidor_url=datos["servidor_url"],
        capabilities=tuple(datos.get("capabilities", ["presence"])),
    )