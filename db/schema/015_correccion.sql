-- ============================================================
-- 015 — corrección
-- Fase 1.4 — que ABEL se pueda corregir
-- ============================================================

-- El cambio de confianza en sí ya queda en assertion_events (kind =
-- 'contradicted'/'retired' en la vieja, 'created' en la nueva si la hay).
-- Este tipo de evento es la marca de que ocurrió una corrección como acto
-- completo: qué afirmación se retiró, cuál la reemplazó (si hubo dato) y
-- con qué texto — para auditar sin tener que reconstruirlo cruzando dos
-- afirmaciones por fecha (ver scripts/creencias.py --corregidas).
INSERT INTO event_types (name, description) VALUES
    ('assertion_corrected', 'La persona corrigió algo que ABEL creía.');
