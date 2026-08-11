# Fase 5 — Estado y plan

**Última sesión:** 2026-08-10
**Estado:** 5.1 en curso

---

## Hecho hoy

- `nucleo/lenguaje/motor.py` — interfaz con el modelo. `generar()` y
  `generar_json()`. El resto de ABEL habla con `MotorLenguaje`, nunca con un
  modelo concreto: cambiar de modelo es cambiar el `.env`, no el código.
- `nucleo/lenguaje/servidor_modelo.py` — levanta el modelo bajo demanda, lo
  baja tras 15 minutos sin uso. Registrado como servicio `vigilante_modelo`.
- Configuración en `.env`: `ABEL_LLM_EXE`, `ABEL_LLM_MODEL`, `ABEL_LLM_PORT`,
  `ABEL_LLM_IDLE`.
- Dependencia nueva: `httpx`.

**Verificado:** carga en 6 s, responde, segunda llamada instantánea, descarga
al cerrar el Núcleo.

---

## El hallazgo de la sesión: Vulkan funciona

| | Generación |
|---|---|
| GPU (Vulkan, `-ngl 99`) | **75 t/s** |
| CPU (`-ngl 0`) | 12 t/s |

`ggml-vulkan.dll` detecta la RX 5500 XT sin necesidad de ROCm. Los 8 GB de
VRAM son utilizables.

**Consecuencia:** la limitación de hardware que se asumió durante todo el
diseño previo no existe. Se elige modelo por calidad, no por lo que la máquina
aguante.

| Modelo | VRAM | Velocidad estimada |
|---|---|---|
| 3-4B Q4 | ~2,5 GB | 60-75 t/s |
| 7-8B Q4 | ~5 GB | 30-40 t/s |
| 14B Q4 | ~8,5 GB | No entra completo |

`pp512` a 661 t/s: procesar contexto es rapidísimo. **Mandarle contexto rico
al modelo casi no cuesta tiempo** — clave para el diseño del intérprete.

Modelo actual: Qwen2.5 3B Q4_K_M. **Es de prueba**, elegido solo para medir.
La comparación real de candidatos queda para el cierre de la fase.

---

## Próximo paso: el intérprete

`nucleo/lenguaje/interprete.py`. Convierte texto en estructura.

### Devuelve una lista de intenciones, no una sola

```json
{
  "intenciones": [
    {"tipo": "consultar_memoria", "confianza": 0.9,
     "parametros": {"metrica": "tiempo_por_aplicacion", "rango": "hoy"}},
    {"tipo": "conversar", "confianza": 0.85,
     "parametros": {"registro": "desahogo", "tono": "cansancio"}}
  ],
  "ambiguedades": []
}
```

Un mensaje puede contener varias cosas. "Estuve todo el día en el código y
estoy quemado" es una consulta **y** algo emocional.

**Qué hace ABEL con esa lista** —responder a las dos, a una, o a ninguna— es
decisión de 5.4, no del intérprete.

Y ahí está el punto: quizás la respuesta correcta a ese mensaje **no sea decir
cuántas horas fueron**. Decirlas sería responder la pregunta literal e ignorar
la real.

### Cuatro tipos de intención

| Tipo | Ejemplo | Destino |
|---|---|---|
| `consultar_memoria` | "¿cuánto estuve en Code hoy?" | `nucleo/memoria` |
| `conversar` | "me siento como el orto" | LLM directo |
| `calcular` | "si tiro 3 dados..." | Motor de cálculo (5.2) |
| `fuera_de_alcance` | "prendé la luz" | Respuesta honesta |

El cuarto es el que más importa: **que ABEL sepa qué no puede hacer y lo diga**
en vez de inventar.

### El contexto va con la consulta

El LLM no puede traducir "lo de mi vieja" sin saber qué lugares conoce ABEL.
La solución no es un analizador después del LLM: es **darle el contexto antes**.

Contexto inicial (magro, porque hoy no hay lugares ni personas):

```
Aplicaciones conocidas: Code.exe, opera.exe, claude.exe, WhatsApp.exe
Dispositivos: PC-Maty
Rango de datos: desde 2026-07-28
Fecha y hora actual: ...
```

Cuando existan lugares y personas, se suman ahí sin tocar nada más.

### Ambigüedad: responder con alternativas, no elegir mal

Si "últimamente" puede ser una semana o un mes y los resultados difieren:

> *"En las últimas 24hs no visitaste a tu mamá. En la última semana, 3 veces."*

