# 0020 — Servicios en el planificador

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.2

## Decisión

El planificador distingue dos clases de trabajo:

| | Tarea | Servicio |
|---|---|---|
| Duración | Corre y termina | Corre indefinidamente |
| Cadencia | Cada N segundos | Arranca una vez |
| Timeout | Sí (0013) | **No** |
| Si termina | Normal | Se reinicia |

`registrar_servicio(nombre, funcion)` para procesos de larga duración.

## Contexto

El servidor WebSocket no encaja en el modelo de `Tarea`: no es periódico,
arranca una vez y corre para siempre.

Dos opciones: arrancarlo aparte en `arranque.py`, o darle al planificador la
noción de servicio. Se eligió lo segundo para que la coordinación del apagado y
la supervisión queden en un solo lugar.

## Por qué los servicios no llevan timeout

La decisión 0013 impone `asyncio.wait_for()` a cada tarea, porque una tarea
colgada es indistinguible de un sistema ocioso.

Un servicio es lo contrario: **debe** estar bloqueado esperando trabajo. Esa es
su función. Aplicarle un timeout lo mataría constantemente.

A cambio, un servicio que termina —solo o por fallo— se reinicia tras una
espera. Un servidor que retorna sin que nadie se lo pidiera es anómalo y se
registra como advertencia.

## Detención inmediata en Windows

Problema aparecido durante las pruebas: con tareas cada 60 segundos, Ctrl+C
tardaba hasta un minuto en tomar efecto.

Causa: en Windows los manejadores de señal de Python **solo se ejecutan cuando
el intérprete recupera el control**. Con asyncio dormido esperando I/O, la señal
queda encolada. `loop.add_signal_handler()` resolvería esto, pero no está
disponible en Windows.

Solución: una tarea interna `_despertador` que hace `sleep(0.2)` en bucle,
dando al intérprete oportunidad de atender la señal. El costo es un
temporizador; el bucle sigue ocioso entre despertares.

El mismo patrón aplica en el Nodo (`_dormir()` en tramos cortos).

Es el pendiente registrado en `fase-1.md` bajo "Ctrl+C puede tardar hasta un
intervalo", ahora resuelto.

## Consecuencias

- `_cancelar_tareas()` no distingue: recorre `self._corriendo`, que incluye
  tareas, servicios y el despertador.
- La espera de reinicio de un servicio es fija (5 s). Si un servicio fallara
  de forma persistente, reintentaría indefinidamente al mismo ritmo. Una espera
  con retroceso exponencial sería más prudente si esto llega a ocurrir.
