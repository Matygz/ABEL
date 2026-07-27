# 0001 — PostgreSQL como base estructurada

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.2

## Decisión

PostgreSQL 18.4 como base de datos relacional del Núcleo, instalado de forma
nativa en Windows (sin contenedores).

## Contexto

El stack de ABEL es combinado y cada motor cubre un ángulo distinto de la
misma realidad:

- **PostgreSQL** — los hechos. Qué pasó, cuándo, quién lo reportó.
- **Qdrant** — el significado. Qué se parece a qué.
- **Neo4j** (en evaluación) — las conexiones. Cómo se relaciona todo.
- **SQLite** — persistencia local en los Nodos.

PostgreSQL no está "limitado" frente a los otros: está especializado en lo
estructurado, y tiene JSONB para lo que todavía no tiene forma definida.

## Alternativas descartadas

- **SQLite para el Núcleo.** Excelente, pero admite un solo escritor a la vez.
  Se queda corto con varios módulos escribiendo en paralelo. Sí se usa en los
  Nodos, que es su lugar natural.
- **MySQL/MariaDB.** Válido. PostgreSQL gana en tipos avanzados (JSONB, arrays,
  tipos propios) y en rigor de validación.
- **MongoDB.** Sin esquema. La disciplina que no impone la base hay que
  imponerla en el código, y no se impone siempre.

## Sobre la versión

Se eligió **18.4** y no **19** porque en la fecha de instalación la 19 estaba
en beta (Beta 2, 16/07/2026), con release final estimada para
septiembre/octubre de 2026. Para un proyecto de largo plazo se prioriza
estabilidad. La rama 18 tiene soporte hasta 2030.

## Sobre Docker

Descartado por ahora, deliberadamente:

1. Es una tecnología entera aparte. Aprenderla junto con PostgreSQL viola el
   principio 4 (aprender antes de construir).
2. En Windows requiere WSL2 y agrega capas donde los fallos se vuelven
   confusos: un problema de Docker se disfraza de problema de Postgres.
3. El Núcleo va a correr como servicio de Windows. Postgres nativo también.
   Menos piezas móviles.

**Reevaluar** cuando haya tres o cuatro servicios (Postgres + Qdrant + Neo4j)
y orquestarlos a mano se vuelva molesto. Ahí se aprende con motivo real.

## Consecuencias

- Instalación acoplada al sistema operativo. Migrar a otra máquina implica
  reinstalar, no copiar un contenedor.
- Los archivos de esquema en `db/schema/` permiten recrear la base desde cero.
