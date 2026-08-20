"""Rutas de la API de la interfaz.

Devuelven JSON. El formateo para mostrar es del navegador: acá se responde
con datos, igual que hace nucleo/memoria (ver 0027).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import wraps

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from comun.eventos import BusEventos
from nucleo.datos.repositorio import Repositorio
from nucleo.lenguaje import conversacion
from nucleo.memoria.consultas import Memoria, hoy, ultimas_horas, ultimos_dias
from nucleo.web.sesiones import ErrorSesion, ServicioSesiones

import json
from uuid import UUID
from decimal import Decimal

logger = logging.getLogger(__name__)

COOKIE_SESION = "abel_sesion"


class _CodificadorABEL(json.JSONEncoder):
    """Serializa los tipos que usa el dominio y JSON no conoce."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class _JSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content, cls=_CodificadorABEL, ensure_ascii=False,
        ).encode("utf-8")


def _json(datos, status: int = 200) -> _JSONResponse:
    return _JSONResponse(datos, status_code=status)

def construir_rutas(
    repo: Repositorio,
    memoria: Memoria,
    sesiones: ServicioSesiones,
    bus: BusEventos,
    version: str,
    conversacion=None,
    sangre=None,
) -> list:
    """Arma las rutas con sus dependencias ya resueltas.

    Sin inyección automática: cada ruta recibe lo que necesita por clausura,
    de forma explícita y visible.
    """
    
    async def _sesion_de(request: Request) -> dict | None:
        token = request.cookies.get(COOKIE_SESION)
        if not token:
            return None
        return await repo.validar_sesion(token)

    _abel_id = None

    async def _actor_abel():
        """El actor del sistema, para atribuirle los turnos de ABEL."""
        nonlocal _abel_id
        if _abel_id is None:
            async with repo._conexion() as conn:
                cur = await conn.execute(
                    "SELECT id FROM actors "
                    "WHERE actor_type = 'system' AND name = 'core'"
                )
                fila = await cur.fetchone()
                _abel_id = fila["id"] if fila else None
        return _abel_id
    
    def requiere_sesion(funcion):
        @wraps(funcion)
        async def envoltorio(request: Request):
            sesion = await _sesion_de(request)
            if sesion is None:
                return _json({"error": "sin_sesion"}, status=401)
            return await funcion(request, sesion)
        return envoltorio

    @requiere_sesion
    async def sangre_actual(request: Request, sesion):
        if sangre is None:
            return _json({"error": "sin_sangre"}, status=503)
        return _json(sangre.instantanea())

    def requiere_admin(funcion):
        @wraps(funcion)
        async def envoltorio(request: Request):
            sesion = await _sesion_de(request)
            if sesion is None:
                return _json({"error": "sin_sesion"}, status=401)
            if sesion["role"] != "admin":
                return _json({"error": "sin_permiso"}, status=403)
            if sesion["trust_level"] != "admin":
                return _json(
                    {"error": "dispositivo_insuficiente"}, status=403
                )
            return await funcion(request, sesion)
        return envoltorio

    # ------------------------------------------------------------------
    # Sesión
    # ------------------------------------------------------------------

    async def estado_sesion(request: Request):
        sesion = await _sesion_de(request)
        if sesion is None:
            return _json({"autenticado": False})

        return _json({
            "autenticado": True,
            "usuario": sesion["display_name"],
            "nombre_completo": sesion["full_name"],
            "rol": sesion["role"],
            "dispositivo": sesion["device_name"],
            "confianza": sesion["trust_level"],
            "version": version,
        })

    async def abrir_sesion(request: Request):
        direccion = request.client.host if request.client else ""

        usuarios = await repo.listar_usuarios()
        if not usuarios:
            return _json({"error": "sin_usuarios"}, status=500)

        try:
            token = await sesiones.abrir_desde(direccion, usuarios[0]["id"])
        except ErrorSesion as exc:
            return _json({"error": str(exc)}, status=403)

        respuesta = _json({"ok": True})
        respuesta.set_cookie(
            COOKIE_SESION, token,
            httponly=True, samesite="strict", max_age=30 * 24 * 3600,
        )
        return respuesta

    async def cerrar_sesion(request: Request):
        token = request.cookies.get(COOKIE_SESION)
        if token:
            await repo.cerrar_sesion(token)
        respuesta = _json({"ok": True})
        respuesta.delete_cookie(COOKIE_SESION)
        return respuesta

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _rango(request: Request):
        params = request.query_params
        if "horas" in params:
            return ultimas_horas(float(params["horas"]))
        if "dias" in params:
            return ultimos_dias(int(params["dias"]))
        return hoy()

    @requiere_sesion
    async def actividad(request: Request, sesion):
        desde, hasta = _rango(request)
        return _json(await memoria.actividad_por_aplicacion(desde, hasta))

    @requiere_sesion
    async def sesiones_ventana(request: Request, sesion):
        desde, hasta = _rango(request)
        limite = int(request.query_params.get("limite", 50))
        return _json(await memoria.sesiones_de_ventana(desde, hasta, limite))

    @requiere_sesion
    async def presencia(request: Request, sesion):
        desde, hasta = _rango(request)
        return _json(await memoria.periodos_de_actividad(desde, hasta))

    @requiere_admin
    async def estado_sistema(request: Request, sesion):
        return _json(await memoria.estado_del_sistema())

    @requiere_sesion
    async def historial(request: Request, sesion):
        """Turnos de la conversación en curso, del más viejo al más nuevo.

        Acotado a la sesión: al recargar la página se recupera lo que venían
        hablando, pero abrir una sesión nueva empieza de cero.
        """
        limite = min(int(request.query_params.get("limite", 30)), 100)

        turnos = await repo.consultar(
            """
            SELECT occurred_at,
                   payload->>'speaker' AS hablante,
                   payload->>'text' AS texto,
                   payload->>'postura' AS postura
              FROM events
             WHERE event_type = 'utterance'
               AND payload->>'session_id' = %s
             ORDER BY occurred_at DESC
             LIMIT %s
            """,
            (str(sesion["id"]), limite),
        )

        return _json([
            {
                "momento": t["occurred_at"],
                "hablante": t["hablante"],
                "texto": t["texto"],
                "callo": t["hablante"] == "abel" and not (t["texto"] or "").strip(),
            }
            for t in reversed(turnos)
        ])
    # ------------------------------------------------------------------
    # Canal en vivo
    # ------------------------------------------------------------------

    async def canal(websocket: WebSocket):
        token = websocket.cookies.get(COOKIE_SESION)
        sesion = await repo.validar_sesion(token) if token else None

        if sesion is None:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        logger.debug("Interfaz suscrita al canal de eventos.")

        try:
            async with bus.suscribirse() as cola:
                while True:
                    aviso = await cola.get()
                    await websocket.send_json({
                        "tipo": aviso.tipo_evento,
                        "momento": aviso.occurred_at.isoformat(),
                        "resumen": aviso.resumen,
                    })
        except WebSocketDisconnect:
            logger.debug("Interfaz desconectada del canal.")
    @requiere_sesion
    async def conversar(request: Request, sesion):
            if conversacion is None:
                return _json({"error": "lenguaje_no_disponible"}, status=503)
    
            try:
                cuerpo = await request.json()
            except Exception:
                return _json({"error": "cuerpo_invalido"}, status=400)
    
            mensaje = str(cuerpo.get("mensaje", "")).strip()
            if not mensaje:
                return _json({"error": "mensaje_vacio"}, status=400)
            if len(mensaje) > 4000:
                return _json({"error": "mensaje_muy_largo"}, status=400)

            turno = await conversacion.responder(
            mensaje,
            usuario=sesion["display_name"],
            user_id=sesion["user_id"],
            abel_id=await _actor_abel(),
            session_id=sesion["id"],
        )
    
            return _json({
                "texto": turno.texto,
                "postura": turno.postura,
                "habla": turno.habla,
            })

    return [
        Route("/api/sesion", estado_sesion),
        Route("/api/sesion/abrir", abrir_sesion, methods=["POST"]),
        Route("/api/sesion/cerrar", cerrar_sesion, methods=["POST"]),
        Route("/api/actividad", actividad),
        Route("/api/sesiones-ventana", sesiones_ventana),
        Route("/api/presencia", presencia),
        Route("/api/estado", estado_sistema),
        Route("/api/conversar", conversar, methods=["POST"]),
        Route("/api/historial", historial),
        Route("/api/sangre", sangre_actual),
        WebSocketRoute("/api/canal", canal),
    ]
    
    