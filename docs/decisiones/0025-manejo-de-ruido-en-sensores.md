# 0025 — Manejo de ruido en sensores

**Estado:** Vigente
**Fecha:** 2026-08-03
**Fase:** 3.2

## Decisión

Un sensor emite **hechos**, no muestras. La agregación ocurre en el Nodo,
antes de encolar.

Dos patrones, según la naturaleza del dato:

| Patrón | Emite | Ejemplo |
|---|---|---|
| **Transición** | Solo cuando el estado cambia | `session_state` |
| **Sesión** | Al terminar, con la duración incluida | `window_session` |

## El problema

El sensor de sesión muestrea cada 30 segundos. Emitir en cada muestreo daría
2.880 filas por día diciendo lo mismo. Emitiendo transiciones: dos o tres por
día, y cada una es información real.

La ventana activa es peor: cambia constantemente por alt-tab, notificaciones
que roban foco, cambio de pestañas. Sin tratamiento, un día de trabajo son
miles de filas donde la mayoría no significa nada.

## El muestreo filtra ruido por construcción

Windows puede notificar cambios de ventana, pero eso requiere un bucle de
mensajes Win32 que no se lleva bien con asyncio.

El muestreo cada 2 segundos es más simple **y tiene un efecto secundario
deseable**: un cambio de foco más breve que el intervalo no se observa. Pasar
medio segundo por una ventana buscando otra no es usarla.

## Sesiones, no cambios

Dos formas de modelar la ventana activa:

- **Cada cambio** — "ahora estoy en Chrome". Para saber cuánto se usó hay que
  calcular diferencias entre filas consecutivas.
- **Sesiones** — "estuve en Chrome de 14:30 a 14:47, 17 minutos". El dato viene
  con su duración.

Se eligió sesiones: menos filas y consultas triviales.

**Costo:** el dato llega con retraso, cuando la sesión termina. Se mitiga
emitiendo un parcial si una sesión supera 30 minutos — si no, un editor abierto
tres horas no produciría ningún dato hasta cerrarlo.

## El umbral simple no alcanza

Descartar sesiones de menos de 10 segundos elimina la mayor parte del alt-tab.
Pero hay un caso que rompe:

> Alternar entre dos ventanas cada 5 segundos durante una hora. Con umbral
> simple, **no se registra nada** — y eso sí era actividad.

Solución: acumular el tiempo descartado **por aplicación**. Si el total supera
el umbral, se emite como sesión `fragmentada`, sin título (no hubo uno
dominante).

Verificado en la práctica: alternar rápido entre dos aplicaciones produjo una
sesión fragmentada de 10 segundos que el umbral simple habría perdido.

## Detalles que importan

**`time.monotonic()`, no `time.time()`.** El primero no se altera con cambios
del reloj del sistema (sincronización horaria, horario de verano). Con
`time.time()`, un ajuste produciría duraciones negativas.

**Cambio de título sin cambio de aplicación no corta la sesión.** Cambiar de
pestaña actualiza el título; no es una sesión nueva. Se conserva el último.

**El motivo de cierre se registra** (`cambio`, `parcial`, `sin_foco`,
`fragmentada`). Permite distinguir una sesión que terminó naturalmente de una
cortada por el límite.

## Pendiente: calibración

Los umbrales —10 segundos de mínimo, 30 minutos de corte, 2 segundos de
muestreo— **se eligieron por criterio, no con datos**.

Hace falta una corrida de un día completo para ver el volumen real y ajustar.

**Asimetría a tener en cuenta:** si el umbral está alto, se pierden datos que
no se pueden recuperar — el pasado no se vuelve a capturar. Si está bajo, sobra
ruido que se puede filtrar después.
