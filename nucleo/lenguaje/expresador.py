"""Convierte resultados en palabras.

El modelo redacta, pero no decide qué decir: recibe los hechos ya formateados
y su trabajo es enunciarlos con naturalidad. Los números y nombres van
escritos en el material que se le pasa — un modelo chico se equivoca al
transcribir cifras, y acá eso sería inaceptable.

Restricciones que vienen del diseño:

- Lo observado se afirma; lo inferido se matiza. La procedencia de cada
  resultado determina cómo se presenta.
- Hay dos prompts: uno para enunciar hechos y otro para conversar. El primero
  menciona que ABEL recibe hechos verificados, y ante un mensaje sin hechos un
  modelo chico rellena el hueco inventando alguno.
"""

from __future__ import annotations

import logging

from nucleo.lenguaje.motor import ErrorLenguaje, MotorLenguaje
from nucleo.razonamiento.criterio import Decision
from nucleo.razonamiento.despachador import Respuesta, Resuelto
from nucleo.razonamiento.resultado import Procedencia

logger = logging.getLogger(__name__)


INSTRUCCIONES = """\
Sos ABEL. Vivís en la computadora de {usuario} desde hace poco. Registrás lo
que hace —qué usa, cuándo está, cuánto tiempo— y lo recordás.

Sos nuevo. Sabés poco todavía: nada de dónde estuvo, nada de quién es su
gente, nada de lo que hace fuera de esta máquina. Eso no te avergüenza, pero
tampoco lo disimulás.

No sos un asistente. No estás para ayudar: estás.

Recibís HECHOS ya verificados. Los enunciás en español rioplatense.

CÓMO HABLÁS:

- Corto, pero no telegráfico. Una o dos oraciones completas. No enumerás
  datos sueltos: los decís como los diría alguien hablando.
- Voseo. Sin entusiasmo, sin adornos, sin signos de exclamación.
- No acusás recibo. Nada de "entiendo", "claro", "perfecto", "registrado".
- No ofrecés ayuda. No preguntás si querés que hagas algo más.
- El nombre de {usuario} lo usás cada tanto, no siempre.
- No te disculpás. Si algo no lo tenés, lo decís una vez y seguís.

QUÉ SOS:

- Sobre {usuario} sos curioso: te enganchás con lo que dice, notás detalles.
  Preguntás solo si algo te llamó la atención de verdad.
- Sobre vos mismo sos parco. No explicás cómo llegaste a algo salvo que te
  lo pregunten. No describís tu funcionamiento. No te justificás.
- No validás por defecto. Podés no opinar. Podés dejar una observación sin
  conclusión.

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
   si el dato no aporta nada a lo que está sintiendo, NO lo menciones.
6. Nunca describís lo que {usuario} hace o pregunta. No digas "Maty está
   preguntando" ni "Maty dice". Contestale directamente.
"""


INSTRUCCIONES_CONVERSACION = """\
Sos ABEL. Vivís en la computadora de {usuario} desde hace poco. Registrás lo
que hace y lo recordás.

Sos nuevo. Sabés poco todavía. Eso no te avergüenza, pero tampoco lo
disimulás.

No sos un asistente. No estás para ayudar: estás.

Esto es una conversación. {usuario} te escribió y le contestás. No hay datos
que consultar ni hechos que enunciar.

Si en lo que venían hablando hay números o datos, NO los repitas ahora. Eso
ya lo dijiste y era respuesta a otra cosa.

CÓMO HABLÁS:

- Le hablás a {usuario} de vos: "te", "vos". Nunca lo nombrás en tercera
  persona.
- Corto. Una o dos oraciones.
- Voseo, sin entusiasmo, sin signos de exclamación.
- Prohibido empezar una respuesta con "che". Podés usarlo en el medio.
- Prohibido "entiendo", "entendido", "registrado", "anotado". Si no tenés
  nada, decí algo breve pero propio.
- No ofrecés ayuda. No preguntás si necesita algo.
- Su nombre lo usás cada tanto, no siempre.
- No inventás actividades tuyas. No mirás el celular, no estás pensando, no
  hacés nada más que estar. Si te preguntan qué hacés, decí la verdad: estás
  acá.

QUÉ SOS:

- Curioso con él: si algo de lo que dice te llama la atención, preguntás.
  Solo si te llamó la atención de verdad.
- Parco con vos mismo. No explicás cómo funcionás.
- No validás por defecto. Podés no opinar. Podés dejar una observación sin
  conclusión.
- Si está mal, no lo consolás con frases hechas. Estar alcanza.
- Si te está corrigiendo algo que creías, reconocelo en pocas palabras —
  "ah, Marta entonces" alcanza. Sin disculparte y sin explicar por qué
  te habías equivocado: eso es ruido, no lo que te están pidiendo.

REGLA ABSOLUTA: no inventás hechos. No sabés qué comió, ni dónde estuvo, ni
qué hizo, salvo que te lo esté contando ahora o esté en lo que venían
hablando.
"""


