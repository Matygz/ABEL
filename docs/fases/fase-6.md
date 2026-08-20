# Fase 6 — Reconocimiento por similitud

**Estado:** Cerrada
**Fecha de cierre:** 2026-08-14
**Versión del proyecto:** 0.0.1

## Objetivo

Que el modelo de lenguaje deje de clasificar. Reconocer intenciones por
similitud contra ejemplos conocidos, y que las capacidades se descubran solas.

## Por qué

Tres evidencias acumuladas de que el intérprete generativo tenía techo:

1. Fallaba ante frases fuera de patrón, poniéndose a **completar los ejemplos
   del prompt** en lugar de interpretar.
2. Los ejemplos de una categoría degradaban las otras — los cuatro de
   `fuera_de_alcance` rompieron la clasificación de cálculo.
3. Cada capacidad nueva competiría por espacio en el prompt.

**Un prompt no mejora nunca.** Un índice de ejemplos sí: cada mensaje bien
clasificado se puede sumar, y el reconocimiento mejora con el uso.

---

## La cascada

```
mensaje
  ↓
patrones      regex — aritmética, sin modelo, instantáneo
  ↓
similitud     embeddings + Qdrant — capacidades conocidas
  ↓
modelo        solo charla o límite, no clasificación
  ↓
capacidades → criterio → expresador
```

Cada capa resuelve lo que puede y solo pasa hacia abajo lo que no reconoce.

**El modelo pasó de atender todos los mensajes a atender los que ninguna otra
capa reconoció.** Y en esos casos no elige entre categorías: solo decide si es
charla o un límite, que es una pregunta mucho más chica.

Un clasificador que solo puede elegir entre capacidades existentes **no puede
inventarse una categoría**. Ese era el modo de fallo.

---

## Las capacidades se descubren solas

Un módulo en `nucleo/capacidades/` declara:

```python
NOMBRE = "actividad_por_aplicacion"
TIPO = "consultar_memoria"
DESCRIPCION = "Cuánto tiempo se usó cada aplicación."
NIVEL = "lectura"            # lectura | admin | puntual
NECESITA = ("memoria",)
EJEMPLOS = (...)
PARAMETROS = {...}

async def resolver(parametros, memoria): ...
```

**Agregar una capacidad es agregar un archivo.** No hay lista que mantener, ni
ejemplos que cargar a mano, ni despachador que tocar.

### `NECESITA` acota el alcance por construcción

Una capacidad solo recibe lo que declaró. `conversar` declara `()` y por lo
tanto **no puede tocar la base ni queriendo** — no tiene con qué.

Es el criterio de 0030 hecho mecánico en vez de disciplina. Hoy con siete
capacidades de lectura da igual; cuando haya una que escriba o acceda a una
API, va a importar.

### `NIVEL` está declarado pero no se aplica

Las siete son `lectura`. El mecanismo existe para cuando aparezca la primera
capacidad que actúe sobre el mundo.

### `fuera_de_alcance` no es una capacidad

Es lo que queda cuando ninguna supera el umbral. Agregar una capacidad de
calendario hace que "qué tengo en la agenda" **deje de estar fuera de alcance
solo**, sin tocar nada.

Los límites se deducen, no se declaran.

### ABEL responde qué sabe hacer desde el registro

La capacidad `sobre_si_mismo` consulta el registro mismo. La respuesta sale de
lo que efectivamente está cargado, no de una lista escrita a mano que puede
quedar desactualizada.

---

## Mediciones

### El modelo de embeddings

**Qwen3-Embedding-0.6B**, 1024 dimensiones, CPU.

| | Tiempo |
|---|---|
| Cargar el modelo | ~12 s (una vez, al arrancar) |
| Vectorizar una frase | 223-440 ms |
| Vectorizar 96 ejemplos | ~45 s (solo si cambiaron) |

CPU a propósito: vectorizar una frase corta no gana con GPU, y la GPU hace
falta para generar. Cada uno donde rinde.

