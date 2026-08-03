"""Generación del certificado TLS del Núcleo.

El certificado es la identidad del Núcleo, no de la red: si el Núcleo se
muda a otra máquina o cambia de red, el certificado sigue siendo el mismo.

Es autofirmado: no hay autoridad certificadora externa. Los Nodos confían en
él por fijación (pinning), no por cadena de confianza. Es más estricto que el
modelo de internet — un navegador acepta cualquier certificado firmado por
cualquiera de sus ~150 autoridades; un Nodo de ABEL acepta exactamente uno.

Uso:
    python -m scripts.certificado generar --salida certs/ --dias 365
"""

from __future__ import annotations

import argparse
import datetime
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID

NOMBRE_COMUN = "ABEL Nucleo"
ARCHIVO_CERT = "nucleo.crt"
ARCHIVO_CLAVE = "nucleo.key"


def _construir_sans(direcciones: list[str]) -> list[x509.GeneralName]:
    """Arma la lista de nombres para los que vale el certificado.

    Una IP y un nombre de host se declaran distinto. Incluir varias desde el
    principio evita tener que regenerar el certificado si el Núcleo cambia de
    dirección.
    """
    nombres: list[x509.GeneralName] = []
    for direccion in direcciones:
        try:
            nombres.append(x509.IPAddress(ipaddress.ip_address(direccion)))
        except ValueError:
            nombres.append(x509.DNSName(direccion))
    return nombres


def generar(args) -> None:
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)

    ruta_cert = destino / ARCHIVO_CERT
    ruta_clave = destino / ARCHIVO_CLAVE

    for ruta in (ruta_cert, ruta_clave):
        if ruta.exists():
            print(
                f"Error: {ruta} ya existe.\n"
                f"Regenerar el certificado obliga a actualizar la copia fijada "
                f"en cada Nodo. Movelo antes de continuar.",
                file=sys.stderr,
            )
            sys.exit(1)

    clave = ed25519.Ed25519PrivateKey.generate()

    sujeto = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, NOMBRE_COMUN),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ABEL"),
    ])

    ahora = datetime.datetime.now(datetime.timezone.utc)

    certificado = (
        x509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(sujeto)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(minutes=5))
        .not_valid_after(ahora + datetime.timedelta(days=args.dias))
        .add_extension(
            x509.SubjectAlternativeName(_construir_sans(args.direcciones)),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_cert_sign=False,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(clave, algorithm=None)
    )

    ruta_clave.write_bytes(
        clave.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    ruta_cert.write_bytes(certificado.public_bytes(serialization.Encoding.PEM))

    huella = certificado.fingerprint(hashes.SHA256()).hex(":")

    print(f"\nCertificado generado.")
    print(f"  certificado: {ruta_cert}")
    print(f"  clave:       {ruta_clave}")
    print(f"  válido para: {', '.join(args.direcciones)}")
    print(f"  vence:       {(ahora + datetime.timedelta(days=args.dias)).date()}")
    print(f"\n  huella SHA-256:\n  {huella}")
    print(
        f"\nCopiá {ARCHIVO_CERT} a cada Nodo y referencialo en su configuración."
        f"\nLa clave privada se queda en el Núcleo y no se comparte."
    )


def mostrar(args) -> None:
    ruta = Path(args.archivo)
    if not ruta.exists():
        print(f"Error: no existe {ruta}.", file=sys.stderr)
        sys.exit(1)

    cert = x509.load_pem_x509_certificate(ruta.read_bytes())
    ahora = datetime.datetime.now(datetime.timezone.utc)
    dias = (cert.not_valid_after_utc - ahora).days

    print(f"  sujeto:  {cert.subject.rfc4514_string()}")
    print(f"  desde:   {cert.not_valid_before_utc.date()}")
    print(f"  hasta:   {cert.not_valid_after_utc.date()}  ({dias} días)")

    sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    print(f"  válido para: {', '.join(str(n.value) for n in sans.value)}")
    print(f"  huella SHA-256:\n  {cert.fingerprint(hashes.SHA256()).hex(':')}")

    if dias < 0:
        print("\n  VENCIDO.")
    elif dias < 30:
        print(f"\n  Vence pronto: quedan {dias} días.")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.certificado",
        description="Certificado TLS del Núcleo de ABEL.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_gen = sub.add_parser("generar", help="Genera un certificado autofirmado.")
    p_gen.add_argument("--salida", default="certs",
                       help="Directorio destino (por defecto: certs).")
    p_gen.add_argument("--dias", type=int, default=365,
                       help="Días de validez (por defecto: 365).")
    p_gen.add_argument("--direcciones", nargs="+",
                       default=["127.0.0.1", "localhost", "::1"],
                       help="IPs y nombres para los que vale el certificado.")
    p_gen.set_defaults(funcion=generar)

    p_ver = sub.add_parser("mostrar", help="Muestra los datos de un certificado.")
    p_ver.add_argument("--archivo", default=f"certs/{ARCHIVO_CERT}")
    p_ver.set_defaults(funcion=mostrar)

    args = parser.parse_args()
    args.funcion(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())