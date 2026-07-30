# Fase 1 — Núcleo mínimo

**Estado:** Cerrada
**Fecha de cierre:** 2026-07-28
**Versión del proyecto:** 0.0.1

## Objetivo

Un proceso que vive de forma sostenida y confiable, conoce su propio estado, y
deja registro de su existencia.

Es infraestructura. No produce nada que se parezca a una conciencia
(principio 7). Produce los cimientos sobre los que todo lo demás se apoya.

La definición completa y el método usado para derivarla están en
`docs/fases/fase-0.md`.

---

## Qué se construyó

```
nucleo/
├── __init__.py
├── __main__.py          Punto de entrada. Elige el bucle de eventos.
├── arranque.py          Ensambla los componentes y arranca.
├── config.py            Configuración de entorno (.env).
├── errores.py           ErrorOperativo, base de fallos esperados.
├── logging_setup.py     Logs de aplicación: consola + archivo rotativo.
├── ciclo_vida.py        Arranque y cierre ordenado de la ejecución.
├── planificador.py      Bucle asíncrono y despacho de tareas.
├── datos/
│   └── repositorio.py   Capa de acceso a datos. Todo el SQL vive acá.
└── tareas/
    └── presencia.py     Marca de presencia.
```

Se ejecuta con:

```bash
python -m nucleo
```

## Las dos reglas estructurales

**El flujo de datos va en un solo sentido.** El Núcleo llama al repositorio;
el repositorio nunca llama hacia arriba ni sabe que existe un planificador. Si
alguna vez la capa de datos necesita "avisarle" algo al Núcleo, es señal de que
algo se diseñó al revés.

**El planificador no sabe qué ejecuta.** Recibe tareas con su cadencia y las
despacha. Agregar comportamiento en fases futuras es registrar una tarea más,
no modificar el planificador. Esta es la "junta preparada" que permite que la
Fase 2 sume el servidor WebSocket como un módulo.

## Decisiones tomadas en esta fase

| N.º | Decisión |
|---|---|
| 0011 | Usuario de aplicación con privilegios mínimos |
| 0012 | Errores operativos vs. inesperados |
| 0013 | Timeouts por tarea en el planificador |

Además, la decisión 0008 (psycopg3) recibió una consecuencia nueva: la
incompatibilidad con `ProactorEventLoop` en Windows.

---

## Criterio de cierre — verificación

| Criterio | Estado | Evidencia |
|---|---|---|
| Arranca desde la terminal | ✅ | `python -m nucleo` |
| Corre de forma sostenida | ✅ | 42 minutos, 42/42 marcas, sin huecos |
| Mantiene su ciclo periódico | ✅ | Marcas continuas cada 60 s |
| Registra su actividad en PostgreSQL | ✅ | `runs` + `events` |
| Se apaga limpiamente con Ctrl+C | ✅ | `stop_reason = 'interrupted'` |
| Recupera identidad y estado al reiniciar | ✅ | Lee `actors` y `current_settings` |
| Tolerancia a fallo temporal de la base | ✅ | Ver prueba de resiliencia |

### Prueba de resiliencia

Procedimiento: con el Núcleo corriendo, detener el servicio
`postgresql-x64-18` desde `services.msc`, esperar, y volver a iniciarlo.

Resultado verificado:

```
15:40:23  marca      uptime 10.1
15:40:38  ERROR      connection timeout expired
15:40:53  ERROR      connection timeout expired
15:40:58  marca      uptime 45.2   ← retomó sin intervención
15:41:03  marca      uptime 50.3
```

El uptime sigue contando desde el arranque original: el Núcleo no se reinició,
aguantó. La recuperación es automática y no hay lógica de reconexión escrita:
se obtiene de abrir y cerrar una conexión por operación.

**Esta prueba fue la que reveló el problema del cuelgue silencioso** que llevó
a la decisión 0013. Sin ejecutarla, la fase se habría cerrado con un criterio
que parecía cumplido y no lo estaba.

### El hueco

```
occurred_at             uptime   seg_desde_anterior
15:40:23                10.1     5.0
15:40:58                45.2     35.1   ← el hueco
15:41:03                50.3     5.1
```

Se perdieron ~7 marcas. Es la decisión anotada en `fase-0.md`: se acepta el
hueco, porque el hueco en sí es información. Delimita cuándo estuvo caído.

---

## Comportamientos observados

**Deriva del intervalo.** El patrón es *ejecutar, después dormir el intervalo*,
así que el tiempo de la operación se acumula. Medido: ~5,035 s para un
intervalo de 5 s. En una hora, ~25 segundos de corrimiento.

Irrelevante para una marca de presencia. Si alguna vez se necesita cadencia
exacta, hay que calcular el próximo instante en lugar de dormir un fijo.

**Apagado lento con la base caída.** Ctrl+C tarda lo que tarde el timeout de
conexión, porque el cierre de la ejecución también intenta escribir. No es un
error, pero es incómodo. Corregido en fase 2.

**Apagado degradado.** Verificado accidentalmente: al cortar con la base caída,
`__aexit__` no pudo escribir el cierre, lo registró en el log y terminó igual
sin explotar. La ejecución quedó sin `ended_at`, o sea marcada como caída —
que es exactamente lo que ocurrió.

---

## Pendientes conocidos

**Recarga de configuración en caliente.** Los valores de `settings` se leen una
sola vez al arrancar. Cambiar el intervalo o el nivel de log en la base no
afecta a un Núcleo ya corriendo; hace falta reiniciar.

Está bien para esta fase, pero choca con la idea de que ABEL ajuste sus propios
parámetros (0006): de nada sirve que cambie su intervalo si no lo relee.
Probablemente se resuelva como otra tarea periódica del planificador.

**Ctrl+C puede tardar hasta un intervalo.** En Windows, el manejador de señales
se ejecuta cuando el intérprete recupera el control. Como las tareas duermen
entre ciclos, la detención puede demorar. Con 60 segundos es incómodo. - Corregido en fase 2.

**El uptime es redundante.** Se puede calcular como
`occurred_at - runs.started_at`. Se guarda por comodidad y porque cuesta nada,
pero es candidato a eliminar si alguna vez se busca ser estricto.

**Ejecución como servicio de Windows.** Pospuesta deliberadamente en el diseño
de la fase. El Núcleo corre desde terminal, donde se puede ver y depurar.

---

## Nota de método

Dos problemas de esta fase aparecieron **solo al ejecutar la prueba**, no al
razonar el diseño:

1. El cuelgue silencioso ante la base caída (→ 0013).
2. `stop_reason = 'clean'` tras un Ctrl+C, porque interceptar la señal impedía
   que la excepción llegara al gestor de contexto.

Los dos parecían resueltos sobre el papel. La conclusión práctica: **los
criterios de cierre se verifican ejecutándolos, no razonándolos.**
