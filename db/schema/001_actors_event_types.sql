-- ============================================================
-- 001 — actors y event_types
-- Fase 0.3 — esquema inicial
-- ============================================================

-- Toda entidad capaz de causar un evento.
-- Supertipo: modules, devices y users comparten su id con esta tabla.
CREATE TABLE actors (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    actor_type  TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    active      BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT actors_type_valid CHECK (
        actor_type IN ('system', 'module', 'device', 'user')
    ),
    CONSTRAINT actors_name_unique UNIQUE (actor_type, name)
);

COMMENT ON TABLE actors IS
    'Entidades capaces de causar eventos. Supertipo de modules/devices/users.';

-- Catálogo de tipos de evento válidos.
-- Un módulo puede registrar tipos nuevos sin migración.
CREATE TABLE event_types (
    name           TEXT PRIMARY KEY,
    description    TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    registered_by  UUID REFERENCES actors(id)
);

COMMENT ON TABLE event_types IS
    'Tipos de evento válidos. Referenciado por events.event_type.';