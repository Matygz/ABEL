# 0012 — Errores operativos vs. inesperados

**Estado:** Vigente
**Fecha:** 2026-07-28
**Fase:** 1

## Decisión

`ErrorOperativo` (en `nucleo/errores.py`) es la clase base de los fallos
**esperados y transitorios** de dependencias externas. El planificador los
registra en una línea, sin traza. Todo lo demás se registra con
`logger.exception()`, con traza completa.

## Contexto

Durante las pruebas de resiliencia, cada fallo de conexión producía ~30 líneas
de traceback. Con reintentos cada 5 segundos, el log se volvía ilegible.

La distinción de fondo: **un error esperado no es un error del programa.** Que
PostgreSQL se reinicie por una actualización de Windows es parte de la vida
normal de un servicio que corre 24/7, no un bug.

- **Error operativo** — se sabe qué falló y por qué. El mensaje alcanza; la
  traza no agrega información.
- **Error inesperado** — no se sabe qué pasó. La traza es lo único que permite
  diagnosticarlo.

Ejemplo del resultado:

```
ERROR  nucleo.planificador: Tarea presencia: connection timeout expired. Reintenta en 5.0s.
```

## Implementación

- `ErrorRepositorio` hereda de `ErrorOperativo`.
- El planificador captura `ErrorOperativo` **antes** que `Exception`. El orden
  importa: Python usa el primer `except` que coincide, y `ErrorOperativo` es
  subclase de `Exception`.
- Se usa `str(exc).splitlines()[0]` para quedarse con la primera línea del
  mensaje de psycopg y descartar el detalle de intentos múltiples.
- El repositorio registra el error en `DEBUG`, no en `ERROR`: el planificador
  ya lo reporta. Con `DEBUG` activo se ven ambos, útil al depurar.

## Consecuencias

- Al agregar excepciones nuevas hay que decidir de qué lado caen. Regla: si el
  Núcleo puede seguir funcionando y reintentando, es operativa.
- Un error operativo mal clasificado esconde información. Ante la duda, dejarlo
  como inesperado: es preferible ruido a un diagnóstico perdido.
