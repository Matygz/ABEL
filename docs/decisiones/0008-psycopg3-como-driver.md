# 0008 — psycopg3 como driver de PostgreSQL

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

**psycopg 3** (paquete `psycopg`, instalado con el extra `[binary]`) como
driver de PostgreSQL desde Python.

## Contexto

Requisito previo (ver 0007): el driver debe ser **compatible con asyncio**. Un
driver sincrónico bloquea el bucle de eventos y anula toda la arquitectura.

Eso descarta de entrada a **psycopg2**, el clásico que aparece en la mayoría de
los tutoriales antiguos.

Quedan dos candidatos reales: **asyncpg** y **psycopg3**.

### Sobre el rendimiento

Los benchmarks publicados **se contradicen entre sí**: desde 5× a favor de
asyncpg (medición del propio proyecto) hasta 25-35% de ventaja en latencia en
mediciones independientes, y al menos una fuente que da ventaja a psycopg3 por
su modo de pipeline.

**Es irrelevante para este caso.** La Fase 1 escribe del orden de una fila por
minuto. Una diferencia de milisegundos, una vez por minuto, es indetectable.
Elegir por rendimiento acá sería optimizar algo que no es el cuello de botella.

### Criterios que sí pesaron

1. **API unificada sync/async.** Las mismas clases y métodos, con `async`/`await`
   agregados. Permite escribir primero la versión sincrónica para entender el
   acceso a datos, y agregar async después sin reescribir lógica — separando
   dos aprendizajes que de otro modo habría que enfrentar juntos.
2. **Manejo de JSONB.** psycopg3 devuelve diccionarios de Python
   directamente. asyncpg devuelve JSONB como texto por defecto y exige
   registrar un codec por conexión. El esquema de ABEL usa JSONB en tres
   tablas.
3. **Ecosistema.** Hereda el mundo de psycopg2, estándar durante quince años.
   Más material disponible al trabarse.

Verificado en la práctica: `SELECT value FROM current_settings` devolvió `30`
como entero de Python y `'INFO'` como texto, sin conversión manual.

## Consecuencias

- Se resigna rendimiento bruto que no se va a usar en años, si alguna vez.
- El extra `[binary]` instala una versión precompilada. Sin él, pip intentaría
  compilar desde código fuente, lo que en Windows requiere herramientas de C.
- **La decisión es reversible a bajo costo** si la capa de acceso a datos está
  bien aislada: cambiar de driver sería reescribir un módulo, no el proyecto.
- Nota de nomenclatura: el paquete se llama `psycopg` a secas, no `psycopg3`.
  El `3` es solo la versión mayor.
