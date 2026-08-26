"""Corrige actors.name para las personas que quedaron desfasadas.

Uso:
    python -m scripts.resincronizar_nombres --simular   # muestra qué cambiaría
    python -m scripts.resincronizar_nombres             # aplica

Script de una vez. La sincronización normal pasa por
Afirmaciones._sincronizar_nombre en cada afirmar/confirmar/contradecir/
retirar/revivir sobre "se_llama" (ver nucleo/memoria/afirmaciones.py); esto
es solo para arreglar lo que quedó mal desde antes de que existiera eso, o
lo que se haya escrito por fuera de ese camino. Por default simula: es un
script que modifica datos, y aplicar sin querer no tiene vuelta atrás fácil
para una etiqueta que ya se mostró en otro lado.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio


async def _detectar(repo: Repositorio) -> list[dict]:
    personas = await repo.consultar(
        "SELECT id, name FROM actors WHERE actor_type = 'person'"
    )

    desfasados = []
    for persona in personas:
        activa = await repo.consultar_una(
            """
            SELECT object_text FROM assertions
             WHERE subject_id = %s AND predicate = 'se_llama' AND retired_at IS NULL
             ORDER BY confidence DESC LIMIT 1
            """,
            (persona["id"],),
        )
        # Sin afirmación activa de nombre, no hay nada contra qué comparar:
        # se conserva la última etiqueta conocida.
        if activa is None or activa["object_text"] == persona["name"]:
            continue

        desfasados.append({
            "id": persona["id"],
            "nombre_actual": persona["name"],
            "nombre_correcto": activa["object_text"],
        })

    return desfasados


async def _resincronizar(repo: Repositorio, simular: bool) -> int:
    desfasados = await _detectar(repo)

    if not desfasados:
        print("Nada desfasado.")
        return 0

    for d in desfasados:
        print(f'  {d["nombre_actual"]!r} → {d["nombre_correcto"]!r}  (actor {d["id"]})')

    if simular:
        print(f"\n{len(desfasados)} nombre(s) cambiarían. Corré sin --simular para aplicar.")
        return 0

    # Modifica datos: pide confirmación explícita en vez de aplicar directo.
    respuesta = input(f"\n¿Aplicar estos {len(desfasados)} cambio(s)? [s/N] ").strip().lower()
    if respuesta != "s":
        print("Cancelado. No se tocó nada.")
        return 0

    for d in desfasados:
        await repo.ejecutar(
            "UPDATE actors SET name = %s WHERE id = %s",
            (d["nombre_correcto"], d["id"]),
        )

    print(f"{len(desfasados)} nombre(s) actualizados.")
    return 0


async def _main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede escribir
    # caracteres que aparecen en los nombres guardados. Se fuerza UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="python -m scripts.resincronizar_nombres",
        description="Corrige actors.name para que siga a la afirmación se_llama activa.",
    )
    parser.add_argument(
        "--simular", action="store_true",
        help="Muestra qué cambiaría sin tocar la base. Es el comportamiento por default.",
    )
    args = parser.parse_args()

    repo = Repositorio(cargar_config())

    try:
        return await _resincronizar(repo, simular=args.simular)
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))
