# 0038 — ABEL corre en background, no como servicio

**Estado:** Vigente
**Fecha:** 2026-08-11
**Fase:** 5.6

## Decisión

`abel.py` lanza el Núcleo y el Nodo sin ventanas visibles y deja un ícono en
la bandeja del sistema. **No es un servicio de Windows.**

## Por qué no un servicio

Un servicio de Windows sería lo "correcto" formalmente: arranca antes del
inicio de sesión, sobrevive a cerrarla.

Pero **un servicio corre en otra sesión y no puede acceder al escritorio del
usuario**. El sensor de ventana activa dejaría de funcionar por completo.

ABEL necesita ver qué ventana está en primer plano. Eso solo se puede desde la
sesión del usuario.

## Lo que hace el lanzador

- Arranca ambos procesos con `pythonw` y `CREATE_NO_WINDOW`: invisibles.
- Vigila cada 10 segundos y reinicia lo que se caiga.
- Menú de bandeja: estado, abrir la interfaz, ver el registro, salir.
- Al salir, termina los procesos hijo ordenadamente.

Es la misma lógica de supervisión del planificador, un nivel más arriba.

## El modelo se carga bajo demanda

Decisión tomada por consumo de VRAM, y es la que hace viable que ABEL corra
siempre:

```
Sin conversación → modelo descargado, 0 GB de VRAM
Le hablás       → se levanta (~6 s)
15 min sin uso  → se baja solo
```

Un modelo residente ocuparía 2,5 GB de los 8 GB de VRAM permanentemente, y esa
VRAM le hace falta al resto del sistema.

Lo que sí corre siempre: Núcleo, Nodo y PostgreSQL. **Unos 340 MB de RAM y
cero VRAM** — menos que una pestaña de navegador.

**Mejora prevista:** usar `session_state` para descargar el modelo cuando se
detecta que el usuario se fue, sin esperar el temporizador.

## Servidores duplicados

Bug encontrado y corregido: si una ejecución no cerraba bien, quedaba un
`llama-server` vivo. Dos procesos compitiendo por la misma VRAM degradan el
rendimiento de forma **dramática y silenciosa** — se midieron 2 t/s contra 55.

`_matar_huerfanos()` los termina antes de arrancar uno nuevo.

## Arranque automático

Un `.vbs` que lanza sin consola, más un acceso directo en la carpeta de inicio.

No es un `.exe`: compilar con PyInstaller tiene sentido cuando el código deje
de cambiar a diario. Hoy sería recompilar en cada iteración.

**PostgreSQL debe arrancar antes.** Como servicio de Windows lo hace solo,
pero puede tardar unos segundos más que la sesión. El Núcleo tolera ese fallo
inicial (Fase 1), así que no rompe.
