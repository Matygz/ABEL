"""Errores base del Núcleo."""


class ErrorOperativo(Exception):
    """Fallo esperado y transitorio de una dependencia externa.

    Se registra sin traza: el mensaje ya explica qué pasó. La traza se
    reserva para errores inesperados, donde sí hace falta saber dónde ocurrió.
    """