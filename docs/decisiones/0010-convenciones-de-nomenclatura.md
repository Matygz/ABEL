# 0010 — Convenciones de nomenclatura

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

**El esquema de base de datos y el código se escriben en inglés. La
documentación, en español.**

## Convenciones

| Elemento | Convención | Ejemplo |
|---|---|---|
| Tablas | `snake_case`, plural | `events`, `event_types` |
| Columnas | `snake_case`, singular | `actor_id`, `event_type` |
| Columnas de tiempo | sufijo `_at` | `created_at`, `occurred_at` |
| Booleanos | adjetivo sin prefijo | `active`, `enabled` |
| Restricciones | `tabla_descripcion_tipo` | `actors_type_valid` |
| Índices | `tabla_columna_idx` | `events_occurred_at_idx` |
| Archivos de esquema | `NNN_descripcion.sql` | `003_runs_modules_events.sql` |

## Contexto

Argumentos a favor del español: naturalidad, coherencia con la documentación
existente.

Argumentos a favor del inglés, que pesaron más:

- Convención dominante; se mezcla mejor con librerías y ejemplos.
- Evita tildes y `ñ` en identificadores. PostgreSQL los soporta, pero generan
  fricción constante (comillas, problemas de codificación en consola).

Lo importante no es cuál se elige, sino **no mezclar**. Una tabla
`dispositivos` con columna `created_at` es un dolor de cabeza permanente.

## Numeración de archivos de esquema

Los números **no se reutilizan nunca**, aunque un archivo se elimine. El número
queda quemado. Esto permite recrear la base desde cero ejecutando los archivos
en orden, y es el germen de un sistema de migraciones — necesario en un
proyecto de este plazo.

## Consecuencias

- Los mensajes de error de PostgreSQL mencionan nombres en inglés; la
  documentación que los explica está en español. Fricción menor y aceptada.
