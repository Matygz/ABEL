"""Cliente WebSocket de un Nodo.

Se conecta al Núcleo, se presenta, y envía lo que tenga en cola. Reconecta
solo ante cualquier corte.

El Nodo no interpreta nada: transporta observaciones, nunca conclusiones.
No accede a la base de datos del Núcleo ni importa nada de nucleo/.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid7

import websockets
from websockets.asyncio.client import connect

from nodos.cola import ColaObservaciones
from nodos.config import ConfigNodo
from protocolos.contenidos import (
    Observacion,
    Welcome,
    crear_hello,
    crear_observation,
    leer_ack,
    leer_challenge,
    leer_welcome,
)
from protocolos.firma import a_texto, desde_texto, firmar, material_a_firmar
from protocolos.mensajes import ErrorProtocolo, TipoMensaje, deserializar

logger = logging.getLogger(__name__)

VERSION_CLIENTE = "0.0.1"
ESPERA_RECONEXION = 5.0


class ClienteNodo:
    """Mantiene la conexión de un Nodo con el Núcleo."""

    def __init__(self, config: ConfigNodo) -> None:
        self._config = config
        self._cola = ColaObservaciones()
        self._inicio = datetime.now(timezone.utc)
        self._sesion: Welcome | None = None
        self._contexto_tls = self._construir_contexto_tls(config.certificado_nucleo)

    @staticmethod
    def _construir_contexto_tls(certificado: str) -> ssl.SSLContext:
        """Arma el contexto TLS del cliente.

        Confía únicamente en el certificado del Núcleo (fijación), no en las
        autoridades del sistema. Es más estricto que el modelo de internet:
        un navegador acepta cualquier certificado firmado por cualquiera de
        sus autoridades; este cliente acepta exactamente uno.
        """
        contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        contexto.minimum_version = ssl.TLSVersion.TLSv1_2
        contexto.load_verify_locations(cafile=str(Path(certificado)))
        contexto.check_hostname = True
        contexto.verify_mode = ssl.CERT_REQUIRED
        return contexto

    def observar(self, event_type: str, data: dict) -> None:
        """Encola una observación. No requiere conexión."""
        self._cola.agregar(
            Observacion(
                id=uuid7(),
                occurred_at=datetime.now(timezone.utc),
                event_type=event_type,
                data=data,
            )
        )

    async def ejecutar(self) -> None:
        """Conecta y mantiene la sesión, reconectando ante cualquier corte."""
        async for ws in connect(
            self._config.servidor_url,
            ssl=self._contexto_tls,
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
        ):
            try:
                await self._sesion_completa(ws)
            except websockets.ConnectionClosed:
                logger.warning(
                    "Conexión perdida. Reintenta en %ss. Pendientes: %d",
                    ESPERA_RECONEXION, len(self._cola),
                )
            except ErrorProtocolo as exc:
                logger.error("Error de protocolo: %s", exc.detalle)
            finally:
                self._sesion = None
            await asyncio.sleep(ESPERA_RECONEXION)

    async def _sesion_completa(self, ws) -> None:
        """Saluda y luego alterna entre enviar pendientes y marcar presencia."""
        await self._saludar(ws)

        while True:
            await self._marcar_presencia(ws)
            await self._enviar_pendientes(ws)
            await self._dormir(self._sesion.presence_interval_seconds)

    async def _dormir(self, segundos: float) -> None:
        """Duerme en tramos cortos para que Ctrl+C se atienda rápido en Windows."""
        restante = segundos
        while restante > 0:
            await asyncio.sleep(min(0.2, restante))
            restante -= 0.2

    async def _saludar(self, ws) -> None:
        """Saludo en tres pasos: declarar, recibir desafío, firmar."""
        await ws.send(
            crear_hello(
                device_id=self._config.device_id,
                capabilities=list(self._config.capabilities),
                client_version=VERSION_CLIENTE,
            ).serializar()
        )

        sobre = deserializar(await ws.recv())

        if sobre.tipo == TipoMensaje.REJECT:
            raise ErrorProtocolo(
                f"El Núcleo rechazó la conexión: {sobre.payload.get('code', 'unknown')}"
            )

        if sobre.tipo != TipoMensaje.CHALLENGE:
            raise ErrorProtocolo(f"Se esperaba challenge, llegó {sobre.tipo}.")

        desafio = desde_texto(leer_challenge(sobre))
        material = material_a_firmar(desafio, self._config.device_id)
        firma = firmar(self._config.clave_privada, material)

        await ws.send(
            crear_hello(
                device_id=self._config.device_id,
                capabilities=list(self._config.capabilities),
                client_version=VERSION_CLIENTE,
                credential=a_texto(firma),
            ).serializar()
        )

        sobre = deserializar(await ws.recv())

        if sobre.tipo == TipoMensaje.REJECT:
            raise ErrorProtocolo(
                f"El Núcleo rechazó la credencial: {sobre.payload.get('code', 'unknown')}"
            )

        if sobre.tipo != TipoMensaje.WELCOME:
            raise ErrorProtocolo(f"Se esperaba welcome, llegó {sobre.tipo}.")

        self._sesion = leer_welcome(sobre)
        logger.info(
            "Autenticado ante el Núcleo %s. Presencia cada %ss, lotes de hasta %d.",
            self._sesion.server_version,
            self._sesion.presence_interval_seconds,
            self._sesion.max_batch_size,
        )

    async def _enviar_pendientes(self, ws) -> None:
        """Envía la cola en lotes y descarta solo lo que el Núcleo confirmó."""
        while True:
            lote = self._cola.pendientes(self._sesion.max_batch_size)
            if not lote:
                return

            await ws.send(crear_observation(lote).serializar())
            sobre = deserializar(await ws.recv())

            if sobre.tipo != TipoMensaje.ACK:
                logger.warning("Se esperaba ack, llegó %s. Se reintenta.", sobre.tipo)
                return

            ack = leer_ack(sobre)
            self._cola.confirmar(list(ack.acknowledged))
            self._cola.descartar([i for i, _ in ack.rejected])

            logger.debug(
                "Lote enviado: %d confirmadas, %d rechazadas, %d en cola.",
                len(ack.acknowledged), len(ack.rejected), len(self._cola),
            )

            if len(lote) < self._sesion.max_batch_size:
                return

    async def _marcar_presencia(self, ws) -> None:
        uptime = (datetime.now(timezone.utc) - self._inicio).total_seconds()
        self.observar("presence_mark", {"uptime_seconds": round(uptime, 1)})