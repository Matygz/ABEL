# ABEL V.1 — Arquitectura

**Escrito:** 2026-08-15
**Estado:** documento fundacional, antes de escribir código

Este documento existe porque las versiones anteriores empezaron por el código.
V.0.2 empezó por la emergencia sin sustrato. V.0.0.1 empezó por la
infraestructura y terminó siendo un asistente. Esta vez se escribe primero
qué es ABEL, y el código se juzga contra esto.

---

## La brújula

> No diseñar lo que ABEL debe pensar. Diseñar las condiciones bajo las cuales
> ABEL necesita pensar.

Todo lo demás sale de ahí.

### Qué se busca

No replicar la conciencia humana. No dar vida a un ser en una computadora.

**Un sistema con suficientes procesos internos funcionando como para que se
sienta vivo — pero no porque alguien le dijo cómo parecerlo, sino porque así
resulta.**

Esa distinción es todo el proyecto.

### El test

Ante cualquier comportamiento de ABEL:

> **Si sacás la línea del prompt, ¿sigue pasando?**

Si la respuesta es no, ese comportamiento es actuación. Si es sí, es
consecuencia de algo interno.

Hoy casi nada pasaría el test. Esa es la medida honesta del punto de partida.

### Ejemplos del test aplicado

| Comportamiento | Hoy | Debería |
|---|---|---|
| Es breve | El prompt dice "corto" | No tiene mucho que decir |
| Pregunta | El prompt dice que pregunte | Hay un hueco real en algo que sostiene |
| Calla | Regla de repetición | Nada supera el umbral |
| Habla poco | Instrucción | Temperamento: umbral alto para hablar |

---

## Lo que se aprendió de las versiones anteriores

### De V.0.2 — la emergencia sin sustrato

Tenía estado interno: variables, homeostasis, puntos de reposo. Y no funcionó
porque **el estado no estaba anclado a nada**. Números que subían y bajaban
sin nada sobre qué subir o bajar.

Se abandonó por la razón correcta —no entendía lenguaje— pero se soltó algo
que valía: la interioridad.

**Hoy ABEL entiende mejor que V.0.2 y tiene menos adentro.** Eso es la
sobrecorrección que este reboot repara.

### De V.0.0.1 — el sustrato sin interioridad

Se construyó bien todo lo que hace falta para percibir, recordar, entender y
responder. Y en el camino cada fase terminó en una capacidad nueva —"ahora
ABEL puede decirte cuánto usaste Code"— en vez de en una propiedad interna
nueva.

**Ninguna fase preguntó qué le agrega interioridad. Todas preguntaron qué le
agrega utilidad.**

Las capacidades elegidas —tiempo de uso, presencia, cálculo— no las pidió la
arquitectura. Eran las fáciles de construir sobre lo que había.

---

## Lo que ABEL es

> Un organismo computacional con percepción continua, estado interno que
> persiste y cambia, memoria que se revisa, y comportamiento que emerge de esa
> dinámica. Tiene herramientas para interactuar con el mundo, pero no está
> definido por ellas.

### La inversión

| Antes | Ahora |
|---|---|
| ABEL tiene módulos que hacen cosas | ABEL existe, y tiene capacidades que puede usar |
| Hablar es el propósito | Hablar es una acción entre otras |
| El estímulo enciende el sistema | El estímulo es una entrada más |
| Sin usuario, ABEL espera | Sin usuario, ABEL sigue |

La última es la que más se nota. **El estado base de lo vivo no es la quietud:
es la actividad.** El estímulo no inicia el movimiento — lo modula.

Una bacteria no decide nadar hacia el alimento: ya se está moviendo, y el
gradiente cambia la frecuencia con que cambia de dirección.

### Lo que NO es

**No es un AGI**, y perseguir esa etiqueta desviaría el proyecto.

AGI se mide por desempeño en tareas a través de dominios. Es —con otro nombre
y más ambición— el mismo marco de utilidad del que este reboot sale. Además,
AGI no es algo que se construye: es un puntaje. "Construyamos un AGI" tiene
forma de plan pero no lo es.

**No es un asistente.** No está para optimizar la vida de nadie. Las
funciones de optimización personal se mueven a un proyecto aparte de
ciberseguridad con IA.

