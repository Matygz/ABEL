# Estado — reconocimiento por similitud

**Última sesión:** 2026-08-13
**Estado:** clasificación funcionando, expresador con regresión

---

## Lo que cambió

El intérprete generativo se reemplazó por una cascada de tres capas. El
modelo de lenguaje pasó de clasificar todos los mensajes a atender solo los
que ninguna otra capa reconoció.

```
mensaje
  ↓
patrones      regex — aritmética, sin modelo
  ↓
similitud     embeddings + Qdrant — capacidades conocidas
  ↓
modelo        solo charla o límite, no clasificación
  ↓
capacidades → criterio → expresador
```

Verificado en uso real: de siete mensajes de prueba, **seis se clasificaron
sin tocar el modelo**.

---

## Piezas nuevas

| Archivo | Qué hace |
|---|---|
| `nucleo/lenguaje/vectorizador.py` | Texto a vectores, en CPU |
| `nucleo/lenguaje/indice.py` | Ejemplos en Qdrant, con huella anti-recarga |
| `nucleo/lenguaje/clasificador.py` | Vota entre coincidencias, decide capacidad |
| `nucleo/lenguaje/extractor.py` | Parámetros por patrón; modelo solo si falta |
| `nucleo/lenguaje/particion.py` | Corta el mensaje en intenciones propias |
| `nucleo/lenguaje/analizador.py` | Orquesta la cascada |
| `nucleo/capacidades/registro.py` | Descubrimiento por módulo |
| `nucleo/capacidades/*.py` | Siete capacidades |

### Borrados

`nucleo/lenguaje/interprete.py`, `nucleo/lenguaje/capacidades.py`,
`nucleo/razonamiento/motor_memoria.py`, `tests/test_interprete.py`,
`tests/test_despacho.py`, `tests/test_criterio.py`, `tests/test_conversar.py`.

`MotorCalculo` se conserva: lo usan las capacidades de probabilidad y
aritmética. Su firma cambió a `resolver(clase, enunciado)` — ya no depende de
la estructura de intenciones.

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

### `NIVEL` está declarado pero no se aplica todavía

Las tres son `lectura`. El mecanismo existe para cuando aparezca la primera
capacidad que actúe sobre el mundo.

### `fuera_de_alcance` no es una capacidad

Es lo que queda cuando ninguna supera el umbral. Agregar una capacidad de
calendario hace que "qué tengo en la agenda" **deje de estar fuera de alcance
solo**, sin tocar nada.

Los límites se deducen, no se declaran.

---

## Mediciones

### El modelo de embeddings

**Qwen3-Embedding-0.6B**, 1024 dimensiones, CPU.

| | Tiempo |
|---|---|
| Cargar el modelo | ~12 s (una vez, al arrancar) |
| Vectorizar una frase | 223-440 ms |
| Vectorizar 76 ejemplos | ~40 s (solo si cambiaron) |

**Truncar a 512 dimensiones no sirvió:** el tiempo no bajó (el costo está en
pasar el texto por el modelo, no en el vector de salida) y la separación
empeoró — un caso que debía quedar fuera cruzó el umbral.

### La separación

Con dos frases sueltas el margen era 0,14. Con 76 ejemplos indexados:

| | Rango |
|---|---|
| Reconocidos correctamente | 0,788 – 1,000 |
| Fuera de alcance | 0,592 – 0,659 |

**0,13 de aire limpio.** Umbral en 0,72.

Se confirmó lo previsto: más ejemplos, mejor separación. Comparar contra
veinte ejemplos por capacidad es distinto de comparar dos frases.

### Contra lo que reemplaza

| | Tiempo |
|---|---|
| Intérprete por LLM | ~4.000 ms |
| Clasificador por similitud | ~300 ms |

Y sin posibilidad de inventar categorías.

---

## Pruebas

| Prueba | Resultado |
|---|---|
| `test_vectorizador` | 5/5 pares correctos |
| `test_capacidades` | 7 capacidades descubiertas |
| `test_indice` | 9/9 clasificaciones correctas |
| `test_clasificador` | **15/15** |
| `test_extractor` | 7/7, sin tocar el modelo |
| `test_particion` | 9/9 |

---

## PROBLEMAS ABIERTOS

### 1. El expresador tuvo una regresión

Es lo más urgente. Los HECHOS llegan correctos —verificado en el log:
`- Calculado con exactitud: 11 * 11 = 121`— pero el modelo no los enuncia.

Respuestas observadas: *"Estuve registrado"*, *"Estuve en Code hoy"*, *"Te
escribí"*. Sin el número, sin el dato.

Y hay un círculo vicioso confirmado: **el historial contamina.** Cuatro
respuestas seguidas con "Registrado. Maty..." hicieron que el modelo copiara
el patrón. Con sesión limpia mejora, pero vuelve a degradarse.

Intentos que no alcanzaron:
- Mover la marca de procedencia a corchetes después del dato
- Regla explícita contra la tercera persona
- Advertencia de que el historial no es modelo a imitar

**Necesita revisión completa, no más parches.**

### 2. El umbral es permisivo para frases cortas

*"Me parece bien"* se clasificó como `estado_del_sistema` — probablemente por
cercanía con *"estás funcionando bien"*.

Opciones: subir el umbral para partes cortas, exigir un mínimo de contenido, o
descartar partes que solo aportan cortesía.

### 3. El filtro de aplicación no siempre agarra

*"estoy quemado de code hoy, cuanto tiempo estuve?"* devolvió tres
aplicaciones en vez de filtrar Code. Los patrones funcionan aislados
(`test_extractor` da 7/7), así que el problema es que tras la partición la
parte con la pregunta ya no contiene "code".

**La partición pierde contexto entre partes.** Habría que pasar el mensaje
completo al extractor aunque la clasificación use la parte.

### 4. Pendientes de antes

- El eco: ante "Le pifiaste" respondió "Le pifiaste."
- Gramática rota ocasional — techo del modelo de 4B
- `test_criterio` se borró y no se reemplazó: **falta una prueba de punta a
  punta del flujo nuevo**

---

## Configuración

`.env`:

```
ABEL_QDRANT_URL=http://127.0.0.1:6333
HF_HUB_OFFLINE=1
```

Lo segundo evita que HuggingFace consulte al arrancar. El modelo ya está en
caché, y así ABEL arranca sin internet.

Dependencias nuevas: `sentence-transformers`, `qdrant-client`.

---

## Lo primero al retomar

**El expresador.** Todo lo demás funciona; eso es lo que hace que ABEL
responda mal aunque entienda bien.

Sugerencia de enfoque: revisarlo entero con el flujo nuevo en mano, en vez de
seguir agregando reglas al prompt. Los datos llegan bien — el problema es cómo
se le presentan al modelo.
