-- ============================================================
-- 011 — turnos de conversación
-- Fase 5.5
-- ============================================================

INSERT INTO event_types (name, description) VALUES
    ('utterance',
     'Un turno de conversación. speaker indica quién habló: user o abel. '
     'Los turnos de ABEL registran además qué intenciones detectó y si '
     'decidió no responder.');
    