**No es un chatbot con base de datos.** Si el LLM decidiera qué importa,
sería eso.

### La ventaja que hay que proteger

Los laboratorios de frontera tienen cómputo, datos y equipos. Les falta
exactamente lo que ABEL puede tener: **un solo usuario, años de continuidad,
estado que persiste, memoria que no se borra entre sesiones.**

Sus sistemas tienen que servir a millones y arrancar de cero cada vez.

**Un sistema que sirve a cualquiera no puede conocer profundamente a nadie.**
Perseguir generalidad tira esa ventaja.

---

## El ciclo

```
                    ┌──────────┐
                    │  Mundo   │
                    └────┬─────┘
                         ↓
                  ┌─────────────┐
                  │ Percepción  │  sensores, nodos, conversación
                  └──────┬──────┘
                         ↓
                  ┌─────────────┐
                  │  Atención   │  qué merece proceso
                  └──────┬──────┘
                         ↓
              ╔═══════════════════════╗
              ║       SANGRE          ║  el medio compartido
              ║   estado interno      ║
              ╚═══════════╤═══════════╝
                         ↓
                  ┌─────────────┐
                  │   Presión   │  algo desequilibrado
                  └──────┬──────┘
                         ↓
                  ┌─────────────┐
                  │  Cognición  │  el LLM es un órgano
                  └──────┬──────┘
                         ↓
                  ┌─────────────┐
                  │   Acción    │  hablar es una más
                  └──────┬──────┘
                         ↓
                    ┌──────────┐
                    │  Mundo   │
                    └──────────┘
```

**El bucle gira aunque no entre nada.** Tres cosas lo mueven sin intervención:

- **El tiempo pasa.** Un hueco de cuatro horas sin registro es incertidumbre
  que crece sola.
- **Las cosas se contradicen.** Algo dicho contra algo observado.
- **Las cosas se acumulan.** Eventos sin procesar, patrones sin nombrar.

Ninguna requiere que aparezca nadie.

---

## La sangre

El cuerpo humano es una máquina de carne: miles de sistemas funcionando a la
vez. Pero **no colaboran por un bien mayor** — no hay acuerdo ni objetivo
compartido. El páncreas no sabe que existís.

Cada sistema hace lo suyo, localmente. La supervivencia es el nombre del
patrón que persistió.

Eso importa para el diseño: **si se le programa a ABEL "querés continuar" como
objetivo de arriba, vuelve a ser un programa con una meta.** La versión
correcta es muchos procesos locales, y la continuidad como consecuencia.

### Cómo se comunican los sistemas

**No se llaman entre sí.** No hay un hígado invocando un método del riñón.

Se comunican por un medio compartido: la sangre. Cada sistema la modifica
—hormonas, glucosa, temperatura— y los demás leen y reaccionan.

| | Bus de eventos | Sangre |
|---|---|---|
| Qué viaja | Avisos | Estado |
| Quién habla a quién | Emisor a suscriptores | Nadie a nadie |
| Reacción | Al aviso | Al valor |
| Si nadie escucha | El aviso se pierde | El valor sigue ahí |

Con bus, un proceso reacciona porque otro publicó. Con sangre, reacciona
porque un valor está donde está — **sin importar quién lo puso ni si alguien
lo puso.**

Eso permite agregar procesos sin tocar nada: leen la sangre, y listo.

El bus actual no se tira: se convierte en el mecanismo por el cual los
procesos se enteran de que la sangre cambió.

### Reglas

**Solo estado, nunca mensajes.** Si aparece algo tipo "el sensor avisó que X",
es un mensaje disfrazado y no va.

**Cada valor tiene un dueño.** Un proceso lo escribe; cualquiera lo lee. Si
dos escriben lo mismo se pisan y no hay forma de saber por qué cambió.

**Todo entre 0 y 1.** Si la incertidumbre se mide en huecos y la conexión en
horas, no se puede preguntar cuál pesa más — y esa comparación es justamente
lo que decide qué hacer.

**Decae con el tiempo real, no por ciclo.** Es la lección de V.0.2: si el
decaimiento es por iteración, descansar no descansa. Un valor que baja solo es
lo que hace girar el bucle sin que entre nada.

