"""Establecimiento de sesiones de interfaz.

No hay contraseñas. Una sesión se abre porque el Nodo del dispositivo firmó
un desafío con su clave privada (ver 0021): el dispositivo autorizado es la
credencial.

Consecuencia asumida: quien tenga acceso al dispositivo obtiene sesión. Es
la misma propiedad que tiene una sesión de sistema operativo desbloqueada.
La mitigación es la suspensión por inactividad, no una contraseña —que
tampoco protegería una vez abierta la sesión.
"""

from __future__ import annotations

import logging
from uuid import UUID

from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from nucleo.red.servidor import ServidorNodos
from protocolos.firma import ErrorFirma, desde_texto, material_sesion, verificar

logger = logging.getLogger(__name__)


class ErrorSesion(Exception):
    """No se pudo establecer la sesión."""


class ServicioSesiones:
    """Abre sesiones de interfaz verificando con el Nodo del dispositivo."""

    def __init__(self, repositorio: Repositorio, servidor: ServidorNodos) -> None:
        self._repo = repositorio
        self._servidor = servidor

    async def abrir_desde(self, direccion: str, user_id: UUID) -> str:
        """Abre una sesión para un navegador que viene de una dirección.

        Devuelve el token. Falla si no hay un Nodo conectado desde ahí, si no
        autoriza, o si la firma no verifica.
        """
        device_id = self._servidor.dispositivo_en(direccion)
        if device_id is None:
            await self._registrar_rechazo(user_id, "sin_nodo", direccion)
            raise ErrorSesion(
                "No hay un Nodo de ABEL corriendo en este dispositivo."
            )

        resultado = await self._servidor.solicitar_firma_de_sesion(device_id)
        if resultado is None:
            await self._registrar_rechazo(user_id, "sin_respuesta", direccion)
            raise ErrorSesion("El Nodo no autorizó la sesión.")

        solicitud_id, desafio, firma_texto = resultado

        claves = await self._repo.obtener_claves_activas(device_id)
        material = material_sesion(desafio, solicitud_id, device_id)
        # Si ya hay una sesión activa reciente para este usuario y dispositivo,
        # se cierra antes de abrir la nueva. Sin esto, cada intento acumula
        # una sesión más: pedirle al Nodo que firme cuesta tiempo, y nueve
        # sesiones abiertas son nueve firmas y nueve escrituras.
        await self._repo.cerrar_sesiones_de(user_id, device_id)
        try:
            firma = desde_texto(firma_texto)
        except ErrorFirma:
            await self._registrar_rechazo(user_id, "firma_invalida", direccion)
            raise ErrorSesion("La autorización del Nodo no es válida.") from None

        if not any(verificar(clave, material, firma) for clave in claves):
            await self._registrar_rechazo(user_id, "firma_invalida", direccion)
            raise ErrorSesion("La autorización del Nodo no es válida.")

        token = await self._repo.abrir_sesion(user_id, device_id)
        logger.debug("Sesión abierta desde %s (dispositivo %s)", direccion, device_id)
        return token

    async def _registrar_rechazo(
        self, user_id: UUID, motivo: str, direccion: str
    ) -> None:
        try:
            await self._repo.registrar_evento(
                event_type="session_denied",
                actor_id=user_id,
                payload={"reason": motivo, "address": direccion},
            )
        except ErrorRepositorio as exc:
            logger.error("No se pudo registrar session_denied: %s", exc)