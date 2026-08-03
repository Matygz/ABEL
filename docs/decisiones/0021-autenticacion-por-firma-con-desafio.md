# 0021 — Autenticación por firma con desafío

**Estado:** Vigente
**Fecha:** 2026-07-31
**Fase:** 2.3

## Decisión

Un Nodo prueba su identidad **firmando un desafío** con una clave privada
Ed25519 que nunca sale del dispositivo. El Núcleo guarda solo la clave pública.

El saludo pasa de dos a cuatro mensajes:

```
Nodo   → hello      (device_id, credential: null)
Núcleo → challenge  (32 bytes aleatorios, un solo uso)
Nodo   → hello      (device_id, credential: firma del desafío)
Núcleo → welcome
```

## Contexto

Hasta la Fase 2.2, el `hello` declaraba un `device_id` y el Núcleo lo buscaba
en `devices`. **Ese UUID es público**: está en la base, aparece en los logs, lo
imprime `scripts.dispositivos listar`. Cualquiera que lo conociera podía
presentarse como el dispositivo. Era como abrir la puerta a quien diga tu
nombre.

Consecuencia sobre 0014: la revocación permanente no significaba nada si la
identidad era un dato copiable.

## Por qué Ed25519

| | Problema |
|---|---|
| **RSA** | Necesita 3072+ bits hoy. Firmas grandes, operaciones lentas, varias formas de configurarlo mal |
| **ECDSA** | Si el número aleatorio de una firma se reutiliza, **se puede derivar la clave privada**. Así se comprometió la PlayStation 3 |
| **Ed25519** | Determinístico: no depende de aleatoriedad por firma, así que el fallo de ECDSA no existe |

Ed25519: clave privada 32 bytes, pública 32, firma 64. Rápido en hardware
modesto — relevante cuando el Nodo sea un celular.

Se eligió porque **resiste mejor los errores de implementación**, no por
elegancia.

Librería: `cryptography` (envuelve OpenSSL). **Nunca implementar primitivas
criptográficas a mano**: es el área donde un error sutil no se nota hasta que
alguien lo explota. El principio 3 no entra en conflicto — un algoritmo
criptográfico es infraestructura heredada, como TCP.

## Firmar no es cifrar

- **Cifrar** — que nadie más pueda leerlo. Es TLS, Fase 2.4.
- **Firmar** — que se pueda verificar quién lo escribió y que nadie lo alteró.

Un mensaje firmado se lee perfectamente. Lo que no se puede es falsificarlo ni
modificarlo sin invalidar la firma.

## Por qué hace falta el desafío

Firmar un mensaje fijo no alcanza. Si el Nodo firmara "soy el dispositivo X",
alguien que intercepte ese mensaje puede **reenviarlo tal cual** más tarde: la
firma sigue siendo válida porque es el mensaje original.

Se llama **ataque de repetición**. El desafío lo elimina: el valor cambia en
cada conexión, así que una firma capturada no sirve dos veces.

Costo: un ida y vuelta más en el saludo. El Núcleo necesita el `device_id`
antes de emitir el desafío, porque el device_id forma parte del material
firmado.

## Detalles que cierran ataques

**Separación de dominio.** El material firmado es
`b"ABEL-auth-v1|" + desafio + device_id.bytes`. El prefijo evita que una firma
generada para autenticación se reutilice en otro contexto donde el sistema
también firme. Cuesta trece bytes.

**El device_id va en el material firmado.** Una firma obtenida para un
dispositivo no sirve declarando ser otro. Además el servidor verifica que el
`device_id` no cambie entre los dos `hello`.

**`secrets`, nunca `random`.** El módulo `random` es determinístico: con
suficientes salidas se predice el resto. Los desafíos usan la fuente de
aleatoriedad del sistema operativo.

**El desafío se emite aunque el dispositivo no exista.** Si solo se emitiera
para dispositivos válidos, un atacante sabría qué UUID están registrados según
recibiera desafío o rechazo. El trabajo se hace igual.

**`verificar()` devuelve `False`, no lanza.** Una firma inválida es un
resultado esperado —alguien intentó y no pudo—, no un fallo del programa.
Misma distinción que 0012.

## Tabla `device_keys`, no columna

Un dispositivo puede tener varias claves a lo largo del tiempo, con período de
validez — igual que `settings` en 0006.

El argumento decisivo es la auditoría: si una clave se filtra, con una columna
sobrescribible **no habría forma de saber qué eventos entraron firmados con
ella**. Con historial, sí.

Permite además rotación sin cortar el servicio: dos claves activas durante la
transición.

Restricciones: `CHECK (octet_length(public_key) = 32)` porque una clave
Ed25519 tiene exactamente ese tamaño, e índice único sobre `public_key` porque
dos dispositivos con la misma clave sería ambigüedad de identidad.

## Enrolamiento manual, por ahora

El momento en que el Núcleo acepta una clave que nunca vio **no se puede
verificar criptográficamente**: todavía no hay nada compartido. La confianza
tiene que venir de otro lado.

| Opción | Estado |
|---|---|
| Manual (script genera par, admin registra la pública) | **Implementado** |
| Código de emparejamiento estilo Bluetooth | Futuro |
| Certificados con autoridad firmante | Descartado: overkill para uso personal |

El enrolamiento por código tiene sus propias decisiones (duración, transmisión,
reuso) y necesita interfaz para ser cómodo. Mezclarlo con la firma sería
resolver dos problemas a la vez.

El script se niega a sobrescribir un archivo de clave existente: dejaría al
dispositivo sin poder autenticarse, sin recuperación posible.

## Límite conocido

**La clave privada es un archivo en disco. Sigue siendo copiable.**

Lo que sí se gana:

- La clave **nunca viaja por la red**. El UUID sí lo hacía.
- No aparece en logs, ni en la base, ni en salidas de scripts.
- Un mensaje capturado no sirve para suplantar.
- Rotar una clave comprometida no requiere reidentificar el dispositivo.

Lo que **no** resuelve: acceso al sistema de archivos del Nodo. Para eso hacen
falta almacenes seguros del sistema operativo (Keychain, Android Keystore,
TPM), específicos de cada plataforma.

## Consecuencia operativa

Un Nodo sin credencial es rechazado. **Al desplegar esto hay que actualizar
ambos lados o el dispositivo queda incomunicado.** Verificado: el Nodo de la
Fase 2.2 deja de conectarse contra el Núcleo de la 2.3.

## Verificación

`tests/test_firma.py` — 7 pruebas, incluidas: una firma no sirve para otro
desafío, ni declarando otro dispositivo.

`tests/test_autenticacion.py` — contra el servidor real:

| Caso | Resultado |
|---|---|
| Clave válida | `welcome` |
| Clave inválida | `reject` |
| Sin credencial | `reject` |
| Dispositivo inexistente | `reject` |

Los fallos quedan registrados como eventos `auth_failed`, lo que permite notar
intentos de acceso.

## Nota sobre los logs

Cada conexión recibe un identificador corto (`secrets.token_hex(3)`) que
antecede a todas sus líneas de log.

Sin él, los logs de conexiones concurrentes se entrelazan y parecen
contradecirse: durante las pruebas apareció un `Firma inválida` seguido
inmediatamente de un `Nodo conectado` del mismo `device_id`. Eran dos
conexiones distintas — la válida estaba escribiendo en la base mientras la
siguiente ya fallaba. Los manejadores corren concurrentemente aunque el cliente
pruebe en orden.
