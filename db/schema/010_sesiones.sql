-- ============================================================
-- 010 — sesiones de interfaz
-- Fase 4.1
-- ============================================================

-- Una sesión vincula a una persona con un dispositivo autorizado durante
-- un tiempo. No hay contraseñas: la sesión se establece porque el Nodo del
-- dispositivo firmó un desafío con su clave (ver 0021).
--
-- Se guardan en base, no solo en cookie, para poder listarlas y cerrarlas
-- a distancia: si se pierde un dispositivo, su sesión se revoca desde otro.
CREATE TABLE sessions (
    id            UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id       UUID NOT NULL REFERENCES actors (id),
    device_id     UUID NOT NULL REFERENCES devices (id),

    token_hash    BYTEA NOT NULL,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,

    revoked_at    TIMESTAMPTZ,
    revoked_by    UUID REFERENCES actors (id),

    CONSTRAINT sessions_token_length CHECK (octet_length(token_hash) = 32)
);

COMMENT ON TABLE sessions IS
    'Sesiones de interfaz web. El token nunca se guarda: solo su hash, por
     la misma razón que una contraseña — quien lea la base no debe poder
     hacerse pasar por una sesión activa.';

CREATE UNIQUE INDEX sessions_token_idx ON sessions (token_hash);

CREATE INDEX sessions_activas_idx
    ON sessions (user_id, device_id)
    WHERE revoked_at IS NULL;

INSERT INTO event_types (name, description) VALUES
    ('session_opened',  'Se abrió una sesión de interfaz en un dispositivo.'),
    ('session_closed',  'Se cerró una sesión de interfaz.'),
    ('session_denied',  'Se rechazó un intento de abrir sesión.');