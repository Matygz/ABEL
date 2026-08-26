"""Corre todas las pruebas.

    python -m tests            solo las que no necesitan servicios
    python -m tests --todas    incluye las que requieren el Núcleo corriendo

Las pruebas se dividen por lo que necesitan: las de protocolo, firma,
patrones y bus son puras y corren siempre. Las demás dependen de la base, del
Núcleo o del modelo, y fallan de forma confusa si eso no está.
"""

from __future__ import annotations

import asyncio
import importlib
import subprocess
import sys
import time
import os

# Pruebas puras: sin base, sin red, sin modelo.
AISLADAS = [
    "test_protocolo",
    "test_firma",
    "test_patrones",
    "test_bus",
    "test_sangre",
    "test_particion",
]

# Necesitan PostgreSQL.
CON_BASE = [
    "test_observaciones",
    "test_afirmaciones",
    "test_inferencia",
]

# Necesitan el Núcleo corriendo.
CON_NUCLEO = [
    "test_rechazo",
    "test_autenticacion",
    "test_tls",
]

# Necesitan el modelo de lenguaje.
CON_MODELO = [
    "test_calculo",
    "test_clasificador",
    "test_conversacion",
    "test_extraccion",
]


def correr(nombre: str, limite: float = 180.0) -> tuple[bool, float]:
    """Ejecuta una prueba en un proceso aparte y devuelve (ok, segundos).

    Proceso aparte para que una prueba que deja algo colgado —un servidor de
    modelo, una conexión— no afecte a las siguientes. Y con límite de tiempo:
    una prueba trabada no debe frenar la corrida entera.
    """

    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    inicio = time.monotonic()

    try:
        resultado = subprocess.run(
            [sys.executable, "-m", f"tests.{nombre}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=entorno,
            timeout=limite,
        )
    except subprocess.TimeoutExpired:
        duracion = time.monotonic() - inicio
        print(f"\n{'─' * 60}")
        print(f"AGOTÓ EL TIEMPO  tests.{nombre} (más de {limite:.0f}s)")
        print(f"{'─' * 60}")
        return False, duracion

    duracion = time.monotonic() - inicio

    if resultado.returncode != 0:
        print(f"\n{'─' * 60}")
        print(f"FALLÓ  tests.{nombre}\n")
        salida = (resultado.stdout + resultado.stderr).strip()
        print(salida[-2000:])
        print(f"{'─' * 60}")

    return resultado.returncode == 0, duracion


def main() -> int:
    todas = "--todas" in sys.argv

    grupos = [("aisladas", AISLADAS)]
    if todas:
        grupos += [
            ("con base", CON_BASE),
            ("con núcleo", CON_NUCLEO),
            ("con modelo", CON_MODELO),
        ]

    fallidas: list[str] = []
    total = 0

    for etiqueta, pruebas in grupos:
        print(f"\n{etiqueta.upper()}")
        for nombre in pruebas:
            ok, segundos = correr(nombre)
            marca = "ok  " if ok else "FALLÓ"
            print(f"  {marca} {nombre:<24} {segundos:>5.1f}s")
            total += 1
            if not ok:
                fallidas.append(nombre)

    print()
    if fallidas:
        print(f"{len(fallidas)} de {total} fallaron: {', '.join(fallidas)}")
        return 1

    print(f"{total} pruebas pasaron.")
    if not todas:
        print("Con --todas se incluyen las que necesitan servicios corriendo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())