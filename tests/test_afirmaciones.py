"""Memoria semántica. Necesita PostgreSQL. Ejecutar: python -m tests.test_afirmaciones

La prueba del presupuesto es la más importante: es la que verifica que no
se repita lo de V.0.2, donde todo terminaba cerca de 1 y dejaba de
distinguir nada.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid7

from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from nucleo.memoria.afirmaciones import (
    Afirmaciones,
    CONFIANZA_INICIAL,
    PISO_RETIRO,
    PRESUPUESTO_POR_PREDICADO,
)


async def _actor(repo: Repositorio) -> UUID:
    """Un actor de prueba descartable, para no ensuciar sujetos reales."""
    filas = await repo.ejecutar(
        "INSERT INTO actors (actor_type, name) VALUES ('person', %s) RETURNING id",
        (f"test-{uuid7()}",),
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
