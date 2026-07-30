# 0014 — Niveles de confianza y asimetría conceder/revocar

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.1

## Decisión

`devices.trust_level` con tres valores. El nivel se guarda como columna, no
como tabla separada por tipo.

| Nivel | Alcance |
|---|---|
| `admin` | Recibe todo, puede solicitar acciones, puede participar en enrolar otros dispositivos |
| `trusted` | Autorizado explícitamente por un humano. Sensa y recibe. No eleva a otros |
| `restricted` | Sensor y nada más. Sin información sensible, sin acciones |

Valor por defecto: `restricted`. El nivel más seguro es el que se aplica si
nadie especifica.

## Contexto

La computadora del usuario no puede valer lo mismo que una cámara arbitraria.
Sin jerarquía, cualquier dispositivo autorizado tendría el mismo alcance.

**Por qué columna y no tabla separada por tipo:** un dispositivo puede subir o
bajar de nivel. Con tablas distintas eso implicaría mover filas entre tablas
mientras `events` las referencia. Con una columna es un `UPDATE`, y el cambio
queda registrado como evento (`device_trust_changed`), lo que da el historial
completo sin inventar una tabla de versionado.

## Las tres reglas

**1. La política automática solo otorga el nivel mínimo.**

Un dispositivo que se enrola por regla entra como `restricted` y ahí se queda.
Elevar a `trusted` o `admin` requiere un acto explícito de un usuario con rol
`admin`. La automatización tiene techo.

**2. ABEL puede revocar solo. No puede conceder solo.**

| Acción | ¿ABEL solo? | Si falla |
|---|---|---|
| Revocar | Sí | Se pierde un sensor |
| Conceder | No | Entra un intruso |

La asimetría es deliberada: cada operación falla del lado seguro.

**3. Una revocación humana bloquea el reenrolamiento automático.**

Sin esta regla habría un agujero: un dispositivo revocado que sigue cumpliendo
la política sería reautorizado al siguiente intento, deshaciendo la decisión
del usuario. `revoked_at IS NOT NULL` bloquea el enrolamiento; solo un admin
puede levantarlo.

**Consecuencia sobre la identidad:** esto exige que la identidad de un
dispositivo esté atada a una clave criptográfica y no a un UUID
autoasignado — si no, bastaría generar uno nuevo para evadir la revocación.
Condiciona el diseño de la Fase 2.3.

## Sobre la automatización que sí se puede

La intuición de que ABEL escale sin depender del usuario para todo es
correcta, pero se satisface moviendo **dónde** interviene el humano, no
eliminándolo:

- ABEL detecta un dispositivo nuevo y lo propone. Cero trabajo hasta acá.
- El usuario aprueba con un gesto liviano.
- O el usuario define una **política** y ABEL la aplica sin preguntar.

Con una política definida, cien dispositivos se autorizan sin intervención.
Pero la política la escribió una persona. El acto humano se movió de "aprobar
cada dispositivo" a "definir bajo qué condiciones se aprueba".

Encaja con los niveles de 0006: aplicar una regla existente es nivel 2;
modificar la regla es nivel 4.

## Por qué el usuario no delega esto

`devices` no es un inventario: es el **perímetro de seguridad**. Define qué
máquinas pueden hablarle a ABEL, mandarle datos que tomará como verdad, y
eventualmente recibir órdenes.

Si ABEL pudiera autorizar dispositivos, comprometerlo una vez daría acceso
ilimitado y creciente: el atacante no necesita volver a entrar, consigue que
ABEL autorice sus propios dispositivos.

Y hay un límite más profundo: **ABEL no puede verificar que un dispositivo sea
del usuario.** Puede verificar credenciales, red, comportamiento. Nada de eso
prueba propiedad — que es un hecho del mundo físico.

## Trazabilidad

`devices` registra `authorized_by`, `authorization_policy`, `revoked_by` y
`revocation_reason`. `authorized_by` referencia a `actors`, así que distingue
si autorizó un humano o ABEL aplicando una regla.

Nota de auditoría: el script exige `--por <username>` sin valor por defecto.
Aunque hoy haya un solo usuario, asumir la identidad haría que la columna
mienta el día que haya dos admins. Un registro de auditoría que miente es peor
que no tenerlo.