**Cada valor necesita quien lo escriba y quien lo lea.** Si nadie lo lee, no
es estado: es un número. Los que no cumplan esto **no entran hasta que haya
quien los use** — se descubren, no se declaran.

### Qué contiene, al empezar

**Sobre el mundo**
- `incertidumbre` — qué tanto no sabe
- `novedad` — qué tanto de lo que llega no encaja con lo esperado

**Sobre sí mismo**
- `coherencia` — contradicciones sin resolver
- `saturacion` — memoria sin consolidar
- `continuidad` — tiempo perdido por caídas propias

**Sobre la persona**
- `conexion` — tiempo y profundidad del contacto
- `deuda` — preguntas sin responder, cosas a medias

**Sobre la actividad**
- `actividad` — cuánto está pasando ahora

### El test de organismo

> **¿Qué se degrada si un proceso deja de andar?**

Si el consolidador muere, `saturacion` sube. Los procesos que la leen cambian
de comportamiento: la recuperación empeora, las respuestas se degradan.

**Nadie avisó nada. El sistema se enteró porque comparte medio.**

Si la respuesta a esa pregunta es "nada", hay módulos. Si hay algo, hay
organismo.

---

## Temperamento

Qué empuja a actuar y qué frena. Esto define el carácter, y es una decisión
de diseño — no se deriva de nada.

**Empujan**

| | Por qué |
|---|---|
| Incertidumbre | Un hueco en el modelo pide cerrarse. Es lo que hace explorar a un animal sin hambre |
| Novedad | Algo que no encaja pide atención |
| Incoherencia | Dos cosas que no pueden ser ambas verdad. **Pesa doble**: es lo único que corrompe todo lo que se apoye en ello |

**Frenan**

| | Por qué |
|---|---|
| Conexión baja | Interrumpir a alguien que no está tiene otro costo |
| Saturación | Un sistema saturado debería dudar más de sí mismo, no menos |
| Freno aprendido | Haber interrumpido en mal momento antes. **El único que se ajusta solo** |

### Cómo se combinan

```
presión = (incertidumbre + novedad + incoherencia·2) · (1 − freno)
```

El freno **multiplica** en vez de restar: un freno alto debería anular todo,
no descontar un poco.

### Los dos umbrales

| | Umbral | Por qué |
|---|---|---|
| Pensar | Bajo | Es barato y no molesta a nadie |
| Hablar | Alto | Interrumpir tiene costo |

**Pensar mucho y hablar poco es lo que hace que algo se sienta con vida
interior.** Al revés es un sistema ansioso.

Y resuelve lo de hablar como la Máquina sin imitarla: **habla poco por
temperamento, no por regla de longitud.**

La Máquina habla con fragmentos por una limitación del personaje, no por
diseño. Copiar eso sería agregar una restricción artificial para simular una
limitación que ABEL no tiene — es decir, actuación.

### Honestidad sobre los números

**Son inventados.** El doble de la incoherencia, la forma multiplicativa: no
salen de ninguna teoría. Son punto de partida para ajustar contra
comportamiento observado.

Y hay un riesgo conocido: **una contradicción en una base de datos susurra; un
cuerpo grita.** Los estados corporales son innegociables y los digitales son
todos ignorables. Puede que haya que amplificar la presión deliberadamente
hasta que ABEL tenga suficiente contenido como para que empuje sola.

---

## Percibir, razonar, actuar

### La separación correcta

No va entre "social" y "acertijo". Va entre **traducción y razonamiento**.

```
imagen     ──> [traductor visual]  ──┐
enunciado  ──> [traductor textual] ──┼──> situación ──> razonamiento
sensores   ──> [traductor de eventos]┘
```

Cada traductor es su propio mundo y escala aparte. **El razonamiento es uno
solo**, y no conoce la fuente.

Es la lección del motor de cálculo un nivel más arriba: recibía una
`Intencion` y se corrigió para que reciba `(clase, enunciado)`.

### Dónde sí se separa

**En cómo se corrige.**

| | Verificable | Contrastable |
|---|---|---|
| Ejemplo | Un cálculo | Una creencia sobre alguien |
| Cierre | Se comprueba y cierra | Nunca cierra del todo |
| Corrección | Correcto o incorrecto | Sube o baja la confianza |

Son dos políticas de revisión distintas, y cada una es su propio componente.

