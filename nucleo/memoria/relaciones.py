"""Las relaciones tienen dirección, y dos formas de decirse.

"Soy hijo de Julio" y "Julio es mi papá" son la misma relación. Si cada
una entrara como una fila distinta, ABEL creería dos cosas donde hay una, y
ninguna consulta las juntaría.

La dirección canónica sale de la relación, no de quién la cuenta: de quien
tiene el rol hacia quien lo recibe. `Julio / padre_de / Maty`, sin importar
si lo contó Maty o Julio.

Eso importa cuando hay más de una persona: si la canónica dependiera del
hablante, lo que cuenta Santiago sobre su padre quedaría al revés que lo que
cuenta Maty sobre el suyo, y las dos personas se modelarían distinto.
"""

from __future__ import annotations

from uuid import UUID

# Cada relación apunta a su inversa. El diccionario tiene las dos entradas
# (padre_de -> hijo_de y hijo_de -> padre_de) para que tanto normalizar()
# como una lectura derivada (ver Afirmaciones.sobre) puedan ir en cualquier
# sentido con el mismo mapa.
#
# madre_de y padre_de comparten la misma inversa (hijo_de): "hijo_de" no
# distingue el género de quien lo cuenta. Separarlo en hijo_de_madre /
# hijo_de_padre sería peor que perder esa distinción — nadie habla así, y
# habría que duplicar todo el resto del catálogo. Por eso la vuelta desde
# hijo_de usa padre_de como genérico: si algún día se sabe el género del
# progenitor, se puede afinar, pero mientras tanto no hace falta.
INVERSAS = {
    "padre_de": "hijo_de",
    "madre_de": "hijo_de",
    "hijo_de": "padre_de",
    "abuelo_de": "nieto_de",
    "nieto_de": "abuelo_de",
    "tio_de": "sobrino_de",
    "sobrino_de": "tio_de",
    "jefe_de": "empleado_de",
    "empleado_de": "jefe_de",
    "esposo_de": "esposa_de",
    "esposa_de": "esposo_de",
}

# Relaciones sin jerarquía: la misma vista desde cualquiera de los dos
# lados. Acá no hay "quién tiene el rol" — hace falta un criterio estable
# (el UUID menor como sujeto) para que la misma relación no entre dos veces
# según quién la cuente primero.
SIMETRICAS = frozenset({
    "hermano_de", "hermana_de", "primo_de", "amigo_de",
    "companero_de", "vecino_de", "conoce_a",
})

# Cuál de las dos formas se guarda: la que tiene el rol jerárquico como
# sujeto (el padre es sujeto de padre_de, no el hijo). esposo_de/esposa_de
# están las dos acá porque ninguna es "más canónica" que la otra — a
# diferencia de padre_de/hijo_de, no hay una que sea el genérico y otra la
# derivada; cada una vale como se dijo, y solo se usa la inversa para leer
# desde el otro lado (ver Afirmaciones.sobre).
CANONICAS = frozenset({
    "padre_de", "madre_de", "abuelo_de", "tio_de", "jefe_de",
    "esposo_de", "esposa_de",
})


# Predicados que son formas del mismo rol. Una persona no puede ser padre y
# madre del mismo hijo: si llega una y ya existe la otra, es la misma
# relación dicha de otra forma, no una nueva.
#
# Aparece porque hijo_de no distingue el género del progenitor, y elegir el
# genérico (padre_de) a ciegas creaba una segunda relación donde ya había
# una: se vio a Marta quedando como madre_de y padre_de del mismo hijo.
EQUIVALENTES = (
    frozenset({"padre_de", "madre_de"}),
    frozenset({"hermano_de", "hermana_de"}),
    frozenset({"esposo_de", "esposa_de"}),
)


def equivalentes_de(predicado: str) -> frozenset[str]:
    """Los predicados que cuentan como el mismo rol, incluido el propio.

    Si el predicado no tiene un grupo de equivalencia, el conjunto es solo
    él mismo: "equivalente" sin más compañía sigue siendo un conjunto
    válido para comparar.
    """
    for grupo in EQUIVALENTES:
        if predicado in grupo:
            return grupo
    return frozenset({predicado})


def normalizar(sujeto_id: UUID, predicado: str, objeto_id: UUID) -> tuple[UUID, str, UUID]:
    """Lleva una terna (sujeto, predicado, objeto) a su forma canónica.

    - Si el predicado ya es canónico, se devuelve igual.
    - Si es la inversa de una canónica, se invierten sujeto y objeto y se
      usa el predicado canónico.
    - Si es simétrico, se ordena por UUID para que la misma relación no
      entre dos veces según quién la cuente.
    - Si no está en el catálogo, se devuelve sin tocar: que un predicado no
      esté acá no es un error, el catálogo crece con el tiempo.
    """
    if predicado in SIMETRICAS:
        if objeto_id < sujeto_id:
            return objeto_id, predicado, sujeto_id
        return sujeto_id, predicado, objeto_id

    if predicado in CANONICAS:
        return sujeto_id, predicado, objeto_id

    canonico = INVERSAS.get(predicado)
    if canonico is not None:
        return objeto_id, canonico, sujeto_id

    return sujeto_id, predicado, objeto_id
