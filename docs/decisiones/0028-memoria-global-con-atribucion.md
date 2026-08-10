# 0028 — Memoria global con atribución

**Estado:** Vigente
**Fecha:** 2026-08-08
**Fase:** 4

## Decisión

**Una sola memoria, global, con atribución por `actor_id`.** No hay bloques
separados por persona.

## Contexto

Aparecía una tensión aparente entre dos objetivos: que ABEL esté
personalizado para cada persona —sus rutas, su historia, sin confundirlas con
las de otros— y que sea global como la Máquina de POI.

Son dos lecturas de la misma cosa, no dos arquitecturas. La Máquina es un
único sistema con una única memoria, y aun así distingue a cada persona.

**El esquema ya funcionaba así desde la Fase 0.3.** Cada evento lleva
`actor_id`. Consultar lo de una persona es filtrar; consultar todo es no
filtrar.

## Por qué no bloques separados

Lo que se separa no es el almacenamiento sino **la vista**:

| Pregunta | Filtro |
|---|---|
| ¿Qué hice ayer? | Un actor |
| ¿Quién estuvo en casa? | Ninguno |
| ¿Cuándo coincidimos? | Dos actores cruzados |

La tercera es la que descarta los bloques: **con la memoria partida por
persona, esa consulta sería imposible.** Y es justamente el tipo de relación
que hace interesante al modelo.

Un ABEL por persona sería un ABEL más chico, incapaz de ver relaciones. Un
ABEL sin atribución sería un ABEL confundido, mezclando datos de gente
distinta.

## Política de acceso

Decidido:

- Cada usuario accede a lo suyo.
- El rol `admin` ve todo.

**Sin definir:** qué puede ver un usuario sobre otro. La idea de acceso
"superficial" a los conocidos necesita concretarse — no es un nivel que exista
en el esquema. Formas posibles: por tipo de evento, por agregación (resúmenes
sí, eventos individuales no), o por consentimiento de cada persona.

Y una pregunta previa a todas: **¿la otra persona sabe que ABEL la registra?**
El principio 1 aplica de lleno.

**Hay que resolverlo antes de que exista un segundo usuario**, no después.

## Afirmaciones sobre personas — pendiente de Fase 5/6

El esquema hoy no soporta hechos sobre un actor ("se llama X", "tiene Z
años", "es la madre de Maty"). Faltan tres piezas:

**Afirmaciones** — con fuente, momento y confianza. Varias pueden coexistir
aunque se contradigan.

**Relaciones entre actores** — con dirección: "madre de" no es simétrico. Es
donde asoma Neo4j.

**Reconciliación de identidad** — cuando una persona de la que se habló entra
por primera vez, ¿cómo se reconoce que es la misma?

### El caso de la edad, que expone el problema

Si el usuario dice que su madre tiene 45 y ella dice 46:

- **No es un hecho, es una derivación.** Lo que se guarda es la fecha de
  nacimiento; la edad se calcula. "52 años" queda viejo en un año.
- **Nadie es la verdad.** ABEL no puede saber quién acierta.
- **No debe sobrescribir.** Debe registrar **dos afirmaciones en conflicto**,
  con quién las dijo y cuándo. La contradicción es información que se perdería.

Es la misma lógica de `settings` (0006) y de la distinción observado/inferido:
no destruir lo anterior al recibir algo nuevo.

Por el principio 7, cuando ABEL afirme algo sobre una persona debe poder citar
su fuente. Un sistema que afirma sin poder decir de dónde lo sacó es
exactamente lo que no se quiere construir.

## Nota de alcance

Esto **no** habilita ABEL como servicio abierto. Ver 0031.
