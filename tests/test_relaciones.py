"""Relaciones con dirección. Necesita PostgreSQL. Ejecutar: python -m tests.test_relaciones"""

from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid7

import psycopg
from psycopg.rows import dict_row

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.relaciones import normalizar


async def _persona(repo: Repositorio, nombre: str | None = None) -> UUID:
    """Una persona con fila en persons — normalizar()/resolver() la necesitan."""
    filas = await repo.ejecutar(
        """
        WITH nuevo_actor AS (
            INSERT INTO actors (actor_type, name) VALUES ('person', %s) RETURNING id
        )
        INSERT INTO persons (id) SELECT id FROM nuevo_actor
        RETURNING id
        """,
        (nombre or f"test-{uuid7()}",),
    )
    return filas[0]["id"]


async def _limpiar(repo: Repositorio, actores: list[UUID]) -> None:
    """Borra lo que crean las pruebas. abel_app no tiene DELETE, se usa postgres."""
    if not actores:
        return

    conninfo = (
        f"host={os.getenv('ABEL_DB_HOST', '127.0.0.1')} "
        f"port={os.getenv('ABEL_DB_PORT', '5432')} "
        f"dbname={os.getenv('ABEL_DB_NAME', 'abel')} "
        f"user=postgres "
        f"password={os.getenv('ABEL_DB_ROOT_PASSWORD', '')}"
    )
    async with await psycopg.AsyncConnection.connect(
        conninfo, row_factory=dict_row
    ) as conn:
        await conn.execute(
            """
            DELETE FROM assertion_events WHERE assertion_id IN (
                SELECT id FROM assertions
                 WHERE subject_id = ANY(%s) OR object_actor_id = ANY(%s)
            )
            """,
            (actores, actores),
        )
        await conn.execute(
            "DELETE FROM assertions WHERE subject_id = ANY(%s) OR object_actor_id = ANY(%s)",
            (actores, actores),
        )
        await conn.execute("DELETE FROM events WHERE actor_id = ANY(%s)", (actores,))
        await conn.execute("DELETE FROM persons WHERE id = ANY(%s)", (actores,))
        await conn.execute("DELETE FROM actors WHERE id = ANY(%s)", (actores,))
        await conn.commit()


async def probar_normalizar_canonico_no_cambia(repo, af):
    a, b = await _persona(repo), await _persona(repo)
    try:
        sujeto, predicado, objeto = normalizar(a, "padre_de", b)
        assert (sujeto, predicado, objeto) == (a, "padre_de", b)
    finally:
        await _limpiar(repo, [a, b])


async def probar_normalizar_inversa_invierte(repo, af):
    a, b = await _persona(repo), await _persona(repo)
    try:
        # a="hijo_de" b: a es el hijo, b el padre. Canónico: b/padre_de/a.
        sujeto, predicado, objeto = normalizar(a, "hijo_de", b)
        assert (sujeto, predicado, objeto) == (b, "padre_de", a)
    finally:
        await _limpiar(repo, [a, b])


async def probar_simetrica_igual_desde_los_dos_lados(repo, af):
    a, b = await _persona(repo), await _persona(repo)
    try:
        desde_a = normalizar(a, "hermano_de", b)
        desde_b = normalizar(b, "hermano_de", a)
        assert desde_a == desde_b, "la misma relación simétrica debería normalizar igual"
    finally:
        await _limpiar(repo, [a, b])


async def probar_predicado_fuera_del_catalogo_no_se_toca(repo, af):
    a, b = await _persona(repo), await _persona(repo)
    try:
        resultado = normalizar(a, "predicado_inventado", b)
        assert resultado == (a, "predicado_inventado", b)
    finally:
        await _limpiar(repo, [a, b])


async def probar_afirmar_las_dos_formas_produce_una_sola_fila(repo, af):
    hijo, padre = await _persona(repo), await _persona(repo)
    try:
        # "Julio es mi papá": sujeto=padre, predicado=padre_de, objeto=hijo.
        id1 = await af.afirmar(
            padre, "padre_de", "yo", "Julio es mi papá", "told", hijo,
            object_actor_id=hijo,
        )
        # "Soy hijo de Julio": sujeto=hijo, predicado=hijo_de, objeto=padre.
        # Se normaliza a la misma forma canónica: debería confirmar, no duplicar.
        id2 = await af.afirmar(
            hijo, "hijo_de", "Julio", "soy hijo de Julio", "told", hijo,
            object_actor_id=padre,
        )
        assert id1 == id2, "las dos formas de la misma relación deberían ser una sola fila"

        filas = await repo.consultar(
            "SELECT id FROM assertions WHERE predicate IN ('padre_de', 'hijo_de') "
            "AND (subject_id = %s OR subject_id = %s)",
            (padre, hijo),
        )
        assert len(filas) == 1, f"debería haber una sola fila, hubo {len(filas)}"
    finally:
        await _limpiar(repo, [hijo, padre])


async def probar_sobre_devuelve_relaciones_como_objeto_invertidas(repo, af):
    hijo, padre = await _persona(repo), await _persona(repo)
    try:
        await af.afirmar(
            padre, "padre_de", "yo", "Julio es mi papá", "told", hijo,
            object_actor_id=hijo,
        )

        propias = await af.sobre(hijo)
        invertida = next((f for f in propias if f["predicate"] == "hijo_de"), None)
        assert invertida is not None, "sobre(hijo) debería traer la relación invertida"
        assert invertida["object_actor_id"] == padre
    finally:
        await _limpiar(repo, [hijo, padre])


