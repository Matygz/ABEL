-- ============================================================
-- 004 — settings
-- Configuración con historial. Nunca se modifica una fila:
-- se cierra la vigente y se inserta la nueva.
-- ============================================================

CREATE TABLE settings (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    changed_by  UUID NOT NULL REFERENCES actors (id),
    reason      TEXT,
    valid_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to    TIMESTAMPTZ
);

COMMENT ON TABLE settings IS
    'Configuración versionada. valid_to NULL indica el valor vigente.';

-- Solo puede haber un valor vigente por clave.
CREATE UNIQUE INDEX settings_current_key_idx
    ON settings (key)
    WHERE valid_to IS NULL;

-- Para consultar el historial de una clave.
CREATE INDEX settings_key_valid_from_idx
    ON settings (key, valid_from DESC);

-- Acceso simplificado a la configuración vigente.
CREATE VIEW current_settings AS
SELECT key, value, changed_by, valid_from
FROM settings
WHERE valid_to IS NULL;

-- Configuración inicial del Núcleo.
INSERT INTO settings (key, value, changed_by, reason)
SELECT
    v.key,
    v.value,
    a.id,
    'Configuración inicial - Fase 0.3'
FROM actors a
CROSS JOIN (VALUES
    ('presence_interval_seconds', '60'::jsonb),
    ('log_level',                 '"INFO"'::jsonb)
) AS v(key, value)
WHERE a.actor_type = 'system' AND a.name = 'core';