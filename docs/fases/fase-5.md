# Fase 5 — Comprensión de lenguaje

**Estado:** Cerrada
**Fecha de cierre:** 2026-08-11
**Versión del proyecto:** 0.0.1

## Objetivo

Que ABEL entienda lo que se le dice y responda con su propia memoria detrás.

Es la fase más grande hasta ahora y la que más discusión de diseño requirió
antes de escribir código.

---

## El hallazgo que cambió el planteo

Toda la conversación previa asumió que el hardware limitaría el proyecto. Se
midió:

| | Generación |
|---|---|
| GPU (Vulkan, `-ngl 99`) | **75 t/s** |
| CPU (`-ngl 0`) | 12 t/s |

`ggml-vulkan.dll` detecta la RX 5500 XT **sin necesidad de ROCm**, que ya no
soporta esa generación. Los 8 GB de VRAM son utilizables.

**La limitación que se dio por sentada no existía.** Se elige modelo por
calidad, no por lo que la máquina aguante.

Y `pp512` a 654 t/s significa que procesar contexto es rapidísimo:
**mandarle contexto rico al modelo casi no cuesta tiempo** — clave para el
diseño del intérprete.

---

## Partición

| | Contenido |
|---|---|
| 5.1 | Motor de lenguaje, gestión del modelo, contexto e intérprete |
| 5.2 | Despachador y motores de razonamiento |
| 5.3 | Expresador con carácter propio |
| 5.4 | Criterio de habla |
| 5.5 | Conversación persistente y chat en la interfaz |
| 5.6 | Servicio en background con ícono de bandeja |

Decisiones: 0034 a 0038.

---

## El flujo completo

```
mensaje
   ↓
[ProveedorContexto]  ¿qué sabe ABEL? ¿qué NO sabe?
   ↓
[Intérprete]         texto → lista de intenciones + confianza
   ↓
[Despachador]        cada intención a su motor, en paralelo
   ↓                  ├── MotorMemoria    → SQL
   ↓                  ├── MotorCalculo    → enumeración exacta
   ↓                  └── (conversar, fuera_de_alcance: sin motor)
   ↓
[Criterio]           ¿vale la pena decir esto? ¿algo de esto?
   ↓
[Expresador]         resultados → palabras, o silencio
   ↓
respuesta (o gesto)
```

Cada turno —el del usuario y el de ABEL— se registra en `events`.

---

## Elección del modelo

Se probaron tres, con las mismas preguntas.

| Modelo | Velocidad | Resultado |
|---|---|---|
| Qwen2.5 3B Q4 | 75 t/s | Falla en registro emocional, mezcla portugués |
| Gemma 3 12B Q4 | **3,3 t/s** | Se desborda de VRAM. Inutilizable |
| Gemma 3 12B Q3 | 14,6 t/s | Buena calidad, 13-30 s por mensaje |
| **Gemma 3 4B Q4** | **55 t/s** | **Elegido** |

**Se eligió el 4B**, y no por resignación:

- Los casos donde el 12B gana son los que el criterio de habla resuelve de
  otra forma.
- Trece segundos de espera rompen la sensación de presencia. Y esa sensación
  es más difícil de recuperar que una respuesta un poco mejor a "hola".
- La arquitectura no necesita un modelo grande: el LLM enuncia hechos ya
  formateados, no razona.

Un 12B desbordado es peor que un 4B que entra: más lento *y* con el sistema
ahogado.

**Anotado:** escalar al modelo pesado para casos que lo justifiquen —un
acertijo complejo, un análisis largo— donde ya se va a esperar de todos modos.
Cambiar de modelo cuesta ~15 s de carga y descarga.

### Configuración que importa

Dos parámetros que costaron encontrar:

- **`-c 8192`**, no `--ctx-size`. El nombre largo se acepta sin error pero se
  ignora, y el modelo toma el contexto completo de Gemma: **131.072 tokens**,
  reservando 3 GB de VRAM innecesarios.
- **`-np 1`**. Por defecto crea 4 slots, cada uno con su propio caché.

Con esos dos, de 3 t/s a 55.

---

## Verificación de cierre

| Mensaje | Respuesta |
|---|---|
| ¿cuánto tiempo estuve en Code hoy? | Estuviste en Code por 11 minutos. |
| si tiro 3 dados, ¿probabilidad de más de 15? | Calculado con exactitud. 4.63%. |
| estuve todo el día en el código y estoy quemado | Te noto que estás quemado. *(descarta el dato)* |
| ¿dónde estuve ayer a las 6? | No tengo registro de dónde estuviste. |
| me siento como el orto | Che, te noto que no andás bien. |
| hola | Che, Maty. ¿Qué contás? |
| hola *(repetido)* | *(silencio + gesto)* |
| ¿quién sos? | Soy ABEL. Estoy en la computadora de Maty. |

El tercero es el que resume la fase: ABEL **tiene** el dato de los 11 minutos
y decide que no aporta a lo que la persona está sintiendo.

