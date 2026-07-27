# Fase 0 — Preparación del entorno

**Estado:** Cerrada
**Fecha de cierre:** 2026-07-27
**Versión del proyecto:** 0.0.1

## Objetivo

Dejar el entorno de desarrollo funcional y el esquema inicial de base de datos
diseñado, antes de escribir código del Núcleo.

---

## 0.1 — Repositorio y documentación fundacional

- Repositorio inicializado y subido a GitHub (privado).
- Estructura base de directorios.
- Documentación fundacional: README, `vision.md`, `principios.md`,
  `arquitectura.md`.

---

## 0.2 — PostgreSQL

- **PostgreSQL 18.4** instalado en Windows 10 con el instalador oficial
  (distribuido por EDB, descargado desde postgresql.org).
- Componentes: Server, pgAdmin 4, Command Line Tools. Stack Builder omitido.
- Corre como **servicio de Windows**, arranque automático. Puerto 5432.
- Base `abel` creada con encoding **UTF8**.

Justificación de la elección de motor y versión: ver
`docs/decisiones/0001-postgresql-como-base-estructurada.md`.

**Verificación de cierre:**

```bash
psql --version          # PostgreSQL 18.4
psql -U postgres -d abel
```
```sql
SELECT version();
\l                      -- Encoding debe ser UTF8
```

---

## 0.3 — Esquema inicial

Seis objetos de base de datos. Los archivos SQL están en `db/schema/`,
numerados por orden de ejecución.

| Archivo | Contenido |
|---|---|
| `001_actors_event_types.sql` | `actors`, `event_types` |
| `002_seed_base.sql` | Actor `core`, tipos de evento base |
| `003_runs_modules_events.sql` | `runs`, `modules`, `events`, índices |
| `004_settings.sql` | `settings`, vista `current_settings`, config inicial |

### Objetos creados

| Objeto | Rol |
|---|---|
| `actors` | Toda entidad capaz de causar un evento. Supertipo. |
| `event_types` | Catálogo de tipos de evento válidos. |
| `runs` | Ejecuciones del Núcleo. Una fila por arranque. |
| `modules` | Subtipo de `actors`. Primer subtipo implementado. |
| `events` | Registro central de todo lo que ocurre. |
| `settings` | Configuración con historial de cambios. |
| `current_settings` | Vista. Acceso a la configuración vigente. |

**`devices` y `users` NO se crearon.** Corresponden a fases posteriores.
Diseñarlas ahora sería adivinar cómo funcionan sistemas que todavía no existen.
El patrón supertipo/subtipo (decisión 0004) permite agregarlas después sin
migración ni movimiento de datos.

### Tipos de evento definidos

| Tipo | Significado |
|---|---|
| `core_started` | El Núcleo inició una ejecución |
| `core_stopped` | El Núcleo terminó de forma ordenada |
| `presence_mark` | Marca periódica de existencia |
| `error` | Se produjo un error durante la ejecución |

### Configuración inicial

| Clave | Valor | Uso |
|---|---|---|
| `presence_interval_seconds` | `60` | Cadencia de la marca de presencia |
| `log_level` | `"INFO"` | Nivel de detalle de los logs |

### Detección de caídas

Combinación de dos mecanismos independientes:

- **`runs.ended_at IS NULL`** en una ejecución que no es la vigente → **se cayó**.
- **El último `presence_mark`** de esa ejecución → **cuándo** se cayó.

Ninguno de los dos da esa información por sí solo. Ver `glosario.md`, entrada
*marca de presencia*.

**Verificación de cierre:**

```sql
\dt                                  -- 5 tablas
SELECT * FROM current_settings;      -- 2 filas

-- Debe FALLAR (prueba de integridad referencial):
INSERT INTO events (occurred_at, event_type, actor_id)
VALUES (now(), 'tipo_inexistente', '<uuid_de_core>');
```

---

## Extra: entorno Python

No estaba en el plan original de la Fase 0. Se resolvió acá por ser requisito
directo de la Fase 1.

