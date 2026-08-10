# 0033 — Bus de eventos interno

**Estado:** Vigente
**Fecha:** 2026-08-07
**Fase:** 4.1

## Decisión

`comun/eventos.py` publica un aviso cada vez que se registra un evento. Quien
esté interesado se suscribe.

**El publicador nunca se bloquea.** Si un suscriptor no da abasto, pierde
avisos.

## Contexto

Antes, `registrar_evento` escribía en la base y terminaba. Nadie se enteraba.

Para que la interfaz se actualice sola hace falta que algo **avise** cuando
ocurre un evento. Y esa pieza sirve para mucho más: cualquier módulo futuro
que reaccione a lo que pasa se conecta al mismo lugar.

Se implementó en la 4.1 y no después, porque si el canal en tiempo real se
agrega al final, la interfaz nace escrita para *pedir* datos y hay que
reescribirla para *recibirlos*.

## Publicar no puede bloquear

`publicar()` no es asíncrono a propósito, y descarta cuando la cola de un
suscriptor está llena.

**Quien registra un evento no puede quedar esperando a un navegador lento.**
Si un suscriptor no da abasto, pierde *avisos* —no datos, que están en la
base— y el Núcleo sigue a su ritmo.

Límite: 256 avisos pendientes por suscriptor.

## El aviso no es el evento

Es la noticia de que algo pasó, con un resumen. Si un suscriptor necesita el
detalle, lo consulta. Así el bus se mantiene liviano y no duplica lo que ya
está en PostgreSQL.

## La suscripción se limpia sola

Es un contexto asíncrono: al salir, la cola se descarta. Sin eso, cada pestaña
abierta y cerrada dejaría una cola creciendo — una fuga de memoria lenta y
difícil de diagnosticar.

## El bus es opcional en el repositorio

`Repositorio(config, bus=None)`. Los scripts que lo usan sin interfaz
—`dispositivos.py`, `consultar.py`— funcionan igual. Solo el Núcleo en
ejecución le pasa uno.

El repositorio **no depende** del bus: lo usa si está.

## Detalle de registro

Un suscriptor lento puede descartar cientos de avisos seguidos. Se informa
cada 100 en vez de en cada descarte: un fallo esperado y recurrente no debe
inundar el log. Mismo criterio que 0012 y que la cola del Nodo (0023).

## Límite honesto del "tiempo real"

El bus es instantáneo, pero **los sensores no**. El de ventana muestrea cada 2
segundos y emite cuando la sesión termina; el de sesión, cada 30.

"Tiempo real" en ABEL significa **segundos, no milisegundos**, y en algunos
casos más. No es un problema de la interfaz: es la latencia del sensor.
