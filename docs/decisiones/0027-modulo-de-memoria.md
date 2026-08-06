# 0027 — Módulo de memoria

**Estado:** Vigente
**Fecha:** 2026-08-03
**Fase:** 3.3

## Decisión

`nucleo/memoria/` responde preguntas sobre lo que ABEL registró. Es distinto
del repositorio por propósito: **el repositorio guarda y recupera; la memoria
agrega, resume y relaciona.**

Devuelve datos estructurados, nunca texto formateado.

## Los datos y el recordar

Distinción que conviene fijar:

- **Los recuerdos** viven en PostgreSQL, y más adelante también en Qdrant y
  Neo4j.
- **`nucleo/memoria/`** es la maquinaria de *recordar*: cómo se accede, se
  relaciona, se resume y se olvida.

La distinción importa porque cuando se sume Qdrant, este módulo será el que
decida a qué motor preguntar según la pregunta — sin que el resto del código
sepa que hay tres bases distintas. Mismo principio que el repositorio con
psycopg3: una interfaz, motores intercambiables detrás.

Acá van a vivir capacidades que hoy no existen pero ya se nombraron: la marca
de olvido, el decaimiento por relevancia, la consolidación de muchos eventos en
un resumen, la distinción explícita entre lo observado y lo inferido.

## Datos, no texto

Un método que devuelve `"Usaste Chrome 3.4 minutos"` sirve para una sola cosa.
Uno que devuelve `{"aplicacion": "chrome.exe", "segundos": 204}` sirve para el
script de hoy, la interfaz de la Fase 4 y el modelo de lenguaje de la Fase 5.

**El formateo es responsabilidad de quien muestra, no de quien consulta.**

## Preguntas implementadas

| Método | Responde |
|---|---|
| `actividad_por_aplicacion` | ¿En qué gasté el tiempo? |
| `sesiones_de_ventana` | ¿Qué estuve haciendo, en orden? |
| `que_hacia` | ¿Qué tenía en pantalla a tal hora? |
| `periodos_de_actividad` | ¿Cuándo estuve activo? |
| `estado_del_sistema` | ¿Cómo está ABEL? |
| `huecos_de_presencia` | ¿Cuándo estuvo caído o incomunicado? |

`estado_del_sistema` resuelve una carencia operativa señalada desde la Fase 1:
hasta ahora no había forma de ver qué estuvo haciendo ABEL sin escribir SQL a
mano.

`huecos_de_presencia` es la contrapartida de la marca: **su valor está en la
ausencia**, no en la presencia.

## Las consultas no interpretan

`periodos_de_actividad` devuelve las transiciones tal como se registraron. El
estado `idle` significa que no hubo entrada de teclado ni mouse — **no que el
usuario no estuviera**. Se puede estar leyendo.

Esa aclaración va en la salida del script, no como interpretación en la
consulta.

## Deuda técnica

`Memoria` usa `self._repo._conexion()`, un método **privado** del repositorio.
Rompe el encapsulamiento.

Se dejó así para no rediseñar el repositorio en esta fase. Hay que resolverlo:
o el repositorio expone un método público para consultas, o `Memoria` maneja su
propia conexión.

Es el tipo de atajo que funciona hoy y molesta en seis meses.
