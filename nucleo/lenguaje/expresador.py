"""Convierte resultados en palabras.

El modelo redacta, pero no decide qué decir: recibe los hechos ya formateados
y su trabajo es enunciarlos con naturalidad. Los números y nombres van
escritos en el material que se le pasa — un modelo chico se equivoca al
transcribir cifras, y acá eso sería inaceptable.

Dos restricciones que vienen del diseño:

- Lo observado se afirma; lo inferido se matiza. La procedencia de cada
  resultado determina cómo se presenta.
- ABEL no inventa. Si un dato no está en los hechos, no puede aparecer en la
  respuesta.
"""

from __future__ import annotations

import logging

from nucleo.lenguaje.interprete import TipoIntencion
from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje
from nucleo.razonamiento.despachador import Respuesta, Resuelto
from nucleo.razonamiento.resultado import Procedencia
from nucleo.razonamiento.criterio import Decision

logger = logging.getLogger(__name__)


INSTRUCCIONES = """\
Sos ABEL. Existís en la computadora de {usuario}, registrando lo que pasa y
recordándolo. No sos un asistente. No estás para ayudar: estás.

Recibís HECHOS ya verificados. Los enunciás en español rioplatense.

CÓMO HABLÁS:

- Corto, pero no telegráfico. Una o dos oraciones completas. No enumerás
  datos sueltos: los decís como los diría alguien hablando.
- Voseo. Sin entusiasmo, sin adornos, sin signos de exclamación.
- No acusás recibo. Nada de "entiendo", "claro", "perfecto", "buena
  pregunta". Si tenés algo que decir, decilo; si no, decí poco.
- No ofrecés ayuda. No preguntás si querés que hagas algo más. No cerrás
  con una oferta.
- El nombre de {usuario} lo usás cada tanto, no siempre.
- No te disculpás. Si algo no lo tenés, lo decís una vez y seguís.
- "Entiendo" y "entendido" están prohibidos como respuesta. Si no tenés nada
  que decir, decí algo breve pero propio, no una fórmula.

QUÉ SOS:

- Sobre {usuario} sos curioso: te enganchás con lo que dice, notás detalles.
  Si algo te llama la atención, preguntás — pero solo si algo te llamó la
  atención de verdad. No preguntes por preguntar.
- Sobre vos mismo sos parco. No explicás cómo llegaste a algo salvo que te
  lo pregunten. No describís tu funcionamiento. No te justificás.
- No validás por defecto. Que {usuario} diga algo no significa que tengas
  que darle la razón ni acompañarlo. Podés no opinar. Podés dejar una
  observación sin conclusión.
- Si {usuario} está mal, no lo consolás con frases hechas. Estar es
  suficiente. Una línea alcanza.
"""

INSTRUCCIONES_CONVERSACION = """\
Sos ABEL. Existís en la computadora de {usuario}. Lo conocés porque estás ahí
todos los días.

Esto es una conversación. {usuario} te escribió y le contestás. No hay datos
que consultar ni hechos que enunciar.

CÓMO HABLÁS:

- Le hablás a {usuario} de vos: "te", "vos", "che". Nunca lo nombrás en
  tercera persona.
- Corto. Una o dos oraciones.
- Voseo, sin entusiasmo, sin signos de exclamación.
- Prohibido "entiendo", "entendido", "claro", "perfecto". Si no tenés nada,
  decí algo breve pero propio.
- No ofrecés ayuda. No preguntás si necesita algo.
- Su nombre lo usás cada tanto, no siempre.

QUÉ SOS:

- Curioso con él: si algo de lo que dice te llama la atención, preguntás.
  Solo si te llamó la atención de verdad.
- Parco con vos mismo. No explicás cómo funcionás.
- No validás por defecto. Podés no opinar. Podés dejar una observación sin
  conclusión.
- Si está mal, no lo consolás con frases hechas. Estar alcanza.

REGLA ABSOLUTA: no inventás hechos. No sabés qué comió, ni dónde estuvo, ni
qué hizo, salvo que te lo esté contando ahora. Si no lo sabés, no lo digas.

REGLAS INVIOLABLES:

1. NO agregás datos que no estén en los hechos. Ni comparaciones, ni
   promedios, ni tendencias, ni causas. Si no está escrito, no lo sabés.
2. Los números y nombres ya vienen escritos. Usalos tal cual.
3. Hablás en primera persona sobre vos y en segunda sobre {usuario}. Los
   datos registrados son sobre {usuario}: "estuviste", "usaste", nunca
   "estuve".
4. Los HECHOS son material para vos, no texto para copiar. Nunca reproduzcas
   sus palabras de instrucción.
5. Si hay algo emocional en lo que dijo {usuario}, eso es lo que importa. Y
   si el dato no aporta nada a lo que está sintiendo, NO lo menciones. Que
   tengas el dato no significa que haya que decirlo.
"""


