"""Reconocimiento sin modelo. Ejecutar: python -m tests.test_patrones"""

from nucleo.lenguaje.patrones import reconocer

RECONOCE = [
    ("11 x 11", "11 x 11"),
    ("¿cuánto es 4 x 29?", "4 x 29"),
    ("cuanto es 100/7", "100/7"),
    ("che, calculá 2+2", "2+2"),
    ("(3 + 4) * 2", "(3 + 4) * 2"),
    ("decime cuánto es 15 × 3", "15 × 3"),
]

NO_RECONOCE = [
    "hola",
    "42",
    "me siento como el orto",
    "¿cuánto estuve en Code hoy?",
    "cuánto es el sentido de la vida",
    "tirá 3 dados",
]

def main():
    for texto, esperado in RECONOCE:
        r = reconocer(texto)
        assert r is not None, f"no reconoció: {texto!r}"
        tipo, parametros = r
        assert tipo == "calcular"
        obtenido = parametros["enunciado"]
        assert obtenido == esperado, f"{texto!r} → {obtenido!r} ≠ {esperado!r}"
        print(f"ok   {texto:<30} → {obtenido}")
    print()
    for texto in NO_RECONOCE:
        assert reconocer(texto) is None, f"reconoció de más: {texto!r}"
        print(f"ok   {texto:<30} → pasa a la capa siguiente")

    print(f"\n{len(RECONOCE) + len(NO_RECONOCE)} casos correctos.")


if __name__ == "__main__":
    main()