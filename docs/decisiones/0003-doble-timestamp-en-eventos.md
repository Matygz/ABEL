# 0003 — Doble timestamp en eventos

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

La tabla `events` tiene dos columnas de tiempo, ambas `TIMESTAMPTZ`:

- **`occurred_at`** — cuándo ocurrió el hecho, en el dispositivo donde pasó.
- **`recorded_at`** — cuándo entró a la base del Núcleo.

Todas las columnas de tiempo del proyecto usan `TIMESTAMPTZ`, nunca `TIMESTAMP`.

## Contexto

**Por qué TIMESTAMPTZ:** `TIMESTAMP` guarda "14:30" sin saber de dónde. Con un
Nodo en otra zona horaria, un cambio de horario de verano, o al comparar
eventos de dos dispositivos, el dato queda ambiguo y no se puede corregir
retroactivamente. `TIMESTAMPTZ` normaliza internamente a UTC.

**Por qué dos columnas:** en un sistema centralizado los dos tiempos son casi
idénticos y la distinción parece innecesaria. En un sistema distribuido con
Nodos que trabajan desconectados pueden diferir por horas. Guardar uno solo
pierde información que después no se recupera.

## Consecuencias

- Una columna extra por evento. Costo despreciable.
- En la Fase 1 los dos valores van a ser prácticamente iguales. La utilidad
  aparece en la Fase 2, con sincronización de Nodos.
- Las consultas tienen que elegir explícitamente cuál usar. Por defecto,
  `occurred_at` (cuándo pasó realmente).
