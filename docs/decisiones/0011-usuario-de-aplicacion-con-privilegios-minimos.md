# 0011 — Usuario de aplicación con privilegios mínimos

**Estado:** Vigente
**Fecha:** 2026-07-28
**Fase:** 1

## Decisión

El Núcleo se conecta a PostgreSQL como `abel_app`, un rol dedicado que **no
puede modificar el esquema ni borrar datos**. El superusuario `postgres` queda
reservado para migraciones, ejecutadas a mano.

Permisos otorgados: `SELECT`, `INSERT`, `UPDATE`.
Deliberadamente NO otorgados: `DELETE`, `TRUNCATE`, `CREATE`.

## Contexto

Hasta la Fase 0 el código se conectaba como `postgres`, con capacidad de borrar
bases enteras, crear usuarios y leer todo. Un error de programación —o algo
peor en fases posteriores— podía destruir la instalación.

Dos mecanismos independientes protegen ahora el esquema:

- **Privilegios** — `abel_app` no tiene `CREATE` sobre el esquema `public`.
- **Propiedad** — las tablas pertenecen a `postgres`. Aunque `abel_app`
  tuviera todos los privilegios, no podría hacer `DROP`: no es el dueño.

Verificado en la práctica: los tres intentos (`DELETE`, `DROP`, `CREATE`)
fallan con errores distintos, cada uno del mecanismo correspondiente.

## Relación con la auto-modificación

Esta decisión **no limita** la auto-modificación prevista en 0006. La refuerza.

| Nivel | Operación | ¿Puede `abel_app`? |
|---|---|---|
| 1 — Parámetros | `INSERT` / `UPDATE` | Sí |
| 2 — Reglas | `INSERT` / `UPDATE` | Sí |
| 4 — Estructura | `CREATE` / `ALTER` / `DROP` | **No** |

Es la aplicación, a nivel de base de datos, del principio de que la parte que
ejecuta las modificaciones no debe ser modificable por el sistema.

**Fricción aceptada:** si un módulo futuro necesita su propia tabla, hace falta
intervención manual con `postgres`. Ese es el punto de control buscado.

## Sobre el olvido

La ausencia de `DELETE` hace que el registro de eventos sea **append-only por
construcción**, no por convención.

Esto no impide que ABEL olvide. Olvidar no es borrar: es debilitar el acceso.
Marcar como olvidado, consolidar, decaer por relevancia y superar un valor son
todas operaciones de `INSERT` y `UPDATE`. Ninguna necesita borrado.

Ventaja adicional: **el olvido queda auditable.** Se puede consultar qué olvidó
ABEL, cuándo y por qué. Con borrado real no habría rastro de que algo existió.

La línea resultante:

> **ABEL olvida. Solo el usuario borra.**

## Consecuencias

- La contraseña se asigna con `\password` en psql, nunca en un archivo del
  repositorio: así no queda en el historial de psql ni en los logs del servidor.
- Las migraciones requieren cambiar de usuario. Es deliberado.
- `ALTER DEFAULT PRIVILEGES` deja la regla puesta para tablas futuras creadas
  por `postgres`. Sin eso, `devices` (Fase 2) nacería inaccesible.

## Reevaluar

- **Fase 3**, cuando los datos de percepción empiecen a acumularse en volumen y
  la retención deje de ser teórica.
- **En cuanto haya datos de terceros**, donde el principio 1 puede imponer
  obligaciones reales de eliminación.
