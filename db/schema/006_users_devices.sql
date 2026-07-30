-- ============================================================
-- 006 — users y devices
-- Fase 2.1 — segundo y tercer subtipo de actors
-- ============================================================

-- ------------------------------------------------------------
-- Los nombres de persona se repiten en el mundo real. La unicidad
-- de actors.name deja de aplicar a los usuarios: su identificador
-- único es users.username, y actors.name pasa a ser un apodo.
-- ------------------------------------------------------------
ALTER TABLE actors DROP CONSTRAINT actors_name_unique;

CREATE UNIQUE INDEX actors_name_unique_idx
    ON actors (actor_type, name)
    WHERE actor_type <> 'user';

-- ------------------------------------------------------------
-- users: personas que interactúan con ABEL.
-- Subtipo de actors (ver decisión 0004).
--
-- Tres identificadores distintos, deliberadamente separados:
--   actors.id    → identidad. Único, inmutable, es a lo que apuntan los eventos.
--   username     → identificador de autenticación. Único, estable, elegido.
--   full_name    → nombre real. Puede repetirse.
--   actors.name  → nombre para mostrar. Apodo.
-- ------------------------------------------------------------
CREATE TABLE users (
    id          UUID PRIMARY KEY,
    actor_type  TEXT NOT NULL DEFAULT 'user',
    username    TEXT NOT NULL UNIQUE,
    full_name   TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'standard',
    metadata    JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT users_type_check CHECK (actor_type = 'user'),
    CONSTRAINT users_role_valid CHECK (
        role IN ('admin', 'standard', 'guest')
    ),
    CONSTRAINT users_actor_fk
        FOREIGN KEY (id, actor_type) REFERENCES actors (id, actor_type)
);

COMMENT ON TABLE users IS
    'Personas. Subtipo de actors. Solo el rol admin puede elevar la confianza
     de un dispositivo o levantar una revocación. ABEL no crea usuarios.';

-- ------------------------------------------------------------
-- Usuario administrador inicial.
-- ------------------------------------------------------------
WITH nuevo_actor AS (
    INSERT INTO actors (actor_type, name)
    VALUES ('user', 'Maty')
    RETURNING id
)
INSERT INTO users (id, username, full_name, role)
SELECT id, 'maty', 'Matias Ivan Gonzalez', 'admin' FROM nuevo_actor;

-- ------------------------------------------------------------
-- devices: dispositivos autorizados. Órganos sensoriales.
-- No poseen cognición: capturan, almacenan en cola y transmiten.
-- ------------------------------------------------------------
CREATE TABLE devices (
    id                    UUID PRIMARY KEY,
    actor_type            TEXT NOT NULL DEFAULT 'device',
    platform              TEXT NOT NULL,
    trust_level           TEXT NOT NULL DEFAULT 'restricted',

    authorized_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorized_by         UUID NOT NULL REFERENCES actors (id),
    authorization_policy  TEXT,

    revoked_at            TIMESTAMPTZ,
    revoked_by            UUID REFERENCES actors (id),
    revocation_reason     TEXT,

    metadata              JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT devices_type_check CHECK (actor_type = 'device'),
    CONSTRAINT devices_trust_valid CHECK (
        trust_level IN ('admin', 'trusted', 'restricted')
    ),
    CONSTRAINT devices_actor_fk
        FOREIGN KEY (id, actor_type) REFERENCES actors (id, actor_type)
);

COMMENT ON TABLE devices IS
    'Dispositivos autorizados. trust_level restricted por defecto: la política
     automática solo puede otorgar el nivel mínimo. Elevar requiere un admin.
     Una revocación humana bloquea el reenrolamiento automático.';

CREATE INDEX devices_trust_idx ON devices (trust_level) WHERE revoked_at IS NULL;

-- ------------------------------------------------------------
-- Tipos de evento del ciclo de vida de dispositivos.
-- ------------------------------------------------------------
INSERT INTO event_types (name, description) VALUES
    ('device_authorized',    'Un dispositivo fue autorizado a conectarse.'),
    ('device_revoked',       'Un dispositivo fue revocado. Bloquea reenrolamiento automático.'),
    ('device_trust_changed', 'Cambió el nivel de confianza de un dispositivo.'),
    ('device_connected',     'Un dispositivo estableció conexión con el Núcleo.'),
    ('device_disconnected',  'Un dispositivo terminó su conexión. El motivo indica si fue activa o pasiva.');