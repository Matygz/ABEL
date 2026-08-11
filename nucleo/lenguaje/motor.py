"""Acceso al modelo de lenguaje.

El modelo es un órgano, no la identidad de ABEL: convierte texto en
estructura y estructura en texto. No decide, no recuerda, no razona sobre
el mundo — eso vive en el Núcleo.

Esta interfaz existe para que el modelo sea reemplazable. El resto de ABEL
habla con `MotorLenguaje`, nunca con un modelo concreto: cambiar de modelo
es cambiar la configuración, no el código.

El servidor corre aparte y se levanta bajo demanda: un modelo residente
ocupa VRAM permanentemente, y esa VRAM le hace falta al resto del sistema.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from comun.errores import ErrorOperativo

logger = logging.getLogger(__name__)

TIMEOUT_GENERACION = 60.0
TIMEOUT_ARRANQUE = 90.0


class ErrorLenguaje(ErrorOperativo):
    """El modelo no está disponible o no pudo responder."""


@dataclass(frozen=True)
class Respuesta:
    """Lo que devuelve el modelo, con lo necesario para juzgarla."""

    texto: str
    tokens_entrada: int
    tokens_salida: int
    segundos: float

    @property
    def velocidad(self) -> float:
        return self.tokens_salida / self.segundos if self.segundos else 0.0


class MotorLenguaje:
    """Habla con el servidor del modelo.

    No sabe nada de ABEL: recibe instrucciones y texto, devuelve texto.
    Toda la inteligencia sobre qué pedirle vive en las capas de arriba.
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:8090",
        timeout: float = TIMEOUT_GENERACION,
    ) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout
        self._cliente: httpx.AsyncClient | None = None

    async def _obtener_cliente(self) -> httpx.AsyncClient:
        if self._cliente is None:
            self._cliente = httpx.AsyncClient(timeout=self._timeout)
        return self._cliente

    async def cerrar(self) -> None:
        if self._cliente is not None:
            await self._cliente.aclose()
            self._cliente = None

    async def disponible(self) -> bool:
        """Si el servidor está levantado y con el modelo cargado."""
        try:
            cliente = await self._obtener_cliente()
            r = await cliente.get(f"{self._url}/health", timeout=2.0)
            return r.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    async def esperar_disponible(self, timeout: float = TIMEOUT_ARRANQUE) -> bool:
        """Espera a que el servidor termine de cargar el modelo."""
        limite = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < limite:
            if await self.disponible():
                return True
            await asyncio.sleep(0.5)
        return False

    async def generar(
        self,
        instrucciones: str,
        entrada: str,
        temperatura: float = 0.3,
        max_tokens: int = 512,
        formato_json: bool = False,
    ) -> Respuesta:
        """Pide una respuesta al modelo.

        `temperatura` baja para interpretación —donde se quiere precisión y
        consistencia— y más alta para conversación, donde la variedad es
        deseable.
        """
        cuerpo: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": instrucciones},
                {"role": "user", "content": entrada},
            ],
            "temperature": temperatura,
            "max_tokens": max_tokens,
        }

        if formato_json:
            # Fuerza al modelo a emitir JSON válido restringiendo la
            # generación token a token. Sin esto, un modelo chico devuelve
            # JSON con comentarios, comas de más o texto alrededor.
            cuerpo["response_format"] = {"type": "json_object"}

        cliente = await self._obtener_cliente()
        inicio = asyncio.get_running_loop().time()

        try:
            r = await cliente.post(f"{self._url}/v1/chat/completions", json=cuerpo)
            r.raise_for_status()
            datos = r.json()
        except httpx.TimeoutException:
            raise ErrorLenguaje(
                f"El modelo no respondió en {self._timeout}s."
            ) from None
        except httpx.HTTPError as exc:
            raise ErrorLenguaje(f"Fallo al consultar el modelo: {exc}") from None

        segundos = asyncio.get_running_loop().time() - inicio

        try:
            texto = datos["choices"][0]["message"]["content"]
            uso = datos.get("usage", {})
        except (KeyError, IndexError):
            raise ErrorLenguaje("El modelo devolvió una respuesta inesperada.") from None

        return Respuesta(
            texto=texto.strip(),
            tokens_entrada=uso.get("prompt_tokens", 0),
            tokens_salida=uso.get("completion_tokens", 0),
            segundos=segundos,
        )

    async def generar_json(
        self,
        instrucciones: str,
        entrada: str,
        temperatura: float = 0.1,
    ) -> dict[str, Any]:
        """Pide una respuesta estructurada y la valida.

        Si el modelo no devuelve JSON utilizable, falla de forma explícita.
        Una interpretación mal formada tiene que ser detectable, no una
        respuesta que suena bien y está mal.
        """
        respuesta = await self.generar(
            instrucciones, entrada,
            temperatura=temperatura, formato_json=True,
        )

        texto = respuesta.texto.strip()

        # Algunos modelos envuelven el JSON en un bloque de markdown aunque
        # se les pida JSON puro. Se limpia antes de parsear.
        if texto.startswith("```"):
            lineas = texto.split("\n")
            lineas = lineas[1:]                      # quita ```json
            if lineas and lineas[-1].strip() == "```":
                lineas = lineas[:-1]
            texto = "\n".join(lineas).strip()

        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            logger.warning("El modelo no devolvió JSON: %r", texto[:200])
            raise ErrorLenguaje("El modelo no devolvió JSON válido.") from None
        except json.JSONDecodeError:
            logger.warning("El modelo no devolvió JSON: %r", respuesta.texto[:200])
            raise ErrorLenguaje("El modelo no devolvió JSON válido.") from None

        if not isinstance(datos, dict):
            raise ErrorLenguaje("Se esperaba un objeto JSON.")

        logger.debug(
            "Interpretación en %.2fs (%d tokens de entrada, %d de salida)",
            respuesta.segundos, respuesta.tokens_entrada, respuesta.tokens_salida,
        )
        return datos