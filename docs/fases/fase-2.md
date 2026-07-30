# Fase 2 — Comunicación y primer Nodo

**Estado:** En curso — 2.1 y 2.2 cerradas
**Versión del proyecto:** 0.0.1

## Objetivo

Que el Núcleo y un Nodo se reconozcan, se hablen de forma segura, y que lo que
se dicen quede registrado.

Derivado con el método de `fase-0.md`: *¿qué tiene que ser verdad para que la
Fase 3 (capacidades sensoriales) sea posible?* Un canal por donde viaje el
dato, un registro de qué dispositivos existen, capacidad de distinguir de cuál
vino cada cosa, y que el canal sobreviva a cortes.

**El Nodo de esta fase no percibe nada.** Solo demuestra que el canal funciona.

## Partición

La fase introduce siete tecnologías nuevas de golpe. Se dividió para poder
verificar por partes:

| | Contenido | Estado |
|---|---|---|
| 2.1 | Tabla `devices` y registro de dispositivos | Cerrada |
| 2.2 | WebSocket sin cifrar, en localhost | Cerrada |
| 2.3 | Autenticación de Nodos | Pendiente |
| 2.4 | TLS | Pendiente |
| 2.5 | Nodo con SQLite y reconexión | Pendiente |

El orden importa: **WebSocket antes que TLS**, para poder depurar el protocolo
viendo los mensajes en claro. Meter cifrado antes de que la comunicación
funcione es depurar dos problemas a la vez.

---

## El modelo: Núcleo y órganos sensoriales

Definición acordada tras una discusión larga, y que conviene no perder:

| | Núcleo | Nodo |
|---|---|---|
| Cognición | Toda | Ninguna |
| Decisiones | Todas | Ninguna |
| Persistencia | Memoria completa | Cola temporal |
| Estado | Permanente | Se vacía al confirmar |

**El Nodo no es un ABEL chico.** Es una terminación nerviosa con un buffer.

### Autonomía cognitiva vs. resiliencia operativa

Distinción central. "Autonomía" mezcla dos cosas:

- **Autonomía cognitiva** — el Nodo piensa, decide, tiene criterio. **Rechazada.**
- **Resiliencia operativa** — el Nodo guarda lo captado mientras no hay enlace,
  reintenta, no pierde datos. **No es autonomía en ningún sentido filosófico:
  es no perder información.**

### Por qué la analogía con POI se rompe acá

Las cámaras de la Máquina estaban en infraestructura cableada. Si el enlace se
caía era porque la cámara se había caído: las dos fallas colapsan en una.

Un celular rompe esa equivalencia. En el subte el GPS anda, el acelerómetro
anda, el micrófono anda. Lo único que no anda es la red. El dispositivo está
captando — solo que no lo puede transmitir.

Sin cola, ese período no existe. No porque no se haya captado, sino por una
limitación de transporte.

### La cola no reconstruye el pasado

El Nodo no dice *"estuve caído de 3 a 6, dejame reconstruir qué pasó"*. Dice
*"esto lo capté a las 3:47, recién ahora te lo puedo pasar"*. Es una carta
escrita el lunes que llega el miércoles por un paro de correo.

**El hueco y los datos no compiten: se registran las dos cosas.**

- Que el enlace estuvo caído → por la ausencia de marcas de presencia.
- Qué se captó en ese período → por lo que llegó de la cola.

| Situación | Qué llega | Qué sabe ABEL |
|---|---|---|
| Sensor apagado | Nada | Hueco real, irrecuperable |
| Sensor OK, red caída | La cola | Hueco de enlace + los datos |

La cola solo puede contener lo que efectivamente se captó. No inventa nada.

### Capacidades declaradas

Un Nodo declara qué sabe hacer al conectarse: `["sensar", "conversar", "actuar"]`.

Esto **no limita lo que ABEL aprenda**. Declarar capacidades dice qué hardware
existe en ese lugar, no qué puede pensar el Núcleo. Es propiocepción: un cerebro
que no sabe qué miembros tiene no puede actuar.

El ojo detecta fotones — capacidad fija. *Aprender a leer* es lo que el cerebro
hace con esos fotones, y no tiene techo.

El diseño que sí limitaría es tener las capacidades fijas en el código. Como
son datos, un Nodo puede registrar capacidades nuevas y ABEL las descubre.

### Sensar, conversar y actuar son roles distintos

En POI están separados: la Máquina recibe de cámaras, se comunica por teléfonos.
Un dispositivo puede tener uno, varios o ninguno.

**El Nodo es presencia y transporte; la interfaz es algo que corre sobre un
Nodo.** Así la Fase 4 construye sobre la 2 en vez de pisarla.

---

## 2.1 — Registro de dispositivos

- Tablas `users` y `devices`, subtipos de `actors` (patrón de 0004).
- Tres niveles de confianza, con `restricted` por defecto (0014).
- Cuatro identificadores separados para un usuario (0015).
- Métodos en el repositorio: autorizar, revocar, listar, obtener.
- Script `scripts/dispositivos.py` con verificación de rol y confirmación
  explícita para niveles altos.

Archivo de esquema: `db/schema/006_users_devices.sql`.

**Verificación de cierre:**