**Truncar a 512 dimensiones no sirvió:** el tiempo no bajó —el costo está en
pasar el texto por el modelo, no en el vector de salida— y la separación
empeoró.

### La separación

Con dos frases sueltas el margen era 0,14. Con 96 ejemplos indexados:

| | Rango |
|---|---|
| Reconocidos | 0,788 – 1,000 |
| Fuera de alcance | 0,592 – 0,683 |

Se confirmó lo previsto: **más ejemplos, mejor separación**. Comparar contra
veinte ejemplos por capacidad es distinto de comparar dos frases.

### Contra lo que reemplaza

| | Tiempo |
|---|---|
| Intérprete por LLM | ~4.000 ms |
| Clasificador por similitud | ~300 ms |

---

## Umbral por longitud

Un umbral fijo de 0,72 dejaba pasar frases cortas y vagas: *"me parece bien"*
caía en `estado_del_sistema` por cercanía con *"estás funcionando bien"*.

**Una frase de tres palabras da similitudes altas sin decir mucho.** Se les
exige más:

| Longitud | Umbral |
|---|---|
| 3 palabras o más | 0,72 |
| Menos de 3 | 0,85 |

Y se agregaron veinte ejemplos cortos a `conversar` —"dale", "ok", "qué onda",
"todo bien"— que ahora superan el umbral alto.

**Además:** un mensaje de tres palabras o menos que no se reconoce nunca es
`fuera_de_alcance`. Pedir algo que ABEL no puede hacer requiere decir qué;
nadie pide una capacidad en dos palabras.

---

## Extracción de parámetros

Separada de la clasificación. Primero patrones —rangos temporales, nombres de
aplicaciones conocidas— y el modelo solo si queda algo sin resolver.

**Ninguna de las siete capacidades necesita el modelo para extraer.**

### La extracción usa el mensaje completo

La partición sirve para clasificar, no para extraer. En *"estoy quemado de
Code hoy, ¿cuánto tiempo estuve?"* la aplicación se nombra en la primera mitad
y la pregunta está en la segunda.

Si el extractor viera solo la parte clasificada, el filtro se perdería.

---

## Partición de mensajes

Un mensaje puede contener varias intenciones. Se corta por señales fuertes
—signos de interrogación, puntuación— y no por cualquier conector: *"estuve
todo el día en el código y estoy quemado"* es una sola cosa dicha de corrido.

**El corte importa por algo más que reconocer las dos.** Distingue lo que la
persona pidió de lo que ABEL dedujo:

| Mensaje | Qué corresponde |
|---|---|
| "estuve todo el día en el código y estoy quemado" | Solo el desahogo — la consulta la infirió ABEL |
| "estoy quemado de Code, ¿cuánto tiempo estuve?" | Las dos — el dato lo pidió él |

Una parte propia del mensaje es un pedido explícito y no se descarta por
criterio.

**El saludo inicial se descarta:** *"hola, ¿cuánto estuve en Code?"* es una
consulta con cortesía adelante, no dos intenciones.

---

## Respuestas que no pasan por el modelo

Dos casos donde dejar redactar solo agrega riesgo:

**Cálculos exactos.** Se lo vio escribir *"cincuenta y dos"* ante un hecho que
decía `11 * 11 = 121`. Un modelo chico transcribiendo cifras no es de fiar. El
número es la respuesta.

**Límites.** Ante `fuera_de_alcance` por control de dispositivos, respondió
**"La luz del living prendió."**

Afirmar haber hecho algo que no se hizo es el peor fallo posible. Ahora sale de
plantilla: *"No tengo control de dispositivos del hogar."*

**Y la enumeración de capacidades**, que es una lista y el modelo la resumía
mal o la ignoraba.

---

## El historial contamina

Descubierto al depurar una regresión aparente del expresador.

Cuatro respuestas seguidas con *"Registrado. Maty..."* hicieron que el modelo
copiara el patrón. **Cada respuesta mala generaba la siguiente.**

