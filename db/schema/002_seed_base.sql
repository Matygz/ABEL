-- ============================================================
-- 002 — datos base del sistema
-- ============================================================

-- ABEL como entidad. Actor de los eventos que no vienen
-- de ningún módulo en particular.
INSERT INTO actors (actor_type, name)
VALUES ('system', 'core');

-- Tipos de evento del Núcleo mínimo.
INSERT INTO event_types (name, description) VALUES
    ('core_started',  'El Núcleo inició una ejecución.'),
    ('core_stopped',  'El Núcleo terminó una ejecución de forma ordenada.'),
    ('presence_mark', 'Marca periódica de existencia. Su ausencia indica caída.'),
    ('error',         'Se produjo un error durante la ejecución.');