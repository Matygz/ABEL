"""Corrección: que ABEL se pueda corregir.
Necesita PostgreSQL y el modelo de lenguaje. Ejecutar: python -m tests.test_correccion

Cada prueba limpia lo que crea: nada de esto debe quedar en la base real.
La limpieza usa una conexión aparte con el usuario root, porque abel_app no
tiene DELETE (append-only por diseño, ver db/schema/005_usuario_aplicacion.sql)
— acá se rompe esa regla a propósito, solo para dejar la base como estaba.
"""

from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid4, uuid7

import psycopg
from psycopg.rows import dict_row

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.corrector import Corrector
from nucleo.lenguaje.extractor_hechos import ExtractorHechos
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.preguntas import Preguntas


async def _actor(repo: Repositorio) -> UUID:
    filas = await repo.ejecutar(
        "INSERT INTO actors (actor_type, name) VALUES ('person', %s) RETURNING id",
        (f"test-hablante-{uuid7()}",),
    )
    return filas[0]["id"]


async def _turno(repo: Repositorio, actor_id: UUID, texto: str, session_id: UUID) -> UUID:
    return await repo.registrar_turno(actor_id, "user", texto, session_id=session_id)


async def _assertion(repo: Repositorio, subject_id: UUID, predicate: str) -> dict:
    fila = await repo.consultar_una(
        """
        SELECT id, object_text, confidence, retired_at FROM assertions
         WHERE subject_id = %s AND predicate = %s
         ORDER BY created_at DESC LIMIT 1
        """,
        (subject_id, predicate),
    )
    assert fila is not None, f"esperaba una afirmación {predicate} para {subject_id}"
    return fila


async def probar_correccion_con_dato_retira_y_registra_nueva(
    repo: Repositorio, extractor: ExtractorHechos, corrector: Corrector, creados: list[UUID],
) -> None:
    hablante = await _actor(repo)
    creados.append(hablante)

    await extractor.extraer_y_registrar("mi vieja se llama Elena", hablante, None)
    vinculo = await _assertion(repo, hablante, "madre_de")
    persona_id = (
        await repo.consultar_una(
            "SELECT object_actor_id FROM assertions WHERE id = %s", (vinculo["id"],)
        )
    )["object_actor_id"]
    vieja_nombre = await _assertion(repo, persona_id, "se_llama")

    await corrector.corregir("no, mi vieja se llama Marta", hablante, None, None)

    vieja_actualizada = await repo.consultar_una(
        "SELECT retired_at FROM assertions WHERE id = %s", (vieja_nombre["id"],)
    )
    assert vieja_actualizada["retired_at"] is not None, (
        "la afirmación vieja (Elena) debería quedar retirada"
    )

    nueva = await repo.consultar_una(
        """
        SELECT object_text, confidence FROM assertions
         WHERE subject_id = %s AND predicate = 'se_llama' AND retired_at IS NULL
        """,
        (persona_id,),
    )
    assert nueva is not None, "debería haber una afirmación nueva y activa"
    assert nueva["object_text"] == "Marta", f"esperaba Marta, fue {nueva['object_text']}"
    assert nueva["confidence"] >= 0.85, (
        f"una corrección debería tener más confianza que un told normal, fue {nueva['confidence']}"
    )


async def probar_vieja_queda_retirada_con_historial(
    repo: Repositorio, extractor: ExtractorHechos, corrector: Corrector, creados: list[UUID],
) -> None:
    hablante = await _actor(repo)
    creados.append(hablante)

    # Sin vínculo, directo sobre quien habla: evita la ambigüedad de que el
    # modelo use dos textos distintos para la misma persona en un mismo
    # mensaje (se vio con "mi hermano"/"Tomi" en frases compuestas), que
    # esta prueba no necesita para verificar el historial.
    await extractor.extraer_y_registrar("estudio ingeniería", hablante, None)
    vieja = await _assertion(repo, hablante, "estudia")

    await corrector.corregir("no, estudio medicina", hablante, None, None)

    afirmaciones = Afirmaciones(repo)
    historial = await afirmaciones.historial(vieja["id"])
    assert historial, "una afirmación retirada debe conservar su historial"
    razones = " ".join(e["reason"] for e in historial)
    assert "corregi" in razones.lower(), (
        f"el historial debería explicar que fue una corrección: {razones!r}"
    )


async def probar_correccion_sin_dato_retira_ultima_de_sesion(
    repo: Repositorio, extractor: ExtractorHechos, corrector: Corrector, creados: list[UUID],
) -> None:
    hablante = await _actor(repo)
    creados.append(hablante)
    session_id = uuid7()

    event_id = await _turno(repo, hablante, "trabajo en una fábrica de autopartes", session_id)
    await extractor.extraer_y_registrar(
        "trabajo en una fábrica de autopartes", hablante, event_id
    )
    vieja = await _assertion(repo, hablante, "trabaja_en")
    assert vieja["retired_at"] is None

    await corrector.corregir("eso está mal", hablante, None, session_id)

    actualizada = await repo.consultar_una(
        "SELECT retired_at FROM assertions WHERE id = %s", (vieja["id"],)
    )
    assert actualizada["retired_at"] is not None, (
        "sin dato nuevo, debería retirar la última afirmación de la sesión"
    )


