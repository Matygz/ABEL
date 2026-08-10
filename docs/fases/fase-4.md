# Fase 4 — Interfaz

**Estado:** Cerrada
**Fecha de cierre:** 2026-08-08
**Versión del proyecto:** 0.0.1

## Objetivo

Que ABEL sea visible: que lo registrado se pueda ver, en vivo, desde cualquier
dispositivo autorizado.

## El recorte

La pregunta del método —*¿qué tiene que ser verdad para que la Fase 5 sea
posible?*— dio una respuesta incómoda: **la Fase 5 no necesita interfaz
gráfica.** Un modelo de lenguaje procesa texto y podría vivir en una consola.

Así que la pregunta correcta era otra: *¿para qué se quiere la interfaz?* Tres
respuestas, y las tres válidas: ver lo registrado, administrar, y —más
adelante— conversar.

## Lo que se decidió sobre la forma

**Una sola interfaz, servida por el Núcleo.** No una por Nodo.

La razón de fondo es la misma que sostiene todo el diseño: la cognición vive
en el Núcleo. El navegador solo dibuja.

La razón práctica: una interfaz por plataforma significaría escribir y mantener
N interfaces. Con una, se mejora en un lugar y se ve en todos lados.

**La interfaz es independiente del Nodo.** Son dos cosas distintas:

| | Qué hace |
|---|---|
| **Nodo** | Sensa y transporta. Corre siempre, en background |
| **Interfaz** | Muestra y recibe. Se abre cuando se quiere |

Un dispositivo puede tener las dos, una o ninguna. No hay "tipos de Nodo":
`conversar` es una capacidad, no una categoría.

## Dos zonas, no dos interfaces

**Zona de uso** — actividad, registro, presencia. Cualquier dispositivo
autorizado.

**Zona de administración** — estado del sistema, dispositivos, memoria.
Requiere rol `admin` **y** dispositivo con confianza `admin`.

Los dos ejes ya existían en el esquema desde la Fase 2.1. La interfaz solo los
usa.

---

## 4.1 — Servidor y sesión

- Bus de eventos interno (0033).
- Servidor Starlette como servicio del planificador.
- Sesión vinculada al Nodo, sin contraseña (0029).
- Canal WebSocket hacia el navegador.

Esquema: `db/schema/010_sesiones.sql`.

### Starlette, no FastAPI

FastAPI está optimizado para APIs públicas: validación de entrada,
documentación OpenAPI para terceros, inyección de dependencias.

Nada de eso aplica cuando el único consumidor escribió el servidor. Y traería
Pydantic, un segundo sistema de validación conviviendo con las dataclasses que
usa todo el proyecto.

Starlette da la capa ASGI sin defaults pesados. Si algún día hace falta la
documentación automática, migrar es directo: **FastAPI es Starlette con capas
encima.**

### El Núcleo inicia un mensaje

Por primera vez el Núcleo le pide algo a un Nodo: `session_request`. Hasta
ahora el flujo era en un solo sentido.

No hizo falta cambiar nada estructural — el sobre siempre fue bidireccional
(0016). Es la puerta que se dejó abierta.

### Verificación de cierre

```
18:07:59  Sesión abierta: 019fde0d-... en dispositivo 019fb4b1-...
18:07:59  Sesión abierta desde 127.0.0.1
```

Sin escribir nada: el servidor identificó el Nodo por dirección, le pidió
firma, el Nodo firmó con su clave Ed25519, se verificó contra `device_keys`.

---

## 4.2 — La interfaz

Núcleo geodésico en Three.js sobre vacío, con paneles emergentes.

### El comportamiento, no la forma

La referencia estética combina dos cosas opuestas a propósito: **el entorno es
frío y vacío; el objeto que lo habita es curioso.** El contraste es lo que le
da fuerza.

Concretamente, la forma **no gira porque sí**:

