# Depuración — 12 de agosto de 2026

Sesión de estabilización antes de sumar embeddings. Sin funcionalidad nueva:
migración de servicios, refactor, y ocho bugs corregidos.

---

## Servicios en Docker

PostgreSQL y Qdrant pasan a contenedores, definidos en `docker-compose.yml`.

**Motivo del cambio:** con dos servicios y más por venir, instalar cada uno
nativo se acumula. Migrar dos ahora es más barato que migrar cuatro después.

La instalación nativa de PostgreSQL quedó detenida y en modo Manual, no
desinstalada.

### Detalles que costaron

**La imagen 18 cambió la ruta del volumen.** Ahora esperan el montaje en
`/var/lib/postgresql`, no en `/var/lib/postgresql/data`. Con la ruta vieja el
contenedor entra en bucle de reinicio con un mensaje largo sobre
`pg_ctlcluster`.

**Los puertos se publican como `127.0.0.1:5432:5432`.** Sin el prefijo, Docker
abre el puerto a toda la red local — cualquiera en el mismo WiFi podría
conectarse a la base. Es un error silencioso y común.

**Docker Desktop se instaló por usuario**, así que el ejecutable queda en
`AppData\Local\Programs\DockerDesktop\resources\bin` y hubo que agregarlo al
PATH del usuario a mano.

### El esquema resultó reproducible

Los datos viejos eran de prueba y se descartaron. Los once archivos de
`db/schema/` corrieron en orden sobre una base limpia **sin un solo error**.

Eso no estaba verificado: hasta ahora se habían ejecutado uno por uno a medida
que se escribían. Es la primera confirmación de que el esquema se puede
recrear desde cero.

---

## Regla del proyecto: `127.0.0.1`, nunca `localhost`

**Tercera vez que muerde.** En este entorno `localhost` resuelve a IPv6
primero; los servicios escuchan en IPv4, y cada conexión espera el timeout
completo antes de reintentar.

Medido: **5,05 segundos** en la primera consulta a la base, exactamente el
`connect_timeout` configurado. Con `127.0.0.1`: 0,02 segundos.

| Dónde apareció | Fase |
|---|---|
| Reintentos de conexión del Núcleo | 1 |
| URL del servidor en el Nodo | 2.4 |
| `ABEL_DB_HOST` con PostgreSQL en Docker | Hoy |

---

## Refactor: el repositorio partido por área

`nucleo/datos/repositorio.py` tenía 839 líneas — más del doble que cualquier
otro archivo. Se dividió en cuatro piezas que se componen por mixins:

| Archivo | Contenido | Líneas |
|---|---|---|
| `conexion.py` | Conexión y consultas de lectura | 80 |
| `eventos.py` | Eventos, ejecuciones, observaciones, conversación | 256 |
| `actores.py` | Usuarios, dispositivos, claves | 332 |
| `sesiones.py` | Sesiones de interfaz | 227 |
| `repositorio.py` | Compone los anteriores | 31 |

**Ningún llamador cambió.** `Repositorio` sigue exponiendo los 30 métodos, y
los imports son los mismos. Los mixins permiten partir el archivo sin partir
la interfaz.

### Método público de consulta

Se agregó `consultar` y `consultar_una`, y se eliminó el uso del método
privado `_conexion()` desde fuera del repositorio — deuda anotada desde la
decisión 0027 y presente en tres lugares.

**Solo lectura a propósito.** Si se expusiera escritura arbitraria, cualquier
módulo podría modificar la memoria sin que quede rastro en la interfaz. Las
escrituras siguen siendo métodos con nombre, y eso mantiene acotada y visible
la superficie de modificación. Es el criterio de 0011 un nivel más arriba.

---

## Bugs corregidos

### El bus publicaba antes de escribir

`registrar_evento` avisaba al bus **antes** del INSERT. Si la escritura
fallaba, la interfaz ya había recibido el aviso de un evento inexistente.

Encontrado al leer el archivo durante el refactor, no por síntoma.

### Sesiones duplicadas

Cada clic en "Entrar" abría una sesión nueva. Como el arranque tardaba 5
segundos (ver `localhost`), el usuario apretaba varias veces y se acumulaban:
**nueve sesiones en tres segundos**, cada una con su firma del Nodo y su
escritura en base.

Círculo completo: tardaba porque había clics de más, y había clics de más
porque tardaba.

Dos arreglos: bloqueo del botón mientras hay una petición en curso, y
`cerrar_sesiones_de` que revoca las anteriores del mismo par usuario-dispositivo.

### El servidor web se reiniciaba durante el apagado

`_ejecutar_servicio` interpretaba que uvicorn terminando por cancelación era
una caída, y lo relanzaba en medio de la detención.

Ahora comprueba `self._detener.is_set()` antes de reiniciar: **un servicio que
retorna durante el apagado no se cayó, se le pidió terminar.**

### Ctrl+C repetido

Cada pulsación registraba una detención más. Ahora la primera marca una
bandera y las siguientes se ignoran, más un `print` inmediato con `flush=True`
para que se vea que el apagado empezó.

### El silencio se trababa a sí mismo

El criterio de repetición miraba si el mensaje aparecía en el historial. Si
ABEL había callado, ese turno seguía ahí, y cada repetición encontraba la
anterior y volvía a callar. **Cuatro "hola" seguidos, cuatro silencios.**

Ahora solo mira el intercambio inmediatamente anterior, y solo cuenta si ABEL
efectivamente respondió. El resultado alterna: responde, calla, responde.

