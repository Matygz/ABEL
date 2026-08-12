"""El servidor debe rechazar a un desconocido. Ejecutar: python -m tests.test_rechazo"""

import asyncio
import ssl
from uuid import uuid7

from websockets.asyncio.client import connect

from protocolos.contenidos import crear_hello
from protocolos.mensajes import deserializar

def _contexto():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile="certs/nucleo.crt")
    return ctx

async def main():
    ctx = _contexto()
    async with connect("wss://127.0.0.1:8765", ssl=ctx) as ws:
        await ws.send("esto no es un mensaje válido")
        try:
            await ws.recv()
            print("FALLO: el servidor no cerró.")
        except Exception as exc:
            print("basura rechazada ok:", type(exc).__name__)

    async with connect("wss://127.0.0.1:8765", ssl=ctx) as ws:
        await ws.send(crear_hello(uuid7(), ["presence"], "0.0.1").serializar())
        respuesta = deserializar(await ws.recv())
        print("dispositivo desconocido ->", respuesta.tipo, respuesta.payload)


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)