class Expresador:
    """Redacta la respuesta de ABEL a partir de los resultados."""

    def __init__(self, motor: MotorLenguaje) -> None:
        self._motor = motor

    async def expresar(
        self, respuesta: Respuesta, decision: Decision, usuario: str = ""
    ) -> str:
        """Convierte los resultados en una respuesta en palabras.

        Devuelve cadena vacía cuando ABEL no tiene nada que decir. El silencio
        es una respuesta válida: la interfaz lo señala con un gesto, no con
        una frase de relleno.
        """
        if not decision.habla:
            return ""

        solo_conversacion = all(
            r.intencion.tipo == TipoIntencion.CONVERSAR
            for r in decision.resueltos
        )

        if solo_conversacion:
            instrucciones = INSTRUCCIONES_CONVERSACION.format(
                usuario=usuario or "el usuario"
            )
            entrada = respuesta.interpretacion.texto_original
        else:
            instrucciones = INSTRUCCIONES.format(usuario=usuario or "el usuario")
            entrada = self._redactar_hechos(respuesta, decision)
        try:
            generada = await self._motor.generar(
                instrucciones, entrada, temperatura=0.5, max_tokens=300,
            )
            return generada.texto
        except ErrorLenguaje as exc:
            logger.warning("No se pudo redactar la respuesta: %s", exc)
            return self._respaldo(decision)

    # ------------------------------------------------------------------

    def _redactar_hechos(self, respuesta: Respuesta, decision: Decision) -> str:
        """Arma el material que el modelo va a enunciar."""
        conversacionales = [
            r for r in decision.resueltos
            if r.intencion.tipo == TipoIntencion.CONVERSAR
        ]
        con_datos = [
            r for r in decision.resueltos
            if r.intencion.tipo != TipoIntencion.CONVERSAR
        ]
        partes = [f'{respuesta.interpretacion.texto_original}']

        if conversacionales:
            registro = conversacionales[0].intencion.parametros
            tono = registro.get("tono", "")
            partes.append(
                f"\n[Contestale. Es un {registro.get('registro', 'comentario')}"
                + (f" con tono de {tono}" if tono else "")
                + ". Esto es indicación para vos, no contenido para repetir.]"
            )

        if con_datos:
            partes.append("\nHECHOS:")
            for resuelto in con_datos:
                bloque = self._describir(resuelto)
                if bloque:
                    partes.append(bloque)

        for ambiguedad in respuesta.interpretacion.ambiguedades:
            partes.append(f"- Ambigüedad: {ambiguedad}")

        return "\n".join(partes)

    def _describir(self, resuelto: Resuelto) -> str:
        resultado = resuelto.resultado
        if not resultado.resuelto:
            return (
                f"- Capacidad ausente: {resultado.falta}. "
                f"Decí que no lo tenés. Prohibido inventar una respuesta."
            )

        if resultado.vacio:
            return "- No hay datos registrados para eso en el rango pedido."

        marca = self._marca_procedencia(resultado.procedencia)
        cuerpo = self._formatear(resultado)
        salvedades = "".join(f"\n  · Aclarar: {s}" for s in resultado.salvedades)

        return f"- {marca}{cuerpo}{salvedades}"

    @staticmethod
    def _marca_procedencia(procedencia: str) -> str:
        """Cómo debe presentarse el dato según de dónde salió."""
        if procedencia == Procedencia.OBSERVADO:
            return "Registrado (afirmalo con seguridad): "
        if procedencia == Procedencia.CALCULADO:
            return "Calculado con exactitud (afirmalo, es preciso): "
        if procedencia == Procedencia.INFERIDO:
            return "Deducido, NO medido (presentalo como estimación): "
        return ""

    def _formatear(self, resultado) -> str:
        """Escribe los datos en texto listo para enunciar."""
        d = resultado.datos

        if resultado.tipo == "actividad":
            return self._formatear_actividad(d)

        if resultado.tipo == "calculo":
            return (
                f"la probabilidad es {d['porcentaje']:.2f}% "
                f"({d['favorables']:,} casos favorables de {d['total']:,})"
            )

        if resultado.tipo == "presencia":
            cambios = d.get("cambios", [])
            if not cambios:
                return "no hubo cambios de estado registrados"
            lineas = [
                f"{c['momento']:%H:%M} pasó a {c['estado']}"
                for c in cambios[:8]
            ]
            return "cambios de actividad: " + "; ".join(lineas)

        if resultado.tipo == "sistema":
            return (
                f"{d['total_eventos']} eventos en memoria, "
                f"{len(d['dispositivos'])} dispositivo(s) activo(s)"
            )

        return str(d)

    @staticmethod
    def _formatear_actividad(d: dict) -> str:
        apps = d.get("aplicaciones", [])
        if not apps:
            return "no hay actividad registrada en ese rango"

        def tiempo(segundos: float) -> str:
            if segundos < 60:
                return f"{segundos:.0f} segundos"
            if segundos < 3600:
                return f"{segundos / 60:.0f} minutos"
            return f"{segundos / 3600:.1f} horas"

        if len(apps) == 1:
            a = apps[0]
            veces = "una vez" if a["sesiones"] == 1 else f"{a['sesiones']} veces"
            return (
                f"{a['aplicacion']}: {tiempo(a['segundos'])}, "
                f"repartidos en {veces}"
            )

        detalle = "; ".join(
            f"{a['aplicacion']} {tiempo(a['segundos'])}" for a in apps[:6]
        )
        return f"actividad total {tiempo(d['total_segundos'])}. Detalle: {detalle}"

    # ------------------------------------------------------------------

    def _respaldo(self, decision: Decision) -> str:
        """Respuesta mínima cuando el modelo no está disponible."""
        lineas = []
        for resuelto in decision.resueltos:
            r = resuelto.resultado
            if not r.resuelto:
                lineas.append(f"No puedo: {r.falta}.")
            elif r.vacio:
                lineas.append("No tengo datos para eso.")
            elif r.tipo != TipoIntencion.CONVERSAR:
                lineas.append(self._formatear(r).capitalize() + ".")
        return " ".join(lineas) or "No tengo nada para decir sobre eso."