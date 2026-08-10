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
| 0011 | Usuario de aplicación con privilegios mínimos | Vigente | 1 |
| 0012 | Errores operativos vs. inesperados | Vigente | 1 |
| 0013 | Timeouts por tarea en el planificador | Vigente | 1 |
| 0014 | Niveles de confianza y asimetría conceder/revocar | Vigente | 2.1 |
| 0015 | Cuatro identificadores separados para un usuario | Vigente | 2.1 |
| 0016 | Diseño del protocolo de Nodos | Vigente | 2.2 |
| 0017 | Semántica del ack e idempotencia | Vigente | 2.2 |
| 0018 | Superficie mínima de error por el cable | Vigente | 2.2 |
| 0019 | El Nodo se programa como remoto | Vigente | 2.2 |
| 0020 | Servicios en el planificador | Vigente | 2.2 |
| 0021 | Autenticación por firma con desafío | Vigente | 2.3 |
| 0022 | TLS con fijación de certificado | Vigente | 2.4 |
| 0023 | Cola persistente en SQLite | Vigente | 2.5 |
| 0024 | Estructura de sensores | Vigente | 3.1 |
| 0025 | Manejo de ruido en sensores | Vigente | 3.2 |
| 0026 | Registro de títulos de ventana | Vigente | 3.2 |
| 0027 | Módulo de memoria | Vigente | 3.3 |
| 0028 | Memoria global con atribución | Vigente | 4 |
| 0029 | Sesión de interfaz sin contraseña | Vigente | 4.1 |
| 0030 | Criterio de permisos: conocimiento sí, alcance no | Vigente | 4 |
| 0031 | Identificar no es autenticar | Vigente | 4 |
| 0032 | Alcance: ABEL asume acceso exclusivo | Vigente | 4 |
| 0033 | Bus de eventos interno | Vigente | 4.1 |