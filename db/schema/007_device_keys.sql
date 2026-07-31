-- ============================================================
-- 007 — claves públicas de dispositivos
-- Fase 2.3 — autenticación por firma
-- ============================================================

-- Un dispositivo puede tener varias claves a lo largo del tiempo.
-- Guardar el historial permite auditar qué credencial estaba vigente
-- en cada momento: si una clave se filtra, se puede determinar qué
-- eventos entraron firmados con ella.
CREATE TABLE device_keys (
    id                 UUID PRIMARY KEY DEFAULT uuidv7(),
    device_id          UUID NOT NULL REFERENCES devices (id),
    public_key         BYTEA NOT NULL,
    algorithm          TEXT NOT NULL DEFAULT 'ed25519',
    label              TEXT,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by         UUID NOT NULL REFERENCES actors (id),

    revoked_at         TIMESTAMPTZ,
    revoked_by         UUID REFERENCES actors (id),
    revocation_reason  TEXT,

    CONSTRAINT device_keys_algorithm_valid CHECK (algorithm IN ('ed25519')),
    CONSTRAINT device_keys_length_valid CHECK (octet_length(public_key) = 32)
);

COMMENT ON TABLE device_keys IS
    'Claves públicas de dispositivos. Las claves privadas nunca llegan acá:
     viven solo en el dispositivo y no viajan por la red.';

-- La misma clave pública no puede registrarse dos veces.
CREATE UNIQUE INDEX device_keys_public_key_idx ON device_keys (public_key);

-- Búsqueda de claves vigentes de un dispositivo.
CREATE INDEX device_keys_activas_idx
    ON device_keys (device_id)
    WHERE revoked_at IS NULL;

INSERT INTO event_types (name, description) VALUES
    ('device_key_registered', 'Se registró una clave pública para un dispositivo.'),
    ('device_key_revoked',    'Se revocó una clave pública. El dispositivo no puede autenticarse con ella.'),
    ('auth_failed',           'Un intento de autenticación falló la verificación de firma.');