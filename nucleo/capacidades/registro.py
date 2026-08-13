"""Descubrimiento y despacho de capacidades.

Una capacidad es un módulo en esta carpeta. Al arrancar, el registro escanea
el directorio, valida lo que encuentra, y arma el catálogo.

Agregar una capacidad es agregar un archivo. No hay que registrarla en
ninguna lista, ni cargar sus ejemplos a mano, ni tocar el despachador: todo
sale de lo que el módulo declara.

Eso importa por algo más que comodidad: cuando ABEL se pregunta qué puede
hacer, la respuesta sale de lo que efectivamente está cargado, no de una
lista que alguien mantiene aparte y puede quedar desactualizada.

Cada módulo declara:

    NOMBRE       identificador único
    TIPO         a qué familia pertenece (consultar_memoria, calcular, ...)
    DESCRIPCION  una línea, legible
    EJEMPLOS     cómo se le pide, en lenguaje natural
    NIVEL        qué permiso requiere (lectura, admin, puntual)
    NECESITA     qué dependencias usa
    resolver()   la función que la ejecuta

`NECESITA` no es decorativo: una capacidad solo recibe lo que declaró. Si no
pide el repositorio, no puede escribir en la base — ni por error ni a
propósito. Es el criterio de 0030 aplicado por construcción.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from comun.errores import ErrorOperativo

logger = logging.getLogger(__name__)


class Nivel:
    """Qué hace falta para ejecutar una capacidad."""

    LECTURA = "lectura"    # Consultar lo que ABEL ya registró
    ADMIN = "admin"        # Rol admin y dispositivo de confianza admin
    PUNTUAL = "puntual"    # Autorización explícita, cada vez

    TODOS = frozenset({LECTURA, ADMIN, PUNTUAL})


class ErrorCapacidad(ErrorOperativo):
    """Una capacidad está mal declarada o falló al resolver."""


@dataclass(frozen=True)
class Capacidad:
    """Una capacidad descubierta y validada."""

    nombre: str
    tipo: str
    descripcion: str
    ejemplos: tuple[str, ...]
    nivel: str
    necesita: tuple[str, ...]
    resolver: Any
    parametros: dict = None

    def __post_init__(self):
        if self.parametros is None:
            object.__setattr__(self, "parametros", {})


class RegistroCapacidades:
    """Descubre las capacidades y las ejecuta con lo que declararon."""

    def __init__(self, dependencias: dict[str, Any]) -> None:
        self._dependencias = dependencias
        self._capacidades: dict[str, Capacidad] = {}

    # ------------------------------------------------------------------

    def descubrir(self) -> int:
        """Escanea el paquete y carga lo que encuentre. Devuelve cuántas."""
        import nucleo.capacidades as paquete

        # El registro se ofrece como dependencia: una capacidad puede
        # necesitar saber qué capacidades hay — es cómo ABEL responde qué
        # sabe hacer sin una lista escrita aparte.
        self._dependencias.setdefault("registro", self)

        for info in pkgutil.iter_modules(paquete.__path__):
            if info.name.startswith("_") or info.name == "registro":
                continue

            try:
                modulo = importlib.import_module(
                    f"nucleo.capacidades.{info.name}"
                )
                capacidad = self._leer(modulo, info.name)
            except ErrorCapacidad as exc:
                # Una capacidad mal declarada no impide arrancar: las demás
                # siguen sirviendo. Mismo criterio que los sensores.
                logger.error("Capacidad %s descartada: %s", info.name, exc)
                continue

            if capacidad.nombre in self._capacidades:
                logger.error(
                    "Nombre repetido: %s (en %s). Se ignora la segunda.",
                    capacidad.nombre, info.name,
                )
                continue

            self._capacidades[capacidad.nombre] = capacidad

        logger.info(
            "Capacidades: %d (%d ejemplos)",
            len(self._capacidades),
            sum(len(c.ejemplos) for c in self._capacidades.values()),
        )
        return len(self._capacidades)

    def _leer(self, modulo: ModuleType, archivo: str) -> Capacidad:
        """Valida lo que declara un módulo."""
        def exigir(atributo: str):
            if not hasattr(modulo, atributo):
                raise ErrorCapacidad(f"le falta {atributo}")
            return getattr(modulo, atributo)

        nombre = exigir("NOMBRE")
        tipo = exigir("TIPO")
        descripcion = exigir("DESCRIPCION")
        ejemplos = tuple(exigir("EJEMPLOS"))
        nivel = getattr(modulo, "NIVEL", Nivel.LECTURA)
        necesita = tuple(getattr(modulo, "NECESITA", ()))
        parametros = dict(getattr(modulo, "PARAMETROS", {}))
        resolver = exigir("resolver")

        if not ejemplos:
            raise ErrorCapacidad("no declara ningún ejemplo")

        if nivel not in Nivel.TODOS:
            raise ErrorCapacidad(f"nivel desconocido: {nivel!r}")

        if not inspect.iscoroutinefunction(resolver):
            raise ErrorCapacidad("resolver() tiene que ser async")

        faltantes = [n for n in necesita if n not in self._dependencias]
        if faltantes:
            # Falla al arrancar y no en medio de una conversación: un módulo
            # que pide algo inexistente es un error de programación.
            raise ErrorCapacidad(
                f"pide dependencias que no existen: {', '.join(faltantes)}"
            )

        return Capacidad(
            nombre=nombre,
            tipo=tipo,
            descripcion=descripcion,
            ejemplos=ejemplos,
            nivel=nivel,
            necesita=necesita,
            parametros=parametros,
            resolver=resolver,
        )

    # ------------------------------------------------------------------

    def todas(self) -> tuple[Capacidad, ...]:
        return tuple(self._capacidades.values())

    def obtener(self, nombre: str) -> Capacidad | None:
        return self._capacidades.get(nombre)

    def de_tipo(self, tipo: str) -> tuple[Capacidad, ...]:
        return tuple(c for c in self._capacidades.values() if c.tipo == tipo)

    async def ejecutar(self, nombre: str, parametros: dict) -> Any:
        """Ejecuta una capacidad con las dependencias que declaró.

        Solo recibe lo que pidió en NECESITA: el alcance de cada capacidad
        está acotado por construcción, no por disciplina.
        """
        capacidad = self._capacidades.get(nombre)
        if capacidad is None:
            raise ErrorCapacidad(f"No existe la capacidad {nombre!r}.")

        argumentos = {n: self._dependencias[n] for n in capacidad.necesita}
        return await capacidad.resolver(
            {**capacidad.parametros, **parametros}, **argumentos
        )