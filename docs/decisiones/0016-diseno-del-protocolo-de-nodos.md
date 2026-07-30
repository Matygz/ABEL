# 0016 — Diseño del protocolo de Nodos

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.2

## Decisión

Comunicación por WebSocket, mensajes en JSON, con un sobre común a todo
mensaje en cualquier dirección:

```json
{
  "protocol_version": 1,
  "id": "019fb4c2-...",
  "type": "observation",
  "sent_at": "2026-07-30T20:15:00.123456Z",
  "payload": { }
}
```

Siete tipos de mensaje: `hello`, `welcome`, `reject`, `presence_mark`,
`observation`, `ack`, `error`.

## Librería: `websockets`

Pura Python, sin dependencias obligatorias, enfocada en corrección del
protocolo. Techo de ~10.000 conexiones concurrentes por núcleo — sobra por
varios órdenes de magnitud para dispositivos personales.

**Atención:** la implementación asyncio fue reescrita. La nueva vive en
`websockets.asyncio.server` / `websockets.asyncio.client`; la original quedó en
`websockets.legacy`, deprecada. La mayoría de los tutoriales muestran las rutas
viejas.

Descartadas: `aiohttp` (traería un servidor HTTP completo innecesario) y
FastAPI/Starlette (frameworks web; reconsiderar si la Fase 4 usa FastAPI).

## Formato: JSON

Elegido por depurabilidad. En esta fase se leen mensajes crudos constantemente,
y un formato binario obliga a decodificar para entender qué pasa. Además el
payload va directo a una columna JSONB sin conversión.

Descartados: MessagePack (~30% más compacto) y Protobuf (esquema estricto). El
costo en tamaño importará cuando la Fase 3 mande audio o imágenes, pero ese
contenido viajará aparte del mensaje de control de todos modos.

## Campos del sobre

**`protocol_version`** — el campo más fácil de omitir y el más caro de agregar
después. Un Nodo con código viejo hablándole a un Núcleo actualizado necesita
que el desajuste se detecte explícitamente. Sin versión no hay forma de
degradar con elegancia ni de saber qué esperar.

**`id`** — UUIDv7 generado por el emisor. Correlaciona confirmaciones y permite
detectar duplicados (ver 0017).

**`sent_at`** — cuándo se envió el mensaje. **Distinto de cuándo ocurrió lo que
el mensaje reporta:** una observación captada a las 15:00 sin señal puede
enviarse a las 18:00. El `occurred_at` va dentro de cada observación. Es la
lógica de 0003 aplicada al protocolo.

## Los tipos de mensaje van en el código, no en la base

Distinto de `event_types`, que sí es catálogo en base de datos (0005).

Un tipo de evento es un **dato** que ABEL manipula y que un módulo puede
registrar dinámicamente. Un tipo de mensaje es un **contrato entre dos
programas**: si el Nodo no sabe qué es, no puede procesarlo por más que esté
en la base del Núcleo. Los contratos se versionan con el protocolo.

## Todo va en listas

`observations` y `acknowledged` son listas aunque lleven un solo elemento.

Que el sobre soporte lotes es **fundacional**: cambiarlo después rompe
compatibilidad con todo Nodo instalado. Que el Núcleo *acumule* mensajes antes
de confirmar es una **optimización** que se puede agregar después sin tocar el
protocolo, porque el Nodo ya sabe manejar listas.

La forma de lote que sí se implementó no es especulativa: cuando el Nodo vacía
su cola tras reconectar, manda todo junto, el Núcleo lo escribe en una
transacción y confirma lo que escribió.

## El Núcleo impone lo que anuncia

`welcome` comunica `max_batch_size`, pero el servidor **valida por su cuenta al
recibir**. Un Nodo comprometido puede ignorar lo acordado.

Regla general: todo límite que se declara también hay que hacerlo cumplir.

## El Nodo transporta observaciones, nunca conclusiones

Cada observación lleva `event_type`, validado contra el catálogo. El Nodo
declara qué clase de dato manda (`gps_reading`), nunca lo interpreta
(`usuario_en_casa`). La interpretación es del Núcleo.

Es la restricción que preserva la distinción entre lo observado y lo inferido.

## Validación en el borde

`deserializar()` es la frontera. Todo lo que llega de la red se valida ahí:
JSON válido, campos presentes, versión compatible, tipos correctos, límites de
tamaño. Después de esa función el resto del código puede confiar en el sobre;
antes, no.

Todo campo tiene tope: largo de texto, cantidad de elementos, cantidad de
capacidades. Sin límites, un mensaje hostil con una lista de un millón de
elementos consume la memoria antes de ser rechazado.

Detalle de Python: `isinstance(True, int)` devuelve `True`. El validador de
enteros excluye booleanos explícitamente, o `{"max_batch_size": true}` pasaría
como el número 1.

## Puertas dejadas abiertas

- **`credential`** en el `hello`, hoy siempre `null`. La Fase 2.3 la llena sin
  cambiar el tipo de mensaje.
- **Bidireccionalidad**. Nada en el diseño asume que solo el Nodo habla. El rol
  "actuar" (Núcleo → Nodo) no requiere cambios de estructura.
- **`_sesiones`** en el servidor mantiene las conexiones abiertas por
  dispositivo. Hoy solo lleva la cuenta.
