"""Pruebas del protocolo. Sin red: solo serialización y validación.

Ejecutar con: python -m tests.test_protocolo
"""

from datetime import datetime, timezone
from uuid import uuid7

from protocolos.mensajes import ErrorProtocolo, TipoMensaje, deserializar
from protocolos.contenidos import (
    Observacion,
    crear_ack,
    crear_hello,
    crear_observation,
    crear_welcome,
    leer_ack,
    leer_hello,
    leer_observation,
    leer_welcome,
)


def _ida_y_vuelta(sobre):
    """Simula el viaje por el cable."""
    return deserializar(sobre.serializar())


def probar_hello():
    dev = uuid7()
    leido = leer_hello(_ida_y_vuelta(crear_hello(dev, ["presence"], "0.0.1")))
    assert leido.device_id == dev
    assert leido.capabilities == ("presence",)
    assert leido.credential is None


def probar_welcome():
    ses = uuid7()
    leido = leer_welcome(_ida_y_vuelta(crear_welcome(ses, "0.0.1", 60, 500)))
    assert leido.session_id == ses
    assert leido.presence_interval_seconds == 60


def probar_observaciones():
    obs = [
        Observacion(uuid7(), datetime.now(timezone.utc), "presence_mark", {"n": i})
        for i in range(3)
    ]
    leidas = leer_observation(_ida_y_vuelta(crear_observation(obs)))
    assert len(leidas) == 3
    assert leidas[0].id == obs[0].id
    assert leidas[0].data["n"] == 0


def probar_ack():
    a, b = uuid7(), uuid7()
    leido = leer_ack(_ida_y_vuelta(crear_ack([a], [(b, "rejected")])))
    assert leido.acknowledged == (a,)
    assert leido.rejected == ((b, "rejected"),)


def probar_rechazos():
    casos = [
        ("no soy json", "JSON"),
        ("{}", "obligatorios"),
        ('{"protocol_version":99,"id":"x","type":"hello","sent_at":"x"}', "99"),
        ('{"protocol_version":1,"id":"x","type":"inventado","sent_at":"x"}', None),
    ]
    for crudo, _ in casos:
        try:
            deserializar(crudo)
            raise AssertionError(f"Debió rechazar: {crudo}")
        except ErrorProtocolo:
            pass


def probar_limite_de_lote():
    obs = [
        Observacion(uuid7(), datetime.now(timezone.utc), "presence_mark", {})
        for _ in range(3)
    ]
    sobre = _ida_y_vuelta(crear_observation(obs))
    try:
        leer_observation(sobre, maximo=2)
        raise AssertionError("Debió rechazar el lote por exceder el máximo.")
    except ErrorProtocolo:
        pass


def probar_booleano_no_es_entero():
    """True es int en Python. El validador no debe aceptarlo como número."""
    from protocolos.mensajes import Sobre

    sobre = _ida_y_vuelta(
        Sobre(
            tipo=TipoMensaje.WELCOME,
            payload={
                "session_id": str(uuid7()),
                "server_version": "0.0.1",
                "presence_interval_seconds": True,
                "max_batch_size": 100,
            },
        )
    )
    try:
        leer_welcome(sobre)
        raise AssertionError("Debió rechazar True como entero.")
    except ErrorProtocolo:
        pass


if __name__ == "__main__":
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("probar_")]
    for prueba in pruebas:
        prueba()
        print(f"ok  {prueba.__name__}")
    print(f"\n{len(pruebas)} pruebas pasaron.")