- Se orienta hacia el cursor con mucha inercia. Mira, no persigue.
- Después de unos segundos sin movimiento, empieza a derivar sola. Se detiene
  apenas hay actividad.
- **Late con cada `presence_mark`** y se sacude con cada evento que llega.

Eso último es lo que importa: la animación responde a lo que ABEL
efectivamente registra, no a un temporizador decorativo.

Subdivisión 2 en vez de 3: con 3 la malla se lee como esfera y se pierde la
geometría.

### Quien no entra, no ve

La geodésica arranca oculta y aparece con un fundido al abrirse la sesión.
Antes se dibujaba siempre: alguien sin acceso veía a ABEL igual.

### Vacío por defecto

Al abrir no hay paneles. La forma, el nombre en una esquina, la hora en otra,
la última marca de pulso. Los invocadores están al 25% de opacidad hasta que
se acerca el cursor.

Los datos aparecen **encima**, con la forma visible detrás. Se cierran con
Escape o clic afuera. Nunca se navega fuera de ABEL.

### Three.js local

Se descargó al proyecto en vez de usar CDN: ABEL debe funcionar sin internet.
Son dos archivos — `three.module.js` importa `three.core.js`.

---

## 4.3 — Reemplazada

La sub-fase planificada era administración web: formularios para autorizar
dispositivos, revocar, configurar.

**Se descartó**, por decisión de diseño: la vía principal de interacción va a
ser la conversación. Construir formularios ahora sería construir algo que la
Fase 5 reemplaza.

Lo que queda en su lugar:

- **Los scripts siguen sirviendo** para administración. Autorizar un
  dispositivo ocurre cada varios meses; la fricción de abrir una terminal es en
  sí una protección.
- **Las acciones se mueven a la Fase 5**, donde nacen junto con el lenguaje.

Y ahí aparece lo que realmente falta: **un catálogo de acciones que ABEL puede
ejecutar, cada una con su nivel de permiso** (0030). Sin eso, un modelo de
lenguaje solo puede hablar.

Excepción prevista: las acciones donde la interfaz debe ser deliberadamente
incómoda —conceder acceso, elevar confianza— conservan un lugar aparte.
**Conceder no debería ocurrir en medio de una conversación.**

---

## Decisiones de esta fase

| N.º | Decisión |
|---|---|
| 0028 | Memoria global con atribución |
| 0029 | Sesión de interfaz sin contraseña |
| 0030 | Criterio de permisos: conocimiento sí, alcance no |
| 0031 | Identificar no es autenticar |
| 0032 | Alcance: ABEL asume acceso exclusivo |
| 0033 | Bus de eventos interno |

---

## Estado al cierre

El dato viaja de punta a punta sin intervención:

```
sensor → cola SQLite → TLS → Núcleo → PostgreSQL → bus → navegador
```

Un cambio de aplicación aparece en pantalla segundos después, sin recargar.

---

## Pendientes conocidos

| Pendiente | Origen |
|---|---|
| `Memoria` usa un método privado del repositorio | 0027 |
| Umbrales del sensor de ventana sin calibrar | 0025 |
| Recarga de configuración en caliente | Fase 1 |
| Límite de cola por tamaño, no por cantidad | 0023 |
| Estado de sensores no persiste entre reinicios | Fase 3 |
| Actualización perdida con dos pantallas | 0029 |
| Suspensión de sesión por inactividad | 0029 |
| Reglas de exclusión de títulos | 0026 |
| Acceso entre usuarios: qué es "superficial" | 0028 |

---

## Lo que la fase NO tiene

**No hay conversación.** Es Fase 5.

**No hay administración desde la web.** Solo lectura. Las acciones siguen en
scripts.

**No hay nada que ABEL diga por su cuenta.** La interfaz muestra lo que se le
pide y refleja lo que llega. Que ABEL *note* algo y lo comunique sin que se lo
pregunten es Fase 6 — y es lo que separa una herramienta de una presencia.
