# 0035 — Despacho por tipo de problema

**Estado:** Vigente
**Fecha:** 2026-08-11
**Fase:** 5.2

## Decisión

El intérprete clasifica cada mensaje en un tipo de intención, y el despachador
lo enruta al motor que sabe resolverlo.

```
"¿cuánto estuve en Code hoy?"    → consultar_memoria → SQL
"si tiro 3 dados, ¿cuál es...?"  → calcular          → motor de cálculo
"me siento como el orto"         → conversar         → LLM directo
"prendé la luz"                  → fuera_de_alcance  → respuesta honesta
```

Agregar una clase nueva de problema es registrar un motor más.

## El cuarto tipo es el que más importa

`fuera_de_alcance` existe para que **ABEL sepa qué no puede hacer y lo diga**,
en vez de forzar el mensaje para que encaje en algo que sí sabe.

Verificado en las primeras pruebas: sin ese tipo, "prendé la luz del living"
se clasificaba como consulta de memoria y ABEL respondía con datos de uso de
aplicaciones. El modelo prefiere devolver algo antes que admitir que no aplica.

## Múltiples intenciones por mensaje

Un mensaje puede contener varias cosas. *"Estuve todo el día en el código y
estoy quemado"* es una consulta **y** un desahogo.

El intérprete devuelve una lista ordenada por confianza. **Qué se hace con
esa lista —responder a las dos, a una, o a ninguna— lo decide el criterio de
habla (0036), no el intérprete.**

Y ahí está el punto: quizás la respuesta correcta a ese mensaje **no sea decir
cuántas horas fueron**. Decirlas sería responder la pregunta literal e ignorar
la real.

## El cálculo, resuelto exacto

El LLM extrae la estructura del enunciado —cantidad de dados, caras,
comparador, objetivo— y un motor propio **enumera todas las combinaciones y
cuenta**. Sin fórmulas ni aproximaciones.

Se usa `Fraction` en vez de `float`: la probabilidad se calcula como fracción
exacta y recién al final se convierte. El resultado no arrastra error de coma
flotante.

Verificado con cuatro casos, todos exactos. Y uno que muestra la diferencia:
ante "probabilidad de sacar más de 30 con tres dados" no solo devuelve 0% sino
que **detecta que el pedido es imposible** y explica que el máximo es 18.

Los `pasos` de cada resultado permiten que ABEL explique cómo llegó — un LLM
no puede: genera el número sin saber de dónde salió.

## Contexto antes, no análisis después

Un modelo no puede traducir "lo de mi vieja" sin saber qué lugares conoce
ABEL. La solución **no es analizar la oración con más detalle**: es darle la
información antes de pedirle que interprete.

`ProveedorContexto` arma ese material: aplicaciones registradas, dispositivos,
rango de datos disponible, y —crucialmente— **qué NO registra ABEL**.

Esa última línea es tan importante como las otras: sin ella el modelo intenta
interpretar "¿dónde estuve ayer?" como una consulta válida.

El contexto se escribe en prosa, no en JSON. Los modelos siguen mejor un
contexto redactado que una estructura anidada.

## Ambigüedad: responder con alternativas

Cuando una pregunta admite varias lecturas y los resultados difieren:

> *"En las últimas 24hs no visitaste a tu mamá. En la última semana, 3 veces."*

**Criterio:** si las interpretaciones dan resultados parecidos, responder con
las dos. Si dan resultados incompatibles, o falta un dato que ABEL no tiene,
preguntar.

Ese "difieren de forma significativa" es código propio, no LLM.

## Validación en el borde

Todo lo que devuelve el modelo se valida: tipos contra el catálogo, confianza
acotada a [0,1], parámetros que sean diccionarios, máximo cinco intenciones.
Un modelo chico inventa tipos que no existen.

Y `fuera_de_alcance` es **excluyente**: si aparece, se descarta cualquier
consulta de memoria en el mismo mensaje. Si ABEL no registra lo que se pide,
no hay memoria que consultar.

## Lección sobre prompts

Los cuatro ejemplos de `fuera_de_alcance` que se agregaron para arreglar un
problema **crearon otro**: el modelo generalizó y empezó a rechazar también
los cálculos.

Se corrigió agregando al contexto la línea *"ABEL SÍ resuelve cálculos de
probabilidad: eso nunca es fuera_de_alcance"*.

**Enseñarle a decir que no también se puede sobre-enseñar.**
