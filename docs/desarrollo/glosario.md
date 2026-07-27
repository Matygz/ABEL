# Glosario

Vocabulario del proyecto. Su función es evitar que un mismo término signifique
cosas distintas en momentos distintos.

Se agregan entradas cuando un término genera confusión real, no de forma
preventiva.

---

## marca de presencia (`presence_mark`)

Registro periódico que deja constancia de que el Núcleo existía en un momento
dado. **No inspecciona nada ni procesa nada.** Es una marca en el tiempo.

**Su valor está en la ausencia, no en la presencia.** Un `presence_mark` no
aporta información; un hueco entre dos marcas indica que el Núcleo estuvo
caído, y delimita cuándo.

> ⚠️ **No confundir con "latido" en el sentido de ABEL V.0.2.**
>
> En V.0.2, el latido era el pulso de procesamiento: el tick donde los módulos
> se actualizaban y el estado avanzaba un paso. **El latido *era* el acto de
> pensar** — sin latido no había cognición, y por eso su frecuencia era crítica.
>
> El `presence_mark` es algo completamente distinto: una fila en una tabla que
> dice "estaba vivo a las 14:32". Es contabilidad, no cognición. Su intervalo
> es indiferente para el comportamiento del sistema.
>
> Se eligió el nombre `presence_mark` precisamente para dejar el término
> "latido" libre para su acepción original, que probablemente reaparezca en
> fases posteriores.

---

## comprobación de estado

Inspección **activa** de si algo funciona: ¿la base responde?, ¿hay memoria?,
¿el Nodo sigue conectado?

Distinto de la marca de presencia:

| | Qué hace |
|---|---|
| **marca de presencia** | "estuve acá" |
| **comprobación de estado** | "revisé que X funciona" |

En la Fase 1 los dos conceptos se superponen por accidente: como la marca se
escribe en PostgreSQL, si la escritura funciona es porque la base respondió.
Es una coincidencia de esta fase, no la definición. Con más componentes, las
comprobaciones serán tareas aparte con sus propias cadencias.

---

## evento

Registro estructurado en base de datos de algo que ABEL hizo o percibió.
Consultable, relacionable, permanente. Es la memoria de su existencia.

**Cada evento lo escribe quien lo produce, en el momento en que ocurre.** No
se recolectan ni se agrupan periódicamente.

---

## log

Archivo de texto para depurar, dirigido al programador. Mensajes de progreso,
excepciones, trazas de error. Se lee cuando algo se rompe. Rota y se borra.

**Regla práctica para distinguirlo de un evento:** si es para el programador
depurando, es log. Si es parte de lo que ABEL sabe sobre su propia historia,
es evento. Se necesitan los dos.

---

## actor

Toda entidad capaz de causar un evento: un módulo, un dispositivo, un usuario,
o el propio Núcleo (`actor_type = 'system'`).

Ver `docs/decisiones/0004-supertipo-subtipo-para-actores.md`.

---

## ejecución (`run`)

Un arranque del Núcleo, desde que inicia hasta que termina. Permite distinguir
"lo que pasó anoche" de "lo que está pasando ahora".

Una ejecución con `ended_at IS NULL` que no es la vigente indica que el proceso
murió sin apagarse ordenadamente.

---

## Núcleo

El proceso central que corre en la PC principal. Contiene el bucle de eventos,
el planificador de tareas y el acceso a la base de datos.

## Nodo

Presencia periférica en un dispositivo autorizado. Tiene SQLite local, puede
operar desconectado, y sincroniza con el Núcleo cuando hay conexión.

Esa capacidad de operar desconectado es la razón de varias decisiones de
esquema (ver 0002 y 0003).