async def probar_correccion_no_identificable_no_retira_nada_y_abre_pregunta(
    repo: Repositorio, extractor: ExtractorHechos, corrector: Corrector, creados: list[UUID],
) -> None:
    hablante = await _actor(repo)
    creados.append(hablante)
    session_id = uuid7()

    # Una afirmación en la sesión que no tiene nada que ver con lo que se
    # va a "corregir" después: sirve de ancla para la pregunta, no de
    # blanco válido.
    event_id = await _turno(repo, hablante, "trabajo en una fábrica", session_id)
    await extractor.extraer_y_registrar("trabajo en una fábrica", hablante, event_id)
    trabaja = await _assertion(repo, hablante, "trabaja_en")

    # Trae un dato (se_llama Julio) pero el hablante no tiene ninguna
    # afirmación se_llama activa: no hay qué reemplazar. No debe adivinar
    # (por ejemplo, retirando trabaja_en al azar).
    await corrector.corregir("no, se llama Julio", hablante, None, session_id)

    trabaja_actualizada = await repo.consultar_una(
        "SELECT retired_at FROM assertions WHERE id = %s", (trabaja["id"],)
    )
    assert trabaja_actualizada["retired_at"] is None, (
        "no debería haber retirado una afirmación sin relación"
    )

    se_llama = await repo.consultar_una(
        "SELECT id FROM assertions WHERE subject_id = %s AND predicate = 'se_llama'",
        (hablante,),
    )
    assert se_llama is None, "no debería haber creado un se_llama sin poder identificar a quién"

    preguntas = Preguntas(repo)
    abiertas = await preguntas.abiertas(hablante)
    assert abiertas, "debería haber abierto una pregunta sobre lo que no entendió"


async def probar_correccion_no_duplica_afirmaciones(
    repo: Repositorio, extractor: ExtractorHechos, corrector: Corrector, creados: list[UUID],
) -> None:
    hablante = await _actor(repo)
    creados.append(hablante)

    # Sin vínculo, por el mismo motivo que en probar_vieja_queda_retirada_
    # con_historial: acá lo que se prueba es que no queden dos activas, no
    # la reconciliación de vínculos (eso ya lo cubre extractor_hechos).
    await extractor.extraer_y_registrar("vivo en Quilmes", hablante, None)

    await corrector.corregir("no, vivo en Bernal", hablante, None, None)

    activas = await repo.consultar(
        """
        SELECT id FROM assertions
         WHERE subject_id = %s AND predicate = 'vive_en' AND retired_at IS NULL
        """,
        (hablante,),
    )
    assert len(activas) == 1, (
        f"debería haber una sola afirmación vive_en activa, hubo {len(activas)}"
    )


async def _limpiar(creados: list[UUID]) -> None:
    """Borra todo lo que las pruebas crearon. abel_app no tiene DELETE
    (ver db/schema/005_usuario_aplicacion.sql) — se conecta como postgres
    solo para esto."""
    if not creados:
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
        ids = list(creados)
        # Las preguntas se borran antes que las afirmaciones y por las dos
        # vías: por sujeto, y por la afirmación que las originó. Una
        # pregunta puede apuntar a una afirmación cuyo sujeto no está en la
        # lista de creados, y ahí la clave foránea bloquea el borrado.
        await conn.execute(
            """
            DELETE FROM open_questions
             WHERE subject_id = ANY(%s)
                OR origin_assertion_id IN (
                    SELECT id FROM assertions
                     WHERE subject_id = ANY(%s)
                        OR source_actor_id = ANY(%s)
                        OR object_actor_id = ANY(%s)
                )
            """,
            (ids, ids, ids, ids),
        )
        await conn.execute(
            """
            DELETE FROM assertion_events WHERE assertion_id IN (
                SELECT id FROM assertions
                 WHERE subject_id = ANY(%s)
                    OR source_actor_id = ANY(%s)
                    OR object_actor_id = ANY(%s)
            )
            """,
            (ids, ids, ids),
        )
        await conn.execute(
            """
            DELETE FROM assertions
             WHERE subject_id = ANY(%s)
                OR source_actor_id = ANY(%s)
                OR object_actor_id = ANY(%s)
            """,
            (ids, ids, ids),
        )
        await conn.execute("DELETE FROM events WHERE actor_id = ANY(%s)", (ids,))
        await conn.execute("DELETE FROM persons WHERE id = ANY(%s)", (ids,))
        await conn.execute("DELETE FROM actors WHERE id = ANY(%s)", (ids,))
        await conn.commit()


async def main() -> None:
    config = cargar_config()
    repo = Repositorio(config)
    motor = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")

    servidor = ServidorModelo(
        ejecutable=config.llm_ejecutable, modelo=config.llm_modelo, motor=motor,
    )
    await servidor.asegurar_disponible()

    afirmaciones = Afirmaciones(repo)
    preguntas = Preguntas(repo)
    extractor = ExtractorHechos(
        motor=motor, afirmaciones=afirmaciones, preguntas=preguntas, repositorio=repo,
    )
    corrector = Corrector(
        motor=motor, afirmaciones=afirmaciones, preguntas=preguntas, repositorio=repo,
    )

    # Cada prueba agrega acá los actors (hablantes y personas) que crea.
    # Las personas se descubren a través de las afirmaciones de vínculo,
    # pero como object_actor_id apunta a ellas, alcanza con seguir el
    # rastro desde subject_id/source_actor_id al limpiar.
    creados: list[UUID] = []

    pruebas = [v for k, v in globals().items() if k.startswith("probar_")]
    try:
        for prueba in sorted(pruebas, key=lambda f: f.__name__):
            await prueba(repo, extractor, corrector, creados)
            print(f"ok  {prueba.__name__}")

        # Las personas creadas por vínculo no quedan en `creados`
        # directamente (solo los hablantes) — se completan acá antes de
        # limpiar, buscando por source_actor_id.
        extra = await repo.consultar(
            "SELECT DISTINCT subject_id FROM assertions WHERE source_actor_id = ANY(%s)",
            (creados,),
        )
        creados.extend(f["subject_id"] for f in extra if f["subject_id"] not in creados)

        print(f"\n{len(pruebas)} pruebas pasaron.")
    finally:
        await _limpiar(creados)
        await servidor.cerrar()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
