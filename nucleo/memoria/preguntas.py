"""Preguntas abiertas: lo que ABEL sabe que no sabe.

De "programa mucho" no se sigue "es programador" — ese salto ABEL no puede
darlo solo. Pero sí puede saber que le falta una pieza concreta: cuando una
inferencia sobre una conducta supera cierta confianza y ninguna afirmación
explica la causa, queda una pregunta pendiente.

No se pregunta desde acá. Este módulo solo registra que algo falta —
hablar por iniciativa propia es otra fase (ver nucleo/ciclo.py). abrir() y
responder() son las únicas escrituras, y ninguna borra: answered_at marca,
no elimina, igual que retired_at en assertions.

Restricción de diseño: este módulo no le habla al ciclo ni al expresador.
Lo usan nucleo/lenguaje/extractor_hechos.py (para cerrar preguntas cuando
llega la causa) y nucleo/memoria/inferencia.py (para abrirlas); el ciclo
solo lee abiertas() para empujar la sangre.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from nucleo.datos.repositorio import Repositorio

logger = logging.getLogger(__name__)

# Predicados que, al aparecer, explican una conducta inferida. Son pocos y
# conocidos a propósito — igual que PREDICADOS_MULTIPLES en afirmaciones.py,
# hardcodeado por ahora, más adelante debería aprenderse.
CAUSAS_CONOCIDAS = {"trabaja_en", "estudia", "proyecto"}


class Preguntas:
    """Lo que ABEL registra como pendiente, y cuándo deja de estarlo."""

    def __init__(self, repositorio: Repositorio) -> None:
        self._repo = repositorio

    async def abrir(
        self,
        subject_id: UUID,
        question: str,
        origin_assertion_id: UUID,
        weight: float,
    ) -> UUID:
        """Registra una pregunta pendiente. No duplica una igual ya abierta."""
        existente = await self._repo.consultar_una(
            """
            SELECT id FROM open_questions
             WHERE subject_id = %s AND question = %s AND answered_at IS NULL
            """,
            (subject_id, question),
        )
        if existente is not None:
            return existente["id"]

        filas = await self._repo.ejecutar(
            """
            INSERT INTO open_questions
                (subject_id, question, origin_assertion_id, weight)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (subject_id, question, origin_assertion_id, weight),
        )
        question_id = filas[0]["id"]

        await self._repo.registrar_evento(
            event_type="question_opened",
            actor_id=subject_id,
            payload={
                "question_id": str(question_id),
                "question": question,
                "weight": weight,
            },
        )
        return question_id

    async def responder(self, question_id: UUID, motivo: str) -> bool:
        """Marca una pregunta como respondida. Devuelve si hizo algo."""
        filas = await self._repo.ejecutar(
            """
            UPDATE open_questions SET answered_at = now()
             WHERE id = %s AND answered_at IS NULL
            RETURNING subject_id
            """,
            (question_id,),
        )
        if not filas:
            return False

        await self._repo.registrar_evento(
            event_type="question_answered",
            actor_id=filas[0]["subject_id"],
            payload={"question_id": str(question_id), "motivo": motivo},
        )
        return True

    async def responder_por_causa(self, subject_id: UUID, predicate: str) -> int:
        """Cierra las preguntas pendientes de alguien si llegó su causa.

        Se llama después de afirmar() un hecho contado (told). Si el
        predicado nuevo es una causa conocida (trabaja_en, estudia,
        proyecto), cualquier pregunta pendiente sobre esa persona queda
        respondida: ya no falta saber a qué se dedica.
        """
        if predicate not in CAUSAS_CONOCIDAS:
            return 0

        pendientes = await self.abiertas(subject_id)
        cerradas = 0
        for pregunta in pendientes:
            if await self.responder(pregunta["id"], f"cubierta por {predicate}"):
                cerradas += 1
        return cerradas

    async def abiertas(self, subject_id: UUID | None = None) -> list[dict[str, Any]]:
        """Preguntas sin responder, las de más peso primero."""
        condicion = "WHERE answered_at IS NULL"
        parametros: tuple = ()
        if subject_id is not None:
            condicion += " AND subject_id = %s"
            parametros = (subject_id,)

        return await self._repo.consultar(
            f"""
            SELECT id, subject_id, question, origin_assertion_id, weight, created_at
              FROM open_questions
              {condicion}
             ORDER BY weight DESC, created_at
            """,
            parametros,
        )

    async def con_sujeto(self, subject_id: UUID | None = None) -> list[dict[str, Any]]:
        """Como abiertas(), con el nombre del sujeto. Para scripts.creencias."""
        condicion = "WHERE q.answered_at IS NULL"
        parametros: tuple = ()
        if subject_id is not None:
            condicion += " AND q.subject_id = %s"
            parametros = (subject_id,)

        return await self._repo.consultar(
            f"""
            SELECT q.id, s.name AS sujeto, q.question, q.weight,
                   q.created_at, q.origin_assertion_id
              FROM open_questions q
              JOIN actors s ON s.id = q.subject_id
              {condicion}
             ORDER BY q.weight DESC, q.created_at
            """,
            parametros,
        )
