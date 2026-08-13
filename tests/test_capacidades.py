# tests/test_capacidades.py
"""Descubrimiento de capacidades. Ejecutar: python -m tests.test_capacidades"""

from nucleo.capacidades.registro import RegistroCapacidades


def main():
    # Dependencias falsas: acá solo se prueba el descubrimiento.
    registro = RegistroCapacidades({
        "memoria": object(),
        "llm": object(),
        "repositorio": object(),
    })
    cantidad = registro.descubrir()

    print(f"{cantidad} capacidad(es)\n")
    for c in registro.todas():
        necesita = ", ".join(c.necesita) or "nada"
        print(f"  {c.nombre:<28} {c.tipo:<18} {c.nivel:<8} "
              f"{len(c.ejemplos):>2} ej.  necesita: {necesita}")

    assert cantidad > 0, "no se descubrió ninguna capacidad"


if __name__ == "__main__":
    main()