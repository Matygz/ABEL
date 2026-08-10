# 0032 — Alcance: ABEL asume acceso exclusivo

**Estado:** Vigente
**Fecha:** 2026-08-08
**Fase:** 4

## Decisión

ABEL se diseña **exclusivamente para su dueño y sus allegados**, con acceso
desde dispositivos que él autoriza.

Abrirlo a usuarios no vinculados a un dispositivo autorizado **no es una
extensión: es un cambio de premisa** que requeriría reescribir partes
sustanciales.

## Por qué se escribe esto

Surgió la pregunta de si ABEL debería poder usarse como se usa un asistente
comercial: cualquiera entra, lo consulta, obtiene ayuda.

Es un escenario legítimo, pero **invierte el supuesto sobre el que está
construido todo lo anterior**: el principio 2, acceso exclusivo a dispositivos
autorizados.

## Qué se rompería

**Registro abierto.** ABEL tendría que crear usuarios sin aprobación de un
admin. Contradice 0015 y toda la asimetría conceder/revocar de 0014.

**Vuelven las contraseñas.** No se puede autorizar el dispositivo de cada
desconocido. Y con ellas: recuperación de cuenta, verificación de identidad,
manejo de dispositivos comprometidos — todo lo que 0029 descartó.

**Exposición a internet.** Hoy escucha en localhost. Un servicio público es
otra superficie de ataque completa.

**Datos de terceros.** Lo más pesado. Dejarían de ser datos propios en una
máquina propia: habría responsabilidad legal sobre información de otras
personas. El principio 1 pasaría de guía personal a cumplimiento normativo.

## Por qué no se diseña para eso hoy

**Diseñar para un escenario hipotético produce peores decisiones para el
real.** La simplicidad de "solo dispositivos autorizados" es una virtud
concreta hoy; anticipar acceso público la destruiría.

**El caso intermedio es más probable que el extremo.** Cinco personas de la
familia, dispositivos conocidos: eso sí encaja con la arquitectura actual, con
el ajuste de reconocimiento facial (0031) para distinguir personas en un
dispositivo compartido.

**Y quizás no sea deseable.** Lo que hace valioso a ABEL —que conozca la vida,
el contexto y la historia de una persona— es exactamente lo que no escala a
desconocidos.

## Si algún día se decide

Que quede claro qué se rompe: registro, autenticación, exposición de red y
responsabilidad legal. Serían cuatro reescrituras, no cuatro ajustes.