- Entorno virtual en `.venv/` — Python 3.14.4.
- **psycopg 3.3.4** con extra `[binary]` (decisión 0008).
- **python-dotenv 1.2.2** para configuración por variables de entorno.
- Credenciales en `.env`, excluido de Git. Plantilla en `.env.example`.
- Dependencias congeladas en `requirements.txt`.

Particularidades del entorno Windows/Git Bash: ver `docs/entorno-desarrollo.md`.

---

## Definición de la Fase 1

Trabajo conceptual realizado durante esta fase. El plan original listaba las
fases como hitos, sin especificar su contenido.

### Método usado

La pregunta que define el contenido de una fase **no** es *"¿qué quiero que
ABEL haga acá?"* — con esa pregunta la respuesta siempre es "todo". Es:

> **¿Qué tiene que ser verdad al terminar esta fase para que la siguiente sea
> posible?**

Es una pregunta de habilitación, no de ambición. La respuesta casi siempre es
más chica de lo esperado.

Aplicada a la Fase 2 (comunicación y primer Nodo), lo que hace falta es: un
Núcleo que **esté corriendo** cuando el Nodo intente conectarse, que **sepa qué
dispositivos existen**, y que **registre** que la conexión ocurrió.

### El Núcleo mínimo es

Un proceso que vive de forma sostenida y confiable, conoce su propio estado, y
deja registro de su existencia.

Es **infraestructura**, y eso no es un desvío del objetivo del proyecto: es la
fase haciendo lo que le toca. No produce nada que se parezca a una conciencia
(principio 7). Produce los cimientos sobre los que todo lo demás se apoya.

### Incluye

- Ciclo de vida completo: arranque, ejecución sostenida, apagado ordenado.
- Persistencia de identidad entre reinicios.
- Bucle de eventos asíncrono con planificador de tareas (decisión 0007).
- Una sola tarea registrada: la marca de presencia.
- Registro de actividad en PostgreSQL + logs locales de aplicación.
- Configuración recuperable desde base de datos.
- Tolerancia a fallo temporal de la base: no muere, reintenta.

### NO incluye

| Fuera de alcance | Corresponde a |
|---|---|
| Comunicación con Nodos | Fase 2 |
| Sensores y captura de datos | Fase 3 |
| Interfaz gráfica | Fase 4 |
| LLM y comprensión de lenguaje | Fase 5 |
| Aprendizaje y metacognición | Fase 6 |
| **Ejecución como servicio de Windows** | pospuesto deliberadamente |

Sobre el servicio de Windows: aunque `arquitectura.md` lo especifica, para la
Fase 1 alcanza con un proceso normal ejecutado desde terminal. Envolverlo en un
servicio agrega permisos, logs invisibles y depuración a ciegas — problemas que
conviene no mezclar con "hacer que el ciclo funcione bien". Primero que
funcione donde se puede ver.

### Criterio de cierre

> El Núcleo arranca desde la terminal, corre de forma sostenida durante horas,
> mantiene su ciclo periódico, registra su actividad en PostgreSQL, se apaga
> limpiamente con Ctrl+C, y al reiniciarse recupera su identidad y estado
> previo.

### Decisión abierta

Si la base de datos está caída durante un período, quedan **huecos** en la
marca de presencia. Para la Fase 1 se acepta el hueco: es más simple, y el
hueco en sí es información.

Anotado porque **es el mismo problema que aparece en la Fase 2** con Nodos
desconectados, a mayor escala. Resolverlo bien acá enseña el patrón para allá.

---

## Nota de método

El diseño del esquema se detuvo hasta definir el comportamiento de la Fase 1.

**Un esquema no se puede diseñar sin saber qué comportamiento persiste.**
Hacerlo antes es adivinar, y produce tablas vacías que representan suposiciones
sobre sistemas que todavía no existen.

Esta secuencia — comportamiento primero, esquema después — conviene repetirla
en las fases siguientes.
