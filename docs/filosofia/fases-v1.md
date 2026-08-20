# ABEL V.1 — Fases

**Escrito:** 2026-08-15

Cada fase termina en **una propiedad que ABEL tiene**, no en una capacidad que
ABEL hace. Esa es la diferencia con la numeración anterior, y es deliberada.

El orden sigue una regla: **primero lo que funciona sin que nadie intervenga.**
Percepción, sangre, procesos de fondo y modelo de la persona se alimentan
solos, todo el día. Conversación, acertijos e imágenes requieren que alguien
haga algo.

Con eso, ABEL tiene sobre qué pensar desde el primer día.

---

## Fase 1 — La sangre

**Propiedad:** ABEL tiene una condición, no solo una base de datos.

- `comun/sangre.py`: el medio compartido, con las ocho variables iniciales
- Decaimiento por tiempo real, no por ciclo
- Cada valor con su dueño declarado
- Los sensores existentes escriben en la sangre además de registrar eventos
- Un panel en la interfaz que muestra la sangre en vivo

**Cómo se sabe que funciona:** se deja ABEL corriendo una noche sin hablarle.
A la mañana, la sangre cambió de forma que tiene sentido — `conexion` bajó,
`incertidumbre` subió, `actividad` cayó.

Si está igual, el bucle no gira.

**Lo que NO tiene todavía:** nadie lee la sangre. Es un estado que existe y no
produce nada. Eso es correcto para esta fase.

---

## Fase 2 — El bucle

**Propiedad:** algo pasa cuando nadie mira.

- Ciclo continuo que corre en el planificador, independiente de toda entrada
- Cálculo de presión con la fórmula del temperamento
- Los dos umbrales: pensar y hablar
- Procesos de fondo: consolidación, revisión, decaimiento
- El bus pasa a avisar que la sangre cambió, no a transportar contenido

**Cómo se sabe que funciona:** el registro muestra actividad interna en
períodos sin usuario. ABEL pensó sin que nadie le hablara.

**Y el test de organismo:** apagar el consolidador a mano y verificar que
`saturacion` sube y que otros procesos cambian de comportamiento — sin que
nadie les haya avisado.

---

## Fase 3 — El modelo de la persona

**Propiedad:** ABEL puede estar equivocado sobre algo que importa.

Es la fase que desbloquea todo lo demás: sin un modelo de alguien, no hay
sobre qué tener incertidumbre, ni qué preguntar, ni en qué fallar.

- Afirmaciones con fuente, momento y confianza
- Afirmaciones contradictorias que **coexisten** en vez de sobrescribirse
- `persons` como subtipo de `actors`, distinto de `users`
- Contraste automático contra lo observado
- La `incertidumbre` y la `coherencia` de la sangre pasan a calcularse desde acá

### La distinción que importa

> Una **persona** es alguien de quien ABEL sabe cosas. No interactúa.
> Un **usuario** es alguien que puede hablarle. Tiene credenciales.

ABEL puede reconocer a alguien sin que eso lo convierta en usuario. Crear un
usuario requiere acto humano.

### Lo que hay que pensar antes de construir

**ABEL va a saber cosas de gente que nunca le habló, y esa gente no eligió ser
registrada.** Es distinto de registrar el uso propio de aplicaciones.

La pregunta sigue abierta: **¿la otra persona sabe que ABEL la registra?**

### El caso testigo

Si el usuario dice que su madre tiene 45 y ella dice 46, ABEL no puede saber
quién acierta. **Registra las dos, con su fuente.** La contradicción es
información que se perdería al sobrescribir.

Y lo que se guarda es la fecha de nacimiento, no la edad: "52 años" queda
viejo en un año. **Un hecho no es una derivación.**

---

## Fase 4 — Memoria asociativa

**Propiedad:** una cosa trae otra sin que nadie las haya vinculado.