Que es más parecido a lo que haría alguien: te ignora una vez, y si insistís,
te contesta.

### El historial cruzaba conversaciones

`ultimos_turnos` filtraba por tiempo — 45 minutos. Pero **la sesión es la
señal correcta**: abrir una sesión nueva es empezar otra conversación, aunque
hayan pasado tres minutos.

Los turnos ahora llevan `session_id` en su payload y el historial se acota a
la sesión en curso. **Los turnos siguen persistiendo para siempre**; lo que se
acota es qué se considera contexto inmediato.

Y se corrigió un error de orden: el historial se lee **antes** de registrar el
turno actual. Antes se leía después y se recortaba el último con `[:-1]`, lo
que hacía que un mensaje se detectara a sí mismo como repetición.

### La conversación se descartaba por confianza

El criterio descartaba intenciones con confianza menor a 0.35, incluidas las
conversacionales.

Pero **la confianza mide qué tan claro está el intérprete de qué clase de cosa
es** — si resultó ser charla, siempre se puede responder algo. Ahora
`conversar` se evalúa antes del chequeo de confianza y nunca se descarta.

### `UnicodeEncodeError` en los scripts

La consola de Windows usa cp1252 y no puede escribir `→`, `·` o `≥`. Se fuerza
UTF-8 con `sys.stdout.reconfigure()` en los scripts, y con
`PYTHONIOENCODING=utf-8` en el corredor de pruebas.

---

## Corredor de pruebas

`python -m tests` corre las once pruebas del proyecto, agrupadas por lo que
necesitan:

| Grupo | Pruebas | Requiere |
|---|---|---|
| Aisladas | protocolo, firma, patrones, bus | Nada |
| Con base | observaciones | PostgreSQL |
| Con núcleo | rechazo, autenticación, TLS | Núcleo corriendo |
| Con modelo | cálculo, intérprete, criterio | Servidor del modelo |

Sin `--todas` corre solo las aisladas: **4 segundos** contra 72 de la corrida
completa. Las tres que usan el modelo se llevan 68 de esos 72.

**Cada prueba corre en su propio proceso**, con límite de 180 segundos. Sin
eso, una prueba que deja un servidor de modelo colgado hace fallar a las
siguientes por una razón que no es suya.

Solo se muestra la salida cuando algo falla.

### Lo que reveló

`test_rechazo` y `test_autenticacion` seguían usando `ws://` — eran de antes de
TLS y nunca se actualizaron. Nadie los corría desde entonces.

Se eliminaron `test_conversar.py` (obsoleto tras el criterio de habla),
`test_tiempos.py` (instrumentación temporal) y `test_conexion.py` (de la Fase
0, cubierto por otros).

---

## Persistencia del historial en la interfaz

Ruta `/api/historial` y carga al iniciar. Al recargar la página se recupera lo
que venían hablando.

**Los silencios se reconstruyen como silencios**, no como mensajes vacíos: que
ABEL decidiera no responder es información y queda visible.

---

## Ajustes de estilo

**El "Che" en cada respuesta.** El prompt lo usaba como ejemplo de tono
rioplatense y el modelo lo tomó como fórmula de apertura: ocho de nueve
respuestas empezaban igual.

Pedirle variedad no funcionó — un modelo de 4B no puede evaluar "¿empecé igual
la vez anterior?". La prohibición explícita sí: *"Prohibido empezar una
respuesta con 'che'. Podés usarlo en el medio."*

**Confirma el patrón de la Fase 5:** las prohibiciones concretas son lo único
que un modelo de este tamaño sigue con fiabilidad.

**Actividades inventadas.** Ante "¿qué hacés?" respondía *"acá, mirando el
celu"*. La regla de no inventar hechos no cubría que inventara cosas sobre sí
mismo. Se agregó explícitamente.

---

## El límite del intérprete, otra vez

Ante frases que no encajan en ninguna categoría —*"acá tratando de darte vida y
forma"*— el modelo **se pone a completar los ejemplos del prompt** en lugar de
interpretar:

```
'Mensaje: "Maty, ¿cuánto tiempo usé Code hoy?"\n{"intenciones": [...]}'
```

Agregar un delimitador de fin de ejemplos no lo frenó.

El respaldo lo cubre —devuelve `conversar` con confianza 0.5, subida desde
0.2— pero es un parche.

**La solución real es la que ya está planeada: embeddings en vez de un modelo
generativo para clasificar.** Un modelo que solo puede elegir entre categorías
conocidas no puede inventarse ejemplos nuevos.

Es la tercera evidencia de que ese camino es el correcto.

---

## Pendiente para después de los embeddings

- **ABEL no sabe qué puede hacer.** Ante *"¿sabés resolver ecuaciones?"*
  respondió *"No sé si puedo"*. Debería consultar su catálogo de capacidades,
  no suponer.
- El eco: ante "Qonda" responde "Qonda?".
- "Registrado" se filtra del prompt de hechos a la conversación.
- Gramática rota ocasional — techo del modelo, sin arreglo por prompt.

## Deuda que sigue abierta

| Pendiente | Origen |
|---|---|
| Recarga de configuración en caliente | Fase 1 |
| Límite de cola por tamaño, no por cantidad | 0023 |
| Estado de sensores no persiste entre reinicios | Fase 3 |
| Umbrales del sensor de ventana sin calibrar | 0025 |
| Reglas de exclusión de títulos | 0026 |
| Suspensión de sesión por inactividad | 0029 |
