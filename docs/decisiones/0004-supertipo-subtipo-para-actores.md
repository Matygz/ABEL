# 0004 — Patrón supertipo/subtipo para actores

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

Una tabla `actors` unifica a toda entidad capaz de causar un evento. Los tipos
concretos (`modules`, `devices`, `users`) son tablas subtipo que **comparten su
clave primaria** con la fila correspondiente en `actors`.

```
actors (id, actor_type, name, ...)
   ↑ mismo id
modules (id, ...)   devices (id, ...)   users (id, ...)
```

## Contexto

Un evento puede provenir de un módulo, un dispositivo, el propio Núcleo, o del
usuario. Son entidades de naturaleza distinta que viven en tablas distintas.

PostgreSQL **no admite una clave foránea que apunte a veces a una tabla y a
veces a otra**. Sin una tabla unificadora, `events.actor_id` quedaría sin
validación: la base aceptaría cualquier UUID, existiera o no.

La tabla `actors` recupera esa garantía. `events.actor_id` referencia a
`actors(id)` y la integridad la verifica el motor, no el código.

`actor_type = 'system'` representa a ABEL mismo (el Núcleo como entidad). No
tiene tabla subtipo porque no tiene atributos propios.

## Implementación

La integridad entre supertipo y subtipo se refuerza con **clave foránea
compuesta**: `modules` referencia a `actors (id, actor_type)` y tiene un `CHECK`
que fuerza `actor_type = 'module'`. Así la base garantiza que un `modules.id`
no pueda apuntar a un actor que sea, por ejemplo, un dispositivo.

Esto exige una restricción `UNIQUE (id, actor_type)` en `actors` — técnicamente
redundante (el `id` ya es único), pero requerida por PostgreSQL para permitir
la referencia compuesta.

## Alternativas descartadas

- **`actor_type` + `actor_id` sin clave foránea.** Flexible pero sin ninguna
  validación. La base aceptaría IDs inexistentes.
- **Columnas separadas** (`module_id`, `device_id`, ...). Cada tipo nuevo de
  actor exige una columna nueva, y la mayoría queda vacía siempre.

## Consecuencias

- Crear un actor requiere **dos INSERT en orden** (primero `actors`), dentro de
  una transacción. Se escribe una vez en la capa de acceso a datos.
- Agregar un tipo de actor nuevo es **una tabla nueva**, sin migración ni
  movimiento de datos. Por eso `devices` y `users` no se crearon en la Fase 0:
  corresponden a fases posteriores y la estructura ya los admite.
- Consultar "quién causó este evento" solo necesita `actors`. Los atributos
  específicos se buscan en la tabla subtipo.