Tiempo por respuesta: **4-6 segundos**, con el prompt cacheado entre llamadas.

---

## El carácter

Se fijó ahora, antes de que haya memoria elaborada, porque después estaría
mezclado y sería más difícil de aislar.

La apertura del prompt:

> *Sos ABEL. Vivís en la computadora de {usuario} desde hace poco. Registrás
> lo que hace y lo recordás.*
>
> *Sos nuevo. Sabés poco todavía: nada de dónde estuvo, nada de quién es su
> gente, nada de lo que hace fuera de esta máquina. Eso no te avergüenza, pero
> tampoco lo disimulás.*
>
> *No sos un asistente. No estás para ayudar: estás.*

**"Sos nuevo. Sabés poco todavía"** es la línea que más cambió el
comportamiento: un modelo que se cree completo inventa; uno que se sabe
incompleto admite. Es contramedida directa contra las alucinaciones.

Y es honesto. Cuando ABEL sepa más, esa línea cambia — y el cambio será real.

### La asimetría

**Curioso hacia el usuario, parco sobre sí mismo.** Se engancha con lo que
dice, pregunta si algo le llama la atención de verdad; no explica cómo
funciona, no se justifica.

### Lo que NO se puede con instrucciones

- **Curiosidad genuina.** Querer saber requiere un estado interno que le falte
  información. Hoy no lo tiene. Lo que se logra es que *suene* curioso.
- **Discrepar de verdad.** Que ABEL no concuerde es cognición, no lenguaje.
  Lo que sí se hizo es **sacarle el reflejo de validar**, para que cuando
  tenga criterio propio pueda expresarlo. Un prompt de carácter que valida por
  defecto habría horneado el hábito.

---

## Lecciones de prompt engineering

Tras unas quince iteraciones, patrones que se repitieron:

**Los ejemplos pesan más que las reglas.** Cuatro ejemplos de
`fuera_de_alcance` arreglaron lo que tres reglas abstractas no lograban.

**Sobre-enseñar es un riesgo real.** Esos mismos ejemplos hicieron que el
modelo rechazara también los cálculos. Hubo que agregar el contraste explícito.

**Nombrar las frases prohibidas funciona.** "Prohibido 'entiendo', 'claro',
'registrado'" es más efectivo que "no acuses recibo".

**Las instrucciones no deben mezclarse con los datos.** El modelo copió
literalmente `"ABEL NO PUEDE: ..."` porque estaba en el bloque de hechos. Las
instrucciones van en el prompt del sistema.

**Un 4B sostiene pocas reglas a la vez.** Cada regla agregada afloja otra. Hay
un punto de rendimientos decrecientes, y conviene reconocerlo.

**Cuando el modelo no obedece, va a código.** La detección de repeticiones se
intentó primero por prompt y falló con el historial completo en contexto. En
código funcionó a la primera.

---

## Interfaz

El chat se despliega desde un invocador y se repliega con Escape. No está a la
vista por defecto: el estado natural sigue siendo la forma sola en el vacío.

Mientras ABEL procesa, la geodésica **se contrae y late más rápido**. La
espera se ve en ABEL, no en un cartel de "escribiendo…".

El silencio se marca con tres puntos tenues y un destello.

---

## Pendientes de estilo

Detectados y sin resolver:

- **Eco**: ante "Qonda" responde "Qonda?". Un modelo chico que no entiende el
  registro repite la palabra.
- **"Registrado"** se filtra desde el prompt de hechos a la conversación.
- **Confusión de rol** ante "¿cómo estás?": devuelve la pregunta como si el
  usuario fuera ABEL.

Los tres son del mismo tipo y probablemente se atenúen con un modelo mejor.

---

## Pendientes conocidos

| Pendiente | Origen |
|---|---|
| `Memoria` usa un método privado del repositorio | 0027 |
| Umbrales del sensor de ventana sin calibrar | 0025 |
| Recarga de configuración en caliente | Fase 1 |
| Límite de cola por tamaño, no por cantidad | 0023 |
| Suspensión de sesión por inactividad | 0029 |
| Reglas de exclusión de títulos | 0026 |
| Descargar el modelo al detectar ausencia | 0038 |
| Escalada al modelo grande bajo demanda | Fase 5 |

---

## Lo que la fase NO tiene

**ABEL no dice nada por su cuenta.** Responde cuando se le habla. Que note
algo y lo traiga sin que se lo pregunten es Fase 6 — y es lo que separa una
herramienta de una presencia.

**No razona acertijos complejos.** El motor de cálculo resuelve probabilidad
con dados. Búsqueda con restricciones, optimización y lógica quedan pendientes;
el LLM extrae la estructura, pero **las restricciones implícitas** —"la
linterna debe volver" no está en el enunciado— son donde un modelo chico falla.

**No ejecuta acciones sobre el mundo.** El catálogo de acciones con permisos
(0030) sigue sin construirse.

**No ve, no oye, no reconoce caras.** Son sensores; la estructura ya los
soporta.