- Recuperación por relevancia, no por recencia
- El índice crece con el uso: cada mensaje bien clasificado se suma
- Consolidación en diferido — procesar de noche lo acumulado
- Olvido y decaimiento de lo que no se usa
- `saturacion` pasa a calcularse desde el volumen sin consolidar

La infraestructura ya está: embeddings, Qdrant, el índice. Lo que falta es que
apunte a la memoria en vez de a la clasificación de intenciones.

**Es lo más cerca de la tesis del proyecto** —la memoria mejorando la
cognición— y lo más barato de lo que queda.

---

## Fase 5 — Atención

**Propiedad:** algunas cosas pesan más que otras, y eso cambia.

- No todo lo percibido llega al procesamiento
- Filtro previo a cualquier cognición cara
- Lo que está en foco influye qué se recupera de la memoria
- `novedad` pasa a calcularse desde lo que no encaja con lo esperado

Sin esto, cada evento dispara procesamiento y el sistema se ahoga. Con esto,
ABEL puede ignorar.

---

## Fase 6 — Revisión de creencias

**Propiedad:** ABEL se corrige con evidencia.

- Dos políticas: verificable y contrastable
- Ajuste de confianza ante observaciones nuevas
- Resolución de contradicciones — y `coherencia` bajando cuando se resuelven
- El freno aprendido: haber interrumpido en mal momento inhibe la próxima

Acá aparece el placer como señal de aprendizaje: no motiva, marca qué salió
bien para que el impulso sea más fuerte por ahí la próxima.

---

## Fase 7 — Composición

**Propiedad:** comportamientos nuevos sin código nuevo.

- Capacidades que se combinan en secuencias que nadie escribió
- Recetas que se guardan y se reutilizan
- ABEL puede darse capacidades nuevas **combinando**, no escribiendo código

Es la salida intermedia de la discusión sobre generar código propio: cubre la
mayoría de los casos sin romper la regla de que la parte que ejecuta no sea
modificable por el sistema.

"Avisame cuando lleve 4 horas sin moverme" no necesita un sensor nuevo.

---

## Fase 8 — Razonamiento sobre situaciones

**Propiedad:** ABEL puede resolver algo que no vio antes.

- Representación de situaciones: actores, propiedades, restricciones
- Motores: búsqueda en espacio de estados, optimización, simulación
- El traductor textual alimenta la misma representación que los sensores

**El límite conocido:** extraer restricciones implícitas es donde un modelo
chico falla. "La linterna debe volver" no está en el enunciado del acertijo
del puente.

Cuando la traducción sale bien, la resolución es exacta. Cuando falla, ABEL
tiene que decirlo y pedir aclaración, no inventar.

---

## Fase 9 — Sensores nuevos

**Propiedad:** ABEL percibe más del mundo.

- Voz: transcripción local, palabra de activación
- Cámara: embeddings faciales, reconocimiento
- El traductor visual — lo más caro de todo, y donde el hardware pesa

**Identificar no es autenticar.** El reconocimiento facial es un factor de
conveniencia que desbloquea una credencial existente, nunca la credencial
misma.

Depende de la Fase 3: reconocer a alguien requiere saber quién es.

---

## Lo que queda fuera

**Entender la pantalla en tiempo real y dar consejos estratégicos.** No
alcanzable con este hardware ni con proyectos de esta escala.

**Que ABEL escriba su propio código.** Evaluado y pospuesto. La Fase 7 cubre
la mayoría de los casos sin romper el principio.

**Superar benchmarks de AGI.** No es la brújula. Si algún día mide bien en
algo, será de rebote.

---

## Sobre el orden

Las fases 1 a 3 son las que hacen que ABEL exista sin intervención. Hasta
terminarlas, no hay organismo — hay infraestructura.

Las fases 4 a 6 son lo que hace que cambie con la experiencia. Sin ellas, es
un organismo que no aprende.

Las 7 a 9 son alcance: qué puede hacer y percibir. **Deliberadamente al
final**, porque es donde se desvió la versión anterior.
