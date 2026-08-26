"""Memoria semántica. Necesita PostgreSQL. Ejecutar: python -m tests.test_afirmaciones

La prueba del presupuesto es la más importante: es la que verifica que no
se repita lo de V.0.2, donde todo terminaba cerca de 1 y dejaba de
distinguir nada.
"""

from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid7

import psycopg
from psycopg.rows import dict_row

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.extractor_hechos import ExtractorHechos
from nucleo.memoria.afirmaciones import (
    Afirmaciones,
    CONFIANZA_INICIAL,
    PISO_RETIRO,
    PRESUPUESTO_POR_PREDICADO,
)
from nucleo.memoria.preguntas import Preguntas


async def _actor(repo: Repositorio) -> UUID:
    """Un actor de prueba descartable, para no ensuciar sujetos reales."""
    filas = await repo.ejecutar(
        "INSERT INTO actors (actor_type, name) VALUES ('person', %s) RETURNING id",
        (f"test-{uuid7()}",),
    )
    return filas[0]["id"]


async def _actor_de_nombre(repo: Repositorio, nombre: str, actor_type: str = "person") -> UUID:
    """Como _actor, pero con un nombre elegido — para probar la sincronización."""
    filas = await repo.ejecutar(
        "INSERT INTO actors (actor_type, name) VALUES (%s, %s) RETURNING id",
        (actor_type, nombre),
    )
    return filas[0]["id"]


async def _nombre(repo: Repositorio, actor_id: UUID) -> str:
    fila = await repo.consultar_una("SELECT name FROM actors WHERE id = %s", (actor_id,))
    return fila["name"]


async def _limpiar_nombre(repo: Repositorio, actores: list[UUID]) -> None:
    """Borra lo que crean las pruebas de sincronización de nombre.

    abel_app no tiene DELETE (append-only por diseño), así que se conecta
    como postgres solo para esto — igual que test_inferencia.py.
    """
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
        # Las preguntas primero: origin_assertion_id referencia assertions.
        await conn.execute(
            """
            DELETE FROM open_questions
             WHERE subject_id = ANY(%s)
                OR origin_assertion_id IN (
                    SELECT id FROM assertions
                     WHERE subject_id = ANY(%s) OR object_actor_id = ANY(%s)
                )
            """,
            (actores, actores, actores),
        )
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
        await conn.execute("DELETE FROM users WHERE id = ANY(%s)", (actores,))
        await conn.execute("DELETE FROM actors WHERE id = ANY(%s)", (actores,))
        await conn.commit()


async def _persona(repo: Repositorio, nombre: str | None = None) -> UUID:
    """Una persona con fila en persons, para probar fusión y resolución.

    _actor()/_actor_de_nombre() solo insertan en actors: alcanza para
    sincronización de nombre, pero fusionar()/resolver() leen persons.
    """
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


async def _confidence(repo: Repositorio, assertion_id: UUID) -> float:
    fila = await repo.consultar_una(
        "SELECT confidence FROM assertions WHERE id = %s", (assertion_id,)
    )
    return fila["confidence"]


