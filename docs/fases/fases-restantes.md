# Fases restantes

**Escrito:** 2026-08-14
**Estado del proyecto:** Fases 0 a 6 cerradas

Hasta acá ABEL percibe, guarda, entiende lo que se le dice y responde. Todo
eso es infraestructura para que la cognición sea posible — **no es cognición
todavía**.

Lo que sigue es lo que falta para que ABEL sea lo que se propuso: algo que
sabe cosas del mundo, las relaciona, nota lo que pasa, y razona sobre
situaciones.

---

## Antes de la 7: la cara

Chica e independiente. Se puede hacer en cualquier momento.

Cortar el frente de la geodésica y poner ojos adentro. Hoy la forma se orienta
hacia el cursor —"mira" sin tener con qué—; unos ojos hacen explícito lo que ya
está implícito y le dan dirección a la atención: se puede saber si te mira a
vos o a otra cosa.

**El riesgo es que se vuelva simpático.** Dos formas que se orientan y
parpadean dan presencia; dos ojos de dibujo animado matan el frío. La
referencia es Apollo, no un asistente con carita.

---

## Fase 7 — Conocimiento sobre personas y cosas

Es la base de todo lo demás. Sin esto ABEL solo sabe lo que registran sus
sensores: qué aplicaciones se usaron y cuándo. No puede saber nada del mundo.

### Lo que trae

**Afirmaciones con procedencia.** Un hecho sobre alguien lleva quién lo dijo,
cuándo, y con qué confianza. Varias afirmaciones pueden coexistir aunque se
contradigan: la contradicción es información que se perdería al sobrescribir.

El caso testigo del 0028: si el usuario dice que su madre tiene 45 y ella dice
46, ABEL no puede saber quién acierta. Registra las dos, con su fuente.

Y lo que se guarda es la fecha de nacimiento, no la edad: "52 años" queda
viejo en un año. **Un hecho no es una derivación.**

**Relaciones entre actores**, con dirección: "madre de" no es simétrico. Es
donde asoma Neo4j, que quedó bajo evaluación desde el principio.

**Personas distintas de usuarios.** El esquema ya tiene `actors` como
supertipo y `users` como subtipo. Falta un subtipo `persons`.

> Una **persona** es alguien de quien ABEL sabe cosas. No interactúa.
> Un **usuario** es alguien que puede hablarle. Tiene credenciales.

ABEL puede saber quién es alguien y reconocerlo por cámara **sin que eso lo
convierta en usuario**. Crear un usuario requiere acto humano (0030).

**Reconciliación de identidad:** cuando una persona de la que se habló entra
por primera vez, ¿cómo se reconoce que es la misma? Pendiente anotado en 0028.

### Lo que hay que pensar antes de construir

**ABEL va a saber cosas de gente que nunca le habló, y esa gente no eligió ser
registrada.**

Es distinto de registrar el uso propio de aplicaciones. Si se le pasa una lista
con datos de personas, o si reconoce a alguien por cámara, hay información de
terceros involucrada.

El principio 1 aplica de lleno, y la pregunta de 0028 sigue abierta: **¿la otra
persona sabe que ABEL la registra?**

---

## Fase 8 — Memoria elaborada

Hoy la memoria es un registro: se guarda todo y se consulta por fecha. Falta
que ABEL recuerde como recuerda algo que piensa.

**Recuperación por relevancia, no por recencia.** El historial de 45 minutos es
un buffer de conversación. Traer algo de hace tres semanas porque viene al caso
es otra cosa, y es lo que hace que una memoria sirva.

**El índice crece con el uso.** La infraestructura de la Fase 6 está montada
pero los ejemplos siguen siendo los que se escribieron a mano. Que un mensaje
bien clasificado se sume como ejemplo haría que ABEL reconozca mejor **a esta
persona en particular**.

Es lo más cerca de la tesis del proyecto —la memoria mejorando la cognición— y
es barato: poco código sobre algo que ya funciona.

**Consolidación en diferido.** Procesar de noche lo acumulado durante el día:
buscar patrones, armar resúmenes, escribir conclusiones en la memoria. Al día
siguiente el modelo chico responde con eso ya masticado.

Es más parecido a cómo funciona una mente que a cómo funciona un chatbot.

