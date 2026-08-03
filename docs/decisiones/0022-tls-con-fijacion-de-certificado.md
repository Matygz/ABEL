# 0022 — TLS con fijación de certificado

**Estado:** Vigente
**Fecha:** 2026-08-03
**Fase:** 2.4

## Decisión

El canal usa **TLS 1.2 o superior**. El Núcleo presenta un certificado
autofirmado; cada Nodo confía únicamente en **ese** certificado, no en las
autoridades del sistema (*certificate pinning*).

No hay TLS mutuo: la identidad del Nodo sigue verificándose por firma (0021).

## Qué agrega TLS, y qué ya estaba resuelto

La 2.3 resolvió **quién sos**. La 2.4 resuelve **que nadie más lea ni toque**.

| | Aporta |
|---|---|
| Confidencialidad | Nadie más lee las observaciones en tránsito |
| Integridad | Nadie modifica el contenido sin que se note |
| Autenticación del servidor | El Nodo verifica que habla con el Núcleo real |

El tercero es el que suele pasarse por alto y el que más importa: sin él,
alguien podría interponerse haciéndose pasar por el Núcleo, y el Nodo le
entregaría sus datos creyendo que llegan a destino.

## Por qué autofirmado

El modelo de internet no aplica: **ninguna autoridad certificadora emite
certificados para una IP privada**, porque no puede verificar su titularidad.

| Opción | Estado |
|---|---|
| Autofirmado con fijación | **Elegido** |
| Autoridad certificadora propia | Futuro, si crece la cantidad de Nodos |
| Let's Encrypt | No aplica: requiere dominio real y exposición a internet |

Con pocos Nodos, renovar el certificado y actualizar la copia fijada es barato.
Una CA propia tiene sentido cuando ese costo se multiplique.

## La fijación es más estricta, no un parche

Suena a atajo, pero es lo contrario:

- Un navegador acepta **cualquier** certificado firmado por cualquiera de sus
  ~150 autoridades.
- Un Nodo de ABEL acepta **exactamente uno**.

Como se controlan los dos extremos, no hace falta la cadena de confianza. Y
encaja con lo que ya existía: el Núcleo conoce las claves públicas de sus
Nodos, el Nodo conoce el certificado de su Núcleo. **Confianza explícita en
ambas direcciones, sin terceros.**

| | Qué presenta | Quién verifica |
|---|---|---|
| Núcleo | Certificado | Cada Nodo, contra su copia |
| Nodo | Firma del desafío | El Núcleo, contra `device_keys` |

## El certificado es del Núcleo, no de la red

Distinción con consecuencias prácticas: es la identidad del servidor. Si el
Núcleo se muda a otra máquina o cambia de red, **el certificado sigue siendo
el mismo**. Dos Núcleos en la misma red tendrían certificados distintos.

Incluye varias direcciones desde el principio (`127.0.0.1`, `localhost`, `::1`)
para no tener que regenerarlo si cambia la dirección de escucha.

## Detalles del certificado

**Ed25519**, coherente con 0021. Al firmar se pasa `algorithm=None`: Ed25519
define internamente su función de hash, a diferencia de RSA.

**Cinco minutos de margen hacia atrás** en `not_valid_before`. Si el reloj del
Nodo está unos segundos adelantado, un certificado que empieza a valer "ahora"
sería rechazado por no haber entrado en vigencia. Es un fallo real y molesto de
diagnosticar.

**`ca=False` y `SERVER_AUTH`** declaran explícitamente que sirve para
autenticar un servidor y **no** para firmar otros certificados. Si la clave se
filtrara, no podría usarse para emitir certificados falsos.

**Un año de validez.** Los públicos duran 90 días o menos para limitar el daño
de una filtración; para uso interno un año es razonable, más allá es descuido.

**El script se niega a sobrescribir** un certificado existente: regenerarlo
obliga a actualizar la copia fijada en cada Nodo.

## Cifrar no es autenticar

`check_hostname = True` y `verify_mode = CERT_REQUIRED` se escriben explícitos
en el cliente aunque sean los valores por defecto: **son exactamente las dos
líneas que se desactivan cuando algo no funciona**, y desactivarlas convierte
TLS en cifrado sin autenticación — un intermediario pasaría sin problema.

Verificado en `tests/test_tls.py`:

| Caso | Resultado |
|---|---|
| Certificado del Núcleo | Conecta |
| Certificado impostor (autofirmado por otro) | `rechazado (self-signed certificate)` |
| Sin verificación (`CERT_NONE`) | **Conecta** |

El tercero es deliberadamente educativo: un cliente que no verifica establece
el canal cifrado igual. Pero **no puede autenticarse** — muere en el `hello`
sin credencial. Las dos capas trabajan en serie: TLS filtra primero, la firma
después.

## Consecuencias

- El esquema pasa de `ws://` a `wss://`. Un Nodo no actualizado falla con
  `did not receive a valid HTTP response`: manda HTTP plano y recibe bytes
  cifrados.
- Con `check_hostname` activo, la URL debe coincidir con algún nombre del
  certificado.
- Usar `localhost` hace que el cliente intente IPv6 primero y falle antes de
  probar IPv4, desperdiciando tiempo en cada reconexión. `127.0.0.1` lo evita.
- La clave privada del certificado es tan sensible como las de los Nodos:
  `certs/` va al `.gitignore`.
- Técnicamente ya sería seguro escuchar fuera de localhost. No se hace todavía.
