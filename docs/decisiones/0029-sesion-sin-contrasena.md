# 0029 — Sesión de interfaz sin contraseña

**Estado:** Vigente
**Fecha:** 2026-08-07
**Fase:** 4.1

## Decisión

**No hay contraseñas.** Una sesión de interfaz se abre porque el Nodo del
dispositivo firma un desafío con su clave Ed25519.

Si no hay un Nodo corriendo en ese dispositivo, no hay acceso.

## Contexto

Autenticar a una persona es distinto de autenticar a un dispositivo: el
dispositivo tiene una clave, la persona tiene que recordar o presentar algo.

La opción convencional era contraseña con Argon2. Se descartó por dos motivos.

**Escribir contraseñas es fricción constante** para un sistema que se usa a
diario.

**Y el dispositivo ya se autentica**, con criptografía fuerte, desde la Fase
2.3. El problema era de plomería —el navegador no accede a la clave privada
del Nodo— no de diseño.

## El flujo

```
1. El navegador pide la interfaz. No hay cookie.
2. El servidor busca qué Nodo está conectado desde esa misma dirección IP.
3. Le envía un session_request con un desafío aleatorio.
4. El Nodo firma con su clave privada y responde session_grant.
5. El servidor verifica contra device_keys.
6. La sesión queda registrada y el navegador recibe la cookie.
```

Es la primera vez que **el Núcleo inicia** un mensaje hacia un Nodo. No hizo
falta cambiar nada estructural: el sobre siempre fue bidireccional (0016).

## Separación de dominio

El material firmado usa el prefijo `ABEL-session-v1|`, distinto del
`ABEL-auth-v1|` de la autenticación de Nodos.

Sin eso, una firma capturada durante el saludo serviría para abrir una sesión
web. Es la misma razón por la que existe la separación de dominio en 0021.

## Lo que se acepta

**Quien tenga acceso al dispositivo obtiene sesión.** Es la misma propiedad de
una sesión de sistema operativo desbloqueada.

Y conviene notar que **una contraseña no arreglaría esto**: con sesión
persistente, un intruso tampoco la necesitaría. Lo que sí lo mitiga es exigir
presencia continua — suspensión por inactividad usando el sensor
`session_state`, y más adelante verificación por cámara.

Eso es **mejor** que una contraseña: la contraseña se verifica una vez y
después confía indefinidamente; la presencia se verifica de forma continua.

## Sin puerta trasera

Se evaluó dejar contraseña como respaldo para dispositivos sin Nodo. Se
descartó: si ABEL solo se usa desde dispositivos autorizados, esa puerta no
hace falta y solo agrega superficie.

**Recuperación:** si se pierden todos los dispositivos autorizados, queda el
acceso directo a la base con `psql` desde la máquina del Núcleo.

## Dos ejes de permiso

El esquema ya tenía los dos desde la Fase 2.1, y la interfaz los combina:

| | Qué describe |
|---|---|
| `users.role` | A la persona. Es admin en cualquier dispositivo |
| `devices.trust_level` | Al dispositivo. Un celular se pierde más fácil |

Las acciones de administración exigen **ambos** en `admin`. Un admin desde un
dispositivo `trusted` puede ver sus datos pero no administrar.

Ocultar el botón de admin en la interfaz es comodidad; **el servidor verifica
igual** y devuelve 403.

## Sesiones registradas en base

No solo cookie: una tabla `sessions`. Permite listarlas y **cerrarlas a
distancia** si se pierde un dispositivo.

Solo se guarda el hash SHA-256 del token, nunca el token. Alcanza SHA-256
porque el token es aleatorio de 32 bytes: Argon2 está diseñado para resistir
fuerza bruta contra secretos humanos débiles, y acá no hay nada que adivinar.

## Pendiente

**Actualización perdida.** Dos pantallas editando la misma configuración: la
segunda pisa a la primera sin que nadie se entere. `settings` versionado (0006)
conserva el valor en el historial, pero el usuario no se entera. Se resuelve
con la versión incluida en cada formulario, cuando haya formularios.
