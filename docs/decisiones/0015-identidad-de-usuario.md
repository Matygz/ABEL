# 0015 — Cuatro identificadores separados para un usuario

**Estado:** Vigente
**Fecha:** 2026-07-30
**Fase:** 2.1

## Decisión

Un usuario tiene cuatro identificadores, cada uno con una función distinta:

| Campo | Ejemplo | Función | ¿Único? |
|---|---|---|---|
| `actors.id` | UUID | Identidad. A esto apuntan los eventos | Sí |
| `users.username` | `maty` | Autenticación | Sí |
| `users.full_name` | Matias Ivan Gonzalez | Nombre real | No |
| `actors.name` | Maty | Nombre para mostrar | No |

## Contexto

El diseño original tenía solo `actors.name`, con la restricción
`UNIQUE (actor_type, name)` heredada de la Fase 0.3. Eso hacía que el nombre
funcionara como identificador — correcto para módulos y dispositivos, incorrecto
para personas: **los nombres se repiten en el mundo real.**

Tres personas llamadas Matias no podrían coexistir.

La confusión de fondo era mezclar tres conceptos en una columna:

- **Identidad** — lo que la persona *es*. Único, inmutable, interno.
- **Identificador** — lo que se usa para autenticar. Único, elegido, estable.
- **Nombre para mostrar** — cómo se lo llama. Puede repetirse.

El UUID ya era la identidad, así que internamente nunca hubo ambigüedad: tres
Matías son tres UUID distintos y `events.actor_id` los distingue. El problema
era solo de presentación y de autenticación futura.

## Implementación

La unicidad de `actors.name` deja de aplicar a los usuarios:

```sql
ALTER TABLE actors DROP CONSTRAINT actors_name_unique;

CREATE UNIQUE INDEX actors_name_unique_idx
    ON actors (actor_type, name)
    WHERE actor_type <> 'user';
```

Índice único parcial: módulos y dispositivos conservan nombre único, donde sí
tiene sentido. Misma herramienta usada en `settings` (0006).

## Sobre la tabla `users`

Se creó aunque el criterio de 0004 dice que un subtipo se justifica solo si
aporta atributos propios. Los aporta desde el primer día:

- `username` — identificador de autenticación.
- `full_name` — distinto del nombre para mostrar.
- `role` — y no es cosmético: solo el rol `admin` puede elevar la confianza de
  un dispositivo o levantar una revocación (0014). Sin esta columna, esa regla
  no se puede expresar.

## Lo que NO va en esta tabla

Asociar reconocimiento biométrico (cara, voz) a un usuario **no** son atributos
de `users`. Reconocer a alguien es una **inferencia**: probabilística, con
confianza, con posibilidad de error.

Una columna `users.face_id` haría parecer que la identidad es un hecho de la
tabla, cuando es una conclusión que ABEL saca cada vez. Contradice el principio
de que lo inferido no debe ser indistinguible de lo observado.

Ese problema necesita estructura propia — firmas, umbrales, historial de
reconocimientos — y probablemente viva en parte en Qdrant. Fase 3 o posterior.
`users` existe como entidad estable a la que esas asociaciones podrán apuntar.

## Consecuencias

- ABEL no crea usuarios. Crear una cuenta implica asignar un rol, y un rol
  `admin` controla el perímetro. Puede sugerir un `username` disponible y hacer
  el trabajo administrativo; el acto de crear la cuenta es humano.
- Al implementar autenticación (Fase 4), el `username` debe normalizarse antes
  de guardarse: caracteres visualmente idénticos de alfabetos distintos
  (`а` cirílica vs `a` latina) crean usuarios diferentes que se ven iguales.
