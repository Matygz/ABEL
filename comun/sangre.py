"""La sangre: el medio compartido de ABEL.

Los sistemas de un cuerpo no se llaman entre sí. El páncreas no invoca un
método del hígado: modifica la sangre, y el hígado lee lo que hay. Ninguno
sabe que el otro existe.

Acá pasa lo mismo. Cada proceso empuja los valores que le corresponden y lee
los que le importan. Nadie le habla a nadie.

La diferencia con un bus de eventos no es técnica sino de dirección: en un bus
alguien publica pensando en que otro escuche. Acá un valor está donde está, y
quien lo lea reacciona — sin importar quién lo puso ni si alguien lo puso.

Eso permite agregar procesos sin tocar nada: leen la sangre, y listo.

REGLAS

- Solo estado, nunca mensajes. Si aparece algo como "el sensor avisó que X",
  es un mensaje disfrazado y no va acá.
- Cada valor tiene un dueño. Uno lo empuja; cualquiera lo lee. Si dos empujan
  el mismo, se pisan y no hay forma de saber por qué cambió.
- Todo entre 0 y 1, para que se puedan comparar entre sí. Esa comparación es
  justamente lo que después decide qué hacer.
- Decae con el tiempo real, no por ciclo. Es la lección de V.0.2: con
  decaimiento por iteración, descansar no descansa.
- Un valor que nadie lee no es estado: es un número. No se agregan valores
  hasta que exista quien los use.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Cada cuánto se guarda una muestra para poder calcular tendencia.
INTERVALO_MUESTRA = 30.0

# Cuántas muestras se conservan. Cinco a 30 segundos son dos minutos y medio
# de historia: suficiente para saber si algo sube o baja, poco para pesar.
MUESTRAS = 5


@dataclass
class Valor:
    """Un valor de la sangre: su nivel, su reposo, y cómo vuelve.

    El estímulo lo empuja; el tiempo lo devuelve al reposo. Un valor sin
    estímulos no se queda quieto — tiende a donde le corresponde estar.
    """

    nombre: str
    dueno: str
    descripcion: str

    # Hacia dónde vuelve cuando no pasa nada. No siempre es cero: la
    # incertidumbre de fondo nunca desaparece del todo.
    reposo: float = 0.0

    # Segundos en volver a la mitad del camino hacia el reposo. Más chico,
    # más volátil.
    media_vida: float = 600.0

    nivel: float = 0.0
    actualizado: float = field(default_factory=time.monotonic)

    _muestras: deque = field(default_factory=lambda: deque(maxlen=MUESTRAS))
    _ultima_muestra: float = 0.0

    # ------------------------------------------------------------------

    def empujar(self, cuanto: float) -> None:
        """Mueve el valor. El estímulo empuja; el tiempo devuelve.

        Se satura contra el techo en vez de sumar linealmente: cuanto más
        alto está, menos lo mueve un empujón nuevo. Sin eso, tres estímulos
        seguidos lo clavan en 1 y deja de distinguir intensidades.
        """
        self._decaer()

        if cuanto >= 0:
            self.nivel += (1.0 - self.nivel) * cuanto
        else:
            self.nivel += self.nivel * cuanto

        self.nivel = max(0.0, min(1.0, self.nivel))

    def fijar(self, nivel: float) -> None:
        """Establece el valor directamente.

        Para lo que se puede medir en vez de acumular: la saturación de la
        memoria se calcula, no se empuja.
        """
        self._decaer()
        self.nivel = max(0.0, min(1.0, nivel))

    def leer(self) -> float:
        """Devuelve el nivel actual, ya decaído."""
        self._decaer()
        return self.nivel

    @property
    def tendencia(self) -> float:
        """Cuánto cambió en la ventana. Positivo sube, negativo baja.

        Un valor alto que baja no es lo mismo que uno alto que sube, y sin
        esto no se puede distinguir.
        """
        if len(self._muestras) < 2:
            return 0.0
        return self._muestras[-1] - self._muestras[0]

    # ------------------------------------------------------------------

    def _decaer(self) -> None:
        """Aplica el tiempo transcurrido desde la última operación.

        Por reloj y no por ciclo: si el proceso estuvo dormido tres horas,
        decae tres horas. Es lo que hace que la sangre cambie sola.
        """
        ahora = time.monotonic()
        transcurrido = ahora - self.actualizado
        if transcurrido <= 0:
            return

        # Decaimiento exponencial hacia el reposo.
        factor = 0.5 ** (transcurrido / self.media_vida)
        self.nivel = self.reposo + (self.nivel - self.reposo) * factor

        self.actualizado = ahora
        self._registrar_muestra(ahora)

    def _registrar_muestra(self, ahora: float) -> None:
        if ahora - self._ultima_muestra < INTERVALO_MUESTRA:
            return
        self._muestras.append(self.nivel)
        self._ultima_muestra = ahora

    def avanzar(self, segundos: float) -> None:
        """Adelanta el reloj de este valor. Solo para pruebas."""
        self.actualizado -= segundos
        self._ultima_muestra -= segundos


class Sangre:
    """El estado interno de ABEL, compartido por todos sus procesos."""

    def __init__(self, ruta: Path | None = None) -> None:
        self._ruta = ruta
        self._valores: dict[str, Valor] = {}
        self._nacimiento = time.time()
        self._registrar_iniciales()

    def _registrar_iniciales(self) -> None:
        """Los valores con los que ABEL arranca.

        Cada uno tiene dueño declarado. Si un día alguno no tiene quien lo
        lea, se saca: un valor que nadie lee no es estado.
        """
        # --- Sobre el mundo ---
        self.registrar(
            "incertidumbre",
            dueno="modelo",
            descripcion="Qué tanto no sabe de lo que le importa.",
            # Nunca llega a cero: siempre hay algo que no se sabe.
            reposo=0.25,
            media_vida=3600.0,
        )
        self.registrar(
            "novedad",
            dueno="atencion",
            descripcion="Qué tanto de lo que llega no encaja con lo esperado.",
            media_vida=900.0,
        )

        # --- Sobre sí mismo ---
        self.registrar(
            "coherencia",
            dueno="creencias",
            descripcion="Contradicciones sin resolver. Alto es malo.",
            # Lento: una contradicción no se disuelve con el tiempo, hay que
            # resolverla.
            media_vida=14400.0,
        )
        self.registrar(
            "saturacion",
            dueno="memoria",
            descripcion="Memoria acumulada sin consolidar.",
            media_vida=7200.0,
        )
        self.registrar(
            "continuidad",
            dueno="ciclo_vida",
            descripcion="Tiempo propio perdido por caídas.",
            media_vida=21600.0,
        )

        # --- Sobre la persona ---
        self.registrar(
            "conexion",
            dueno="conversacion",
            descripcion="Cercanía del contacto reciente.",
            media_vida=10800.0,
        )
        self.registrar(
            "deuda",
            dueno="conversacion",
            descripcion="Preguntas sin responder, cosas a medias.",
            media_vida=43200.0,
        )

        # --- Sobre la actividad ---
        self.registrar(
            "actividad",
            dueno="sensores",
            descripcion="Cuánto está pasando ahora.",
            media_vida=300.0,
        )

    # ------------------------------------------------------------------

    def registrar(
        self,
        nombre: str,
        dueno: str,
        descripcion: str,
        reposo: float = 0.0,
        media_vida: float = 600.0,
    ) -> Valor:
        """Agrega un valor a la sangre.

        Falla si ya existe: dos dueños para un mismo valor significa que se
        pisan y no hay forma de saber por qué cambió.
        """
        if nombre in self._valores:
            raise ValueError(
                f"El valor {nombre!r} ya existe, con dueño "
                f"{self._valores[nombre].dueno!r}."
            )

        valor = Valor(
            nombre=nombre,
            dueno=dueno,
            descripcion=descripcion,
            reposo=reposo,
            media_vida=media_vida,
            nivel=reposo,
        )
        self._valores[nombre] = valor
        return valor

    def __getitem__(self, nombre: str) -> Valor:
        try:
            return self._valores[nombre]
        except KeyError:
            raise KeyError(
                f"No existe el valor {nombre!r} en la sangre. "
                f"Hay: {', '.join(sorted(self._valores))}."
            ) from None

    def __iter__(self) -> Iterator[Valor]:
        return iter(self._valores.values())

    def __contains__(self, nombre: str) -> bool:
        return nombre in self._valores

    def leer(self, nombre: str) -> float:
        return self[nombre].leer()

    def empujar(self, nombre: str, cuanto: float) -> None:
        self[nombre].empujar(cuanto)

    def fijar(self, nombre: str, nivel: float) -> None:
        self[nombre].fijar(nivel)

    def instantanea(self) -> dict[str, dict]:
        """Todo el estado, para mostrar o registrar."""
        return {
            v.nombre: {
                "nivel": round(v.leer(), 4),
                "tendencia": round(v.tendencia, 4),
                "reposo": v.reposo,
                "dueno": v.dueno,
                "descripcion": v.descripcion,
            }
            for v in self._valores.values()
        }

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def guardar(self) -> None:
        """Escribe la sangre al disco.

        Sin esto ABEL vuelve a cero cada vez que se cae, y la continuidad
        que dice tener sería mentira.
        """
        if self._ruta is None:
            return

        datos = {
            "guardado_en": time.time(),
            "valores": {
                v.nombre: {"nivel": v.leer(), "muestras": list(v._muestras)}
                for v in self._valores.values()
            },
        }

        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            # Escritura atómica: si el proceso muere a mitad de escribir, el
            # archivo viejo sigue entero.
            temporal = self._ruta.with_suffix(".tmp")
            temporal.write_text(json.dumps(datos, indent=2), encoding="utf-8")
            temporal.replace(self._ruta)
        except OSError as exc:
            logger.warning("No se pudo guardar la sangre: %s", exc)

    def cargar(self) -> float:
        """Recupera la sangre del disco. Devuelve los segundos de ausencia.

        Al volver, se aplica el tiempo transcurrido: si estuvo caído tres
        horas, los valores decaen esas tres horas. Despertar no es empezar
        de nuevo.
        """
        if self._ruta is None or not self._ruta.exists():
            return 0.0

        try:
            datos = json.loads(self._ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo leer la sangre: %s", exc)
            return 0.0

        ausencia = max(0.0, time.time() - datos.get("guardado_en", 0.0))

        for nombre, guardado in datos.get("valores", {}).items():
            valor = self._valores.get(nombre)
            if valor is None:
                # Un valor que ya no existe en el código. Se ignora en
                # silencio: la sangre puede cambiar de forma entre versiones.
                continue

            valor.nivel = float(guardado.get("nivel", valor.reposo))
            valor._muestras.extend(guardado.get("muestras", []))
            valor.avanzar(ausencia)
            valor.leer()   # fuerza el decaimiento por el tiempo ausente

        logger.info(
            "Sangre recuperada. Ausencia: %s.", _duracion(ausencia)
        )
        return ausencia


def _duracion(segundos: float) -> str:
    if segundos < 60:
        return f"{segundos:.0f}s"
    if segundos < 3600:
        return f"{segundos / 60:.0f}min"
    if segundos < 86400:
        return f"{segundos / 3600:.1f}h"
    return f"{segundos / 86400:.1f} días"
