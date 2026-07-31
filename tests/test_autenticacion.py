"""El Núcleo debe rechazar credenciales inválidas.

Requiere el Núcleo corriendo. Ejecutar: python -m tests.test_autenticacion
"""

import asyncio
import json
from pathlib import Path
from uuid import uuid7

from websockets.asyncio.client import connect

from protocolos.contenidos import crear_hello, leer_challenge
from protocolos.firma import (
    a_texto,
    desde_texto,
    firmar,
    generar_par_de_claves,
    material_a_firmar,
)
from protocolos.mensajes import TipoMensaje, deserializar

URL = "ws://127.0.0.1:8765"


def _config():
    datos = json.loads(Path("nodo.config.json").read_text(encoding="utf-8"))
    from uuid import UUID
    clave = desde_texto(Path(datos["clave_privada"]).read_text(encoding="ascii").strip())
    return UUID(datos["device_id"]), clave


async def _intentar(device_id, clave_privada, mandar_credencial=True):
    """Ejecuta el saludo completo. Devuelve el tipo del último mensaje."""
    async with connect(URL) as ws:
        await ws.send(crear_hello(device_id, ["presence"], "test").serializar())
        sobre = deserializar(await ws.recv())

        if sobre.tipo != TipoMensaje.CHALLENGE:
            return sobre.tipo

        credencial = None
        if mandar_credencial:
            desafio = desde_texto(leer_challenge(sobre))
            material = material_a_firmar(desafio, device_id)
            credencial = a_texto(firmar(clave_privada, material))

        await ws.send(
            crear_hello(device_id, ["presence"], "test", credencial).serializar()
        )
        return deserializar(await ws.recv()).tipo


async def main():
    device_id, clave_buena = _config()
    clave_mala, _ = generar_par_de_claves()

    resultado = await _intentar(device_id, clave_buena)
    assert resultado == TipoMensaje.WELCOME, f"clave válida dio {resultado}"
    print("ok  clave válida       -> welcome")

    resultado = await _intentar(device_id, clave_mala)
    assert resultado == TipoMensaje.REJECT, f"clave inválida dio {resultado}"
    print("ok  clave inválida     -> reject")

    resultado = await _intentar(device_id, clave_buena, mandar_credencial=False)
    assert resultado == TipoMensaje.REJECT, f"sin credencial dio {resultado}"
    print("ok  sin credencial     -> reject")

    resultado = await _intentar(uuid7(), clave_buena)
    assert resultado == TipoMensaje.REJECT, f"device inexistente dio {resultado}"
    print("ok  device inexistente -> reject")

    print("\nLa autenticación rechaza todo lo que debe rechazar.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)