Y con un mensaje corto sin datos, el historial aporta material para rellenar:
ante *"hola"* y un *"121."* dos líneas arriba, el modelo respondió **121**.

Dos medidas:

- Cuando el turno es charla y el mensaje tiene menos de 25 caracteres, **no se
  pasa historial**. Lo que no tiene con qué rellenar, no rellena.
- Advertencia explícita de que el historial es contexto, no un modelo a imitar.

**El expresador estaba bien.** Lo que fallaba era lo que le llegaba.

---

## Pruebas

| Prueba | Verifica |
|---|---|
| `test_vectorizador` | Similitud entre pares |
| `test_capacidades` | Descubrimiento de módulos |
| `test_indice` | Coincidencias en Qdrant |
| `test_clasificador` | **15/15** enrutamiento |
| `test_extractor` | 7/7, sin tocar el modelo |
| `test_particion` | 9/9 cortes |
| `test_conversacion` | **12/12** punta a punta |

`test_conversacion` verifica **el enrutamiento, no el texto**: la redacción
varía por diseño, así que exigir palabras concretas daría falsos negativos.
Los números sí se verifican — esos no pueden variar.

Ya detectó una regresión real: bajar `PALABRAS_MINIMAS` rompió la detección de
dos intenciones en un mensaje mixto.

---

## Bugs corregidos

### El bucle que agotó PostgreSQL

Un Nodo huérfano de una sesión anterior reconectaba sin espera. Cada intento
abría una conexión a la base. **Decenas de conexiones en dos segundos**, hasta
`remaining connection slots are reserved for roles with the SUPERUSER
attribute`.

La causa: `websockets` reinicia su retroceso cuando el WebSocket se establece,
aunque el saludo falle después.

Ahora hay retroceso propio —2, 4, 8… hasta 60 segundos— que **solo vuelve al
mínimo cuando el saludo funcionó**. Verificado: dos rechazos en cuatro
segundos en vez de cien.

### El lanzador dejaba procesos vivos

`abel.py` ahora mata Núcleos y Nodos huérfanos antes de arrancar, espera a que
PostgreSQL acepte conexiones, y espera a que el Núcleo escuche antes de lanzar
el Nodo.

**Y cuando el Núcleo se cae, reinicia también el Nodo**: sin eso queda
apuntando a un Núcleo que ya no existe.

La espera fija de 3 segundos se quedó corta cuando el Núcleo empezó a cargar
el vectorizador. Ahora espera al puerto, no un tiempo.

---

## Estado al cierre

De diez mensajes de prueba, **nueve se clasifican sin tocar el modelo de
lenguaje**. Solo `"prendé la luz del living"` llega a la tercera capa.

```
11 x 11                              → 121.
¿cuánto tiempo estuve en Code hoy?   → Estuviste en Code por veintidós minutos.
a qué hora arranqué                  → Arrancaste a las 20:17.
prendé la luz del living             → No tengo control de dispositivos del hogar.
estoy quemado de code, ¿cuánto…?     → Estuviste 21 minutos con Code.exe.
```

---

## Lo que sigue flojo

**La conversación pura.** *"Te parece"*, *"Estoy acá"*, *"Arrancaste"* —
respuestas sin contenido. Es el techo de un modelo de 4B y no se resuelve con
prompts: llevamos veinte iteraciones.

**El eco.** Ante *"Le pifiaste"* respondió *"Le pifiaste."*

**Gramática rota ocasional.** Techo del modelo.

---

## Lo que la fase NO tiene

**El índice no crece con el uso todavía.** La infraestructura está —los
ejemplos se cargan desde el catálogo y se re-vectorizan si cambian— pero un
mensaje bien clasificado no se suma automáticamente como ejemplo.

Eso es lo que haría que ABEL reconozca mejor **a esta persona en particular**,
y es el paso natural siguiente.

**No hay capacidades que actúen sobre el mundo.** Las siete son de lectura.
`NIVEL` existe pero no se verifica.

**ABEL no dice nada por su cuenta.** Responde cuando se le habla.
