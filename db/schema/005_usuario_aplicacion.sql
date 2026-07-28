-- ============================================================
-- 005 — usuario de aplicación
-- abel_app: el rol que usa el Núcleo. Sin DDL, sin DELETE.
-- La contraseña NO se define acá (ver docs).
-- ============================================================

CREATE ROLE abel_app WITH LOGIN;

GRANT CONNECT ON DATABASE abel TO abel_app;
GRANT USAGE ON SCHEMA public TO abel_app;

-- Lectura
GRANT SELECT ON
    actors, event_types, modules, runs, events, settings, current_settings
    TO abel_app;

-- Escritura
GRANT INSERT ON actors, modules, runs, events, settings TO abel_app;
GRANT UPDATE ON actors, modules, runs, settings TO abel_app;

-- Deliberadamente NO se otorga:
--   DELETE    → el registro es append-only por construcción
--   TRUNCATE  → idem
--   CREATE    → el esquema solo lo modifica postgres

-- Tablas futuras creadas por postgres (devices, users, ...)
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO abel_app;