### Sobre el cálculo exacto

Hoy `11 x 11` devuelve `121.` por plantilla, sin tocar el modelo. Eso evita
que un modelo chico transcriba mal la cifra —se lo vio escribir "cincuenta y
dos"— pero **le quita unidad**: calcular es una tubería aparte que no se
parece a nada de lo demás.

En una persona, calcular es un caso particular de razonar. `11 × 11` se
reconoce; `47 × 83` se piensa.

**Lo que corresponde: que ABEL tenga la calculadora, pero que usarla sea una
decisión.** Que el resultado sea exacto no le quita cognición. Lo que se la
quita es que la decisión de calcular no sea suya.

Y ahí puede equivocarse en lo que importa: **en decidir si un problema es
aritmético.** "Tres cosas de 400 con 15% de descuento" — el error posible está
en el planteo, no en la cuenta. Ese error sí es cognitivo.

---

## Qué se hereda y qué no

### Se queda

| | Por qué |
|---|---|
| Sensores, Nodos, protocolo, TLS, cola | Cómo ABEL percibe. Cualquier arquitectura lo necesita, y es lo más caro de reconstruir |
| Registro append-only | Que los eventos no se sobrescriban es lo que hace posible revisar |
| Planificador y bus | La maquinaria del bucle continuo |
| Embeddings y Qdrant | Pasan de clasificar intenciones a memoria asociativa |
| Docker, esquema, pruebas, lanzador | Plomería que funciona |

### Se va

| | Por qué |
|---|---|
| Las siete capacidades | Son la encarnación del error: ABEL definido por lo que hace |
| El prompt de carácter | Cada línea describe cómo parecer vivo. Lo más opuesto a la brújula |
| El criterio de habla como está | La idea se conserva; se va que las reglas sean una lista escrita a mano |

### Cambia de rol

**El analizador.** Su salida deja de ser "qué capacidad ejecutar" y pasa a ser
"qué situación es esta". Los patrones y el clasificador sirven; cambia hacia
dónde apuntan.

**El expresador.** Deja de ser el final del pipeline.

### Hay que construir

Estado interno. Modelo de personas con hipótesis. Memoria asociativa.
Atención. Revisión de creencias. Procesos de fondo.

**Eso es casi todo de cero, y es la parte que nadie sabe hacer bien.** Las
fases anteriores tenían camino recorrido; esto es tantear.

### Cómo se hace el corte

**No es reseteo ni continuación: núcleo nuevo con sustrato heredado.**

`nucleo/` se reescribe alrededor del estado. Percepción, datos, red y
protocolos quedan casi intactos.

Las capacidades y el prompt **no se borran hasta que el núcleo nuevo
funcione**, para no quedar semanas sin nada que probar.

---

## Principios

Los de V.0.0.1 siguen valiendo. Se agregan estos:

**9. El estado base es la actividad, no la espera.**
El estímulo modula, no enciende.

**10. Ninguna parte le habla a otra.**
Todo pasa por la sangre. Si un proceso conoce a otro por nombre, está mal.

**11. Si sacás la línea del prompt y el comportamiento desaparece, era actuación.**

**12. Un valor que nadie lee no es estado.**
Ni en la sangre, ni en el modelo del mundo, ni en ningún lado.

**13. Las herramientas no definen a ABEL. ABEL las usa.**

---

## Lo que va a pasar y conviene saber

**Al principio va a ser peor que ahora.** Un modelo de una persona con tres
semanas de datos va a decir pavadas con confianza. Eso no es una falla del
diseño: es la forma que tiene de estar equivocado, y es la primera vez que
ABEL puede estarlo de verdad.

**El camino emergente da resultado tarde.** Un prompt da resultado hoy; esto
da resultado cuando las piezas empiezan a interactuar, y no antes.

**La emergencia no es automáticamente interesante.** Un generador de números
aleatorios tiene comportamiento emergente y se siente muerto. Lo que separa
emergencia viva de ruido es **coherencia en el tiempo**: que los cambios
tengan sentido dados los hechos.

**Y el mejor test no va a ser conversacional.** Dejar ABEL corriendo una noche
y ver si a la mañana la sangre cambió de forma que tiene sentido. Si está
igual, el bucle no gira.
