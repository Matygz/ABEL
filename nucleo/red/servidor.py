"""Servidor WebSocket del Núcleo.

Acepta conexiones de Nodos, valida su identidad contra `devices`, recibe
observaciones y las persiste. Cada conexión se maneja de forma independiente:
un Nodo que se porta mal no afecta a los demás.

Fase 2.3: autenticación por firma Ed25519 con desafío. Sin TLS todavía:
escucha solo en localhost.
"""

from __future__ import annotations

import asyncio
import secrets
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
    crear_session_request,
    crear_welcome,
    leer_hello,
    leer_observation,
    leer_session_grant,
)
from protocolos.firma import (
    ErrorFirma, a_texto, desde_texto, generar_desafio,
    material_a_firmar, material_sesion, verificar,
)
from protocolos.mensajes import (
    CodigoError,
    ErrorProtocolo,
    Sobre,
    TipoMensaje,
    deserializar,
)
import ssl
from pathlib import Path

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
        tls_cert: str = "certs/nucleo.crt",
        tls_clave: str = "certs/nucleo.key",
        sangre=None,
    ) -> None:
        self._repo = repositorio
        self._version = version
        self._host = host
        self._puerto = puerto
        self._intervalo_presencia = intervalo_presencia
        self._sesiones: dict[UUID, ServerConnection] = {}
        self._ips: dict[str, UUID] = {}
        self._solicitudes: dict[UUID, asyncio.Future] = {}
        self._contexto_tls = self._construir_contexto_tls(tls_cert, tls_clave)
        self._sangre = sangre
    @staticmethod
    def _construir_contexto_tls(cert: str, clave: str) -> ssl.SSLContext:
        """Arma el contexto TLS del servidor.

        Se exige TLS 1.2 como mínimo: las versiones anteriores tienen
        debilidades conocidas y ya no se consideran seguras.
        """
        ruta_cert, ruta_clave = Path(cert), Path(clave)

        for ruta in (ruta_cert, ruta_clave):
            if not ruta.exists():
                raise FileNotFoundError(
                    f"No existe {ruta}. Generá el certificado con: "
                    f"python -m scripts.certificado generar"
                )

        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contexto.minimum_version = ssl.TLSVersion.TLSv1_2
        contexto.load_cert_chain(certfile=ruta_cert, keyfile=ruta_clave)
        return contexto

    async def ejecutar(self) -> None:
        """Arranca el servidor y corre hasta que se lo cancele."""
        async with serve(
            self._atender,
            self._host,
            self._puerto,
            ssl=self._contexto_tls,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 * 1024 * 1024,
        ) as servidor:
            logger.info(
                "Servidor de Nodos escuchando en wss://%s:%s",
                self._host, self._puerto,
            )
            await servidor.serve_forever()

    # ------------------------------------------------------------------
    # Ciclo de una conexión
    # ------------------------------------------------------------------

    async def _atender(self, conexion: ServerConnection) -> None:
        """Maneja una conexión completa, desde el saludo hasta el cierre."""
        cid = secrets.token_hex(3)
        logger.debug("[%s] Conexión entrante desde %s", cid, conexion.remote_address)

        dispositivo = await self._saludar(conexion, cid)
        if dispositivo is None:
            return

        device_id = dispositivo["id"]
        nombre = dispositivo["name"]
        session_id = uuid7()
        self._sesiones[device_id] = conexion
        if conexion.remote_address:
            self._ips[conexion.remote_address[0]] = device_id

        await self._registrar_evento_conexion(
            device_id, "device_connected",
            {"session_id": str(session_id), "trust_level": dispositivo["trust_level"]},
        )
        logger.info("[%s] Nodo conectado: %s (%s)", cid, nombre, device_id)

        motivo = "closed"
        try:
            async for crudo in conexion:
                await self._procesar(conexion, device_id, crudo, cid)
        except websockets.ConnectionClosedError:
            motivo = "link_lost"
        except websockets.ConnectionClosedOK:
            motivo = "closed"
        finally:
            self._sesiones.pop(device_id, None)
            if conexion.remote_address:
                self._ips.pop(conexion.remote_address[0], None)
            await self._registrar_evento_conexion(
                device_id, "device_disconnected",
                {"session_id": str(session_id), "reason": motivo},
            )
            logger.info("[%s] Nodo desconectado: %s (%s)", cid, nombre, motivo)

    async def _saludar(self, conexion: ServerConnection, cid: str) -> dict | None:
        """Procesa el saludo en tres pasos. Devuelve el dispositivo, o None.

        1. El Nodo declara su device_id.
        2. El Núcleo emite un desafío aleatorio de un solo uso.
        3. El Nodo devuelve la firma del desafío con su clave privada.

        El desafío evita ataques de repetición: una firma capturada no sirve
        para una conexión posterior, porque el desafío nunca se repite.

        Antes de completar la autenticación, un error cierra la conexión sin
        explicar (ver decisión 0018).
        """
        hello = await self._recibir_hello(conexion, cid)
        if hello is None:
            return None

        dispositivo = await self._repo.obtener_dispositivo_activo(hello.device_id)
        claves = await self._repo.obtener_claves_activas(hello.device_id)

        desafio = generar_desafio()
        await self._enviar(conexion, crear_challenge(a_texto(desafio)))

        respuesta = await self._recibir_hello(conexion, cid)
        if respuesta is None:
            return None

        if not await self._credencial_valida(
            respuesta, dispositivo, claves, desafio, hello.device_id, cid                      
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

    async def _recibir_hello(self, conexion: ServerConnection, cid: str) -> dict | None:
        """Recibe y valida un mensaje hello. Cierra la conexión si es inválido."""
        try:
            sobre = deserializar(await conexion.recv())
            if sobre.tipo != TipoMensaje.HELLO:
                logger.warning("[%s] Se esperaba hello, llegó %s.", cid, sobre.tipo)
                await conexion.close(code=1002)
                return None
            return leer_hello(sobre)
        except ErrorProtocolo as exc:
            logger.warning("[%s] Saludo inválido: %s", cid, exc.detalle)
            await conexion.close(code=1002)
            return None
        except (websockets.ConnectionClosed, TimeoutError):
            return None

    async def _credencial_valida(
        self, respuesta, dispositivo, claves, desafio, device_id, cid: str
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
            logger.warning("[%s] El device_id cambió entre los dos hello.", cid)
            firma_valida = False

        if dispositivo is None:
            logger.warning("[%s] Dispositivo %s no autorizado o revocado.", cid, device_id)
            return False

        if not claves:
            logger.warning("[%s] Dispositivo %s no tiene claves registradas.", cid, device_id)
            await self._registrar_fallo_auth(device_id, "no_keys")
            return False

        if not firma_valida:
            logger.warning("[%s] Firma inválida de %s.", cid, device_id)
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
        self, conexion: ServerConnection, device_id: UUID, crudo: str | bytes, cid: str
    ) -> None:
        """Procesa un mensaje de un Nodo ya identificado."""
        try:
            sobre = deserializar(crudo)
        except ErrorProtocolo as exc:
            logger.warning("[%s] Mensaje inválido de %s: %s", cid, device_id, exc.detalle)
            await self._enviar(conexion, crear_error(exc.codigo))
            return

        try:
            if sobre.tipo == TipoMensaje.OBSERVATION:
                await self._recibir_observaciones(conexion, device_id, sobre, cid)
            elif sobre.tipo == TipoMensaje.PRESENCE_MARK:
                await self._recibir_presencia(device_id, sobre, cid)
            elif sobre.tipo == TipoMensaje.SESSION_GRANT:
                self._recibir_concesion(sobre, cid)
            else:
                logger.warning(
                    "[%s] Tipo inesperado de %s: %s", cid, device_id, sobre.tipo
                )
                await self._enviar(conexion, crear_error(CodigoError.MALFORMED))
        except ErrorProtocolo as exc:
            logger.warning("[%s] Contenido inválido de %s: %s", cid, device_id, exc.detalle)
            await self._enviar(conexion, crear_error(exc.codigo))
        except ErrorRepositorio as exc:
            logger.error("[%s] Fallo al persistir datos de %s: %s", cid, device_id, exc)
            await self._enviar(conexion, crear_error(CodigoError.INTERNAL))

    async def _recibir_observaciones(
        self, conexion: ServerConnection, device_id: UUID, sobre: Sobre, cid: str
    ) -> None:
        """Persiste un lote y confirma. El ack se envía solo después de escribir."""
        observaciones = leer_observation(sobre, maximo=MAX_OBSERVACIONES_POR_LOTE)

        confirmadas, rechazadas = await self._repo.persistir_observaciones(
            device_id, observaciones
        )

        await self._enviar(conexion, crear_ack(confirmadas, rechazadas))
        logger.debug(
            "[%s] Lote de %s: %d confirmada(s), %d rechazada(s).",
            cid, device_id, len(confirmadas), len(rechazadas),
        )

        # La actividad sube con lo que llega. No es un aviso a nadie: es un
        # valor que sube, y quien lo lea reaccionará o no.
        if self._sangre is not None and confirmadas:
            # Solo lo que implica movimiento real. El sensor muestrea cada
            # dos segundos y reportar no es lo mismo que estar haciendo algo:
            # una noche entera con la máquina quieta dejó la actividad en
            # 0.27 en vez de cero.
            cambios = sum(
                1 for obs in observaciones
                if obs.id in confirmadas
                and obs.event_type in ("window_session", "session_state")
            )
            if cambios:
                self._sangre.empujar("actividad", min(0.3, 0.04 * cambios))

    async def _recibir_presencia(self, device_id: UUID, sobre: Sobre, cid: str) -> None:
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

    # ------------------------------------------------------------------
    # Vinculación de sesiones de interfaz
    # ------------------------------------------------------------------

    def dispositivo_en(self, direccion: str) -> UUID | None:
        """Qué dispositivo tiene un Nodo conectado desde esa dirección.

        Es la forma de relacionar un navegador con el Nodo de su misma
        máquina. Implica que quien esté en ese dispositivo puede obtener
        sesión: el dispositivo es la credencial.
        """
        return self._ips.get(direccion)

    async def solicitar_firma_de_sesion(
        self, device_id: UUID, timeout: float = 15.0
    ) -> tuple[UUID, bytes, str] | None:
        """Pide al Nodo que autorice una sesión. Devuelve lo necesario para
        verificar, o None si no respondió a tiempo.
        """
        conexion = self._sesiones.get(device_id)
        if conexion is None:
            return None

        solicitud_id = uuid7()
        desafio = generar_desafio()
        futuro: asyncio.Future = asyncio.get_running_loop().create_future()
        self._solicitudes[solicitud_id] = futuro

        try:
            await self._enviar(
                conexion, crear_session_request(solicitud_id, a_texto(desafio))
            )
            firma = await asyncio.wait_for(futuro, timeout=timeout)
            return solicitud_id, desafio, firma
        except TimeoutError:
            logger.warning(
                "El Nodo %s no autorizó la sesión en %ss.", device_id, timeout
            )
            return None
        finally:
            self._solicitudes.pop(solicitud_id, None)

    def _recibir_concesion(self, sobre: Sobre, cid: str) -> None:
        """Entrega la firma a quien la estaba esperando."""
        concesion = leer_session_grant(sobre)
        futuro = self._solicitudes.get(concesion.solicitud_id)

        if futuro is None or futuro.done():
            logger.warning(
                "[%s] Concesión de sesión sin solicitud pendiente.", cid
            )
            return

        futuro.set_result(concesion.firma)