async def probar_afirmar_nuevo_usa_confianza_de_la_fuente(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    aid = await af.afirmar(
        sujeto, "color_favorito", "azul", "le gusta el azul",
        "told", fuente,
    )
    confianza = await _confidence(repo, aid)
    assert abs(confianza - CONFIANZA_INICIAL["told"]) < 1e-6, confianza


async def probar_afirmar_repetido_confirma_no_duplica(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    id1 = await af.afirmar(sujeto, "vive_en", "cordoba", "vive en mendoza", "told", fuente)
    id2 = await af.afirmar(sujeto, "vive_en", "cordoba", "vive en mendoza", "told", fuente)
    assert id1 == id2

    filas = await repo.consultar(
        "SELECT id FROM assertions WHERE subject_id = %s AND predicate = %s",
        (sujeto, "vive_en"),
    )
    assert len(filas) == 1, "se afirmó lo mismo dos veces y duplicó la fila"


async def probar_confirmar_satura(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    aid = await af.afirmar(sujeto, "predicado_satura", "x", "x", "told", fuente)

    for _ in range(10):
        await af.confirmar(aid, 0.5, "confirmación de prueba")

    confianza = await _confidence(repo, aid)
    assert confianza < 1.0, "diez confirmaciones no deberían clavar en 1.0"
    assert confianza > 0.99, f"deberían acercarlo mucho: quedó en {confianza}"


async def probar_contradecir_baja_y_retira_bajo_el_piso(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    # inferred nace en 0.35: una contradicción fuerte alcanza para tirarla
    # bajo PISO_RETIRO (0.15).
    aid = await af.afirmar(sujeto, "predicado_inferido", "x", "x", "inferred", fuente)

    nueva = await af.contradecir(aid, 0.9, "evidencia en contra")
    assert nueva < PISO_RETIRO

    fila = await repo.consultar_una(
        "SELECT retired_at FROM assertions WHERE id = %s", (aid,)
    )
    assert fila["retired_at"] is not None, "debería haberse retirado sola"


async def probar_revivir_tras_retirada(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    aid = await af.afirmar(sujeto, "predicado_revive", "x", "x", "inferred", fuente)
    await af.retirar(aid, "se descartó a mano para la prueba")

    fila = await repo.consultar_una(
        "SELECT retired_at FROM assertions WHERE id = %s", (aid,)
    )
    assert fila["retired_at"] is not None

    # Apareció evidencia nueva: la confianza sube por fuera del flujo normal
    # (simula lo que hará la extracción en la parte 2), y ahí revivir()
    # limpia el retiro.
    await repo.ejecutar(
        "UPDATE assertions SET confidence = 0.9 WHERE id = %s", (aid,)
    )
    revivio = await af.revivir(aid, "volvió a confirmarse")
    assert revivio

    fila = await repo.consultar_una(
        "SELECT retired_at FROM assertions WHERE id = %s", (aid,)
    )
    assert fila["retired_at"] is None, "debería haber revivido"


async def probar_decaer_baja_lo_viejo_no_lo_reciente(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    viejo = await af.afirmar(sujeto, "predicado_decae_viejo", "x", "x", "inferred", fuente)
    reciente = await af.afirmar(sujeto, "predicado_decae_reciente", "y", "y", "inferred", fuente)

    await repo.ejecutar(
        """
        UPDATE assertions
           SET confirmed_at = now() - INTERVAL '30 days',
               created_at   = now() - INTERVAL '30 days'
         WHERE id = %s
        """,
        (viejo,),
    )

    antes_viejo = await _confidence(repo, viejo)
    antes_reciente = await _confidence(repo, reciente)

    await af.decaer()

    despues_viejo = await _confidence(repo, viejo)
    despues_reciente = await _confidence(repo, reciente)

    assert despues_viejo < antes_viejo, "lo viejo debería haber decaído"
    assert abs(despues_reciente - antes_reciente) < 1e-6, (
        "lo confirmado hace poco no debería tocarse"
    )


async def probar_presupuesto_reescala_y_no_clava_en_uno(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)

    ids = [
        await af.afirmar(sujeto, "predicado_presupuesto", f"valor-{i}", "x", "observed", fuente)
        for i in range(3)
    ]
    for aid in ids:
        for _ in range(5):
            await af.confirmar(aid, 0.9, "confirmación fuerte de prueba")

    confianzas = [await _confidence(repo, aid) for aid in ids]

    assert sum(confianzas) <= PRESUPUESTO_POR_PREDICADO + 1e-6, (
        f"la suma superó el presupuesto: {sum(confianzas)}"
    )
    assert all(c < 1.0 for c in confianzas), (
        "ninguna afirmación del mismo predicado debería clavarse en 1.0"
    )


async def probar_historial_registra_motivo(repo, af):
    sujeto, fuente = await _actor(repo), await _actor(repo)
    aid = await af.afirmar(sujeto, "predicado_historial", "x", "x", "told", fuente)
    await af.confirmar(aid, 0.5, "motivo particular de la prueba")

    eventos = await af.historial(aid)
    assert len(eventos) >= 2, "debería tener al menos created y confirmed"
    assert eventos[0]["kind"] == "created"
    assert eventos[-1]["reason"] == "motivo particular de la prueba"


async def probar_afirmar_se_llama_actualiza_nombre_del_actor(repo, af):
    persona = await _actor_de_nombre(repo, f"mi vieja-{uuid7()}")
    fuente = await _actor(repo)
    try:
        await af.afirmar(
            persona, "se_llama", "Elena", "mi vieja se llama Elena", "told", fuente,
        )
        assert await _nombre(repo, persona) == "Elena"
    finally:
        await _limpiar_nombre(repo, [persona, fuente])


async def probar_corregir_nombre_actualiza_la_etiqueta(repo, af):
    persona = await _actor_de_nombre(repo, f"provisorio-{uuid7()}")
    fuente = await _actor(repo)
    try:
        vieja_id = await af.afirmar(
            persona, "se_llama", "Elena", "se llama Elena", "told", fuente,
        )
        assert await _nombre(repo, persona) == "Elena"

        # Corregir: retira la vieja (evidencia más fuerte, ver corrector.py)
        # y afirma la nueva. La etiqueta debe seguir a la que queda activa.
        await af.contradecir(vieja_id, 0.95, "corregido por la persona")
        await af.afirmar(
            persona, "se_llama", "Marta", "no, se llama Marta", "told", fuente,
        )
        assert await _nombre(repo, persona) == "Marta"
    finally:
        await _limpiar_nombre(repo, [persona, fuente])


async def probar_retirar_unica_afirmacion_de_nombre_no_borra_etiqueta(repo, af):
    persona = await _actor_de_nombre(repo, f"provisorio-{uuid7()}")
    fuente = await _actor(repo)
    try:
        aid = await af.afirmar(
            persona, "se_llama", "Elena", "se llama Elena", "told", fuente,
        )
        await af.retirar(aid, "se retira para la prueba")

        # Sin ninguna afirmación se_llama activa, se conserva la última
        # etiqueta conocida en vez de dejar a la persona sin nombre.
        assert await _nombre(repo, persona) == "Elena"
    finally:
        await _limpiar_nombre(repo, [persona, fuente])


async def probar_dos_nombres_compitiendo_etiqueta_sigue_la_de_mayor_confianza(repo, af):
    persona = await _actor_de_nombre(repo, f"provisorio-{uuid7()}")
    fuente = await _actor(repo)
    try:
        id_elena = await af.afirmar(
            persona, "se_llama", "Elena", "se llama Elena", "told", fuente,
        )
        id_marta = await af.afirmar(
            persona, "se_llama", "Marta", "se llama Marta", "told", fuente,
        )
        # Empatadas en confianza inicial: confirmar una la deja arriba.
        await af.confirmar(id_marta, 0.5, "se confirma Marta")
        assert await _nombre(repo, persona) == "Marta"

        # Si vuelve a subir Elena por encima, la etiqueta la sigue.
        await af.confirmar(id_elena, 0.9, "se confirma Elena con fuerza")
        assert await _nombre(repo, persona) == "Elena"
    finally:
        await _limpiar_nombre(repo, [persona, fuente])


async def probar_afirmar_se_llama_sobre_usuario_no_cambia_nombre(repo, af):
    # Un usuario tiene credenciales atadas a su nombre (users.username): que
    # ABEL lo renombre porque alguien afirma algo sería peligroso, no solo
    # incorrecto. Es la prueba que evita justamente eso.
    usuario = await _actor_de_nombre(repo, f"usuario-{uuid7()}", actor_type="user")
    fuente = await _actor(repo)
    try:
        await af.afirmar(
            usuario, "se_llama", "Otro Nombre", "se llama otro nombre", "told", fuente,
        )
        assert await _nombre(repo, usuario) != "Otro Nombre"
    finally:
        await _limpiar_nombre(repo, [usuario, fuente])


async def probar_fusionar_reapunta_afirmaciones(repo, af):
    duplicada, real, fuente = await _persona(repo), await _persona(repo), await _actor(repo)
    try:
        aid = await af.afirmar(
            duplicada, "vive_en", "Quilmes", "vive en quilmes", "told", fuente,
        )
        await af.fusionar(duplicada, real, "prueba de fusión")

        fila = await repo.consultar_una(
            "SELECT subject_id FROM assertions WHERE id = %s", (aid,)
        )
        assert fila["subject_id"] == real, (
            "la afirmación de la duplicada debería haberse reapuntado a la real"
        )
    finally:
        await _limpiar_nombre(repo, [duplicada, real, fuente])


async def probar_fusionar_marca_no_borra(repo, af):
    duplicada, real = await _persona(repo), await _persona(repo)
    try:
        await af.fusionar(duplicada, real, "motivo de prueba")

        fila = await repo.consultar_una(
            "SELECT merged_into, merged_reason FROM persons WHERE id = %s", (duplicada,)
        )
        assert fila is not None, "la duplicada no debería borrarse, solo marcarse"
        assert fila["merged_into"] == real
        assert fila["merged_reason"] == "motivo de prueba"
    finally:
        await _limpiar_nombre(repo, [duplicada, real])


async def probar_consultar_duplicada_devuelve_las_de_la_real(repo, af):
    duplicada, real, fuente = await _persona(repo), await _persona(repo), await _actor(repo)
    try:
        await af.afirmar(real, "vive_en", "Bernal", "vive en bernal", "told", fuente)
        await af.fusionar(duplicada, real, "prueba de consulta")

        propias = await af.sobre(duplicada)
        assert any(p["object_text"] == "Bernal" for p in propias), (
            "consultar por la duplicada debería devolver lo que cree de la real"
        )
    finally:
        await _limpiar_nombre(repo, [duplicada, real, fuente])


async def probar_fusionar_confirma_equivalentes_no_duplica(repo, af):
    duplicada, real, fuente = await _persona(repo), await _persona(repo), await _actor(repo)
    try:
        await af.afirmar(duplicada, "vive_en", "Mendoza", "vive en mendoza", "told", fuente)
        await af.afirmar(real, "vive_en", "Mendoza", "vive en mendoza", "told", fuente)

        await af.fusionar(duplicada, real, "prueba de equivalentes")

        filas = await repo.consultar(
            """
            SELECT id FROM assertions
             WHERE subject_id = %s AND predicate = 'vive_en' AND object_text = 'Mendoza'
               AND retired_at IS NULL
            """,
            (real,),
        )
        assert len(filas) == 1, (
            f"debería haber quedado una sola afirmación activa, hubo {len(filas)}"
        )
    finally:
        await _limpiar_nombre(repo, [duplicada, real, fuente])


async def probar_dos_padre_de_distintos_se_detectan_como_duplicado(repo, af):
    hablante = await _actor(repo)
    papa1 = await _persona(repo, f"mi papa-{uuid7()}")
    papa2 = await _persona(repo, f"Julio-{uuid7()}")
    try:
        await af.afirmar(
            hablante, "padre_de", "mi papa", "trabajo con mi papa", "told", hablante,
            object_actor_id=papa1,
        )
        await af.afirmar(
            hablante, "padre_de", "Julio", "mi papa es Julio", "told", hablante,
            object_actor_id=papa2,
        )

        duplicados = await af.buscar_duplicados_por_vinculo(hablante)
        assert any(d["predicate"] == "padre_de" for d in duplicados), (
            "dos padre_de con objetos distintos deberían detectarse como duplicado"
        )
    finally:
        await _limpiar_nombre(repo, [hablante, papa1, papa2])


async def probar_dos_hermano_de_distintos_no_se_detectan(repo, af):
    hablante = await _actor(repo)
    hermano1 = await _persona(repo, f"Tomi-{uuid7()}")
    hermano2 = await _persona(repo, f"Facundo-{uuid7()}")
    try:
        await af.afirmar(
            hablante, "hermano_de", "Tomi", "tengo un hermano tomi", "told", hablante,
            object_actor_id=hermano1,
        )
        await af.afirmar(
            hablante, "hermano_de", "Facundo", "tengo otro hermano facundo", "told", hablante,
            object_actor_id=hermano2,
        )

        duplicados = await af.buscar_duplicados_por_vinculo(hablante)
        assert not any(d["predicate"] == "hermano_de" for d in duplicados), (
            "hermano_de admite varios: dos objetos distintos son dos personas, no un duplicado"
        )
    finally:
        await _limpiar_nombre(repo, [hablante, hermano1, hermano2])


async def probar_dos_nombres_propios_no_fusiona_abre_pregunta(repo, af):
    hablante = await _actor(repo)
    nombre_a, nombre_b = f"Julio-{uuid7()}", f"Mario-{uuid7()}"
    persona_a = await _persona(repo, nombre_a)
    persona_b = await _persona(repo, nombre_b)
    preguntas = Preguntas(repo)
    extractor = ExtractorHechos(
        motor=None, afirmaciones=af, preguntas=preguntas, repositorio=repo,
    )
    try:
        await af.afirmar(
            hablante, "padre_de", nombre_a, "mi papa es Julio", "told", hablante,
            object_actor_id=persona_a,
        )
        await af.afirmar(persona_a, "se_llama", nombre_a, "se llama Julio", "told", hablante)
        await af.afirmar(
            hablante, "padre_de", nombre_b, "mi papa es Mario", "told", hablante,
            object_actor_id=persona_b,
        )
        await af.afirmar(persona_b, "se_llama", nombre_b, "se llama Mario", "told", hablante)

        await extractor._resolver_posible_duplicado(hablante, "padre_de")

        marca_a = await repo.consultar_una(
            "SELECT merged_into FROM persons WHERE id = %s", (persona_a,)
        )
        marca_b = await repo.consultar_una(
            "SELECT merged_into FROM persons WHERE id = %s", (persona_b,)
        )
        assert marca_a["merged_into"] is None and marca_b["merged_into"] is None, (
            "con dos nombres propios distintos no debería fusionar solo"
        )

        abiertas = await preguntas.abiertas(hablante)
        assert any("padre_de" in p["question"] for p in abiertas), (
            "debería haber quedado una pregunta abierta sobre cuál es la correcta"
        )
    finally:
        await _limpiar_nombre(repo, [hablante, persona_a, persona_b])


async def probar_resolver_no_entra_en_ciclo_infinito(repo, af):
    a, b = await _persona(repo), await _persona(repo)
    try:
        # Dos personas apuntándose entre sí: una fusión mal hecha a mano, no
        # algo que fusionar() produzca sola. resolver() tiene que cortar en
        # vez de colgarse.
        await repo.ejecutar(
            "UPDATE persons SET merged_into = %s, merged_at = now(), merged_reason = %s WHERE id = %s",
            (b, "ciclo de prueba", a),
        )
        await repo.ejecutar(
            "UPDATE persons SET merged_into = %s, merged_at = now(), merged_reason = %s WHERE id = %s",
            (a, "ciclo de prueba", b),
        )

        resultado = await asyncio.wait_for(af.resolver(a), timeout=5.0)
        assert resultado in (a, b), "debería cortar la cadena y devolver algo, no colgarse"
    finally:
        # Rompe el ciclo antes de limpiar: si no, cualquier borrado que
        # dependiera de seguir merged_into también podría colgarse.
        await repo.ejecutar("UPDATE persons SET merged_into = NULL WHERE id = ANY(%s)", ([a, b],))
        await _limpiar_nombre(repo, [a, b])


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