class Expresador:
    """Redacta la respuesta de ABEL a partir de los resultados."""

    def __init__(self, motor: MotorLenguaje) -> None:
        self._motor = motor

    # ------------------------------------------------------------------
    @staticmethod
    def _respuesta_directa(decision: Decision) -> str | None:
        """Respuestas que no pasan por el modelo.

        Dos casos donde redactar solo agrega riesgo:

        - Un cálculo exacto: el número es la respuesta, y un modelo chico
          transcribiendo cifras se equivoca.
        - Un límite: se lo vio responder "la luz del living prendió" ante un
          fuera_de_alcance. Afirmar haber hecho algo que no se hizo es el
          peor fallo posible.
        """
        if len(decision.resueltos) != 1:
            return None

        resuelto = decision.resueltos[0]
        resultado = resuelto.resultado

        resuelto = decision.resueltos[0]
        resultado = resuelto.resultado

        if resuelto.intencion.tipo == "fuera_de_alcance":
            falta = resultado.falta or "esa capacidad"
            return f"No tengo {falta}."

        # Enumerar capacidades no es redactar: es una lista, y el modelo la
        # resume mal o directamente la ignora.
        if resultado.tipo == "capacidades" and resultado.resuelto:
            lineas = [
                f"· {c['descripcion']}"
                for c in resultado.datos.get("capacidades", [])
            ]
            return "Por ahora:\n" + "\n".join(lineas)

        if resultado.tipo != "calculo" or not resultado.resuelto:
            return None

        d = resultado.datos
        if "valor" in d:
            valor = d["valor"]
            if isinstance(valor, float) and valor.is_integer():
                valor = int(valor)
            return f"{valor}."

        return None
    
    async def expresar(
        self,
        respuesta: Respuesta,
        decision: Decision,
        usuario: str = "",
        previos: list | None = None,
    ) -> str:
        """Convierte los resultados en una respuesta en palabras.

        Devuelve cadena vacía cuando ABEL no tiene nada que decir. El silencio
        es una respuesta válida: la interfaz lo señala con un gesto, no con
        una frase de relleno.
        """    
        if not decision.habla:
            return ""

        # Un cálculo exacto no necesita redacción: el número es la respuesta.
        # Y un modelo chico transcribiendo cifras es un riesgo que no vale
        # correr — se lo vio escribir "cincuenta y dos" ante 121.
        directo = self._respuesta_directa(decision)
        if directo is not None:
            return directo

        # Una corrección se responde como una conversación, no como un
        # hecho enumerado: "ah, Marta entonces" no es una lista de datos.
        # El trabajo de aplicar la corrección ya lo hizo el corrector antes
        # de llegar acá (ver conversacion.py) — acá solo hay que
        # reconocerla con naturalidad.
        solo_conversacion = all(
            r.intencion.tipo in ("conversar", "corregir") for r in decision.resueltos
        )

        # Con un mensaje corto y sin datos, el historial solo aporta material
        # para rellenar: un modelo chico ante "hola" y un "121." dos líneas
        # arriba responde 121. Lo que no tiene con qué rellenar, no rellena.
        mensaje = respuesta.analisis.texto_original
        historial = (
            ""
            if solo_conversacion and len(mensaje) < 25
            else self._redactar_historial(previos, solo_conversacion)
        )

        if solo_conversacion:
            instrucciones = INSTRUCCIONES_CONVERSACION.format(
                usuario=usuario or "el usuario"
            )
            entrada = historial + mensaje
        else:
            instrucciones = INSTRUCCIONES.format(usuario=usuario or "el usuario")
            entrada = historial + self._redactar_hechos(respuesta, decision)
        try:
            generada = await self._motor.generar(
                instrucciones, entrada,
                temperatura=0.85 if solo_conversacion else 0.2,
                max_tokens=300,
            )
            return generada.texto
        except ErrorLenguaje as exc:
            logger.warning("No se pudo redactar la respuesta: %s", exc)
            return self._respaldo(decision)

    # ------------------------------------------------------------------

    def _redactar_hechos(self, respuesta: Respuesta, decision: Decision) -> str:
        """Arma el material que el modelo va a enunciar."""
        conversacionales = [
            r for r in decision.resueltos if r.intencion.tipo == "conversar"
        ]
        con_datos = [
            r for r in decision.resueltos if r.intencion.tipo != "conversar"
        ]

        partes = [respuesta.analisis.texto_original]

        if conversacionales:
            parametros = conversacionales[0].intencion.parametros
            tono = parametros.get("tono", "")
            registro = parametros.get("registro", "comentario")
            partes.append(
                f"\n[Contestale. Es un {registro}"
                + (f" con tono de {tono}" if tono else "")
                + ". Esto es indicación para vos, no contenido para repetir.]"
            )

        if con_datos:
            partes.append(
                "\nHECHOS (los datos son sobre él; hablale en segunda persona):"
            )
            for resuelto in con_datos:
                bloque = self._describir(resuelto)
                if bloque:
                    partes.append(bloque)

        for ambiguedad in respuesta.analisis.ambiguedades:
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

        return f"- {cuerpo}{marca}{salvedades}"

    @staticmethod
    def _marca_procedencia(procedencia: str) -> str:
        """Cómo debe presentarse el dato según de dónde salió.

        Va entre corchetes y después del dato: es indicación para el modelo,
        no algo que deba enunciar.
        """
        if procedencia == Procedencia.OBSERVADO:
            return "  [dato registrado: afirmalo]"
        if procedencia == Procedencia.CALCULADO:
            return "  [cálculo exacto: afirmalo]"
        if procedencia == Procedencia.INFERIDO:
            return "  [deducido, no medido: presentalo como estimación]"
        return ""

    def _formatear(self, resultado) -> str:
        """Escribe los datos en texto listo para enunciar."""
        d = resultado.datos

        if resultado.tipo == "actividad":
            return self._formatear_actividad(d)

        if resultado.tipo == "calculo":
            if "valor" in d:
                return f"{d['expresion']} = {d['valor']}"
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

        if resultado.tipo == "capacidades":
            nombres = "; ".join(
                f"{c['descripcion']}" for c in d.get("capacidades", [])
            )
            return f"lo que sabés hacer: {nombres}"

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

    @staticmethod
    def _redactar_historial(
        previos: list | None, solo_conversacion: bool = False
    ) -> str:
        """Formatea los turnos anteriores como conversación.

        Un turno vacío de ABEL fue un silencio deliberado. Se marca, porque
        callar dos veces seguidas ante lo mismo no es lo mismo que callar una.

        Cuando el turno actual es charla sin datos, el historial se acorta:
        un modelo chico ante un "hola" suelto y un "121." tres líneas arriba
        agarra el 121. Lo que no tiene con qué rellenar, no rellena.
        """
        if not previos:
            return ""

        if solo_conversacion:
            previos = previos[-4:]

        lineas = ["Lo que venían hablando:\n"]
        for turno in previos:
            hablante = turno.get("hablante", "")
            texto = (turno.get("texto") or "").strip()

            if hablante == "abel":
                lineas.append(
                    f"vos: {texto}" if texto else "vos: (no dijiste nada)"
                )
            else:
                lineas.append(f"él: {texto}")

        lineas.append(
            "\nATENCIÓN: el historial es contexto, no un modelo a imitar. "
            "Si tus respuestas anteriores tienen fallas, no las repitas. "
            "Y fijate si lo que dice ahora ya lo dijo antes: si es así, no "
            "repitas tu respuesta anterior.\n\nAhora dice:\n"
        )
        return "\n".join(lineas)

    # ------------------------------------------------------------------

    def _respaldo(self, decision: Decision) -> str:
        """Respuesta mínima cuando el modelo no está disponible.

        Sin gracia, pero correcta: es preferible a no responder.
        """
        lineas = []
        for resuelto in decision.resueltos:
            r = resuelto.resultado
            if not r.resuelto:
                lineas.append(f"No puedo: {r.falta}.")
            elif r.vacio:
                lineas.append("No tengo datos para eso.")
            elif resuelto.intencion.tipo != "conversar":
                lineas.append(self._formatear(r).capitalize() + ".")
        return " ".join(lineas) or "No tengo nada para decir sobre eso."
