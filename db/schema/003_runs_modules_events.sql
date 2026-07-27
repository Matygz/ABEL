-- ============================================================
-- 003 — runs, modules, events
-- Fase 0.3 — esquema inicial
-- ============================================================

-- Requerido para la clave foránea compuesta de los subtipos.
ALTER TABLE actors
    ADD CONSTRAINT actors_id_type_unique UNIQUE (id, actor_type);

-- Ejecuciones del Núcleo.
CREATE TABLE runs (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at     TIMESTAMPTZ,
    stop_reason  TEXT,
    pid          INTEGER,
    hostname     TEXT NOT NULL,
    version      TEXT NOT NULL
);

COMMENT ON TABLE runs IS
    'Ejecuciones del Núcleo. ended_at NULL en una corrida no vigente indica caída.';

-- Subtipo de actors: módulos del sistema.
CREATE TABLE modules (
    id           UUID PRIMARY KEY,
    actor_type   TEXT NOT NULL DEFAULT 'module',
    version      TEXT NOT NULL,
    enabled      BOOLEAN NOT NULL DEFAULT true,
    config       JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT modules_type_check CHECK (actor_type = 'module'),
    CONSTRAINT modules_actor_fk
        FOREIGN KEY (id, actor_type) REFERENCES actors (id, actor_type)
);

COMMENT ON TABLE modules IS
    'Subtipo de actors. Comparte id con la fila correspondiente en actors.';

-- Registro central de todo lo que ocurre.
CREATE TABLE events (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    occurred_at  TIMESTAMPTZ NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type   TEXT NOT NULL REFERENCES event_types (name),
    actor_id     UUID NOT NULL REFERENCES actors (id),
    run_id       UUID REFERENCES runs (id),
    payload      JSONB NOT NULL DEFAULT '{}'
);

COMMENT ON TABLE events IS
    'Registro de eventos. occurred_at = cuándo pasó; recorded_at = cuándo se guardó.';

CREATE INDEX events_occurred_at_idx ON events (occurred_at DESC);
CREATE INDEX events_type_idx        ON events (event_type);
CREATE INDEX events_actor_idx       ON events (actor_id);
CREATE INDEX events_run_idx         ON events (run_id);