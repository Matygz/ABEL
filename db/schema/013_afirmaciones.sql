-- ============================================================
-- 013 — afirmaciones
-- Fase 1.3 — memoria semántica (parte 1: almacén y reglas)
-- ============================================================

-- Memoria episódica dice qué pasó y cuándo (events). Esta memoria dice qué
-- es cierto (assertions): una regularidad no tiene fecha porque no ocurrió
-- en un momento — se sostiene o se deja de sostener.

-- ------------------------------------------------------------
-- persons: subtipo de actors, tercer tipo de "quien puede ser
-- sujeto de una afirmación" junto a system/module/device/user.
--
-- Una persona es alguien de quien ABEL sabe cosas. No interactúa
-- con ABEL: eso es lo que distingue a un usuario. Reconocer a
-- alguien no lo convierte en usuario — crear un usuario es un
-- acto humano, no una inferencia.
-- ------------------------------------------------------------
ALTER TABLE actors DROP CONSTRAINT actors_type_valid;
ALTER TABLE actors ADD CONSTRAINT actors_type_valid CHECK (
    actor_type IN ('system', 'module', 'device', 'user', 'person')
);

CREATE TABLE persons (
    id              UUID PRIMARY KEY,
    actor_type      TEXT NOT NULL DEFAULT 'person',

    known_since     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Si en algún momento se reconcilia con un usuario existente (la misma
    -- persona resultó ser alguien que también le habla a ABEL).
    linked_user_id  UUID REFERENCES users (id),
    notes           TEXT,

    CONSTRAINT persons_type_check CHECK (actor_type = 'person'),
    CONSTRAINT persons_actor_fk
        FOREIGN KEY (id, actor_type) REFERENCES actors (id, actor_type)
);

COMMENT ON TABLE persons IS
    'Subtipo de actors. Alguien de quien ABEL sabe cosas, sin que le hable.
     linked_user_id conecta con users si se reconcilia con un usuario real.';

-- ------------------------------------------------------------
-- assertions: una afirmación sobre algo o alguien.
--
-- raw_text no es redundante con predicate/object_text: una estructura mal
-- extraída es irrecuperable, con el original se puede volver a intentar.
--
-- retired_at no borra. Una afirmación descartada queda con su historia: si
-- aparece evidencia nueva la confianza vuelve a subir y se reactiva (ver
-- revivir() en nucleo/memoria/afirmaciones.py), y ABEL puede saber que
-- antes creía algo y dejó de creerlo.
-- ------------------------------------------------------------
CREATE TABLE assertions (
    id                 UUID PRIMARY KEY DEFAULT uuidv7(),

    subject_id         UUID NOT NULL REFERENCES actors (id),
    predicate          TEXT NOT NULL,
    object_text        TEXT NOT NULL,
    -- Si el objeto es a su vez otro actor (p.ej. "trabaja_con" alguien que
    -- ABEL también conoce). Nulable: la mayoría de los objetos son texto.
    object_actor_id    UUID REFERENCES actors (id),
    raw_text           TEXT NOT NULL,

    confidence         REAL NOT NULL,

    source_type        TEXT NOT NULL,
    source_actor_id    UUID NOT NULL REFERENCES actors (id),
    source_event_id    UUID REFERENCES events (id),

    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at       TIMESTAMPTZ,
    retired_at         TIMESTAMPTZ,

    CONSTRAINT assertions_confidence_range CHECK (
        confidence >= 0 AND confidence <= 1
    ),
    CONSTRAINT assertions_source_type_valid CHECK (
        source_type IN ('told', 'observed', 'inferred')
    )
);

COMMENT ON TABLE assertions IS
    'Memoria semántica: qué cree ABEL, no qué pasó. Sin fecha de ocurrencia
     porque una regularidad no ocurre en un momento. retired_at no borra.';

CREATE INDEX assertions_subject_idx ON assertions (subject_id);
CREATE INDEX assertions_subject_predicate_idx ON assertions (subject_id, predicate);

-- Las consultas del día a día (sobre(), buscar_contradicciones(),
-- presupuesto) filtran siempre por "activas". Índice parcial para no
-- pagar el costo de las retiradas en cada una.
CREATE INDEX assertions_activas_idx
    ON assertions (subject_id, predicate)
    WHERE retired_at IS NULL;

-- ------------------------------------------------------------
-- assertion_events: por qué cambió una confianza. Append-only,
-- igual que events. Sin esto no se puede saber por qué ABEL cree
-- lo que cree (principio 7: toda afirmación debe poder citar su
-- fuente y su historia).
-- ------------------------------------------------------------
CREATE TABLE assertion_events (
    id                UUID PRIMARY KEY DEFAULT uuidv7(),
    assertion_id      UUID NOT NULL REFERENCES assertions (id),

    kind              TEXT NOT NULL,
    delta             REAL NOT NULL,
    confidence_after  REAL NOT NULL,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason            TEXT NOT NULL,

    CONSTRAINT assertion_events_kind_valid CHECK (
        kind IN ('created', 'confirmed', 'contradicted', 'decayed',
                 'retired', 'revived')
    )
);

COMMENT ON TABLE assertion_events IS
    'Historial append-only de cambios de confianza. Es lo que permite
     citar por qué ABEL cree algo, no solo qué cree ahora.';

CREATE INDEX assertion_events_assertion_idx
    ON assertion_events (assertion_id, occurred_at);

-- ------------------------------------------------------------
-- Tipos de evento del ciclo de vida de una afirmación.
-- ------------------------------------------------------------
INSERT INTO event_types (name, description) VALUES
    ('assertion_created',    'ABEL registró algo nuevo que cree.'),
    ('assertion_retired',    'Una afirmación cayó por debajo del piso y dejó de considerarse.'),
    ('assertion_revived',    'Una afirmación retirada recuperó confianza y volvió a considerarse.'),
    ('contradiction_found',  'Dos afirmaciones sobre lo mismo no pueden ser ambas ciertas.');

-- ------------------------------------------------------------
-- Permisos. Mismo patrón que 005_usuario_aplicacion.sql: sin DELETE,
-- sin TRUNCATE — append-only por construcción (retirar() actualiza una
-- columna, no borra la fila).
-- ------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON persons, assertions, assertion_events TO abel_app;
