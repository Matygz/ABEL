# 0036 — Criterio de habla

**Estado:** Vigente
**Fecha:** 2026-08-11
**Fase:** 5.4

## Decisión

ABEL decide **si responde, qué responde, y con cuánto**. El silencio es una
respuesta válida.

Tres posturas:

| Postura | Qué hace |
|---|---|
| `RESPONDER` | Tiene algo que decir |
| `ACUSAR` | Registró el mensaje, no tiene nada que agregar |
| `CALLAR` | No corresponde ni acusar |

El criterio es **código, no modelo**: tiene que ser predecible y auditable.

## Por qué

Un sistema que siempre contesta algo, y siempre con todo lo que sabe, es un
chatbot. **La diferencia con un compañero está en lo que elige callar.**

Y ningún LLM hace esto solo: están entrenados para responder siempre. Que
ABEL pueda no decir nada requiere una decisión explícita antes de generar.

> **Tener un dato no obliga a decirlo.**

## Las reglas

**El desahogo domina.** Si alguien dice que está quemado, contestarle con
estadísticas de uso de aplicaciones es responder la pregunta literal e ignorar
la real. Cuando hay un `conversar` con registro de desahogo, se descarta todo
lo demás.

**Un límite se dice solo.** Nada de "no tengo tu ubicación, pero usaste Chrome
20 minutos".

**Lo dudoso se descarta.** Una intención con confianza baja produce respuestas
que no vienen al caso.

**Un dato vacío no aporta**, salvo que el usuario haya preguntado
explícitamente por eso (confianza ≥ 0.8).

**Lo repetido no se contesta dos veces.** Si el mensaje es idéntico a uno
reciente, la postura pasa a `ACUSAR`. Alguien que repite un saludo en el mismo
minuto está haciendo otra cosa que saludar.

Esta última se implementó en código porque **el modelo no la respetaba**: con
cuatro repeticiones idénticas en el contexto, un 4B seguía contestando lo
mismo. Es una limitación de tamaño, no de formulación.

## El silencio necesita una señal

Un silencio sin marca es indistinguible de un fallo. La interfaz lo muestra
con un gesto —tres puntos tenues y un destello de la forma— no con una frase
de relleno.

Eso es más expresivo que un "ok" y preserva el vacío.

## El silencio se registra

Un turno con texto vacío y postura `acusar` queda en la memoria. **Que ABEL
decidiera no responder es información**, igual que lo que dijo.
