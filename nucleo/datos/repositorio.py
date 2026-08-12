"""Capa de acceso a datos del Núcleo.

Encapsula todo el SQL del proyecto. El resto del código llama métodos de esta
clase y nunca escribe consultas — salvo `nucleo/memoria`, que usa `consultar`
para sus agregaciones.

El repositorio se compone de piezas por área. Se juntan acá porque la
interfaz pública es una sola: quien lo usa no tiene por qué saber en qué
archivo vive cada método.

    conexion.py   conexión y consultas de lectura
    eventos.py    eventos, ejecuciones, observaciones, conversación
    actores.py    usuarios, dispositivos, claves
    sesiones.py   sesiones de interfaz

Interfaz asíncrona: todos los métodos son corrutinas y no bloquean el bucle
de eventos mientras esperan a la base de datos.
"""

from __future__ import annotations

from nucleo.datos.actores import MixinActores
from nucleo.datos.conexion import ErrorRepositorio, RepositorioBase
from nucleo.datos.eventos import MixinEventos
from nucleo.datos.sesiones import MixinSesiones

__all__ = ["ErrorRepositorio", "Repositorio"]


class Repositorio(MixinEventos, MixinActores, MixinSesiones, RepositorioBase):
    """Acceso asíncrono a la base de datos de ABEL."""
