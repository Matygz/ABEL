"""Administración de dispositivos autorizados.

Interfaz de línea de comandos sobre el repositorio. La lógica vive en
nucleo/datos/repositorio.py: una interfaz futura (Fase 4) llamará a los
mismos métodos.

Uso:
    python -m scripts.dispositivos listar
    python -m scripts.dispositivos autorizar --nombre "Celular" \
        --plataforma android --confianza trusted --por maty
    python -m scripts.dispositivos revocar --id <uuid> --por maty \
        --motivo "Extraviado"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from nucleo.config import cargar_config
from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.logging_setup import configurar_logging

NIVELES = ("admin", "trusted", "restricted")


async def _listar(repo: Repositorio, args) -> None:
    dispositivos = await repo.listar_dispositivos(incluir_revocados=args.todos)
    if not dispositivos:
        print("No hay dispositivos registrados.")
        return

    print(f"{'NOMBRE':<20} {'PLATAFORMA':<12} {'CONFIANZA':<12} {'ESTADO':<10} ID")
    for d in dispositivos:
        estado = "revocado" if d["revoked_at"] else "activo"
        print(
            f"{d['name']:<20} {d['platform']:<12} {d['trust_level']:<12} "
            f"{estado:<10} {d['id']}"
        )


async def _autorizar(repo: Repositorio, args) -> None:
    admin = await repo.obtener_usuario_por_username(args.por)

    if admin["role"] != "admin":
        raise ErrorRepositorio(
            f"{args.por!r} tiene rol {admin['role']!r}. "
            f"Autorizar dispositivos requiere rol admin."
        )

    if args.confianza != "restricted":
        print(
            f"\nSe va a autorizar {args.nombre!r} con confianza "
            f"{args.confianza.upper()}."
        )
        if args.confianza == "admin":
            print("Nivel admin: podrá recibir información sensible y solicitar acciones.")
        if input("¿Confirmar? (escribí 'si'): ").strip().lower() != "si":
            print("Cancelado.")
            return

    device_id = await repo.autorizar_dispositivo(
        nombre=args.nombre,
        platform=args.plataforma,
        autorizado_por=admin["id"],
        trust_level=args.confianza,
        politica="manual",
        metadata={"nota": args.nota} if args.nota else None,
    )
    print(f"Autorizado: {args.nombre} -> {device_id}")


async def _revocar(repo: Repositorio, args) -> None:
    admin = await repo.obtener_usuario_por_username(args.por)

    if admin["role"] != "admin":
        raise ErrorRepositorio(
            f"{args.por!r} tiene rol {admin['role']!r}. "
            f"Revocar dispositivos requiere rol admin."
        )

    dispositivo = await repo.obtener_dispositivo(UUID(args.id))
    if dispositivo is None:
        raise ErrorRepositorio(f"No existe el dispositivo {args.id}.")

    print(f"\nSe va a revocar {dispositivo['name']!r}.")
    print("La revocación es permanente hasta que un admin la levante manualmente.")
    if input("¿Confirmar? (escribí 'si'): ").strip().lower() != "si":
        print("Cancelado.")
        return

    await repo.revocar_dispositivo(UUID(args.id), admin["id"], args.motivo)
    print(f"Revocado: {dispositivo['name']}")


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.dispositivos",
        description="Administración de dispositivos autorizados de ABEL.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_listar = sub.add_parser("listar", help="Lista los dispositivos registrados.")
    p_listar.add_argument("--todos", action="store_true",
                          help="Incluir dispositivos revocados.")
    p_listar.set_defaults(funcion=_listar)

    p_auth = sub.add_parser("autorizar", help="Autoriza un dispositivo nuevo.")
    p_auth.add_argument("--nombre", required=True)
    p_auth.add_argument("--plataforma", required=True,
                        help="windows, android, ios, linux, ...")
    p_auth.add_argument("--por", required=True,
                        help="username del admin que autoriza.")
    p_auth.add_argument("--confianza", choices=NIVELES, default="restricted")
    p_auth.add_argument("--nota", help="Nota libre sobre el dispositivo.")
    p_auth.set_defaults(funcion=_autorizar)

    p_rev = sub.add_parser("revocar", help="Revoca un dispositivo.")
    p_rev.add_argument("--id", required=True, help="UUID del dispositivo.")
    p_rev.add_argument("--por", required=True,
                       help="username del admin que revoca.")
    p_rev.add_argument("--motivo", required=True)
    p_rev.set_defaults(funcion=_revocar)

    return parser


async def _main() -> int:
    args = _construir_parser().parse_args()
    configurar_logging("WARNING")

    repo = Repositorio(cargar_config())
    try:
        await args.funcion(repo, args)
    except ErrorRepositorio as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(), loop_factory=asyncio.SelectorEventLoop))