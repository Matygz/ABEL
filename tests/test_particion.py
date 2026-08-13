"""Corte de mensajes. Ejecutar: python -m tests.test_particion"""

from nucleo.lenguaje.particion import partir

CASOS = [
    # Se parten.
    ("estoy quemado de code hoy, ¿cuánto tiempo estuve?", 2),
    ("estuve laburando un montón. ¿a qué hora arranqué?", 2),
    ("cuánto usé Code y de paso cómo está el sistema", 2),
    # No se parten.
    ("hola, ¿cuánto estuve en Code?", 1),   # el saludo se descarta
    ("estuve todo el día en el código y estoy quemado", 1),
    ("hola", 1),
    ("¿cuánto tiempo estuve en Code hoy?", 1),
    ("me siento como el orto", 1),
    ("hola, ¿qué onda?", 1),
]


def main():
    aciertos = 0
    for mensaje, esperadas in CASOS:
        partes = partir(mensaje)
        ok = len(partes) == esperadas
        aciertos += ok
        marca = "ok  " if ok else "MAL "
        print(f"{marca}{len(partes)}  {mensaje}")
        for p in partes:
            print(f"        · {p}")

    print(f"\n{aciertos} de {len(CASOS)} correctos.")
    

if __name__ == "__main__":
    main()