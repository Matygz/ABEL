"""Detecta y fusiona personas duplicadas: mismo vínculo único, dos objetos.

Uso:
    python -m scripts.fusionar --detectar          # lista duplicados sin tocar nada
    python -m scripts.fusionar --sujeto maty       # fusiona los de una persona

Por defecto solo detecta. Fusionar pide confirmación explícita: es un
script que modifica datos, y una fusión mal hecha mezcla la historia de
dos personas — mejor mostrar qué tiene cada una antes de decidir.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.memoria.afirmaciones import Afirmaciones


async def _nombre(repo: Repositorio, actor_id: UUID) -> str:
    fila = await repo.consultar_una("SELECT name FROM actors WHERE id = %s", (actor_id,))
    return fila["name"] if fila is not None else "?"


async def _tiene_nombre_propio(repo: Repositorio, actor_id: UUID) -> bool:
    fila = await repo.consultar_una(
        """
        SELECT 1 FROM assertions
         WHERE subject_id = %s AND predicate = 'se_llama' AND retired_at IS NULL
         LIMIT 1
        """,
        (actor_id,),
    )
    return fila is not None


def _actores_del_grupo(grupo: dict) -> list[UUID]:
    """Los object_actor_id distintos de un grupo, en orden de aparición."""
    vistos: list[UUID] = []
    for afirmacion in grupo["afirmaciones"]:
        actor_id = afirmacion["object_actor_id"]
        if actor_id is not None and actor_id not in vistos:
            vistos.append(actor_id)
    return vistos


async def _mostrar_grupo(repo: Repositorio, af: Afirmaciones, sujeto_nombre: str, grupo: dict) -> None:
    print(f"\n{sujeto_nombre} — {grupo['predicate']}:")
    for actor_id in _actores_del_grupo(grupo):
        nombre = await _nombre(repo, actor_id)
        print(f"  {nombre!r}  (actor {actor_id})")
        for propia in await af.sobre(actor_id):
            print(f"      {propia['predicate']} = {propia['object_text']}  ({propia['confidence']:.2f})")


async def _detectar_todos(repo: Repositorio, af: Afirmaciones) -> list[tuple[str, dict]]:
    sujetos = await repo.consultar(
        "SELECT DISTINCT subject_id FROM assertions WHERE retired_at IS NULL"
    )
    hallazgos: list[tuple[str, dict]] = []
    for fila in sujetos:
        for grupo in await af.buscar_duplicados_por_vinculo(fila["subject_id"]):
            hallazgos.append((await _nombre(repo, fila["subject_id"]), grupo))
    return hallazgos


async def _detectar(repo: Repositorio, af: Afirmaciones) -> int:
    hallazgos = await _detectar_todos(repo, af)
    if not hallazgos:
        print("Sin duplicados.")
        return 0

    for sujeto_nombre, grupo in hallazgos:
        await _mostrar_grupo(repo, af, sujeto_nombre, grupo)

    print(f"\n{len(hallazgos)} vínculo(s) con posible duplicado.")
    return 0


async def _fusionar_par(repo: Repositorio, af: Afirmaciones, predicado: str, a_id: UUID, b_id: UUID) -> None:
    a_tiene = await _tiene_nombre_propio(repo, a_id)
    b_tiene = await _tiene_nombre_propio(repo, b_id)

    if a_tiene and b_tiene:
        print("  Las dos tienen nombre propio: no se fusiona solo, hay que revisar a mano.")
        return
    if not a_tiene and not b_tiene:
        print("  Ninguna tiene nombre propio todavía: se espera a que lo tenga.")
        return

    duplicada, real = (b_id, a_id) if a_tiene else (a_id, b_id)
    nombre_dup, nombre_real = await _nombre(repo, duplicada), await _nombre(repo, real)

    respuesta = input(
        f"  ¿Fusionar {nombre_dup!r} ({duplicada}) en {nombre_real!r} ({real})? [s/N] "
    ).strip().lower()
    if respuesta != "s":
        print("  Cancelado.")
        return

    await af.fusionar(duplicada, real, f"fusión manual vía scripts.fusionar ({predicado})")
    print(f"  Fusionado: {nombre_dup!r} → {nombre_real!r}.")


async def _fusionar_sujeto(repo: Repositorio, af: Afirmaciones, nombre_sujeto: str) -> int:
    sujeto = await repo.consultar_una(
        "SELECT id, name FROM actors WHERE lower(name) = %s", (nombre_sujeto.lower(),)
    )
    if sujeto is None:
        print(f"No se encontró un actor llamado {nombre_sujeto!r}.", file=sys.stderr)
        return 1

    duplicados = await af.buscar_duplicados_por_vinculo(sujeto["id"])
    if not duplicados:
        print("Nada para fusionar.")
        return 0

    for grupo in duplicados:
        await _mostrar_grupo(repo, af, sujeto["name"], grupo)
        actores = _actores_del_grupo(grupo)
        if len(actores) < 2:
            continue
        await _fusionar_par(repo, af, grupo["predicate"], actores[0], actores[1])

    return 0


async def _main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede escribir
    # caracteres que aparecen en los nombres guardados. Se fuerza UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="python -m scripts.fusionar",
        description="Detecta y fusiona personas duplicadas por vínculo único.",
    )
    parser.add_argument(
        "--detectar", action="store_true",
        help="Lista duplicados sin tocar nada. Es el comportamiento por default.",
    )
    parser.add_argument("--sujeto", help="Fusiona los duplicados de esta persona, con confirmación.")
    args = parser.parse_args()

    repo = Repositorio(cargar_config())
    af = Afirmaciones(repo)

    try:
        if args.sujeto:
            return await _fusionar_sujeto(repo, af, args.sujeto)
        return await _detectar(repo, af)
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))
