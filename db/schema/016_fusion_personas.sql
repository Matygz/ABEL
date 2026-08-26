-- ============================================================
-- 016 — fusión de personas duplicadas
-- Fase 1.4 — dos afirmaciones de un vínculo único con objetos
-- distintos son la misma persona vista dos veces, no dos personas.
-- ============================================================

-- No se borra la duplicada: contradice el append-only y puede tener
-- eventos apuntándola (ver docstring de Afirmaciones.fusionar). Se marca
-- con un puntero a la persona real — las consultas la siguen, y si la
-- fusión estuvo mal se puede deshacer sin haber perdido nada.
ALTER TABLE persons
    ADD COLUMN merged_into   UUID REFERENCES actors (id),
    ADD COLUMN merged_at     TIMESTAMPTZ,
    ADD COLUMN merged_reason TEXT;

CREATE INDEX persons_merged_into_idx
    ON persons (merged_into)
    WHERE merged_into IS NOT NULL;

INSERT INTO event_types (name, description) VALUES
    ('persons_merged',
     'Dos personas resultaron ser la misma. La duplicada queda marcada, '
     'no se borra: si la fusión estuvo mal, se puede deshacer.');

-- persons ya tiene SELECT/INSERT/UPDATE para abel_app desde
-- 013_afirmaciones.sql; se repite acá, explícito, como el resto de las
-- migraciones que tocan columnas nuevas.
GRANT SELECT, INSERT, UPDATE ON persons TO abel_app;
