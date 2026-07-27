# Entorno de desarrollo

Particularidades del setup y tropiezos ya resueltos. Su función es evitar
volver a diagnosticar lo mismo.

**Sistema:** Windows 10 · VS Code · Git Bash (MinTTY) · Python 3.14.4
**Ruta local:** `C:\Users\Maty\Desktop\Proyectos\ABEL`

---

## Entorno virtual

```bash
python -m venv .venv
source .venv/Scripts/activate     # ⚠️ Scripts, NO bin
```

> **`Scripts`, no `bin`.** En Linux y macOS es `bin/activate`. Como la mayoría
> de los tutoriales están escritos para Linux, `bin` aparece por todos lados y
> no funciona en Windows.

El prompt muestra `(.venv)` cuando está activo. **Hay que activarlo en cada
terminal nueva** — no es permanente. Es la causa más común de "instalé el
paquete y no lo encuentra".

Salir: `deactivate`.

### Dependencias

```bash
pip install -r requirements.txt      # reconstruir
pip freeze > requirements.txt        # actualizar tras instalar algo
```

---

## Configuración y credenciales

- **`.env`** — valores reales. **Nunca** se commitea (está en `.gitignore`).
- **`.env.example`** — plantilla sin valores. Sí se commitea. Documenta qué
  variables necesita el proyecto.

Se leen con `python-dotenv`. Las credenciales **nunca** van en el código: una
vez que un secreto entra al historial de Git, sacarlo es un problema serio.

Antes de cualquier commit que toque archivos con conexión a la base:

```bash
git status          # verificar que .env NO aparece
```

---

## psql en Git Bash

### `psql` interactivo se cuelga

MinTTY (el terminal de Git Bash) no se lleva bien con `psql`. Solución:

```bash
winpty psql -U postgres -d abel
```

Alternativa: usar CMD o PowerShell para sesiones interactivas.

### Ejecutar archivos de esquema

```bash
winpty psql -U postgres -d abel -f db/schema/00N_archivo.sql
```

### Comandos útiles

| Comando | Qué hace |
|---|---|
| `\dt` | Listar tablas |
| `\d tabla` | Ver estructura completa de una tabla |
| `\l` | Listar bases de datos |
| `\x` | Alternar modo expandido (vertical, legible en terminal angosta) |
| `\r` | Limpiar el buffer de consulta |
| `\q` | Salir |

> Los comandos de psql usan **backslash** `\`, nunca barra normal `/`. Si se
> escribe `/l` por error, psql lo interpreta como el inicio de una sentencia
> SQL y queda esperando: el prompt cambia de `abel=#` a `abel-#`. Se limpia
> con `\r`.

> Un asterisco en el prompt (`abel=*#`) indica **transacción abierta**. Si
> aparece sin haberlo buscado, hay algo sin confirmar.

---

## Problemas conocidos (sin solución aplicada)

### Codificación de la consola

`psql` advierte que el código de página de la consola (850) difiere del de
Windows (1252). Los caracteres acentuados y la `ñ` se ven mal.

**Es un problema de visualización, no de datos.** La base es UTF8; lo que se
guarda está bien. Solo se dibuja mal en pantalla.

Intentos que no funcionaron: `chcp.com 65001` antes de abrir psql (winpty abre
su propia consola y no hereda el cambio).

Alternativas sin probar:
- `PGCLIENTENCODING=UTF8 winpty psql ...`
- MinTTY → clic derecho en la barra de título → Options → Text → UTF-8

**Solución práctica adoptada:** usar una herramienta gráfica para inspeccionar
datos. El problema no existe fuera de la terminal.

### Finales de línea CRLF

Git avisa `LF will be replaced by CRLF`. Es normal y no requiere acción: Git
normaliza a LF al guardar y devuelve CRLF al escribir en disco.

Sí importa en el futuro: un `^M` invisible al final de una línea rompe un
script `.sh` con errores incomprensibles. Se detectan con `cat -A archivo`.

---

## Herramientas de inspección

Dos necesidades distintas que conviene no mezclar:

### Explorar datos y correr consultas

**Beekeeper Studio** — gratis, código abierto, interfaz simple. Se abre, se ve
la lista de tablas, se hace clic y se ven las filas.

**DBeaver Community** es la alternativa: más pesada, pero multi-base. Ganará
valor cuando se sumen Qdrant y Neo4j.

### Entender la estructura del esquema

**pgAdmin** tiene un generador de diagramas incorporado:
clic derecho sobre la base `abel` → **Generate ERD**.

Dibuja las tablas con sus relaciones de clave foránea. Es la forma más rápida
de ver el esquema completo de un vistazo.

pgAdmin es una herramienta de **administración** (backups, usuarios, permisos,
replicación). Todo eso aparece en primer plano aunque no se necesite, de ahí la
sensación de ruido. Conviene usarlo solo para el ERD y tareas administrativas.

---

## Notas de instalación de PostgreSQL

Si hubiera que reinstalar:

- Instalador oficial desde postgresql.org (distribuido por EDB).
- Componentes: Server, pgAdmin 4, Command Line Tools. **Stack Builder no.**
- Directorios de instalación y datos: valores por defecto.
- Puerto 5432.
- **La contraseña del superusuario `postgres` no se puede recuperar.** Si se
  pierde, hay que reinstalar. Guardar en gestor de contraseñas.
- Si `psql` no se encuentra tras instalar, falta agregar al PATH:
  `C:\Program Files\PostgreSQL\18\bin`. Reabrir la terminal después.
