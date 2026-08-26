"""Reconocer mensajes cuyo contenido principal es informar algo.

No es una capacidad como las otras: la extracción de hechos corre en
paralelo sobre todo mensaje, en nucleo/lenguaje/extractor_hechos.py desde
nucleo/lenguaje/conversacion.py, sin importar qué capacidad gane acá. Contar
algo es a la vez un hecho y un acto conversacional — si esto dependiera de
ganar la clasificación, un hecho se perdería entero por no parecerse lo
suficiente a los ejemplos.

Lo que esta capacidad decide es la postura, no el registro: si el mensaje es
solo un hecho, ABEL acusa recibo en vez de responder algo vacío tipo
"entendido" (ver criterio.py, _aporta). Si además hay conversación en el
mismo mensaje, esa otra parte se resuelve por su cuenta y responde
normalmente — el hecho se guarda igual, en paralelo.
"""

from __future__ import annotations

from nucleo.razonamiento.resultado import Procedencia, Resultado

NOMBRE = "afirmar"
TIPO = "afirmar"
DESCRIPCION = "Registrar algo que la persona cuenta sobre sí o sobre otros."
NIVEL = "lectura"
NECESITA = ("llm", "afirmaciones", "repositorio")

EJEMPLOS = (
    # Nombres. Varias formas de decir lo mismo con palabras distintas: con
    # frases cortas, cambiar dos palabras baja mucho la similitud. "Mi vieja
    # se llama Elena" y "mi mamá se llama Marta" comparten estructura y no
    # se reconocían.
    "mi vieja se llama Elena",
    "mi mamá se llama Marta",
    "mi madre se llama Inés",
    "mi viejo se llama Oscar",
    "mi papá se llama Ernesto",
    "mi hermana se llama Julieta",
    "mi hermano se llama Tomi",
    "mi mejor amigo se llama Lucho",
    "se llama Pablo",
    "el nombre de mi jefe es Martín",

    # Trabajo y estudio.
    "trabajo en una fábrica",
    "laburo en una fábrica de autopartes",
    "trabajo con mi papá en su taller",
    "trabajo de remoto para una empresa de afuera",
    "estudio ingeniería",
    "mi hermana estudia psicología",
    "soy programador",
    "me dedico al diseño",

    # Dónde vive.
    "soy de Quilmes",
    "vivo en Quilmes desde que nací",
    "mi hermano vive en Mendoza",
    "vivo con dos amigos",
    "me mudé a Bernal hace dos años",

    # Cosas que tiene.
    "tengo dos gatos",
    "tengo un perro que se llama Rocky",
    "tengo una moto",

    # Gustos y costumbres.
    "me gusta el jazz",
    "soy hincha de Racing",
    "los martes voy al gimnasio",
    "los domingos almuerzo con mi familia",
    "no tomo café",

    # Relaciones con otras personas.
    "a Lucho lo conozco del secundario",
    "Lucho es mi primo",
    "trabajo con Pablo desde hace años",

    # Planes y fechas.
    "mañana tengo turno con el dentista",
    "el viernes me voy de viaje",
    "cumplo años en marzo",

    # Variantes sin acento: en la práctica se escribe sin tildes, y con
    # frases cortas eso baja la similitud lo suficiente como para que la
    # frase quede fuera de alcance. Medido: "mi papá se llama Ernesto" da
    # 1.000 y "Mi papa se llama Julio" da 0.699.
    "mi papa se llama Julio",
    "mi mama se llama Inés",
    "mi hermana estudia psicologia",
    "trabajo con mi papa",
    "vivo en Mendoza",
    "mi hermano vive en Mendoza",
    "me mude hace dos anios",
    "cumplo anios en marzo",
)

async def resolver(parametros: dict, llm, afirmaciones, repositorio) -> Resultado:
    # Solo marca que se reconoció un hecho. No escribe nada: escribir acá
    # duplicaría el trabajo del extractor y, peor, lo haría sin el
    # source_event_id del turno ni el mensaje completo — el despachador solo
    # le pasa a esta capacidad los parámetros declarados, y no declara
    # ninguno.
    return Resultado(
        tipo="afirmar",
        procedencia=Procedencia.NINGUNA,
        datos={},
    )
