# 0007 — asyncio como modelo de concurrencia

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3 (definición) / 1 (implementación)

## Decisión

El Núcleo se construye sobre un **bucle de eventos asíncrono** (`asyncio`, de
la biblioteca estándar de Python), con un planificador de tareas encima.

Las tareas se registran con su propia cadencia. **El bucle no sabe qué
ejecuta** — solo despacha lo que tenga registrado.

## Contexto

Un programa que habla con el mundo exterior pasa la mayor parte del tiempo
esperando (red, base de datos, disco). En Python sincrónico, esa espera
**bloquea** todo el proceso: mientras se escribe en la base, no se puede
atender nada más.

`asyncio` permite que, al llegar a una espera, el proceso vaya a hacer otra
cosa y vuelva cuando lo esperado esté listo. Es un solo hilo de ejecución que
no se queda quieto — concurrencia, no paralelismo.

### Por qué no un bucle de sondeo

Un bucle que da vueltas cada N milisegundos preguntando "¿pasó algo?" tiene dos
problemas: la latencia de reacción queda **limitada por el intervalo**, y quema
CPU en un proceso que corre 24/7.

Un bucle de eventos hace lo contrario: **duerme, y el sistema operativo lo
despierta cuando llega algo**. Latencia mínima y consumo cero en reposo. El
"tempo del bucle" deja de existir como concepto.

### Separación tempo del bucle / cadencia de tarea

Distinción importante que costó llegar a formular:

- El **bucle** no tiene ritmo propio. Reacciona.
- Cada **tarea** declara su propia cadencia, independiente de las demás.

Un organismo funciona igual: milisegundos para reaccionar, ~1 Hz el corazón,
horas para digerir. Ninguna capa impone su ritmo a las otras. Que el
`presence_mark` sea lento no ralentiza nada más.

## Alternativas descartadas

- **Hilos (threads).** Funcionan con librerías comunes sin reescribir, pero al
  correr realmente en simultáneo pueden corromper datos compartidos, con
  errores intermitentes y difíciles de reproducir. Además el GIL de Python
  impide que aceleren cálculo.
- **Procesos separados.** Aislamiento total y aprovechan varios procesadores,
  pero comunicarlos es trabajo y consumen mucha más memoria.

**No es excluyente:** cuando haya cálculo pesado (Fase 5, LLM local), va en un
proceso aparte y el Núcleo asíncrono le habla.

## Consecuencias

- **Toda librería de I/O debe ser compatible con asyncio.** Una librería
  bloqueante congela el bucle entero y anula la ventaja. Esto condicionó la
  elección del driver de base de datos (ver 0008).
- Cálculos pesados sin puntos de espera deben delegarse fuera del bucle.
- En Windows, la resolución de temporizadores es de ~15,6 ms. Afecta a tareas
  programadas, no a la reacción ante eventos. Suficiente para toda cadencia
  prevista; si alguna vez se necesita precisión de microsegundos, sería un
  módulo en otro lenguaje (Rust/C++, ya contemplado en la arquitectura).
- La estructura permite agregar el servidor WebSocket de la Fase 2 como un
  módulo más: `asyncio` es exactamente donde vive un servidor WebSocket.
