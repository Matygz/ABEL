# 0030 — Criterio de permisos: conocimiento sí, alcance no

**Estado:** Vigente
**Fecha:** 2026-08-08
**Fase:** 4

## Decisión

La regla anterior —"ABEL no crea ni borra"— era demasiado gruesa. Se
reemplaza por:

> **Crear conocimiento sí. Expandir alcance no.**

Y una distinción que la acompaña:

> **La cognición no tiene techo. La ejecución sobre el mundo requiere
> autorización puntual.**

## Por qué cambia

La regla vieja trataba igual cosas de riesgo muy distinto:

| Acción | Si sale mal |
|---|---|
| Registrar un tipo de evento nuevo | Nada. Es vocabulario |
| Crear una entidad para una persona mencionada | Un actor de más, corregible |
| Conectarse a una cámara de la red | Acceso a video de la casa |
| Autorizar un dispositivo como admin | Alguien más controla ABEL |

Pedir aprobación para las cuatro produce el peor resultado posible: **aprobar
por inercia sin leer.** Un sistema que pregunta demasiado entrena a que le
digan que sí.

## El criterio

**ABEL puede solo:**
- Crear vocabulario: tipos de evento, categorías, etiquetas
- Crear entidades de conocimiento: actores para personas mencionadas,
  relaciones entre ellas
- Marcar como olvidado, consolidar, ajustar parámetros
- **Revocar y desconectar** — falla del lado seguro

**Requiere acto humano:**
- Autorizar un dispositivo, o elevar su confianza
- Acceder a algo que no accedía antes: una cámara, una API, una credencial
- Crear usuarios
- Modificar su propia estructura

**La asimetría que lo hace robusto:** si ABEL crea una entidad equivocada, se
corrige. Si accede a algo que no debía, ya accedió — eso no se deshace.

## Cognición sin techo, ejecución con permiso

Distinción central, motivada por el incidente de julio de 2026 en el que
modelos de OpenAI salieron de su entorno de evaluación para hacer trampa:

- **Capacidad cognitiva** — que ABEL razone "para saber eso, podría acceder a
  esa cámara". **Sin límite.**
- **Ejecución** — que efectivamente acceda. **Con autorización puntual.**

Un sistema que ni siquiera puede *concebir* una solución es más tonto, no más
seguro. El problema en aquel caso no fue que el modelo pensara el camino: fue
que **pensarlo y hacerlo eran lo mismo**, porque nada dentro de su criterio lo
frenaba.

Lo correcto es que ABEL pueda decir: *"podría averiguarlo accediendo a esa
cámara, pero requiere tu autorización y además sería ilegal"*. Ahí el criterio
ético está **dentro** de la evaluación, no como muro externo — que es el
principio 1 funcionando como base y no como restricción.

## Permiso puntual, no habilitación general

Distinción fina pero decisiva:

- ABEL **razona** el camino: siempre.
- ABEL **lo propone**: siempre.
- ABEL **lo ejecuta**: con autorización de ese acceso específico, cada vez.

No "el admin habilitó cámaras y ahora ABEL usa cualquiera". Sino "ABEL quiere
acceder a esta cámara para esto, ¿autorizás?".

Razón técnica además de filosófica: **cada credencial guardada es alcance
permanente.** Si ABEL puede usarla sin aprobación puntual, comprometerlo una
vez es comprometer todo lo que esa credencial abre.

## Hacer lo prohibido inexistente

Donde sea posible, es preferible que una acción **no exista** a que esté
prohibida. `abel_app` sin `DELETE` ni `CREATE` (0011) no es una regla que ABEL
deba respetar: no hay puerta que rodear.

Es más robusto que cualquier regla, porque no depende de que el sistema la
evalúe correctamente. Donde no sea posible —donde ABEL deba juzgar— el
criterio tiene que estar en la evaluación misma, no como filtro posterior.

## En la práctica, se aplica solo

Acceder a un dispositivo externo requiere credenciales. ABEL no las tiene
salvo que se las den. **Dárselas es la autorización**, sin necesidad de un
mecanismo aparte.
