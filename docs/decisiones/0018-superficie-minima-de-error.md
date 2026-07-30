# 0018 — Superficie mínima de error por el cable

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.2

## Decisión

> **Detalle completo en el log local. Código mínimo por el cable. Nada antes
> de autenticar.**

`ErrorProtocolo` lleva dos campos: `detalle` (para el log) y `codigo` (lo único
que se envía al otro extremo).

Códigos: `malformed`, `unsupported_version`, `unauthorized`, `rejected`,
`internal`.

## Contexto

Un mensaje de error verboso convierte al servidor en un **oráculo**: el
atacante prueba variantes y el sistema le indica qué corregir. Es la misma
razón por la que un login bien hecho dice "credenciales inválidas" y no "el
usuario existe pero la clave está mal".

## Qué es y qué no es sensible

**La versión del protocolo no lo es.** Es información inherentemente pública:
cualquier Nodo legítimo debe conocerla. TLS, HTTP y SSH anuncian su versión en
el saludo, porque negociar versiones sin declararlas es imposible. Ocultarla no
protege; solo rompe la interoperabilidad.

**Los nombres de campo son discutibles**, y por eso no viajan. Pero conviene ser
honesto: **el formato del mensaje no es el secreto.** El secreto es la
credencial. Un protocolo cuya seguridad dependa de que nadie adivine los nombres
de sus campos no es seguro — es oscuridad, y se cae en cuanto alguien observa un
mensaje legítimo.

## Comportamiento del servidor

**Antes de un `hello` válido** — cualquier error cierra la conexión sin
explicar. A un desconocido no se le da diagnóstico.

**Después de un `hello` válido** — se responde con `error` llevando solo el
código. Un Nodo legítimo necesita saber si reintentar o descartar; el detalle
lo tiene el operador en el log del Núcleo.

Los códigos de cierre de WebSocket complementan sin filtrar: `1002` para error
de protocolo, `1008` para violación de política. El cliente distingue "hablé
mal" de "no me dejan entrar" sin explicación adicional.

## Calibración

Para el estado actual —localhost, un usuario, sin exposición— esto no protege
de nada todavía.

Se implementa ahora por la misma razón que `protocol_version` y
`credential: null`: es una línea hoy y una reescritura de todos los Nodos
instalados mañana.

## Verificado

Un cliente que envía basura recibe un cierre mudo. Un cliente que presenta un
`device_id` inexistente recibe `{"code": "unauthorized"}`. En ambos casos el log
del Núcleo tiene el detalle completo, incluido el error de parseo exacto.