**Criterio de cuándo responder y cuándo preguntar:** si las interpretaciones
dan resultados parecidos, responder con las dos. Si dan resultados
incompatibles, o falta un dato que ABEL no tiene (nunca escuchó "la casa de tu
vieja"), preguntar.

Ese "difieren de forma significativa" es **código propio, no LLM**.

---

## Partición de la fase

| | Contenido | Estado |
|---|---|---|
| 5.1 | Motor + intérprete | Motor hecho, intérprete pendiente |
| 5.2 | Despachador y motores de razonamiento | Pendiente |
| 5.3 | Expresador y conversación con continuidad | Pendiente |
| 5.4 | Criterio de habla: cuándo responder, cuándo callar | Pendiente |
| 5.5 | Servicio en background, bandeja, arranque automático | Pendiente |

Al cerrar la fase: **prueba comparativa de modelos** con preguntas propias.

---

## Decisiones de arquitectura acordadas (para ADR)

### El LLM no razona: traduce

```
texto → [LLM] → estructura → [motor propio] → resultado → [LLM] → texto
```

El LLM nunca calcula. Reconoce que algo es un cálculo, extrae los datos, y un
motor propio lo resuelve **exacto**.

Los LLM son notoriamente malos con probabilidades y aritmética: un modelo chico
inventa un número que suena razonable. Un motor propio da el correcto **y puede
explicar los pasos**.

En ese terreno **ABEL sería mejor que un LLM grande**, no peor.

### Despacho por tipo de problema

```
"¿cuánto estuve en Code hoy?"     → consulta a memoria       → SQL
"si tiro 3 dados, ¿cuál es...?"   → problema probabilístico  → motor de cálculo
"tengo 3 tareas y 5 horas..."     → problema de optimización → motor de búsqueda
"me siento como el orto"          → conversación             → LLM directo
```

Para un acertijo, el LLM extrae la estructura —actores, recursos,
restricciones, objetivo— y un motor de búsqueda en espacio de estados lo
resuelve.

**Límite honesto:** extraer restricciones implícitas ("la linterna debe
volver" no está en el enunciado) es donde un modelo chico va a fallar. Cuando
falle, ABEL debe decirlo y pedir aclaración, no inventar.

### Catálogo de tipos de problema, no de acciones

Cada tipo necesita su propio esquema y su propio motor. Crecer es agregar tipos.

### Carga bajo demanda

El modelo no corre siempre: ocupa VRAM permanentemente y esa VRAM le hace falta
al resto del sistema (juegos, etc.).

```
Sin conversación → modelo descargado, 0 GB de VRAM
Le hablás       → ABEL lo levanta (~6 s)
Seguís hablando → ya está caliente
15 min sin uso  → se baja solo
```

Lo que sí corre siempre: Núcleo, Nodo y PostgreSQL. ~340 MB de RAM, cero VRAM.

**Mejora posible:** usar `session_state` para descargar cuando detecta que el
usuario se fue, sin esperar el temporizador.

---

## Discusiones de fondo de esta sesión

### Sobre el catálogo de acciones

Preocupación planteada: *"si algo no está en la lista, no lo conoce"*.

Resolución: hay **dos ejes** distintos.

- **Eje de conocimiento** — qué puede saber, inferir, relacionar. **Sin
  catálogo, sin límite.**
- **Eje de acciones** — qué puede hacer sobre el mundo. Acá sí hay catálogo.

**Las tres brújulas del proyecto están todas en el primer eje**, así que el
catálogo de acciones no toca lo que realmente importa.

Y dentro del eje de acciones, lo que da libertad no es tener muchas acciones
sino **poder componerlas**. En el incidente de OpenAI, el modelo no ejecutó una
acción prohibida: combinó acciones permitidas hasta salir del sandbox. Ninguna
era el ataque; la secuencia sí.

Además: las capacidades deben ser **genéricas, no específicas**. "Consultar una
API HTTP autorizada" abre cientos de cosas; "leer GPS", "leer cámara", "leer
clima" como acciones separadas es una jaula.

### Sobre la Máquina de POI

Hace **muy pocas cosas**: observar cámaras, cruzar datos, predecir, y comunicar
un número por teléfono público. Nunca genera código ni se agrega sensores.

Su poder no viene de la variedad de acciones sino de **la escala de sus datos y
la profundidad de sus inferencias**.

### Sobre generar código propio

Se evaluó que ABEL escriba sus propios sensores con aprobación del admin. Se
pospuso, no se descartó.

Problemas: aprobar 80 líneas de Python no es como aprobar una acción —con el
tiempo se aprueba sin leer, y la aprobación se vuelve decorativa. Y rompe 0006,
que dice que la parte que ejecuta las modificaciones no debe ser modificable
por el sistema.

**Salida intermedia:** que ABEL cree y guarde **composiciones** —recetas que
combinan capacidades existentes— es seguro y cubre la mayoría de los casos.
"Avisame cuando lleve 4 horas sin moverme" no necesita un sensor nuevo.

### Sobre qué hace a ABEL distinto de un LLM

Lo que hace que un asistente comercial se sienta como herramienta no es que le
falte "parte humana": es que **no tiene continuidad**. Arranca de cero cada vez.

| | Dónde vive | ¿Cambia? |
|---|---|---|
| El modelo | Pesos fijos | No |
| La memoria | PostgreSQL, Qdrant | **Sí, siempre** |

**Si mañana cambiás el LLM por uno mejor, ABEL no pierde nada.** El modelo es
reemplazable; la memoria no.

### Límites honestos reconocidos

- **Entender la pantalla mientras jugás y dar consejos estratégicos:** no
  alcanzable, ni con el mejor hardware. Lo posible: describirle la situación y
  que razone sobre eso.
- **Que sepa cuándo callarse:** no lo da ningún modelo. Los LLM están
  entrenados para responder siempre. Hay que construirlo (5.4).
- **Que discuta y sostenga:** los modelos están ajustados para ser agradables.
  Se puede empujar con instrucciones, pero es peleado.

---

## Pendientes de fases anteriores

| Pendiente | Origen |
|---|---|
| `Memoria` usa un método privado del repositorio | 0027 |
| Umbrales del sensor de ventana sin calibrar | 0025 |
| Recarga de configuración en caliente | Fase 1 |
| Límite de cola por tamaño, no por cantidad | 0023 |
| Estado de sensores no persiste entre reinicios | Fase 3 |
| Suspensión de sesión por inactividad | 0029 |
| Reglas de exclusión de títulos | 0026 |
| Acceso entre usuarios: qué es "superficial" | 0028 |

### Mejora de hardware sugerida

RAM a 3200 MHz (hoy 2400). El A520M la soporta. ~30% más de velocidad en
inferencia por CPU. Menos relevante ahora que Vulkan funciona, pero sigue
siendo la mejor relación costo-beneficio disponible.
