"""Extracción de hechos desde conversación.
Necesita PostgreSQL y el modelo de lenguaje. Ejecutar: python -m tests.test_extraccion
"""

from __future__ import annotations

import asyncio
from uuid import uuid4, uuid7

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje.extractor_hechos import ExtractorHechos
from nucleo.lenguaje.motor import MotorLenguaje
from nucleo.lenguaje.servidor_modelo import ServidorModelo
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.preguntas import Preguntas


async def _actor(repo: Repositorio):
    filas = await repo.ejecutar(
        "INSERT INTO actors (actor_type, name) VALUES ('person', %s) RETURNING id",
        (f"test-hablante-{uuid7()}",),
    )
    return filas[0]["id"]


async def probar_frase_con_hecho_produce_afirmacion(repo, extractor):
    hablante = await _actor(repo)
    mensaje = "trabajo en una fábrica de autopartes"

    ids = await extractor.extraer_y_registrar(mensaje, hablante, None)
    assert ids, "debería haber extraído al menos un hecho"

    fila = await repo.consultar_una(
        "SELECT subject_id, predicate, object_text, raw_text FROM assertions WHERE id = %s",
        (ids[0],),
    )
    assert fila["subject_id"] == hablante, "sujeto 'yo' debería resolver a quien habla"
    assert fila["raw_text"] == mensaje, "raw_text debe quedar intacto"
    assert fila["predicate"], "debería tener un predicado"
    assert fila["object_text"], "debería tener un objeto"


async def probar_mensaje_sin_hechos_no_produce_nada(repo, extractor):
    hablante = await _actor(repo)
    ids = await extractor.extraer_y_registrar("hola, ¿qué onda?", hablante, None)
    assert ids == [], f"un saludo no debería afirmar nada, afirmó {ids}"


async def probar_nombre_desconocido_crea_persona_no_usuario(repo, extractor):
    hablante = await _actor(repo)
    nombre = f"Zoraida{uuid4().hex[:6]}"
    mensaje = f"{nombre} trabaja en un banco"

    ids = await extractor.extraer_y_registrar(mensaje, hablante, None)
    assert ids, "debería haber extraído un hecho sobre esa persona"

    fila = await repo.consultar_una(
        "SELECT subject_id FROM assertions WHERE id = %s", (ids[0],)
    )
    actor = await repo.consultar_una(
        "SELECT actor_type FROM actors WHERE id = %s", (fila["subject_id"],)
    )
    assert actor["actor_type"] == "person", (
        f"debería haberse creado como person, fue {actor['actor_type']}"
    )

    es_usuario = await repo.consultar_una(
        "SELECT 1 FROM users WHERE id = %s", (fila["subject_id"],)
    )
    assert es_usuario is None, "extraer un hecho no debe crear un usuario"


async def probar_vinculo_sin_nombre_crea_persona_y_relacion(repo, extractor):
    hablante = await _actor(repo)
    mensaje = "mi hermano vive en Mendoza"

    ids = await extractor.extraer_y_registrar(mensaje, hablante, None)
    assert ids, "debería haber extraído el hecho sobre el hermano"

    fila = await repo.consultar_una(
        "SELECT subject_id FROM assertions WHERE id = %s", (ids[0],)
    )
    persona_id = fila["subject_id"]
    assert persona_id != hablante, "el hecho es sobre el hermano, no sobre quien habla"

    relacion = await repo.consultar_una(
        """
        SELECT id FROM assertions
         WHERE subject_id = %s AND predicate = 'hermano_de' AND object_actor_id = %s
        """,
        (hablante, persona_id),
    )
    assert relacion is not None, "debería haberse registrado hermano_de además del hecho"


async def main() -> None:
    config = cargar_config()
    repo = Repositorio(config)
    motor = MotorLenguaje(f"http://127.0.0.1:{config.llm_puerto}")

    servidor = ServidorModelo(
        ejecutable=config.llm_ejecutable,
        modelo=config.llm_modelo,
        motor=motor,
    )
    await servidor.asegurar_disponible()

    extractor = ExtractorHechos(
        motor=motor,
        afirmaciones=Afirmaciones(repo),
        preguntas=Preguntas(repo),
        repositorio=repo,
    )

    pruebas = [v for k, v in globals().items() if k.startswith("probar_")]
    for prueba in sorted(pruebas, key=lambda f: f.__name__):
        await prueba(repo, extractor)
        print(f"ok  {prueba.__name__}")

    print(f"\n{len(pruebas)} pruebas pasaron.")
    await servidor.cerrar()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