```powershell
python -m scripts.dispositivos listar
python -m scripts.dispositivos autorizar --nombre X --plataforma Y --por maty
python -m scripts.dispositivos revocar --id <uuid> --por maty --motivo "..."
python -m scripts.dispositivos listar --todos
```

Un dispositivo revocado desaparece del listado normal y aparece marcado en el
listado completo. La autorización con nivel `trusted` o `admin` pide
confirmación; `restricted` no.

---

## 2.2 — Canal y protocolo

### Construido

```
protocolos/
├── mensajes.py      Sobre, tipos, códigos de error, validación
└── contenidos.py    Payload de cada tipo, con extractores tipados

nucleo/red/
└── servidor.py      Servidor WebSocket. Identifica, persiste, confirma

nodos/
├── __main__.py      Punto de entrada. python -m nodos
├── config.py        Lee nodo.config.json
├── cola.py          Cola de observaciones pendientes
└── cliente.py       Conexión, reconexión, envío por lotes
```

Decisiones: 0016 (protocolo), 0017 (ack e idempotencia), 0018 (errores),
0019 (disciplina de Nodo remoto), 0020 (servicios en el planificador).

### Verificación de cierre

| Criterio | Evidencia |
|---|---|
| Un Nodo autorizado se conecta | `Nodo conectado: Celular-Maty` |
| Un desconocido es rechazado | `reject {'code': 'unauthorized'}` |
| Basura cierra la conexión sin explicar | `ConnectionClosedError` en el cliente |
| Las observaciones se persisten | Filas en `events` con `actor_id` del Nodo |
| El reenvío no duplica | `tests/test_observaciones.py` |
| El Nodo sobrevive a la caída del Núcleo | Ver abajo |
| Apagado ordenado en ambos lados | Sin traceback, códigos de cierre correctos |

### Prueba de reconexión

```
18:19:57  Conexión perdida. Reintenta en 5.0s. Pendientes: 1
18:20:04  connect failed; reconnecting in 3.0 seconds
18:20:13  Conectado al Núcleo 0.0.1
18:20:13  Lote enviado: 2 confirmadas, 0 rechazadas, 0 en cola
```

Dos confirmadas: la que estaba en cola desde antes de la caída, más la nueva.
Visible también en el tamaño del mensaje (471 bytes contra los 315 habituales).

En la base, las dos comparten `recorded_at` al microsegundo —misma
transacción— con `occurred_at` separados por 13 segundos.

### Detalle observado: el orden importaba

Las primeras marcas mostraban 60 segundos de demora entre `occurred_at` y
`recorded_at`. Causa: `enviar_pendientes()` corría antes que
`marcar_presencia()`, así que cada marca se encolaba y salía en la vuelta
siguiente. Invertido el orden, la demora bajó a 0.1 s.

Los datos mostraron el bug antes que la lectura del código.

---

## Lo que la fase todavía NO tiene

**Sin autenticación.** Cualquiera que copie `nodo.config.json` se hace pasar por
el dispositivo. Por eso el servidor escucha solo en `127.0.0.1`.

**Sin cifrado.** Los mensajes viajan en claro.

**Cola en memoria.** Se pierde si el Nodo se reinicia. Hoy el Nodo sobrevive a
que se caiga el Núcleo, pero no a que se caiga él mismo.

**Sin enrolamiento.** La identidad se configura a mano. El enrolamiento
estructuralmente necesita criptografía: sin intercambio de claves, "enrolar"
sería un trámite sin verificación posterior — el paso que hace valioso al
emparejamiento Bluetooth es el intercambio de claves, no el apretón de manos.

---

## Restricción que el diseño debe respetar

> **Lo inferido nunca debe ser indistinguible de lo observado.**

ABEL puede reconstruir datos faltantes —interpolar una ruta con GPS
incompleto—, y eso es cognición legítima. Pero si guarda esas posiciones como
si fueran lecturas reales, en un mes nadie puede saber cuáles se midieron.

Es especialmente grave en este proyecto: ABEL está pensado para ayudar a
recordar. **Un sistema que fabrica recuerdos falsos es peor que uno que admite
que no sabe.** El daño no es el dato equivocado; es perder la confianza en todo
lo que diga.

Consecuencia ya aplicada en el protocolo: el Nodo transporta **observaciones**,
nunca conclusiones. Manda `gps_reading`, jamás `usuario_en_casa`.

Parcialmente resuelto por el esquema: `actor_type = 'device'` vs `'module'`
distingue el origen. Pero el origen es un proxy, no la regla: un módulo que lee
la memoria del sistema está observando. Cuando aparezcan módulos que infieren,
la marca deberá ser explícita en el evento.

Falta, para cuando llegue: nivel de confianza de una inferencia, y de qué
eventos observados deriva.

---

## Pendientes conocidos

**Política de cola llena.** Descarta lo más viejo. Privilegia lo reciente sobre
lo completo — discutible según el tipo de dato. Configurable a futuro.

**Espera de reinicio fija.** Un servicio que falle de forma persistente
reintenta cada 5 s indefinidamente. Un retroceso exponencial sería más prudente.

**Recarga de configuración en caliente.** Sigue pendiente desde la Fase 1.
`presence_interval_seconds` se lee al arrancar; cambiarlo requiere reiniciar.
Ahora afecta también a lo que el Núcleo anuncia en el `welcome`.
