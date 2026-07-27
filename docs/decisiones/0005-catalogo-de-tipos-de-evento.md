# 0005 — Catálogo de tipos de evento en tabla

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

Los tipos de evento válidos viven en una tabla `event_types`, referenciada por
clave foránea desde `events.event_type`.

## Contexto

Tres opciones para restringir el tipo de evento:

| Opción | Valida | Agregar un tipo |
|---|---|---|
| `TEXT` libre | No | Trivial |
| `ENUM` | Sí | Requiere migración |
| **Tabla catálogo** | **Sí** | **Un INSERT** |

`TEXT` libre acepta errores de tipeo silenciosamente: `presence_marck` entra
como un tipo fantasma que después no se encuentra nunca.

`ENUM` valida, pero agregar un tipo exige migrar el esquema — lo que choca de
frente con la idea de módulos que se instalan dinámicamente y registran sus
propios tipos de evento.

La tabla catálogo da validación real sin migración.

## Detalles

- `description` es `NOT NULL` a propósito: obliga a explicar qué significa cada
  tipo en el momento de crearlo. Documentación que no se puede omitir.
- `registered_by` apunta a `actors`: cuando un módulo registre sus propios
  tipos, queda constancia de quién fue.

## Consecuencias

- Un `INSERT` con un tipo inexistente **falla en el momento**, no seis meses
  después al descubrir datos huérfanos. Verificado en la Fase 0.3.
- Una tabla más y un `JOIN` en consultas que necesiten la descripción.
- Registrar un tipo nuevo es parte de la instalación de un módulo.
