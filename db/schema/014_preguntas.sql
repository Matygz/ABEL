-- ============================================================
-- 014 — preguntas abiertas
-- Fase 1.3 — memoria semántica (parte 2: extracción, inferencia y preguntas)
-- ============================================================

-- De "programa mucho" no se sigue "es programador": ese salto ABEL no
-- puede darlo solo. Pero sí puede saber que le falta una pieza concreta.
-- Esta tabla registra esa falta — no la pregunta en voz alta, eso es otra
-- fase (ver nucleo/memoria/preguntas.py).
CREATE TABLE open_questions (
    id                   UUID PRIMARY KEY DEFAULT uuidv7(),

    subject_id           UUID NOT NULL REFERENCES actors (id),
    question             TEXT NOT NULL,
    origin_assertion_id  UUID NOT NULL REFERENCES assertions (id),
    weight               REAL NOT NULL,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    answered_at          TIMESTAMPTZ,

    CONSTRAINT open_questions_weight_range CHECK (weight >= 0 AND weight <= 1)
);

COMMENT ON TABLE open_questions IS
    'Lo que a ABEL le falta saber. answered_at no borra: append-only, igual
     que assertions. Se cierra cuando una afirmación nueva cubre la causa.';

CREATE INDEX open_questions_subject_idx ON open_questions (subject_id);

CREATE INDEX open_questions_pendientes_idx
    ON open_questions (subject_id, weight DESC)
    WHERE answered_at IS NULL;

INSERT INTO event_types (name, description) VALUES
    ('question_opened',   'ABEL registró algo que le falta saber, sin preguntarlo.'),
    ('question_answered', 'Una afirmación nueva cubrió la causa de una pregunta pendiente.');

GRANT SELECT, INSERT, UPDATE ON open_questions TO abel_app;