async def probar_derivadas_vienen_marcadas(repo, af):
    hijo, padre = await _persona(repo), await _persona(repo)
    try:
        await af.afirmar(
            padre, "padre_de", "yo", "Julio es mi papá", "told", hijo,
            object_actor_id=hijo,
        )

        propias_de_padre = await af.sobre(padre)
        propia = next(f for f in propias_de_padre if f["predicate"] == "padre_de")
        assert propia["derivada"] is False

        derivadas_de_hijo = await af.sobre(hijo)
        derivada = next(f for f in derivadas_de_hijo if f["predicate"] == "hijo_de")
        assert derivada["derivada"] is True
    finally:
        await _limpiar(repo, [hijo, padre])


async def probar_madre_de_luego_hijo_de_produce_una_sola_fila(repo, af):
    hijo, madre = await _persona(repo), await _persona(repo)
    try:
        await af.afirmar(
            madre, "madre_de", "yo", "mi vieja se llama Marta", "told", hijo,
            object_actor_id=hijo,
        )
        await af.afirmar(
            hijo, "hijo_de", "Marta", "soy hijo de Marta", "told", hijo,
            object_actor_id=madre,
        )

        activas = await repo.consultar(
            "SELECT predicate FROM assertions WHERE subject_id = %s AND object_actor_id = %s "
            "AND retired_at IS NULL",
            (madre, hijo),
        )
        assert len(activas) == 1, f"debería haber una sola fila activa, hubo {len(activas)}"
        assert activas[0]["predicate"] == "madre_de", (
            f"debería sobrevivir lo específico (madre_de), quedó {activas[0]['predicate']}"
        )
    finally:
        await _limpiar(repo, [hijo, madre])


async def probar_hijo_de_luego_madre_de_produce_una_sola_fila(repo, af):
    hijo, madre = await _persona(repo), await _persona(repo)
    try:
        # Orden inverso: primero llega el genérico (hijo_de -> padre_de),
        # después la forma específica. Debería quedar igual que en el
        # orden normal: una sola fila, y sobrevive madre_de.
        await af.afirmar(
            hijo, "hijo_de", "Marta", "soy hijo de Marta", "told", hijo,
            object_actor_id=madre,
        )
        await af.afirmar(
            madre, "madre_de", "yo", "mi vieja se llama Marta", "told", hijo,
            object_actor_id=hijo,
        )

        activas = await repo.consultar(
            "SELECT predicate FROM assertions WHERE subject_id = %s AND object_actor_id = %s "
            "AND retired_at IS NULL",
            (madre, hijo),
        )
        assert len(activas) == 1, f"debería haber una sola fila activa, hubo {len(activas)}"
        assert activas[0]["predicate"] == "madre_de", (
            f"debería sobrevivir lo específico (madre_de), quedó {activas[0]['predicate']}"
        )
    finally:
        await _limpiar(repo, [hijo, madre])


async def probar_hermano_de_y_hermana_de_se_tratan_igual(repo, af):
    a, b = await _persona(repo), await _persona(repo)
    try:
        await af.afirmar(a, "hermano_de", "B", "es mi hermano", "told", a, object_actor_id=b)
        await af.afirmar(a, "hermana_de", "B", "es mi hermana", "told", a, object_actor_id=b)

        # hermano_de/hermana_de son simétricas: se normalizan por UUID, así
        # que hay que buscar la fila activa en cualquiera de los dos
        # sentidos, no asumir quién quedó de sujeto.
        activas = await repo.consultar(
            """
            SELECT predicate FROM assertions
             WHERE predicate IN ('hermano_de', 'hermana_de') AND retired_at IS NULL
               AND ((subject_id = %s AND object_actor_id = %s)
                 OR (subject_id = %s AND object_actor_id = %s))
            """,
            (a, b, b, a),
        )
        assert len(activas) == 1, f"debería haber una sola fila activa, hubo {len(activas)}"
    finally:
        await _limpiar(repo, [a, b])


async def probar_padre_y_madre_de_personas_distintas_no_se_tocan(repo, af):
    papa, mama, hijo = await _persona(repo), await _persona(repo), await _persona(repo)
    try:
        await af.afirmar(
            papa, "padre_de", "yo", "mi papá", "told", hijo, object_actor_id=hijo,
        )
        await af.afirmar(
            mama, "madre_de", "yo", "mi mamá", "told", hijo, object_actor_id=hijo,
        )

        activas = await repo.consultar(
            "SELECT subject_id, predicate FROM assertions "
            "WHERE object_actor_id = %s AND retired_at IS NULL",
            (hijo,),
        )
        assert len(activas) == 2, (
            f"el padre y la madre son dos relaciones legítimas, hubo {len(activas)}"
        )
        predicados = {(f["subject_id"], f["predicate"]) for f in activas}
        assert (papa, "padre_de") in predicados
        assert (mama, "madre_de") in predicados
    finally:
        await _limpiar(repo, [papa, mama, hijo])


async def main() -> None:
    repo = Repositorio(cargar_config())
    af = Afirmaciones(repo)

    pruebas = [v for k, v in globals().items() if k.startswith("probar_")]
    for prueba in sorted(pruebas, key=lambda f: f.__name__):
        await prueba(repo, af)
        print(f"ok  {prueba.__name__}")

    print(f"\n{len(pruebas)} pruebas pasaron.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
