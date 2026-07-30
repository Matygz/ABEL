# 0017 — Semántica del ack e idempotencia

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.2

## Decisión

> **El `ack` significa "lo escribí en PostgreSQL", no "me llegó".**

El Nodo descarta una observación de su cola **solo** cuando el Núcleo confirma
haberla persistido.

La idempotencia se obtiene usando el `id` de la observación —generado por el
Nodo— como `events.id`, con `ON CONFLICT (id) DO NOTHING`.

## Por qué el ack va después de persistir

Si el Núcleo confirmara al recibir y se cayera antes de escribir, el Nodo ya
habría borrado ese dato de su cola. **Se pierde, y nadie se entera.**

Confirmar solo después de persistir cuesta latencia, pero garantiza que un dato
desaparece de la cola únicamente cuando existe en otro lado — que era el
propósito de tener cola.

En el código, el orden es literal: `persistir_observaciones()` primero,
`enviar(crear_ack(...))` después.

## El problema que eso crea, y su solución

Si el `ack` se pierde en el camino, el Nodo reenvía. Sin protección, el Núcleo
crearía eventos duplicados.

Solución: el `id` de cada observación se usa como clave primaria de `events`.
El segundo `INSERT` con el mismo UUID viola la restricción y se ignora
deliberadamente.

**Esto funciona porque el Nodo genera su propio UUID sin consultar a nadie** —
exactamente el razonamiento de la decisión 0002, tomada tres fases antes
pensando en la sincronización de bases separadas. Resuelve este problema sin
trabajo adicional.

Semántica del retorno: se confirma tanto lo insertado ahora como lo que ya
estaba. Las dos cosas significan "este dato está a salvo", que es lo que el
`ack` promete.

## Rechazo parcial

`ack` lleva `acknowledged` y `rejected` por separado. Una observación con
`event_type` inexistente se rechaza sin afectar a las válidas del mismo lote.

Los tipos se validan **antes** del `INSERT`, no durante: si una observación
inválida entrara a la transacción, la violación de clave foránea abortaría el
lote entero y se perderían también las buenas.

El Nodo descarta lo rechazado (reintentarlo no serviría) y conserva lo no
confirmado.

## Verificación

Ejecutar dos veces el mismo lote produce el mismo conjunto de confirmadas y
ninguna fila duplicada (`tests/test_observaciones.py`).

Observado en producción durante las pruebas: tras una caída del Núcleo, el Nodo
reenvió una observación en cola junto con una nueva. Ambas quedaron con el
**mismo `recorded_at` al microsegundo** —misma transacción— y `occurred_at`
separados por 13 segundos. Los dos timestamps de 0003 haciendo visible la
diferencia entre cuándo pasó y cuándo se supo.
