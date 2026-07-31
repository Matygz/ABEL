"""Pruebas de firma. Ejecutar: python -m tests.test_firma"""

from uuid import uuid7

from protocolos.firma import (
    a_texto,
    desde_texto,
    firmar,
    generar_desafio,
    generar_par_de_claves,
    material_a_firmar,
    verificar,
)


def probar_firma_valida():
    priv, pub = generar_par_de_claves()
    dev = uuid7()
    material = material_a_firmar(generar_desafio(), dev)
    assert verificar(pub, material, firmar(priv, material))


def probar_clave_equivocada():
    priv, _ = generar_par_de_claves()
    _, otra_pub = generar_par_de_claves()
    material = material_a_firmar(generar_desafio(), uuid7())
    assert not verificar(otra_pub, material, firmar(priv, material))


def probar_desafio_distinto():
    """Una firma capturada no sirve para otro desafío."""
    priv, pub = generar_par_de_claves()
    dev = uuid7()
    firma = firmar(priv, material_a_firmar(generar_desafio(), dev))
    otro = material_a_firmar(generar_desafio(), dev)
    assert not verificar(pub, otro, firma)


def probar_otro_dispositivo():
    """Una firma no sirve declarando ser otro dispositivo."""
    priv, pub = generar_par_de_claves()
    desafio = generar_desafio()
    firma = firmar(priv, material_a_firmar(desafio, uuid7()))
    assert not verificar(pub, material_a_firmar(desafio, uuid7()), firma)


def probar_desafios_no_se_repiten():
    assert len({generar_desafio() for _ in range(1000)}) == 1000


def probar_codificacion():
    _, pub = generar_par_de_claves()
    assert desde_texto(a_texto(pub)) == pub


def probar_basura():
    assert not verificar(b"corta", b"mensaje", b"firma")


if __name__ == "__main__":
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("probar_")]
    for prueba in pruebas:
        prueba()
        print(f"ok  {prueba.__name__}")
    print(f"\n{len(pruebas)} pruebas pasaron.")