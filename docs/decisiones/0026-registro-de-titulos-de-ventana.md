# 0026 — Registro de títulos de ventana

**Estado:** Vigente
**Fecha:** 2026-08-03
**Fase:** 3.2

## Decisión

Se registra **aplicación y título completo** de la ventana activa.

El filtrado por reglas de exclusión —qué no guardar— es un pendiente, y esas
reglas solo puede definirlas un usuario con rol `admin`.

## Contexto

El título de una ventana puede contener bastante más de lo que sugiere: el
nombre del documento que se edita, el asunto del correo abierto, la página que
se está leyendo, el nombre de la persona con la que se chatea.

Registrar títulos completos significa que la memoria de ABEL va a contener un
registro razonablemente íntimo de la vida del usuario. Y es permanente: el
registro es append-only por construcción (0011).

Las opciones evaluadas:

| Alcance | Utilidad |
|---|---|
| Solo aplicación | Cuánto se usa cada app |
| App + categoría | Ídem, agrupado |
| **App + título completo** | **Contexto real** |
| App + título filtrado | Intermedio |

## Por qué el título completo

**Es donde está el valor informativo.** "Usaste VS Code 40 minutos" no dice
casi nada. "Editaste `cliente.py`" sí. La diferencia se vuelve mucho mayor
cuando la Fase 5 pueda razonar sobre esos títulos.

Verificado en los primeros datos: los títulos capturados
(`cliente.py - ABEL`, `009_evento_ventana.sql - ABEL`) contienen exactamente
el contexto que la aplicación sola no transmite.

**La decisión es del dueño de los datos, no una recomendación técnica.** Se
tomó de forma explícita y no por omisión.

## Asimetría de reversibilidad

Empezar sin títulos y agregarlos después es fácil. Al revés no: **lo registrado
queda.**

Consecuencia directa: **conviene definir las exclusiones obvias antes de
acumular meses de datos**, no después. Una regla de exclusión previene, no
borra retroactivamente — y `abel_app` no tiene `DELETE`.

Si algo ya registrado resulta indeseable, va a requerir intervención manual con
el usuario `postgres`. Es la línea de 0011: **ABEL olvida, solo el usuario
borra.**

## Las reglas las define un admin

ABEL aplica reglas de exclusión; no las escribe. Es coherente con todo el
diseño: aplicar una regla existente es nivel 2 de la escala de 0006, definirla
es una decisión humana.

## Dónde se aplicará el filtro

Cuando exista, **el filtro debe correr en el Nodo**, no en el Núcleo.

| | Ventaja | Costo |
|---|---|---|
| **En el Nodo** | El título nunca sale del dispositivo | La regla tiene que llegar hasta ahí |
| En el Núcleo | Administración centralizada | El dato existió en tránsito |

Un dato que nunca sale no se puede filtrar mal. La configuración del Nodo hoy
es local, así que hará falta que el Núcleo comunique las reglas — probablemente
en el `welcome`, como el intervalo de presencia.
