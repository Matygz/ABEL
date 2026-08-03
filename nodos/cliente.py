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
from comun.planificador import Planificador, Tarea
from nodos.sensores import RegistroSensores, crear_emisor
from nodos.sensores_sistema import construir_sensores


from protocolos.firma import a_texto, desde_texto, firmar, material_a_firmar
from protocolos.mensajes import ErrorProtocolo, TipoMensaje, deserializar

logger = logging.getLogger(__name__)

VERSION_CLIENTE = "0.0.1"
ESPERA_RECONEXION = 5.0


class ClienteNodo:
    """Mantiene la conexión de un Nodo con el Núcleo."""

    def __init__(self, config: ConfigNodo) -> None:
        self._config = config
        self._cola = ColaObservaciones(
            ruta=config.cola_db, durabilidad=config.durabilidad
        )
        self._inicio = datetime.now(timezone.utc)
        self._sesion: Welcome | None = None
        self._contexto_tls = self._construir_contexto_tls(config.certificado_nucleo)
        self._registro = RegistroSensores()
        for sensor in construir_sensores():
            self._registro.registrar(sensor)
        self._emitir = crear_emisor(self._cola)
        self._planificador = Planificador()

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
        """Saluda y mantiene la sesión: envía pendientes y marca presencia.

        El envío corre más seguido que la presencia: los sensores encolan a su
        propio ritmo y no tiene sentido que un dato espere un ciclo completo
        de presencia para salir.
        """
        await self._saludar(ws)

        segundos_desde_presencia = 0.0
        intervalo_envio = 2.0

        while True:
            await self._enviar_pendientes(ws)

            if segundos_desde_presencia >= self._sesion.presence_interval_seconds:
                await self._marcar_presencia(ws)
                segundos_desde_presencia = 0.0

            await self._dormir(intervalo_envio)
            segundos_desde_presencia += intervalo_envio
            
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
                capabilities=self._registro.capacidades(),
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
        self._emitir(
            "presence_mark",
            {
                "uptime_seconds": round(uptime, 1),
                "sensors": self._registro.estado(),
                "queued": len(self._cola),
            },
        )

    async def iniciar_sensores(self) -> None:
        """Inicia los sensores configurados y los registra en el planificador.

        Se llama una vez, antes de conectar: los sensores captan aunque no
        haya enlace, que es el punto de tener cola.
        """
        await self._registro.iniciar_todos(list(self._config.sensores))

        for sensor in self._registro.habilitados():
            self._planificador.registrar(
                Tarea(
                    nombre=f"sensor:{sensor.nombre}",
                    funcion=self._envolver(sensor),
                    intervalo_segundos=sensor.intervalo_segundos,
                )
            )

        habilitados = len(self._registro.habilitados())
        total = len(self._registro.todos())
        logger.info("Sensores activos: %d de %d.", habilitados, total)

    def _envolver(self, sensor):
        """Adapta la firma del sensor a la que espera el planificador."""

        async def ejecutar() -> None:
            await sensor.capturar(self._emitir)

        return ejecutar

    async def ejecutar_sensores(self) -> None:
        """Corre el planificador de sensores. Independiente de la conexión."""
        await self._planificador.iniciar()