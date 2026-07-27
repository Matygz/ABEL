# Decisiones de arquitectura

Registro de decisiones cuya justificación no se deduce leyendo el código.

## Convención

- Un archivo por decisión, con formato `NNNN-titulo-corto.md`.
- La numeración es correlativa y **no se reutiliza ni se renumera**.
- Una decisión no se edita para cambiarla: se marca como `Superada por NNNN`
  y se escribe una entrada nueva. El historial de por qué se pensó algo en su
  momento es tan valioso como la decisión vigente.

## Estados posibles

| Estado | Significado |
|---|---|
| `Vigente` | En uso |
| `Superada por NNNN` | Reemplazada por otra decisión |
| `Revertida` | Se deshizo sin reemplazo |

## Índice

| N.º | Decisión | Estado | Fase |
|---|---|---|---|
| 0001 | PostgreSQL como base estructurada | Vigente | 0.2 |
| 0002 | UUIDv7 como identificadores | Vigente | 0.3 |
| 0003 | Doble timestamp en eventos | Vigente | 0.3 |
| 0004 | Patrón supertipo/subtipo para actores | Vigente | 0.3 |
| 0005 | Catálogo de tipos de evento en tabla | Vigente | 0.3 |
| 0006 | Configuración versionada con vigencia | Vigente | 0.3 |
| 0007 | asyncio como modelo de concurrencia | Vigente | 0.3 |
| 0008 | psycopg3 como driver de PostgreSQL | Vigente | 0.3 |
| 0009 | SQL a mano, sin ORM | Vigente | 0.3 |
| 0010 | Convenciones de nomenclatura | Vigente | 0.3 |
