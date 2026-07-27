# 0006 — Configuración versionada con vigencia

**Estado:** Vigente
**Fecha:** 2026-07-27
**Fase:** 0.3

## Decisión

La tabla `settings` **nunca modifica un valor**. Cada cambio cierra la fila
vigente (asignándole `valid_to`) e inserta una nueva. La fila con
`valid_to IS NULL` es la vigente.

La vista `current_settings` expone solo los valores vigentes.

## Contexto

Una tabla de configuración normal guarda el valor actual y destruye el
anterior. Eso alcanza para un sistema estático.

ABEL está previsto para ajustar sus propios parámetros (ver `docs/filosofia/vision.md`,
principio 8). Si cada cambio destruye el estado previo, se pierde:

- Cuál era el valor antes.
- Cuándo cambió.
- **Quién lo cambió** — un módulo, el sistema, o el usuario.
- Por qué.

Sin eso no se puede evaluar si un cambio automático fue bueno, ni revertirlo,
ni entender el comportamiento pasado.

`changed_by` referencia a `actors` (ver 0004): la trazabilidad de la
auto-modificación queda cableada desde el esquema inicial, aunque todavía no
se use.

## Implementación

La unicidad del valor vigente se garantiza con un **índice único parcial**:

```sql
CREATE UNIQUE INDEX settings_current_key_idx
    ON settings (key) WHERE valid_to IS NULL;
```

Puede haber N filas históricas por clave, pero solo una vigente.

Los cambios se hacen **dentro de una transacción** (cerrar + insertar). Si no,
un fallo entre ambas operaciones dejaría la clave sin valor vigente. Además,
compartir el mismo `now()` hace que `valid_to` de una fila coincida exactamente
con `valid_from` de la siguiente: historia continua, sin huecos ni solapamiento.

## Contexto más amplio: auto-modificación

Esta decisión es la aplicación práctica de un principio general: **la frontera
entre "código" y "datos" se elige al diseñar.**

Grados de auto-modificación, de menor a mayor riesgo:

1. **Parámetros** — cambiar valores. Seguro, reversible, auditable.
2. **Reglas** — cambiar reglas declarativas que el sistema interpreta.
3. **Módulos nuevos** — código nuevo, aditivo, desactivable.
4. **Reescritura de sí mismo** — modificar el código en ejecución.

Cuanto más comportamiento viva como **datos**, más auto-modificación se logra
en los niveles 1 y 2, sin pagar el riesgo del 4.

Principio asociado a respetar: **la parte que ejecuta las modificaciones no
debería ser modificable por el sistema.** Un núcleo chico y estable (bucle de
eventos, acceso a base, carga de módulos, registro) que ABEL no reescribe, y
sobre él todo lo demás, que sí. Así siempre queda alguien vivo capaz de
revertir.

## Consecuencias

- La tabla crece con cada cambio. Aceptable: los cambios de configuración son
  poco frecuentes.
- Leer configuración usa `current_settings`, no `settings`. El mecanismo del
  historial queda oculto al código que solo quiere el valor.
- Escribir configuración exige transacción de dos pasos. Se encapsula en la
  capa de acceso a datos.
