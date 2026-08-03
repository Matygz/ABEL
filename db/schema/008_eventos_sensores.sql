-- ============================================================
-- 008 — tipos de evento de sensores
-- Fase 3.1
-- ============================================================

INSERT INTO event_types (name, description) VALUES
    ('session_state',
     'Transición entre actividad e inactividad del usuario en un dispositivo. '
     'Observación: refleja entrada de teclado o mouse, no presencia física.'),
    ('system_resources',
     'Muestra de CPU, memoria y batería de un dispositivo.');