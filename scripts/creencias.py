"""Qué cree ABEL.

Uso:
    python -m scripts.creencias                    # todo lo que cree, por sujeto
    python -m scripts.creencias --sujeto maty       # solo sobre ese actor
    python -m scripts.creencias --retiradas         # incluye las descartadas
    python -m scripts.creencias --historia <id>     # por qué cambió una confianza
    python -m scripts.creencias --preguntas         # lo que ABEL sabe que no sabe
    python -m scripts.creencias --corregidas        # lo que se corrigió, y con qué

Es el control directo del problema de V.0.2: si la distribución de
confianzas se amontona cerca de 1, algo está mal en cómo suben o bajan.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from itertools import groupby
from uuid import UUID

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.logging_setup import configurar_logging
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.preguntas import Preguntas


def _hace(momento: datetime | None) -> str:
    if momento is None:
        return "nunca"
    segundos = (datetime.now(timezone.utc) - momento).total_seconds()
    if segundos < 60:
        return f"{segundos:.0f}s"
    if segundos < 3600:
        return f"{segundos / 60:.0f}min"
    if segundos < 86400:
        return f"{segundos / 3600:.1f}h"
    return f"{segundos / 86400:.1f}d"


def _resumen_distribucion(filas: list[dict]) -> None:
    if not filas:
        print("\nSin afirmaciones todavía.")
        return

    altas = sum(1 for f in filas if f["confidence"] > 0.8)
    medias = sum(1 for f in filas if 0.5 <= f["confidence"] <= 0.8)
    bajas = sum(1 for f in filas if f["confidence"] < 0.5)

    print(f"\nDistribución de confianza ({len(filas)} afirmación(es)):")
    print(f"  > 0.8        {altas}")
    print(f"  0.5 - 0.8    {medias}")
    print(f"  < 0.5        {bajas}")


def _imprimir_por_sujeto(filas: list[dict]) -> None:
    for sujeto, grupo in groupby(filas, key=lambda f: f["sujeto"]):
        print(f"\n{sujeto}")
        for f in grupo:
            estado = " [retirada]" if f.get("retired_at") else ""
            print(
                f"  {f['predicate']:<20} {f['object_text']:<30} "
                f"{f['confidence']:.2f}  {f['source_type']:<10} "
                f"confirmado hace {_hace(f['confirmed_at'])}{estado}"
            )


def _imprimir_preguntas(filas: list[dict]) -> None:
    if not filas:
        print("Sin preguntas abiertas.")
        return

    for f in filas:
        print(
            f"  {f['sujeto']:<12} peso {f['weight']:.2f}  "
            f"abierta hace {_hace(f['created_at'])}  {f['question']}"
            f"  (origen: {f['origin_assertion_id']})"
        )


async def _preguntas(repo: Repositorio) -> int:
    preguntas = Preguntas(repo)
    filas = await preguntas.con_sujeto()
    _imprimir_preguntas(filas)
    return 0


def _imprimir_corregidas(filas: list[dict]) -> None:
    if not filas:
        print("Sin correcciones registradas.")
        return

    for f in filas:
        cuando = f["occurred_at"].astimezone().strftime("%d/%m %H:%M")
        objeto_nuevo = f["objeto_nuevo"] or "(sin dato nuevo)"
        print(
            f"  {cuando}  {f['sujeto']:<12} {f['predicate'] or '':<15} "
            f"{f['objeto_viejo'] or '(sin predicado)':<20} -> {objeto_nuevo:<20} "
            f"«{f['texto']}»"
        )


async def _corregidas(repo: Repositorio) -> int:
    # Cruza el evento assertion_corrected (nucleo/lenguaje/corrector.py)
    # con la afirmación vieja para mostrar sujeto y predicado. La nueva es
    # opcional: una corrección sin dato ("eso está mal") retira sin
    # reemplazar.
    filas = await repo.consultar(
        """
        SELECT e.occurred_at,
               e.payload->>'raw_text' AS texto,
               s.name AS sujeto,
               vieja.predicate,
               vieja.object_text AS objeto_viejo,
               nueva.object_text AS objeto_nuevo
          FROM events e
          JOIN assertions vieja
            ON vieja.id = (e.payload->>'old_assertion_id')::uuid
          JOIN actors s ON s.id = vieja.subject_id
          LEFT JOIN assertions nueva
            ON nueva.id = (e.payload->>'new_assertion_id')::uuid
         WHERE e.event_type = 'assertion_corrected'
         ORDER BY e.occurred_at DESC
        """
    )
    _imprimir_corregidas(filas)
    return 0


async def _historia(repo: Repositorio, assertion_id: UUID) -> int:
    afirmaciones = Afirmaciones(repo)
    eventos = await afirmaciones.historial(assertion_id)
    if not eventos:
        print(f"Sin historial para {assertion_id}. ¿Existe esa afirmación?")
        return 1

    print(f"Historial de {assertion_id}:\n")
    for e in eventos:
        signo = "+" if e["delta"] >= 0 else ""
        print(
            f"  {e['occurred_at'].astimezone().strftime('%d/%m %H:%M')}  "
            f"{e['kind']:<13} {signo}{e['delta']:.2f} -> {e['confidence_after']:.2f}  "
            f"{e['reason']}"
        )
    return 0


async def _main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede escribir
    # caracteres que aparecen en los textos guardados. Se fuerza UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="python -m scripts.creencias",
        description="Qué cree ABEL, y por qué.",
    )
    parser.add_argument("--sujeto", help="Nombre del actor. Sin esto, todos.")
    parser.add_argument(
        "--retiradas", action="store_true", help="Incluir las descartadas."
    )
    parser.add_argument("--historia", help="Id de una afirmación: su historial.")
    parser.add_argument(
        "--preguntas", action="store_true",
        help="Lo que ABEL sabe que no sabe, en vez de lo que cree.",
    )
    parser.add_argument(
        "--corregidas", action="store_true",
        help="Lo que se corrigió: qué creía, qué se corrigió, y con qué texto.",
    )
    args = parser.parse_args()

    configurar_logging("WARNING")
    repo = Repositorio(cargar_config())

    try:
        if args.historia:
            return await _historia(repo, UUID(args.historia))

        if args.preguntas:
            return await _preguntas(repo)

        if args.corregidas:
            return await _corregidas(repo)

        afirmaciones = Afirmaciones(repo)
        filas = await afirmaciones.todas(incluir_retiradas=args.retiradas)
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.sujeto:
        filas = [f for f in filas if f["sujeto"].lower() == args.sujeto.lower()]

    _imprimir_por_sujeto(filas)
    _resumen_distribucion(filas)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))
