"""El Nodo debe rechazar un certificado que no sea el del Núcleo.

Requiere el Núcleo corriendo. Ejecutar: python -m tests.test_tls
"""

import asyncio
import json
import ssl
import subprocess
import sys
from pathlib import Path

from websockets.asyncio.client import connect

URL = "wss://localhost:8765"
CERT_FALSO = Path("certs_prueba")


def _contexto(certificado: Path) -> ssl.SSLContext:
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_2
    contexto.load_verify_locations(cafile=str(certificado))
    return contexto


async def _conectar(contexto: ssl.SSLContext) -> str:
    try:
        async with connect(URL, ssl=contexto, open_timeout=5):
            return "conectado"
    except ssl.SSLCertVerificationError as exc:
        return f"rechazado ({exc.verify_message})"
    except Exception as exc:
        return f"error ({type(exc).__name__})"


async def main():
    datos = json.loads(Path("nodo.config.json").read_text(encoding="utf-8"))
    cert_real = Path(datos["certificado_nucleo"])

    resultado = await _conectar(_contexto(cert_real))
    assert resultado == "conectado", f"el certificado real dio: {resultado}"
    print(f"ok  certificado del Núcleo  -> {resultado}")

    subprocess.run(
        [sys.executable, "-m", "scripts.certificado", "generar",
         "--salida", str(CERT_FALSO)],
        check=True, capture_output=True,
    )
    try:
        resultado = await _conectar(_contexto(CERT_FALSO / "nucleo.crt"))
        assert resultado.startswith("rechazado"), f"el falso dio: {resultado}"
        print(f"ok  certificado impostor   -> {resultado}")
    finally:
        for archivo in CERT_FALSO.iterdir():
            archivo.unlink()
        CERT_FALSO.rmdir()

    contexto_abierto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto_abierto.check_hostname = False
    contexto_abierto.verify_mode = ssl.CERT_NONE
    resultado = await _conectar(contexto_abierto)
    print(f"    sin verificación        -> {resultado}")
    print("\n    (esperado: conecta. TLS cifra, pero sin verificar no autentica.)")

    print("\nLa fijación de certificado rechaza impostores.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)