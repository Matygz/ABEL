# 0037 — La conversación es memoria

**Estado:** Vigente
**Fecha:** 2026-08-11
**Fase:** 5.5

## Decisión

Cada turno de conversación se registra en `events` con el tipo `utterance`.
No hay tabla nueva: `actor_id` distingue quién habló, `occurred_at` los
ordena, el `payload` lleva el texto.

Los últimos turnos se pasan al modelo como contexto.

## Por qué en `events` y no en una tabla propia

La conversación queda sujeta a las mismas reglas que todo lo demás:
append-only, auditable, y **consultable junto con el resto de la memoria**.

El día que ABEL relacione lo que dijiste con lo que estabas haciendo en ese
momento, los dos datos están en la misma tabla con el mismo eje temporal.

Los turnos de ABEL llevan `addressee` en el payload: es lo que permite
recuperar la conversación completa cuando los dos hablantes son actores
distintos.

## Por qué ahora y no en la Fase 6

**Los datos que no se capturan no se recuperan.**

Si la conversación no se persiste desde el principio, al llegar a la Fase 6 no
habría historial que usar — habría que empezar a acumular ahí.

Es la misma lección de los sensores.

## Tres cosas distintas

Conviene no confundirlas, porque tienen momentos distintos:

| | Qué es | Cuándo |
|---|---|---|
| Variedad ante repeticiones | Temperatura del modelo | Hecho |
| Recordar los últimos turnos | Historial en el contexto | Hecho (5.5) |
| **Usar** esa memoria de forma interesante | Traer algo de hace semanas, notar patrones | Fase 6 |

Lo tercero es lo que separa "recuerda" de "le importa".

## Temperatura por tipo de respuesta

- **0.4 para enunciar hechos** — se quiere precisión y consistencia.
- **0.85 para conversar** — la variedad se agradece.

Ante la misma entrada y temperatura baja, el modelo elige casi siempre las
mismas palabras. Eso está bien para datos y mal para charla.

## Dos prompts, no uno

`INSTRUCCIONES` para cuando hay hechos que enunciar; `INSTRUCCIONES_CONVERSACION`
para conversación pura.

**La razón es concreta:** el prompt de hechos menciona que ABEL "recibe HECHOS
verificados". Ante un "hola" sin hechos, un modelo de 4B **rellena el hueco**
inventando alguno. Apareció literalmente: *"Maty dijo que hoy comió una
ensalada de quinoa"*.

El prompt de conversación nunca menciona hechos, así que no hay hueco que
rellenar.

Y cuando la conversación es pura, al modelo se le pasa **el mensaje tal cual**,
sin la ficha de análisis del intérprete: pasarle su propio análisis lo llevaba
a narrarlo en tercera persona en vez de contestar.
