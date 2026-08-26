"""Lleva las afirmaciones de relación a su forma canónica.

Uso:
    python -m scripts.normalizar_relaciones --simular   # muestra qué cambiaría
    python -m scripts.normalizar_relaciones             # aplica

Arregla lo que quedó guardado al revés desde antes de que existiera
nucleo/memoria/relaciones.py: afirmaciones con un predicado que es la
inversa de uno canónico ("hijo_de" en vez de "padre_de"), o una simétrica
sin ordenar. Por defecto simula: es un script que modifica datos, y mover
sujeto y objeto de una afirmación no es una operación menor.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.memoria.afirmaciones import Afirmaciones, CONFIRMACION_REPETIDA, GENERICOS
from nucleo.memoria.relaciones import CANONICAS, INVERSAS, SIMETRICAS, equivalentes_de, normalizar


async def _nombre(repo: Repositorio, actor_id: UUID) -> str:
    fila = await repo.consultar_una("SELECT name FROM actors WHERE id = %s", (actor_id,))
    return fila["name"] if fila is not None else "?"


async def _candidatas(repo: Repositorio) -> list[dict]:
    """Afirmaciones activas con un predicado del catálogo y objeto-actor.

    Sin object_actor_id no hay nada que invertir: la normalización mueve
    sujeto y objeto entre dos actores, no tiene sentido sobre texto suelto.
    """
    predicados = list(set(INVERSAS) | CANONICAS | SIMETRICAS)
    return await repo.consultar(
        """
        SELECT id, subject_id, predicate, object_actor_id
          FROM assertions
         WHERE retired_at IS NULL
           AND object_actor_id IS NOT NULL
           AND predicate = ANY(%s)
        """,
        (predicados,),
    )


async def _detectar(repo: Repositorio) -> list[dict]:
    """Cuáles cambiarían de forma, y a cuál otra afirmación coincidirían tras cambiar."""
    cambios = []
    for fila in await _candidatas(repo):
        nuevo_sujeto, nuevo_predicado, nuevo_objeto = normalizar(
            fila["subject_id"], fila["predicate"], fila["object_actor_id"]
        )
        if (nuevo_sujeto, nuevo_predicado, nuevo_objeto) == (
            fila["subject_id"], fila["predicate"], fila["object_actor_id"],
        ):
            continue

        # Tras normalizar, puede que ya exista una fila activa igual —
        # la misma relación contada por las dos personas. Si es así, no
        # hay que mover esta: hay que confirmar la que ya está canónica y
        # retirar esta como duplicada.
        equivalente = await repo.consultar_una(
            """
            SELECT id FROM assertions
             WHERE subject_id = %s AND predicate = %s AND object_actor_id = %s
               AND retired_at IS NULL AND id <> %s
            """,
            (nuevo_sujeto, nuevo_predicado, nuevo_objeto, fila["id"]),
        )

        cambios.append({
            "id": fila["id"],
            "predicado_viejo": fila["predicate"],
            "predicado_nuevo": nuevo_predicado,
            "sujeto_viejo": fila["subject_id"],
            "sujeto_nuevo": nuevo_sujeto,
            "objeto_viejo": fila["object_actor_id"],
            "objeto_nuevo": nuevo_objeto,
            "equivalente_id": equivalente["id"] if equivalente is not None else None,
        })
    return cambios


async def _detectar_equivalentes(repo: Repositorio) -> list[dict]:
    """Pares con el mismo sujeto y objeto, pero un predicado equivalente distinto.

    Es el caso que la normalización de dirección no agarra: hijo_de se
    normaliza a padre_de (el genérico) aunque ya hubiera un madre_de para
    el mismo hijo — dos predicados distintos, mismo par de personas, mismo
    rol (ver nucleo/memoria/relaciones.py). afirmar() ya lo evita hacia
    adelante; esto arregla lo que quedó guardado así de antes.
    """
    filas = await repo.consultar(
        """
        SELECT id, subject_id, predicate, object_actor_id, created_at
          FROM assertions
         WHERE retired_at IS NULL AND object_actor_id IS NOT NULL
         ORDER BY subject_id, object_actor_id, created_at
        """
    )

    por_par: dict[tuple, list[dict]] = {}
    for fila in filas:
        clave = (fila["subject_id"], fila["object_actor_id"])
        por_par.setdefault(clave, []).append(fila)

    cambios = []
    for grupo in por_par.values():
        if len({f["predicate"] for f in grupo}) < 2:
            continue

        # Dentro del par, agrupar por conjunto de equivalencia: dos
        # predicados solo importan acá si son formas del mismo rol.
        por_equivalencia: dict[frozenset, list[dict]] = {}
        for fila in grupo:
            por_equivalencia.setdefault(equivalentes_de(fila["predicate"]), []).append(fila)

        for subgrupo in por_equivalencia.values():
            if len({f["predicate"] for f in subgrupo}) < 2:
                continue

            genericas = [f for f in subgrupo if f["predicate"] in GENERICOS]
            especificas = [f for f in subgrupo if f["predicate"] not in GENERICOS]

            if genericas and especificas:
                # Sobrevive lo específico, no lo genérico.
                sobrevive, resto = especificas[0], genericas + especificas[1:]
            else:
                # Ninguna es más genérica que la otra: gana la que ya
                # estaba, como en cualquier afirmar repetido.
                ordenadas = sorted(subgrupo, key=lambda f: f["created_at"])
                sobrevive, resto = ordenadas[0], ordenadas[1:]

            for otra in resto:
                cambios.append({
                    "sobrevive_id": sobrevive["id"],
                    "sobrevive_predicado": sobrevive["predicate"],
                    "retira_id": otra["id"],
                    "retira_predicado": otra["predicate"],
                    "subject_id": otra["subject_id"],
                    "object_actor_id": otra["object_actor_id"],
                })
    return cambios


async def _mostrar_equivalentes(repo: Repositorio, cambios: list[dict]) -> None:
    for c in cambios:
        sujeto = await _nombre(repo, c["subject_id"])
        objeto = await _nombre(repo, c["object_actor_id"])
        print(
            f"  {sujeto} / {c['retira_predicado']} / {objeto}"
            f"  es lo mismo que  {sujeto} / {c['sobrevive_predicado']} / {objeto}"
        )
        print(f"      se confirma {c['sobrevive_predicado']!r} y se retira {c['retira_predicado']!r}.")


async def _aplicar_equivalentes(af: Afirmaciones, cambios: list[dict]) -> None:
    for c in cambios:
        await af.confirmar(
            c["sobrevive_id"], CONFIRMACION_REPETIDA,
            "normalización: ya estaba guardada con un predicado equivalente",
        )
        await af.retirar(
            c["retira_id"],
            f"normalización: es el mismo rol que {c['sobrevive_predicado']}, quedó duplicada",
        )


async def _mostrar(repo: Repositorio, cambios: list[dict]) -> None:
    for c in cambios:
        sujeto_viejo = await _nombre(repo, c["sujeto_viejo"])
        objeto_viejo = await _nombre(repo, c["objeto_viejo"])
        sujeto_nuevo = await _nombre(repo, c["sujeto_nuevo"])
        objeto_nuevo = await _nombre(repo, c["objeto_nuevo"])
        print(
            f"  {sujeto_viejo} / {c['predicado_viejo']} / {objeto_viejo}"
            f"  →  {sujeto_nuevo} / {c['predicado_nuevo']} / {objeto_nuevo}"
        )
        if c["equivalente_id"] is not None:
            print("      ya existe en forma canónica: se confirma esa y se retira esta.")


async def _aplicar(repo: Repositorio, af: Afirmaciones, cambios: list[dict]) -> None:
    for c in cambios:
        if c["equivalente_id"] is not None:
            # La misma relación ya estaba guardada por el otro lado: no se
            # mueve esta, se confirma la que ya es canónica y esta queda
            # retirada, con su historia, como cualquier retiro.
            await af.confirmar(
                c["equivalente_id"], CONFIRMACION_REPETIDA,
                "normalización: ya estaba guardada en forma canónica desde el otro lado",
            )
            await af.retirar(
                c["id"], "normalización: quedó duplicada tras corregir la dirección",
            )
            continue

        await repo.ejecutar(
            """
            UPDATE assertions
               SET subject_id = %s, predicate = %s, object_actor_id = %s, updated_at = now()
             WHERE id = %s
            """,
            (c["sujeto_nuevo"], c["predicado_nuevo"], c["objeto_nuevo"], c["id"]),
        )


async def _main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede escribir
    # caracteres que aparecen en los nombres guardados. Se fuerza UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="python -m scripts.normalizar_relaciones",
        description="Lleva las afirmaciones de relación a su forma canónica.",
    )
    parser.add_argument(
        "--simular", action="store_true",
        help="Muestra qué cambiaría sin tocar la base. Es el comportamiento por default.",
    )
    args = parser.parse_args()

    repo = Repositorio(cargar_config())
    af = Afirmaciones(repo)

    try:
        cambios_direccion = await _detectar(repo)
        cambios_equivalentes = await _detectar_equivalentes(repo)
        total = len(cambios_direccion) + len(cambios_equivalentes)

        if not total:
            print("Nada para normalizar.")
            return 0

        if cambios_direccion:
            print("Dirección al revés:")
            await _mostrar(repo, cambios_direccion)
        if cambios_equivalentes:
            print("\nMismo rol contado dos veces:")
            await _mostrar_equivalentes(repo, cambios_equivalentes)

        if args.simular:
            print(f"\n{total} afirmación(es) cambiarían. Corré sin --simular para aplicar.")
            return 0

        respuesta = input(f"\n¿Aplicar estos {total} cambio(s)? [s/N] ").strip().lower()
        if respuesta != "s":
            print("Cancelado. No se tocó nada.")
            return 0

        await _aplicar(repo, af, cambios_direccion)
        await _aplicar_equivalentes(af, cambios_equivalentes)
        print(f"{total} afirmación(es) normalizadas.")
        return 0
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))
