"""Qué pasó adentro de ABEL en un período, sin que nadie mirara.

Lee los eventos que deja nucleo/ciclo.py: internal_pressure (momentos de
presión) e internal_state (instantáneas periódicas de la sangre).

Uso:
    python -m scripts.interior            # últimas 12 horas
    python -m scripts.interior --horas 24
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.logging_setup import configurar_logging


def _hora(momento: datetime) -> str:
    return momento.astimezone().strftime("%d/%m %H:%M")


async def _presiones(repo: Repositorio, desde: datetime) -> list[dict]:
    filas = await repo.consultar(
        "SELECT occurred_at, payload FROM events "
        "WHERE event_type = 'internal_pressure' AND occurred_at >= %s "
        "ORDER BY occurred_at",
        (desde,),
    )
    return filas


async def _estados(repo: Repositorio, desde: datetime) -> list[dict]:
    filas = await repo.consultar(
        "SELECT occurred_at, payload FROM events "
        "WHERE event_type = 'internal_state' AND occurred_at >= %s "
        "ORDER BY occurred_at",
        (desde,),
    )
    return filas


def _resumen_presiones(presiones: list[dict]) -> None:
    if not presiones:
        print("Sin presión registrada en el período: no hubo nada que pensar.")
        return

    con_impulso = sum(1 for p in presiones if p["payload"].get("impulso_hablar"))
    print(f"\nPresión: {len(presiones)} momento(s) por encima del umbral de pensar.")
    print(f"De esos, {con_impulso} superaron el umbral de hablar (sin hablar todavía).")

    causas = Counter(p["payload"]["causa_dominante"] for p in presiones)
    dominante, veces = causas.most_common(1)[0]
    print(f"Causa dominante más frecuente: {dominante} ({veces} de {len(presiones)}).")

    print("\nMomentos de mayor presión:")
    mayores = sorted(presiones, key=lambda p: p["payload"]["presion"], reverse=True)[:5]
    for p in mayores:
        payload = p["payload"]
        print(
            f"  {_hora(p['occurred_at'])}  presión {payload['presion']:.2f}  "
            f"({payload['causa_dominante']})"
        )


def _evolucion(estados: list[dict]) -> None:
    if not estados:
        print("\nSin instantáneas de sangre en el período.")
        return

    print("\nEvolución por hora (nivel de cada valor):\n")
    nombres = sorted(estados[0]["payload"]["sangre"].keys())
    print("  HORA   " + "  ".join(f"{n[:10]:>10}" for n in nombres))
    for e in estados:
        niveles = e["payload"]["sangre"]
        fila = "  ".join(f"{niveles[n]['nivel']:>10.2f}" for n in nombres)
        print(f"  {e['occurred_at'].astimezone().strftime('%H:%M')}   {fila}")


async def _main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede escribir
    # caracteres como → o ·. Se fuerza UTF-8 en la salida.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="python -m scripts.interior",
        description="Qué pasó adentro de ABEL en un período.",
    )
    parser.add_argument("--horas", type=float, default=12.0, help="Últimas N horas.")
    args = parser.parse_args()

    configurar_logging("WARNING")
    repo = Repositorio(cargar_config())
    desde = datetime.now(timezone.utc) - timedelta(hours=args.horas)

    try:
        presiones = await _presiones(repo, desde)
        estados = await _estados(repo, desde)
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Interior de ABEL, últimas {args.horas:.0f}h (desde {_hora(desde)}).")
    _resumen_presiones(presiones)
    _evolucion(estados)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))
