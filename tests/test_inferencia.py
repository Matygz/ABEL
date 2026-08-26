"""Inferencia de regularidades y preguntas abiertas. Necesita PostgreSQL.
Ejecutar: python -m tests.test_inferencia

La prueba de la generalización es la más importante conceptualmente: es la
que verifica que un contraejemplo cambia de nivel la inferencia en vez de
descartarla (ver docstring de nucleo/memoria/inferencia.py).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4, uuid7

from nucleo.ciclo import Ciclo
from nucleo.config import cargar_config
from nucleo.datos.repositorio import Repositorio
from comun.sangre import Sangre
from nucleo.memoria.afirmaciones import Afirmaciones
from nucleo.memoria.inferencia import MINIMO_CASOS, MINIMO_DIAS, Inferencia
from nucleo.memoria.preguntas import Preguntas


async def _actor(repo: Repositorio, prefijo: str = "test"):
    filas = await repo.ejecutar(
        "INSERT INTO actors (actor_type, name) VALUES ('person', %s) RETURNING id",
        (f"{prefijo}-{uuid7()}",),
    )
    return filas[0]["id"]


async def _sesion_ventana(repo: Repositorio, actor_id, app: str, cuando, segundos: float):
    await repo.registrar_evento(
        event_type="window_session",
        actor_id=actor_id,
        payload={"application": app, "duration_seconds": segundos},
        occurred_at=cuando,
    )


async def probar_pocos_casos_no_produce_afirmacion(repo, inferencia):
    actor = await _actor(repo)
    app = f"pocacosa-{uuid4().hex[:8]}.exe"

    # Bastante menos que MINIMO_CASOS: no debería alcanzar para inferir nada.
    base = datetime.now(timezone.utc) - timedelta(days=1)
    for i in range(5):
        await _sesion_ventana(
            repo, actor, app, base - timedelta(days=i), 300.0
        )

    await inferencia.correr()

    fila = await repo.consultar_una(
        "SELECT id FROM assertions WHERE object_text = %s AND source_type = 'inferred'",
        (app,),
    )
    assert fila is None, "con pocos casos no debería haberse inferido nada"


async def probar_generalizacion_cuando_falla_el_fino(repo, inferencia):
    app = f"generaliza-{uuid4().hex[:8]}.exe"

    # MINIMO_CASOS + un margen, repartidas entre tres franjas horarias para
    # que ninguna llegue a FUERZA_MINIMA (0.65) — el fino debe fallar. Pero
    # con duración enorme por sesión, para que domine el total de tiempo
    # registrado en la base (que puede tener actividad real de otras
    # pruebas) y el nivel grueso ("usa_mucho") sí se cumpla.
    horas = [8, 14, 22]
    base = datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)

    actor = await _actor(repo)
    total_sesiones = max(MINIMO_CASOS + 3, MINIMO_DIAS + 3)
    for i in range(total_sesiones):
        cuando = (base - timedelta(days=i)).replace(hour=horas[i % len(horas)])
        await _sesion_ventana(repo, actor, app, cuando, 150000.0)

    await inferencia.correr()

    fino = await repo.consultar(
        "SELECT predicate FROM assertions WHERE object_text = %s AND predicate LIKE 'usa_de_%%'",
        (app,),
    )
    assert fino == [], f"el patrón fino no debería haber superado la fuerza mínima: {fino}"

    grueso = await repo.consultar_una(
        "SELECT confidence FROM assertions WHERE object_text = %s AND predicate = 'usa_mucho'",
        (app,),
    )
    assert grueso is not None, (
        "cuando el fino falla por contraejemplos, debería generalizarse a usa_mucho"
    )


async def probar_pregunta_sube_deuda_y_responderla_la_baja(repo, af):
    sangre = Sangre()
    preguntas = Preguntas(repo)
    actor_id = await repo.obtener_actor_id("system", "core")

    ciclo = Ciclo(
        sangre=sangre,
        repositorio=repo,
        actor_id=actor_id,
        run_id=uuid7(),
        afirmaciones=af,
        preguntas=preguntas,
    )

    antes = sangre.leer("deuda")

    sujeto = await _actor(repo, "test-deuda")
    origen_id = await af.afirmar(
        sujeto, "usa_mucho", "app-de-prueba.exe", "raw", "inferred", sujeto
    )
    qid = await preguntas.abrir(
        subject_id=sujeto,
        question="¿a qué se dedica?",
        origin_assertion_id=origen_id,
        weight=0.9,
    )

    await ciclo._deuda_desde_preguntas()
    con_pregunta = sangre.leer("deuda")
    assert con_pregunta > antes, "una pregunta pendiente debería subir la deuda"

    await preguntas.responder(qid, "se aclaró en la prueba")
    await ciclo._deuda_desde_preguntas()
    respondida = sangre.leer("deuda")
    assert respondida < con_pregunta, "responderla debería bajar la deuda de nuevo"


async def main() -> None:
    repo = Repositorio(cargar_config())
    af = Afirmaciones(repo)
    inferencia = Inferencia(repo, af, Preguntas(repo))

    await probar_pocos_casos_no_produce_afirmacion(repo, inferencia)
    print("ok  probar_pocos_casos_no_produce_afirmacion")

    await probar_generalizacion_cuando_falla_el_fino(repo, inferencia)
    print("ok  probar_generalizacion_cuando_falla_el_fino")

    await probar_pregunta_sube_deuda_y_responderla_la_baja(repo, af)
    print("ok  probar_pregunta_sube_deuda_y_responderla_la_baja")

    print("\n3 pruebas pasaron.")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
