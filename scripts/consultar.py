"""Consultas sobre la memoria de ABEL desde la línea de comandos.

Interfaz sobre nucleo/memoria/consultas.py. La lógica vive allá: una interfaz
gráfica futura llamará a los mismos métodos.

Uso:
    python -m scripts.consultar hoy
    python -m scripts.consultar actividad --dias 7
    python -m scripts.consultar sesiones --horas 2
    python -m scripts.consultar estado
    python -m scripts.consultar huecos --dispositivo "Celular-Maty"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.memoria.consultas import Memoria, hoy, ultimas_horas, ultimos_dias
from nucleo.logging_setup import configurar_logging


def _duracion(segundos: float) -> str:
    """Formatea una duración en la unidad que la haga legible."""
    if segundos < 60:
        return f"{segundos:.0f}s"
    if segundos < 3600:
        return f"{segundos / 60:.1f}min"
    return f"{segundos / 3600:.1f}h"


def _hora(momento: datetime | None) -> str:
    if momento is None:
        return "-"
    return momento.astimezone().strftime("%H:%M")


def _fecha_hora(momento: datetime | None) -> str:
    if momento is None:
        return "nunca"
    return momento.astimezone().strftime("%d/%m %H:%M")


def _rango(args) -> tuple[datetime, datetime]:
    if getattr(args, "horas", None):
        return ultimas_horas(args.horas)
    if getattr(args, "dias", None):
        return ultimos_dias(args.dias)
    return hoy()


async def _actividad(memoria: Memoria, args) -> None:
    desde, hasta = _rango(args)
    actividad = await memoria.actividad_por_aplicacion(
        desde, hasta, minimo_segundos=args.minimo
    )

    if not actividad:
        print("Sin actividad registrada en ese período.")
        return

    total = sum(a["segundos"] for a in actividad)
    print(f"\nDesde {_fecha_hora(desde)} hasta {_fecha_hora(hasta)}")
    print(f"Tiempo registrado: {_duracion(total)}\n")

    print(f"{'APLICACIÓN':<24} {'TIEMPO':>9} {'%':>6} {'SESIONES':>9}")
    for a in actividad:
        porcentaje = a["segundos"] / total * 100
        print(
            f"{a['aplicacion'][:24]:<24} {_duracion(a['segundos']):>9} "
            f"{porcentaje:>5.1f}% {a['sesiones']:>9}"
        )


async def _sesiones(memoria: Memoria, args) -> None:
    desde, hasta = _rango(args)
    sesiones = await memoria.sesiones_de_ventana(desde, hasta, limite=args.limite)

    if not sesiones:
        print("Sin sesiones registradas en ese período.")
        return

    print(f"\n{'HORA':<7} {'TIEMPO':>8}  {'APLICACIÓN':<18} TÍTULO")
    for s in sesiones:
        titulo = s["titulo"] or "—"
        print(
            f"{_hora(s['momento']):<7} {_duracion(s['segundos']):>8}  "
            f"{s['aplicacion'][:18]:<18} {titulo[:44]}"
        )


async def _presencia(memoria: Memoria, args) -> None:
    desde, hasta = _rango(args)
    cambios = await memoria.periodos_de_actividad(desde, hasta)

    if not cambios:
        print("Sin cambios de estado registrados en ese período.")
        return

    print("\nCambios de estado. 'idle' indica ausencia de entrada de teclado")
    print("o mouse — no implica que no hubiera nadie.\n")

    print(f"{'HORA':<7} {'ESTADO':<10} DISPOSITIVO")
    for c in cambios:
        print(f"{_hora(c['momento']):<7} {c['estado']:<10} {c['dispositivo']}")


async def _momento(memoria: Memoria, args) -> None:
    try:
        instante = datetime.strptime(args.hora, "%H:%M").time()
    except ValueError:
        print("Formato de hora inválido. Usá HH:MM.", file=sys.stderr)
        return

    hoy_local = datetime.now(timezone.utc).astimezone()
    buscado = hoy_local.replace(
        hour=instante.hour, minute=instante.minute, second=0, microsecond=0
    )
    if args.ayer:
        buscado -= timedelta(days=1)

    resultado = await memoria.que_hacia(buscado)

    if resultado is None:
        print(f"Sin registro de actividad a las {args.hora}.")
        return

    print(f"\nA las {args.hora}:")
    print(f"  aplicación: {resultado['aplicacion']}")
    if resultado["titulo"]:
        print(f"  ventana:    {resultado['titulo']}")
    print(f"  sesión de:  {_duracion(resultado['segundos'])}")


async def _estado(memoria: Memoria, args) -> None:
    estado = await memoria.estado_del_sistema()

    vigente = estado["ejecucion_vigente"]
    print("\nNÚCLEO")
    if vigente is None:
        print("  Sin ejecuciones registradas.")
    else:
        marca = "corriendo" if vigente["activa"] else "detenido"
        print(f"  Estado:  {marca} desde {_fecha_hora(vigente['desde'])}")
    if estado["ejecuciones_caidas"]:
        print(
            f"  Atención: {estado['ejecuciones_caidas']} ejecución(es) "
            f"terminaron sin cerrarse."
        )

    print("\nDISPOSITIVOS")
    for d in estado["dispositivos"]:
        print(
            f"  {d['nombre']:<18} {d['confianza']:<12} "
            f"última señal: {_fecha_hora(d['ultima_senal'])}"
        )

    print(f"\nMEMORIA  ({estado['total_eventos']} eventos)")
    for e in estado["eventos"]:
        print(
            f"  {e['tipo']:<24} {e['cantidad']:>7}   "
            f"{_fecha_hora(e['desde'])} → {_fecha_hora(e['hasta'])}"
        )


async def _huecos(memoria: Memoria, args) -> None:
    dispositivos = await memoria._repo.listar_dispositivos()
    elegido = next(
        (d for d in dispositivos if d["name"] == args.dispositivo), None
    )
    if elegido is None:
        nombres = ", ".join(d["name"] for d in dispositivos)
        print(f"No existe {args.dispositivo!r}. Disponibles: {nombres}",
              file=sys.stderr)
        return

    desde, hasta = _rango(args)
    huecos = await memoria.huecos_de_presencia(
        elegido["id"], desde, hasta, tolerancia_segundos=args.tolerancia
    )

    if not huecos:
        print(f"Sin huecos de presencia para {args.dispositivo} en el período.")
        return

    print(f"\nHuecos de presencia de {args.dispositivo}:\n")
    for h in huecos:
        print(
            f"  {_fecha_hora(h['desde'])} → {_fecha_hora(h['hasta'])}  "
            f"({_duracion(h['segundos'])})"
        )


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.consultar",
        description="Consultas sobre la memoria de ABEL.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    def rango(p):
        p.add_argument("--horas", type=float, help="Últimas N horas.")
        p.add_argument("--dias", type=int, help="Últimos N días.")
        return p

    p = rango(sub.add_parser("actividad", help="Tiempo por aplicación."))
    p.add_argument("--minimo", type=float, default=0.0,
                   help="Omitir apps con menos de N segundos.")
    p.set_defaults(funcion=_actividad)

    p = rango(sub.add_parser("hoy", help="Actividad de hoy."))
    p.add_argument("--minimo", type=float, default=0.0)
    p.set_defaults(funcion=_actividad)

    p = rango(sub.add_parser("sesiones", help="Sesiones de ventana."))
    p.add_argument("--limite", type=int, default=40)
    p.set_defaults(funcion=_sesiones)

    p = rango(sub.add_parser("presencia", help="Cambios de actividad."))
    p.set_defaults(funcion=_presencia)

    p = sub.add_parser("momento", help="Qué había en pantalla a tal hora.")
    p.add_argument("--hora", required=True, help="Formato HH:MM.")
    p.add_argument("--ayer", action="store_true")
    p.set_defaults(funcion=_momento)

    p = sub.add_parser("estado", help="Estado del sistema.")
    p.set_defaults(funcion=_estado)

    p = rango(sub.add_parser("huecos", help="Períodos sin marcas de presencia."))
    p.add_argument("--dispositivo", required=True)
    p.add_argument("--tolerancia", type=float, default=180.0)
    p.set_defaults(funcion=_huecos)

    return parser


async def _main() -> int:
    # La consola de Windows usa cp1252 por defecto y no puede escribir
    # caracteres como → o ·. Se fuerza UTF-8 en la salida.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = _construir_parser().parse_args()
    configurar_logging("WARNING")

    memoria = Memoria(Repositorio(cargar_config()))
    try:
        await args.funcion(memoria, args)
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))