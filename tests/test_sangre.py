"""La sangre. Ejecutar: python -m tests.test_sangre"""

import tempfile
from pathlib import Path

from comun.sangre import Sangre


def probar_empuje_satura():
    s = Sangre()
    for _ in range(10):
        s.empujar("actividad", 0.5)
    assert s.leer("actividad") < 1.0, "el empujón debería saturar, no clavar en 1"
    assert s.leer("actividad") > 0.99, "diez empujones deberían acercarlo mucho"


def probar_decae_al_reposo():
    s = Sangre()
    s.empujar("actividad", 1.0)
    assert s.leer("actividad") > 0.9

    s["actividad"].avanzar(3600)
    assert s.leer("actividad") < 0.01, "tras una hora debería estar en su reposo"


def probar_reposo_no_siempre_es_cero():
    s = Sangre()
    s["incertidumbre"].avanzar(86400)
    nivel = s.leer("incertidumbre")
    assert 0.2 < nivel < 0.3, f"debería volver a 0.25, volvió a {nivel}"


def probar_tendencia():
    s = Sangre()
    valor = s["actividad"]
    for _ in range(4):
        valor.empujar(0.3)
        valor.avanzar(31)
        valor.leer()
    assert valor.tendencia != 0.0, "con muestras debería haber tendencia"


def probar_dueno_unico():
    s = Sangre()
    try:
        s.registrar("actividad", "otro", "duplicado")
        raise AssertionError("debería haber fallado por dueño repetido")
    except ValueError:
        pass


def probar_persiste():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "sangre.json"

        una = Sangre(ruta)
        una.empujar("coherencia", 0.8)
        antes = una.leer("coherencia")
        una.guardar()

        otra = Sangre(ruta)
        otra.cargar()
        despues = otra.leer("coherencia")

        assert abs(antes - despues) < 0.01, (
            f"la sangre no sobrevivió al reinicio: {antes} -> {despues}"
        )


def main():
    pruebas = [v for k, v in globals().items() if k.startswith("probar_")]
    for prueba in sorted(pruebas, key=lambda f: f.__name__):
        prueba()
        print(f"ok  {prueba.__name__}")
    print(f"\n{len(pruebas)} pruebas pasaron.")


if __name__ == "__main__":
    main()