# 0031 — Identificar no es autenticar

**Estado:** Vigente
**Fecha:** 2026-08-08
**Fase:** 4

## Decisión

El reconocimiento facial, cuando exista, será un **factor de conveniencia que
desbloquea una credencial existente**, no un reemplazo del sistema de
confianza.

## La distinción

- **Identificar** — "creo que sos Maty". Conjetura con probabilidad.
- **Autenticar** — "probaste ser Maty". Prueba.

El reconocimiento facial es lo primero. Y es la aplicación directa de la regla
de 0026: **una inferencia no puede ser indistinguible de un hecho.**

## Por qué no puede ser la autenticación

**No se puede rotar una cara.** Si alguien logra suplantarla, no hay forma de
cambiar la credencial como con una clave filtrada.

**Con una webcam común, una foto en pantalla suele pasar.** Los sistemas que
resisten eso —Windows Hello, Face ID— usan sensores de profundidad o
infrarrojo.

Si el reconocimiento facial fuera lo único que separa a alguien de ABEL, y esa
persona tiene una foto del usuario, entra.

## La Máquina tampoco autentica por la cara

Reconoce a todo el mundo por cámaras — esa es su función central. Pero cuando
actúa, no lo hace porque reconoció una cara: lo hace porque hay una relación
establecida antes, por otros medios.

**Reconocer es cómo percibe. No es cómo decide en quién confía.**

## El rol correcto

**ABEL reconoce y lo dice.** Saluda por el nombre, prepara el contexto,
muestra lo pertinente. Todo lo que no requiere confianza.

**Para actuar sobre algo que importa, pide la prueba.**

Es como funcionan Windows Hello y Face ID: desbloquean una credencial ya
guardada, no reemplazan el sistema de confianza.

## Dónde sí es necesario

**Distinguir personas cuando el dispositivo no alcanza.** La firma del Nodo
prueba *desde dónde*, no *quién*. Si dos personas comparten un dispositivo, el
dispositivo no las distingue.

Las alternativas son un dispositivo por persona (no siempre realista) o
selección explícita (cómoda pero sin verificación). El reconocimiento facial
es lo único que verifica.

## Requiere (Fase 5/6)

Sensor de cámara en el Nodo, modelo de embeddings faciales, Qdrant para
búsqueda por similitud, y umbrales de confianza con manejo de falsos positivos.
