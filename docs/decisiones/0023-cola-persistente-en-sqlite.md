# 0023 — Cola persistente en SQLite

**Estado:** Vigente
**Fecha:** 2026-08-03
**Fase:** 2.5

## Decisión

La cola de observaciones del Nodo se guarda en **SQLite**, en modo WAL, con
durabilidad configurable por dispositivo.

La interfaz de `ColaObservaciones` no cambia: `cliente.py` no sabe dónde viven
los datos.

## Contexto

La cola de la Fase 2.2 era un diccionario en memoria. Si el Nodo se caía, se
reiniciaba o se apagaba el dispositivo, **todo lo pendiente se perdía**.

Y ese era justamente el escenario que la cola existía para cubrir: el Nodo
captando sin enlace. Si además el proceso se reiniciaba en ese período —cosa
habitual en un celular— la cola no había servido de nada.

SQLite ya estaba previsto en la arquitectura para los Nodos. Su límite conocido
—un escritor a la vez— descartaba usarlo en el Núcleo (0001), pero para un Nodo
de un solo proceso es exactamente lo que hace falta. Viene en la biblioteca
estándar: no agrega dependencias.

## Durabilidad configurable

SQLite controla con `synchronous` si espera confirmación física del disco:

| Valor | Sobrevive a | Costo |
|---|---|---|
| `FULL` | Corte de energía | Un `fsync` por operación |
| `NORMAL` | Reinicio del proceso | Puede perder lo último ante un apagón |
| `OFF` | Nada | — |

**Por defecto `NORMAL` con WAL.** Para un Nodo que escribe una observación por
minuto, `FULL` significaría un `fsync` por minuto, con costo de batería y de
vida útil de la memoria flash.

Es un intercambio consciente: **se pierden como mucho las últimas
observaciones ante un corte abrupto, a cambio de no castigar el disco.**

Pero la política correcta no depende del tipo de dispositivo sino de **cuánto
duele perder lo último**: marcas de presencia cada minuto toleran `NORMAL`;
algo que se captura una vez y no se repite querría `FULL`.

Por eso es un campo del `nodo.config.json`. Encaja con el modelo: **el Nodo no
decide, aplica.** La política la define el operador al instalar cada Nodo.

**Pendiente:** que el Núcleo comunique la durabilidad en el `welcome`, como ya
hace con el intervalo de presencia. Hay un problema de huevo y gallina —la cola
debe existir antes de conectarse— resoluble pero no ahora.

## Detalles de implementación

**`isolation_level=None`** pone SQLite en autoconfirmación. Sin eso, Python
abre transacciones implícitas y una observación agregada no llegaría a disco
hasta un `commit` explícito — exactamente lo que se quiere evitar.

**El orden por `id` es cronológico.** Parece un atajo y es correcto: son
UUIDv7, cuyos primeros bits son un timestamp. Es la decisión 0002 pagando
dividendos en un lugar que no se había previsto.

**`INSERT OR IGNORE`** hace que agregar dos veces la misma observación no sea
un error. Mismo espíritu que el `ON CONFLICT DO NOTHING` del Núcleo (0017).

**Las filas corruptas se descartan, no rompen.** Si una fila quedó a medio
escribir por un apagón, se registra y se elimina. Una cola que revienta al
leerse es peor que perder una observación.

## Verificación

Ciclo completo, verificado: se corta el Núcleo → el Nodo acumula → se apaga el
Nodo por completo → se reinician ambos → `Cola recuperada del disco: 1
pendiente(s)` → se envía → la cola queda en cero.

Eso es exactamente lo que antes se perdía.

## Pendiente conocido

El límite de la cola es por **cantidad de filas** (10.000). Con marcas de
presencia eso es una semana de datos y no representa nada para SQLite.

Cuando la Fase 3 capture audio o imágenes, la cuenta cambia: **el límite tendrá
que ser por tamaño, no por cantidad.**

La política de poda descarta lo más antiguo, privilegiando lo reciente sobre lo
completo. Discutible según el tipo de dato; configurable a futuro.
