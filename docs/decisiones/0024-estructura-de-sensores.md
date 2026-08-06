# 0024 — Estructura de sensores

**Estado:** Vigente
**Fecha:** 2026-08-03
**Fase:** 3.1

## Decisión

Un sensor es **algo que produce observaciones y las encola**. No decide qué
significan, no las transmite, no habla con el Núcleo.

El registro de sensores (`nodos/sensores.py`) los inicia, los expone al
planificador y deriva de ellos las capacidades que el Nodo declara.

## El objetivo real de la fase

No es "ABEL tiene sensores". Es **"agregar un sensor es trivial"**.

Con la estructura correcta, un sensor nuevo es un archivo en el Nodo y una
fila en `event_types`. No toca el protocolo, ni el Núcleo, ni el esquema.

Es la misma lógica del planificador en la Fase 1: no se construyó "una tarea",
se construyó "un lugar donde las tareas viven". El sensor concreto es la
demostración de que la estructura funciona.

**Consecuencia:** sumar sensores deja de ser trabajo de arquitectura y pasa a
ser trabajo de rutina. No hace falta abrir una fase para agregar el quinto.

## No hay tipos de Nodo

El mismo código de Nodo corre en todos lados. Cada instalación **habilita los
sensores que ese hardware permite**, y el Nodo declara lo que habilitó.

Eso evita crear "Nodo-PC" y "Nodo-Celular" como entidades distintas y después
necesitar una tercera.

El modelo de habilitación es **mixto**: el Nodo puede descubrir qué es posible
consultando al sistema operativo, pero **qué se habilita es una decisión del
operador**. Que una PC pueda usar el micrófono no significa que se quiera que
ABEL lo use.

Es el mismo patrón que con los dispositivos (0014): detectar y proponer es de
ABEL, conceder es del humano.

## Un fallo no impide arrancar

Si un sensor falla al iniciarse —por ejemplo, ubicación en una máquina sin
GPS— queda deshabilitado con su motivo registrado, y **el Nodo arranca igual
con los demás**.

Un Nodo que no arranca por un sensor secundario es peor que uno que funciona
parcialmente. Y un sensor roto que desaparece en silencio es peor que uno que
reporta su estado.

**Solo se declaran las capacidades de sensores efectivamente habilitados.**
Declarar una capacidad que no funciona haría que el Núcleo cuente con datos
que nunca van a llegar.

## El sensor no conoce la cola

Un sensor recibe un `emisor`: una función que toma tipo de evento y datos. No
sabe nada de SQLite, del protocolo ni del cliente.

Cambiar la implementación de la cola no afecta a ningún sensor.

## La estructura no impone cómo se capta

Un sensor de muestreo periódico pregunta el estado cada N segundos; uno
reactivo espera a que el sistema le avise. **Los dos cumplen la misma
interfaz.**

Hoy todos son periódicos. Si la estructura solo soportara muestreo, el día que
haga falta reaccionar a un evento del sistema habría que rediseñar.

## Reorganización: el paquete `comun/`

El Nodo necesitaba un planificador. Se movió el del Núcleo a `comun/` en lugar
de escribir uno nuevo: está probado, maneja timeouts (0013) y errores
operativos (0012), y duplicarlo significaría arreglar los bugs dos veces.

```
comun/          Infraestructura compartida (planificador, errores)
protocolos/     Contrato de comunicación
    ↑      ↑
nucleo/    nodos/
```

`comun/` va aparte de `protocolos/` a propósito: el planificador no es parte
del contrato de comunicación. Mezclarlos confundiría el propósito de cada
paquete.

Ninguno de los dos importa nada del proyecto.

## El estado de los sensores viaja en la marca de presencia

El Núcleo se entera de qué sensores tiene cada dispositivo, cuáles fallaron y
por qué, sin que se agregara un mensaje al protocolo: la información va en el
`payload` de `presence_mark`.

Comparación de dos marcas del mismo dispositivo, con dos días de diferencia:

```json
{"uptime_seconds": 2.1}

{"uptime_seconds": 2.2, "queued": 2,
 "sensors": [{"nombre": "sesion", "capacidad": "session",
              "habilitado": true, "motivo": null, "intervalo_segundos": 30.0}]}
```

Misma tabla, misma columna, cero migraciones. Es exactamente el argumento con
que se eligió JSONB en la Fase 0.3 — "datos que todavía no sabés qué forma van
a tener" — confirmado en la práctica.

## Consecuencia: el envío se desacopló de la presencia

Antes, `_marcar_presencia` y `_enviar_pendientes` vivían en el mismo bucle de
60 segundos. Con un solo dato encolado eso no importaba.

Con sensores encolando a su propio ritmo, un dato captado a los 2 segundos
esperaba hasta 60 para salir: la cola se estaba usando como buffer de espera en
lugar de red de seguridad.

Ahora el envío corre cada 2 segundos y la presencia mantiene su cadencia.
