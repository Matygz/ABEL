# 0009 — SQL a mano, sin ORM

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

Las consultas se escriben en SQL, encapsuladas en una capa de acceso a datos.
No se usa ORM (SQLAlchemy u otro) por ahora.

## Contexto

Un ORM permite escribir consultas en Python en lugar de SQL, generando el SQL
por debajo. Es una herramienta legítima y madura.

Razones para no usarlo en este proyecto:

1. **Aprendizaje.** El SQL del esquema se escribió a mano y se está
   entendiendo. Un ORM lo esconde justo en el momento de construir esa
   comprensión.
2. **El esquema usa construcciones que a los ORM les cuesta expresar bien:**
   el índice único parcial de `settings`, la clave foránea compuesta de
   `modules`, el patrón de historial con vigencia.
3. **Principio 3** — herramientas heredadas como componentes, sin delegar el
   pensamiento. Un ORM es una capa más de abstracción entre el programador y
   lo que realmente ocurre.

## Aclaración importante

Un ORM **no** ayuda a *visualizar* la base. Cambia cómo se escriben las
consultas, no cómo se inspeccionan los datos. Para eso se usan herramientas
gráficas, decisión independiente (ver `docs/entorno-desarrollo.md`).

## Consecuencias

- Más código escrito a mano para operaciones repetitivas.
- Los valores **nunca** se concatenan al texto de la consulta: se pasan como
  parámetros (`%s` en psycopg3). Concatenar es inyección SQL.
- Toda consulta vive en la capa de acceso a datos, no dispersa por el código.
  Esto es lo que hace reversible la decisión 0008 y, eventualmente, esta.
- **Reevaluar** si la cantidad de consultas repetitivas se vuelve un problema
  real, no antes.
