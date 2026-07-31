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

from pathlib import Path

from protocolos.firma import a_texto, generar_par_de_claves

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

async def _generar_clave(repo: Repositorio, args) -> None:
    """Genera un par de claves y registra la pública.

    La clave privada se escribe en un archivo y NO se guarda en la base:
    el Núcleo solo conserva la pública. Si el archivo se pierde, hay que
    generar una clave nueva — no hay forma de recuperarla.
    """
    admin = await repo.obtener_usuario_por_username(args.por)
    if admin["role"] != "admin":
        raise ErrorRepositorio(
            f"{args.por!r} tiene rol {admin['role']!r}. "
            f"Registrar claves requiere rol admin."
        )

    device_id = UUID(args.id)
    dispositivo = await repo.obtener_dispositivo(device_id)
    if dispositivo is None:
        raise ErrorRepositorio(f"No existe el dispositivo {args.id}.")

    destino = Path(args.salida)
    if destino.exists():
        raise ErrorRepositorio(
            f"{destino} ya existe. Movelo o elegí otro nombre: sobrescribirlo "
            f"dejaría al dispositivo sin poder autenticarse."
        )

    privada, publica = generar_par_de_claves()

    key_id = await repo.registrar_clave(
        device_id=device_id,
        clave_publica=publica,
        creada_por=admin["id"],
        etiqueta=args.etiqueta,
    )

    destino.write_text(a_texto(privada), encoding="ascii")

    print(f"\nClave registrada para {dispositivo['name']}.")
    print(f"  key_id:  {key_id}")
    print(f"  privada: {destino}")
    print("\nAgregá al archivo de configuración del Nodo:")
    print(f'  "clave_privada": "{destino}"')
    print("\nLa clave privada no está en la base y no se puede recuperar.")


async def _listar_claves(repo: Repositorio, args) -> None:
    claves = await repo.listar_claves(UUID(args.id))
    if not claves:
        print("El dispositivo no tiene claves registradas.")
        return

    print(f"{'ETIQUETA':<20} {'ESTADO':<10} {'CREADA':<20} ID")
    for c in claves:
        estado = "revocada" if c["revoked_at"] else "activa"
        etiqueta = c["label"] or "-"
        creada = c["created_at"].strftime("%Y-%m-%d %H:%M")
        print(f"{etiqueta:<20} {estado:<10} {creada:<20} {c['id']}")

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

    p_clave = sub.add_parser("generar-clave",
                             help="Genera un par de claves para un dispositivo.")
    p_clave.add_argument("--id", required=True, help="UUID del dispositivo.")
    p_clave.add_argument("--por", required=True, help="username del admin.")
    p_clave.add_argument("--salida", required=True,
                         help="Archivo donde escribir la clave privada.")
    p_clave.add_argument("--etiqueta", help="Nombre descriptivo de la clave.")
    p_clave.set_defaults(funcion=_generar_clave)

    p_claves = sub.add_parser("claves", help="Lista las claves de un dispositivo.")
    p_claves.add_argument("--id", required=True, help="UUID del dispositivo.")
    p_claves.set_defaults(funcion=_listar_claves)

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