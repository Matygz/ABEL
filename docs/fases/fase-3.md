# Fase 3 — Capacidades sensoriales

**Estado:** Cerrada
**Fecha de cierre:** 2026-08-03
**Versión del proyecto:** 0.0.1

## Objetivo

Que ABEL empiece a saber cosas **del mundo**, no solo sobre sí mismo.

Derivado con el método de `fase-0.md`: *¿qué tiene que ser verdad para que la
Fase 4 (interfaz) sea posible?* Tiene que haber algo que mostrar, tiene que
poder consultarse de forma útil, y tiene que ser suficiente como para que valga
la pena mirarlo.

## El riesgo de esta fase

Distinto al de las anteriores. Las Fases 1 y 2 tenían un criterio claro de
"funciona o no funciona". Esta no: hay infinitos sensores posibles y la
tentación es agregar muchos.

El resultado típico son diez fuentes a medio hacer y ninguna útil.

**Se hizo lo contrario: pocos sensores, bien resueltos.** Preferible una fuente
que genere volumen real y obligue a resolver los problemas de verdad —ruido,
agregación, consultas— antes de sumar la segunda.

## Partición

| | Contenido | Estado |
|---|---|---|
| 3.1 | Estructura de sensores en el Nodo | Cerrada |
| 3.2 | Sensor de ventana activa y manejo de ruido | Cerrada |
| 3.3 | Consultas sobre la memoria | Cerrada |

---

## 3.1 — Estructura de sensores

- Paquete `comun/` con el planificador y los errores compartidos.
- `nodos/sensores.py`: registro, ciclo de vida, capacidades derivadas.
- Dos sensores de sistema: sesión y recursos.
- El estado de los sensores viaja en la marca de presencia.
- El envío se desacopló del ciclo de presencia.

Decisión: 0024. Esquema: `db/schema/008_eventos_sensores.sql`.

**Verificación de cierre:**

```
Sensor habilitado: sesion (cada 30.0s)
Sensor habilitado: recursos (cada 300.0s)
Sensores activos: 2 de 2.
```

Y el primer dato del mundo real registrado por ABEL:

```json
session_state | {"state": "active", "previous": null, "idle_seconds": 0.3}
```

---

## 3.2 — Ventana activa

- Sensor `nodos/sensores_ventana.py`, con sesiones de uso y duración.
- Umbral mínimo con acumulador de fragmentos.
- Corte de sesiones largas a los 30 minutos.
- Registro de título completo.

Decisiones: 0025 (ruido), 0026 (títulos). Esquema:
`db/schema/009_evento_ventana.sql`.

**Verificación de cierre** — los cuatro motivos de cierre observados en datos
reales:

```
17:39   10s  claude.exe   fragmentada   (sin título)
17:39   14s  Code.exe     cambio        cliente.py - ABEL - Visual Studio Code
17:38  206s  opera.exe    cambio        (5) Probé Claude Opus 5 - YouTube
```

La sesión `fragmentada` es la que un umbral simple habría descartado.

**Bug encontrado y corregido:** el sensor de sesión emitía una transición falsa
a `active` en cada reinicio del Nodo, porque `_ultimo_estado` vive en memoria y
arranca en `None`. Ahora la primera lectura solo se reporta si es `idle`.

Muestra algo general: **el estado de un sensor no persiste entre reinicios.**
Para estos sensores da igual; para uno que necesite recordar, habría que
guardarlo.

---

## 3.3 — Consultas

- Paquete `nucleo/memoria/` con seis consultas.
- Script `scripts/consultar.py` como interfaz de línea de comandos.

Decisión: 0027.

**Verificación de cierre:**

```
Desde 03/08 00:00 hasta 04/08 00:00
Tiempo registrado: 4.9min

APLICACIÓN                  TIEMPO      %  SESIONES
opera.exe                   3.4min  70.1%         1
Code.exe                       56s  19.0%         3
claude.exe                     32s  10.9%         2
```

Es la primera vez que ABEL responde algo sobre el usuario que este no sabía con
precisión.

---

## Estado al cierre

| | |
|---|---|
| Sensores | 3 (sesión, recursos, ventana) |
| Tipos de evento nuevos | 3 |
| Consultas | 6 |
| Eventos acumulados | 289 (mayoría de pruebas) |

**Agregar un sensor ahora es un archivo y una fila en `event_types`.** Ese era
el objetivo real de la fase; los sensores concretos son la demostración.

---

## Decisión operativa

El sistema **no se deja corriendo de forma permanente** por ahora. Decisión del
usuario: evitar acumular datos antes de que el proyecto esté en un estado
utilizable.

Contrapartida registrada: **los umbrales del sensor de ventana no están
calibrados con datos reales.** Ver 0025.

---

## Pendientes conocidos

| Pendiente | Origen |
|---|---|
| Calibrar umbrales con una corrida de un día | 0025 |
| Reglas de exclusión de títulos, aplicadas en el Nodo | 0026 |
| `Memoria` usa un método privado del repositorio | 0027 |
| Estado de sensores no persiste entre reinicios | 3.2 |
| Recarga de configuración en caliente | Fase 1 |
| Límite de cola por tamaño, no por cantidad | 0023 |

---

## Anotado para más adelante

**Sensores por descubrimiento.** El modelo previsto es mixto: el Nodo descubre
qué permite el hardware, el operador decide qué se habilita. Hoy solo está la
segunda mitad — la configuración es explícita.

**Nodos-puente.** Una cámara IP o un dispositivo comercial nunca va a ser un
Nodo: corre firmware del fabricante. Se accede a través de un Nodo que traduce
entre el protocolo del dispositivo y el de ABEL. Ver `fase-2.md`.

**Sensores en otros sistemas.** Los dos sensores implementados dependen de APIs
de Windows y lanzan `NotImplementedError` en otras plataformas. Por diseño (ver
0024) eso los deshabilita sin impedir que el Nodo arranque.
