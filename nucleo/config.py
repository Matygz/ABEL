"""Configuración de entorno del Núcleo.

Lee las variables definidas en .env: dónde está la base de datos y con qué
credenciales conectarse. Es configuración *de la máquina*, estática durante
toda la ejecución.

La configuración de *comportamiento* de ABEL (intervalos, umbrales) vive en
la tabla `settings` y se lee a través del repositorio.
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


class ErrorConfig(Exception):
    """Falta una variable de entorno requerida, o tiene un valor inválido."""


@dataclass(frozen=True)
class ConfigEntorno:
    db_host: str
    db_puerto: int
    db_nombre: str
    db_usuario: str
    db_password: str
    db_connect_timeout: int = 5
    ws_host: str = "127.0.0.1"
    ws_puerto: int = 8765
    tls_cert: str = "certs/nucleo.crt"
    tls_clave: str = "certs/nucleo.key"
    web_host: str = "127.0.0.1"
    web_puerto: int = 8080
    llm_ejecutable: str = ""
    llm_modelo: str = ""
    llm_puerto: int = 8090
    llm_inactividad_segundos: float = 900.0
    qdrant_url: str = "http://127.0.0.1:6333"

    @property
    def conninfo(self) -> str:
        """Cadena de conexión en el formato que espera psycopg."""
        return (
            f"host={self.db_host} "
            f"port={self.db_puerto} "
            f"dbname={self.db_nombre} "
            f"user={self.db_usuario} "
            f"password={self.db_password} "
            f"connect_timeout={self.db_connect_timeout}"
        )

    def __repr__(self) -> str:
        return (
            f"ConfigEntorno(db_host={self.db_host!r}, "
            f"db_puerto={self.db_puerto}, "
            f"db_nombre={self.db_nombre!r}, "
            f"db_usuario={self.db_usuario!r}, "
            f"db_password='***')"
        )


def _requerida(nombre: str) -> str:
    """Devuelve el valor de una variable de entorno, o falla con un mensaje claro."""
    valor = os.getenv(nombre)
    if not valor:
        raise ErrorConfig(
            f"Falta la variable de entorno {nombre}. "
            f"Revisá el archivo .env (ver .env.example)."
        )
    return valor


def cargar_config() -> ConfigEntorno:
    """Carga y valida la configuración de entorno. Falla al arrancar si algo falta."""
    load_dotenv()

    puerto_texto = _requerida("ABEL_DB_PORT")
    try:
        puerto = int(puerto_texto)
    except ValueError:
        raise ErrorConfig(
            f"ABEL_DB_PORT debe ser un número entero, se recibió {puerto_texto!r}."
        ) from None

    return ConfigEntorno(
        db_host=_requerida("ABEL_DB_HOST"),
        db_puerto=puerto,
        db_nombre=_requerida("ABEL_DB_NAME"),
        db_usuario=_requerida("ABEL_DB_USER"),
        db_password=_requerida("ABEL_DB_PASSWORD"),
        ws_host=os.getenv("ABEL_WS_HOST", "127.0.0.1"),
        ws_puerto=int(os.getenv("ABEL_WS_PORT", "8765")),
        tls_cert=os.getenv("ABEL_TLS_CERT", "certs/nucleo.crt"),
        tls_clave=os.getenv("ABEL_TLS_KEY", "certs/nucleo.key"),
        web_host=os.getenv("ABEL_WEB_HOST", "127.0.0.1"),
        web_puerto=int(os.getenv("ABEL_WEB_PORT", "8080")),
        llm_ejecutable=os.getenv("ABEL_LLM_EXE", ""),
        llm_modelo=os.getenv("ABEL_LLM_MODEL", ""),
        llm_puerto=int(os.getenv("ABEL_LLM_PORT", "8090")),
        llm_inactividad_segundos=float(os.getenv("ABEL_LLM_IDLE", "900")),
        qdrant_url=os.getenv("ABEL_QDRANT_URL", "http://127.0.0.1:6333"),
    )