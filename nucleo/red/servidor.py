"""Servidor WebSocket del Núcleo.

Acepta conexiones de Nodos, valida su identidad contra `devices`, recibe
observaciones y las persiste. Cada conexión se maneja de forma independiente:
un Nodo que se porta mal no afecta a los demás.

Fase 2.2: sin TLS ni autenticación. Escucha solo en localhost. La credencial
del `hello` se acepta vacía; la 2.3 la hace obligatoria.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid7

import websockets
from websockets.asyncio.server import ServerConnection, serve

from nucleo.datos.repositorio import ErrorRepositorio, Repositorio
from protocolos.contenidos import (
    MAX_OBSERVACIONES_POR_LOTE,
    crear_ack,
    crear_challenge,
    crear_error,
    crear_reject,
    crear_welcome,
    leer_hello,
    leer_observation,
)
from protocolos.firma import a_texto, generar_desafio, material_a_firmar, verificar, desde_texto, ErrorFirma
from protocolos.mensajes import (
    CodigoError,
    ErrorProtocolo,
    Sobre,
    TipoMensaje,
    deserializar,
)

logger = logging.getLogger(__name__)

TIMEOUT_HELLO_SEGUNDOS = 10.0


class ServidorNodos:
    """Escucha conexiones de Nodos y procesa sus mensajes."""

    def __init__(
        self,
        repositorio: Repositorio,
        version: str,
        host: str = "127.0.0.1",
        puerto: int = 8765,
        intervalo_presencia: int = 60,
    ) -> None:
        self._repo = repositorio
        self._version = version
        self._host = host
        self._puerto = puerto
        self._intervalo_presencia = intervalo_presencia
        self._sesiones: dict[UUID, ServerConnection] = {}

    async def ejecutar(self) -> None:
        """Arranca el servidor y corre hasta que se lo cancele."""
        async with serve(
            self._atender,
            self._host,
            self._puerto,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 * 1024 * 1024,
        ) as servidor:
            logger.info(
                "Servidor de Nodos escuchando en ws://%s:%s",
                self._host, self._puerto,
            )
            await servidor.serve_forever()

    # ------------------------------------------------------------------
    # Ciclo de una conexión
    # ------------------------------------------------------------------

    async def _atender(self, conexion: ServerConnection) -> None:
        """Maneja una conexión completa, desde el saludo hasta el cierre."""
        remoto = conexion.remote_address
        logger.debug("Conexión entrante desde %s", remoto)

        dispositivo = await self._saludar(conexion)
        if dispositivo is None:
            return

        device_id = dispositivo["id"]
        nombre = dispositivo["name"]
        session_id = uuid7()
        self._sesiones[device_id] = conexion

        await self._registrar_evento_conexion(
            device_id, "device_connected",
            {"session_id": str(session_id), "trust_level": dispositivo["trust_level"]},
        )
        logger.info("Nodo conectado: %s (%s)", nombre, device_id)

        motivo = "closed"
        try:
            async for crudo in conexion:
                await self._procesar(conexion, device_id, crudo)
        except websockets.ConnectionClosedError:
            motivo = "link_lost"
        except websockets.ConnectionClosedOK:
            motivo = "closed"
        finally:
            self._sesiones.pop(device_id, None)
            await self._registrar_evento_conexion(
                device_id, "device_disconnected",
                {"session_id": str(session_id), "reason": motivo},
            )
            logger.info("Nodo desconectado: %s (%s)", nombre, motivo)

    async def _saludar(self, conexion: ServerConnection) -> dict | None:
        """Procesa el saludo en tres pasos. Devuelve el dispositivo, o None.

        1. El Nodo declara su device_id.
        2. El Núcleo emite un desafío aleatorio de un solo uso.
        3. El Nodo devuelve la firma del desafío con su clave privada.

        El desafío evita ataques de repetición: una firma capturada no sirve
        para una conexión posterior, porque el desafío nunca se repite.

        Antes de completar la autenticación, un error cierra la conexión sin
        explicar (ver decisión 0018).
        """
        hello = await self._recibir_hello(conexion)
        if hello is None:
            return None

        dispositivo = await self._repo.obtener_dispositivo_activo(hello.device_id)
        claves = await self._repo.obtener_claves_activas(hello.device_id)

        desafio = generar_desafio()
        await self._enviar(conexion, crear_challenge(a_texto(desafio)))

        respuesta = await self._recibir_hello(conexion)
        if respuesta is None:
            return None

        if not await self._credencial_valida(
            respuesta, dispositivo, claves, desafio, hello.device_id
        ):
            await self._enviar(conexion, crear_reject(CodigoError.UNAUTHORIZED))
            await conexion.close(code=1008)
            return None

        await self._enviar(
            conexion,
            crear_welcome(
                session_id=uuid7(),
                server_version=self._version,
                presence_interval_seconds=self._intervalo_presencia,
                max_batch_size=MAX_OBSERVACIONES_POR_LOTE,
            ),
        )
        return dispositivo

    async def _recibir_hello(self, conexion: ServerConnection):
        """Recibe y valida un mensaje hello. Cierra la conexión si es inválido."""
        try:
            sobre = deserializar(await conexion.recv())
            if sobre.tipo != TipoMensaje.HELLO:
                logger.warning("Se esperaba hello, llegó %s.", sobre.tipo)
                await conexion.close(code=1002)
                return None
            return leer_hello(sobre)
        except ErrorProtocolo as exc:
            logger.warning("Saludo inválido: %s", exc.detalle)
            await conexion.close(code=1002)
            return None
        except (websockets.ConnectionClosed, TimeoutError):
            return None

    async def _credencial_valida(
        self, respuesta, dispositivo, claves, desafio, device_id
    ) -> bool:
        """Verifica la firma. Registra el fallo, pero no revela el motivo.

        El trabajo se hace igual aunque el dispositivo no exista: así el
        tiempo de respuesta no delata si un device_id está registrado.
        """
        material = material_a_firmar(desafio, device_id)

        firma_valida = False
        if respuesta.credential is not None:
            try:
                firma = desde_texto(respuesta.credential)
                firma_valida = any(verificar(k, material, firma) for k in claves)
            except ErrorFirma:
                firma_valida = False

        if respuesta.device_id != device_id:
            logger.warning("El device_id cambió entre los dos hello.")
            firma_valida = False

        if dispositivo is None:
            logger.warning("Dispositivo %s no autorizado o revocado.", device_id)
            return False

        if not claves:
            logger.warning("Dispositivo %s no tiene claves registradas.", device_id)
            await self._registrar_fallo_auth(device_id, "no_keys")
            return False

        if not firma_valida:
            logger.warning("Firma inválida de %s.", device_id)
            await self._registrar_fallo_auth(device_id, "invalid_signature")
            return False

        return True

    async def _registrar_fallo_auth(self, device_id: UUID, motivo: str) -> None:
        try:
            await self._repo.registrar_evento(
                event_type="auth_failed",
                actor_id=device_id,
                payload={"reason": motivo},
            )
        except ErrorRepositorio as exc:
            logger.error("No se pudo registrar auth_failed: %s", exc)

    async def _procesar(
        self, conexion: ServerConnection, device_id: UUID, crudo: str | bytes
    ) -> None:
        """Procesa un mensaje de un Nodo ya identificado."""
        try:
            sobre = deserializar(crudo)
        except ErrorProtocolo as exc:
            logger.warning("Mensaje inválido de %s: %s", device_id, exc.detalle)
            await self._enviar(conexion, crear_error(exc.codigo))
            return

        try:
            if sobre.tipo == TipoMensaje.OBSERVATION:
                await self._recibir_observaciones(conexion, device_id, sobre)
            elif sobre.tipo == TipoMensaje.PRESENCE_MARK:
                await self._recibir_presencia(device_id, sobre)
            else:
                logger.warning(
                    "Tipo inesperado de %s: %s", device_id, sobre.tipo
                )
                await self._enviar(conexion, crear_error(CodigoError.MALFORMED))
        except ErrorProtocolo as exc:
            logger.warning("Contenido inválido de %s: %s", device_id, exc.detalle)
            await self._enviar(conexion, crear_error(exc.codigo))
        except ErrorRepositorio as exc:
            logger.error("Fallo al persistir datos de %s: %s", device_id, exc)
            await self._enviar(conexion, crear_error(CodigoError.INTERNAL))

    async def _recibir_observaciones(
        self, conexion: ServerConnection, device_id: UUID, sobre: Sobre
    ) -> None:
        """Persiste un lote y confirma. El ack se envía solo después de escribir."""
        observaciones = leer_observation(sobre, maximo=MAX_OBSERVACIONES_POR_LOTE)

        confirmadas, rechazadas = await self._repo.persistir_observaciones(
            device_id, observaciones
        )

        await self._enviar(conexion, crear_ack(confirmadas, rechazadas))
        logger.debug(
            "Lote de %s: %d confirmada(s), %d rechazada(s).",
            device_id, len(confirmadas), len(rechazadas),
        )

    async def _recibir_presencia(self, device_id: UUID, sobre: Sobre) -> None:
        """Registra la marca de presencia de un Nodo."""
        await self._repo.registrar_evento(
            event_type="presence_mark",
            actor_id=device_id,
            payload=sobre.payload,
            occurred_at=sobre.sent_at,
        )

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    async def _enviar(self, conexion: ServerConnection, sobre: Sobre) -> None:
        try:
            await conexion.send(sobre.serializar())
        except websockets.ConnectionClosed:
            pass

    async def _registrar_evento_conexion(
        self, device_id: UUID, tipo: str, datos: dict
    ) -> None:
        try:
            await self._repo.registrar_evento(
                event_type=tipo,
                actor_id=device_id,
                payload=datos,
                occurred_at=datetime.now(timezone.utc),
            )
        except ErrorRepositorio as exc:
            logger.error("No se pudo registrar %s de %s: %s", tipo, device_id, exc)