**Olvido y decaimiento.** Lo que no se usa pierde peso. Anotado desde el 0027.

---

## Fase 9 — Iniciativa

Hoy ABEL responde. No observa, no relaciona, no le llama la atención nada.

**Que note algo y lo traiga sin que se lo pidan.** "Llevás cuatro horas sin
moverte." "Es la tercera vez esta semana que abrís eso a las 3 de la mañana."

La infraestructura está: el bus de eventos publica todo lo que pasa, y el
planificador puede correr vigilantes. Falta el criterio.

**Vigilantes por capacidad.** Cada módulo puede declarar un bucle de fondo que
avisa cuando corresponde. La forma la mostró HARVIS: `async def WATCHER(avisar,
cfg)`.

**Estado interno.** Que algo le importe, que algo lo inquiete. En V.0.2 esto
existía —variables, homeostasis, puntos de reposo— y en V.0.0.1 no se replicó.

Vale revisar qué de aquello sirve acá. No todo: V.0.2 tenía estados sin nada
sobre qué tenerlos.

**Y criterio para interrumpir.** El 0036 decide si responde; esto decide si
habla sin que le hablen, que es mucho más delicado. Un sistema que interrumpe
mal es peor que uno que calla.

**Esto es lo que separa una herramienta de una presencia.**

---

## Fase 10 — Razonamiento sobre situaciones

La brújula 1 del proyecto: que ABEL pueda modelar una situación y razonarla.

**Representación estructurada:** actores, variables, qué es fijo y qué se
mueve, restricciones. El LLM extrae la estructura del enunciado; motores
propios la resuelven.

**Motores nuevos:** búsqueda en espacio de estados, optimización, simulación.
Hoy solo hay probabilidad con dados y aritmética.

**El límite conocido:** extraer restricciones implícitas es donde un modelo
chico falla. "La linterna debe volver" no está en el enunciado del acertijo del
puente — se deduce de que sin luz no se cruza.

Cuando la traducción sale bien, la resolución es exacta. Cuando falla, ABEL
tiene que decirlo y pedir aclaración, no inventar.

---

## Fase 11 — Sensores nuevos

**Voz.** Whisper local para transcribir, palabra de activación con huella
acústica. HARVIS mostró que se puede sin dependencias pesadas (MFCC + DTW), y
la cancelación de eco importa si hay música sonando.

**Cámara y reconocimiento facial.** Embeddings faciales, Qdrant para buscar por
similitud, umbrales de confianza.

Y acá aplica el 0031 completo: **identificar no es autenticar**. El
reconocimiento facial es un factor de conveniencia que desbloquea una
credencial existente, nunca la credencial misma.

Se conecta con la Fase 7: reconocer a alguien requiere saber quién es.

---

## Lo que queda fuera de todo esto

**Entender la pantalla mientras jugás y dar consejos estratégicos.** No
alcanzable con este hardware ni con proyectos de esta escala. Lo posible:
describirle la situación y que razone sobre eso.

**Que ABEL escriba su propio código.** Evaluado y pospuesto (Fase 5). La salida
intermedia —composiciones de capacidades existentes— cubre la mayoría de los
casos sin romper 0006.

**La conversación pura sigue floja** y es techo del modelo de 4B. Opciones que
quedan: probar otro modelo del mismo tamaño, ajuste fino, o aceptarlo.

---

## Sobre la distancia con la Máquina

La escena de Finch mostrándole fotos y preguntándole quién es víctima requiere
tres cosas distintas:

1. **Ver imágenes y entenderlas** — modelo multimodal. Alcanzable, pesado.
2. **Razonar sobre roles en una situación** — Fase 10.
3. **Sostener una investigación en el tiempo** — acumular evidencia, ajustar
   una hipótesis, cambiar de opinión. Hoy cada mensaje es independiente: **ABEL
   no tiene hipótesis sobre nada.**

Lo tercero es lo más lejos y lo más interesante.

Y algo que no es arquitectura: **esa escena requiere años de datos.** Finch le
muestra fotos y la Máquina ya sabe quiénes son. ABEL tiene tres semanas de qué
aplicaciones se usaron.

Parte de la distancia es tiempo, no diseño.
