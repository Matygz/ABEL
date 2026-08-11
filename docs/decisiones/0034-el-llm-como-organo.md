# 0034 — El modelo de lenguaje como órgano, no como identidad

**Estado:** Vigente
**Fecha:** 2026-08-11
**Fase:** 5

## Decisión

El modelo de lenguaje **traduce, no razona**.

```
texto → [LLM] → estructura → [motor propio] → resultado → [LLM] → texto
```

Nunca calcula, nunca decide, nunca consulta. Reconoce de qué se trata un
mensaje y extrae los datos; resolver es de los motores del Núcleo.

## Contexto

La pregunta que ordenó la fase: *si el LLM solo pone las palabras, ¿qué es
ABEL?*

La respuesta que se sostuvo: **lo que hace que un asistente comercial se
sienta como herramienta no es que le falte "parte humana" — es que no tiene
continuidad.** Arranca de cero cada conversación, no acumula historia, no
tiene nada en juego.

| | Dónde vive | ¿Cambia? |
|---|---|---|
| El modelo | Pesos fijos | No |
| La memoria | PostgreSQL | **Sí, todo el tiempo** |

**Si se cambia el LLM por uno mejor, ABEL no pierde nada.** Su historia sigue
intacta. El modelo es reemplazable; la memoria no.

Eso es exactamente lo contrario de un asistente comercial, donde el modelo es
todo y no hay memoria.

## Interfaz estable, motor intercambiable

`MotorLenguaje` expone `generar()` y `generar_json()`. El resto de ABEL habla
con esa interfaz, nunca con un modelo concreto: cambiar de modelo es cambiar
una línea del `.env`.

Esto convierte la decisión más difícil —qué modelo usar— en una decisión
reversible. Y por eso deja de ser crítica.

## Dos tipos de razonamiento

Distinción central que ordenó el diseño:

**Programable** — cálculo de probabilidades, simulación, búsqueda en espacio
de estados, detección de patrones. Se escribe en Python y sale exacto.

**No programable** — entender lenguaje ambiguo, reconocer de qué trata una
situación, expresarse con naturalidad. Nadie sabe cómo escribir eso
explícitamente; se intentó durante cuarenta años con la IA simbólica.

**El LLM cubre exactamente el segundo grupo.** Y son las dos cosas que ABEL no
puede hacer solo.

La consecuencia práctica: en cálculo, **ABEL es mejor que un LLM grande**. Los
modelos son notoriamente malos con probabilidades — inventan un número que
suena razonable. Un motor propio da el correcto y puede mostrar los pasos.

## Herramientas heredadas, no delegación

El principio 3 dice "herramientas heredadas como componentes, no delegar el
pensamiento". Esta arquitectura es su aplicación literal:

- El LLM es un órgano del lenguaje, como una retina es un órgano de la visión.
- La memoria, las decisiones y el criterio son de ABEL.
- Delegar la cognición al modelo sería construir un chatbot con base de datos.

La alternativa —construir comprensión de lenguaje desde cero— ya se probó en
V.0.2. No funcionó, y no por falta de esfuerzo.
