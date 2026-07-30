# 0019 — El Nodo se programa como remoto

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.2

## Decisión

Aunque Núcleo y Nodo corren en la misma máquina, **el Nodo se programa como si
estuviera en otro continente.**

- No accede a PostgreSQL.
- No importa nada de `nucleo/`.
- No comparte archivos de configuración.
- Toda comunicación pasa por el protocolo.
- Asume que la conexión se corta.

## Contexto

Con ambos procesos en localhost hay atajos que funcionan perfecto y hacen
imposible el paso a red:

| Atajo | Por qué rompe |
|---|---|
| El Nodo consulta la base directo | En otra máquina no hay base |
| El Nodo importa `nucleo/` | En otra máquina no está ese código |
| Compartir archivos por disco | No hay disco común |
| Asumir relojes sincronizados | Los relojes de dos dispositivos difieren |

Cada uno parece inocente y ahorra trabajo hoy. Cada uno significa reescribir
todo cuando aparezca el primer Nodo remoto.

**Localhost es solo la dirección; el diseño no lo sabe.**

## Estructura resultante

```
protocolos/     Contrato. No importa nada del proyecto.
    ↑      ↑
nucleo/    nodos/
```

La dependencia va en un solo sentido: los dos extremos dependen del protocolo,
el protocolo no depende de ninguno. Es lo que permite que evolucionen por
separado.

`nodos/config.py` lee su propio `nodo.config.json`, no el `.env` del Núcleo:
en otra máquina ese archivo no existiría.

## Consecuencia no buscada

Al arrancar el Nodo antes que el Núcleo, reintentó con esperas variables hasta
que el servidor estuvo disponible. La librería aplica *jitter* —variación
aleatoria— para que múltiples clientes no reintenten en el mismo instante,
evitando avalanchas sincronizadas tras una caída.

Nadie programó eso: se obtuvo por tratar al Núcleo como un servicio remoto que
puede no estar.

## Qué NO garantiza esta disciplina

Que el Nodo funcione sin cambios en otra máquina **no está verificado** y no
puede estarlo con un solo equipo. La disciplina reduce el trabajo de esa
migración; no lo elimina. Quedan pendientes al menos: TLS, autenticación real,
y desfase de relojes entre dispositivos.
