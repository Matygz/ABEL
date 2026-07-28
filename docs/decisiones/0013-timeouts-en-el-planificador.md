# 0013 — Timeouts por tarea en el planificador

**Estado:** Vigente
**Fecha:** 2026-07-28
**Fase:** 1

## Decisión

El planificador envuelve cada ejecución de tarea en `asyncio.wait_for()`. Si
una tarea supera su límite, se la cancela, se registra el hecho y el ciclo
continúa con su reintento normal.

Cada `Tarea` puede declarar `timeout_segundos`. Por defecto se usa **la mitad
del intervalo**, con un piso de 1 segundo.

## Contexto

Descubierto en una prueba de resiliencia real, no por análisis previo.

Al detener el servicio de PostgreSQL con el Núcleo corriendo, el log quedó en
**silencio absoluto** durante 36 segundos: ni marcas, ni errores. La tarea no
había fallado — se había **colgado** en el `await` de la conexión, esperando
una respuesta que nunca llegaría. Al no retornar nunca, nunca reintentó.

La diferencia es crítica:

| | Comportamiento |
|---|---|
| **Fallo** | Ruidoso, se registra, se recupera solo |
| **Cuelgue** | Silencioso, permanente, indistinguible de un sistema ocioso |

Peor aún: el proceso seguía vivo, así que la ejecución en `runs` nunca se
cerraba ni se marcaba como caída. El mecanismo de detección de caídas no veía
nada anormal.

El criterio de cierre de la Fase 1 —tolerancia a fallo temporal de la base—
**no se cumplía**, aunque parecía cumplirse.

## Dos arreglos, en dos niveles

**`connect_timeout` (específico).** Parámetro de conexión de psycopg,
configurable vía `.env`, por defecto 5 segundos. Resuelve el caso concreto:
un intento de conexión falla en lugar de esperar indefinidamente.

**Timeout por tarea (general).** Protege contra cualquier cuelgue, incluidos
los que todavía no se conocen: una consulta que no termina, una operación de
red en la Fase 2.

El primero solo tapaba un caso. Un Núcleo que corre desatendido no debería
poder quedarse mudo por ninguna causa.

## Por qué la mitad del intervalo

Garantiza que una tarea nunca se solape consigo misma: para cuando llegue su
próximo turno, la ejecución anterior ya fue cancelada. El piso de 1 segundo
evita timeouts absurdamente cortos en tareas muy frecuentes.

## Limitación conocida

`wait_for` no interrumpe la ejecución desde afuera: inyecta un
`CancelledError` **en el punto donde la corrutina está esperando**.

Consecuencia: **solo funciona si la tarea está en un `await`.** Una tarea que
hiciera cálculo intensivo sin puntos de espera no podría ser cancelada, y el
timeout no la salvaría.

Para tareas de I/O —todo lo previsto para ABEL— siempre hay un `await`. Es una
razón más para no ejecutar cálculo pesado dentro del bucle de eventos (ver 0007).

## Consecuencias

- Una tarea legítimamente lenta necesita declarar un `timeout_segundos` mayor,
  o será cancelada de forma incorrecta.
- El `except asyncio.TimeoutError` va **antes** que `except Exception`, por la
  misma razón de orden explicada en 0012.
