# 0002 — UUIDv7 como identificadores

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

Todas las claves primarias son `UUID`, generadas con `uuidv7()` (función
nativa de PostgreSQL 18).

Excepción: `event_types.name` usa el nombre como clave primaria, por ser un
catálogo chico, estable y legible.

## Contexto

**Esta decisión es arquitectónica, no estética.** La causa es la escritura
distribuida, no la modernidad del tipo de dato.

Los Nodos tienen SQLite local y generan datos **sin estar conectados** al
Núcleo. Un contador autoincremental vive dentro de una sola base y no sabe que
existen otras. Al sincronizar:

- Si el Nodo conserva su ID, choca con el ID que el Núcleo ya usó.
- Si el Núcleo renumera, el mismo hecho pasa a tener dos nombres distintos. Y
  si ese evento estaba referenciado por otros datos locales del Nodo, esas
  referencias apuntan a la nada — o peor, a otra cosa.

Con UUID, el Nodo genera el identificador en el momento de crear el dato, sin
consultar a nadie. Nace único y no cambia nunca. La sincronización se reduce a
"insertá esto si no lo tenés".

**Por qué v7 y no v4:** el v7 incorpora un timestamp en los primeros bits, lo
que lo hace aproximadamente ordenable por tiempo. Mantiene la unicidad
distribuida y elimina la degradación de índices del v4 (aleatorio puro).

## Alternativas descartadas

- **`BIGSERIAL`.** Solo único dentro de una base. Rompe con escritura distribuida.
- **Clave compuesta** (`device_id` + `local_id`). Funciona, pero todas las
  claves foráneas pasan a ser de dos columnas. Incómodo rápido.
- **Rangos por dispositivo.** Frágil: se rompe al agregar un dispositivo no
  previsto o al agotarse un rango.

## Consecuencias

- Identificadores ilegibles a simple vista. Se compensa con la columna `name`
  en `actors` y con nombres legibles en `event_types`.
- Mayor tamaño en disco que un entero. Irrelevante a esta escala.
- Depende de PostgreSQL 18+. En SQLite (Nodos) habrá que generar el UUIDv7
  desde Python.
