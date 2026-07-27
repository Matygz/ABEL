# Arquitectura de ABEL

Este documento describe la arquitectura conceptual y técnica de ABEL. Es el mapa mental del proyecto. Cuando cambia sustancialmente, se actualiza acá.

## Modelo conceptual

ABEL consiste en dos tipos de componentes que se comunican:

- **Núcleo (uno):** el cerebro central. Vive en la PC principal. Contiene memoria, estados internos, cognición, toma de decisiones.
- **Nodos (uno o más):** presencia periférica en cada dispositivo autorizado. Son ojos, oídos, manos de ABEL en ese dispositivo. Reportan al núcleo y ejecutan sus órdenes.

Analogía biológica: el núcleo es el sistema nervioso central, los nodos son el sistema nervioso periférico. El núcleo integra, decide, recuerda. Los nodos perciben y actúan.

## Componentes del Núcleo

### Sistema nervioso central

Recibe información constante de los Nodos. Múltiples canales por tipo (visual, auditivo, textual, eventos de sistema). Filtra lo irrelevante, prioriza lo urgente. La mayoría del procesamiento es preconsciente. Un único hilo "consciente" atiende una cosa a la vez, con el resto en periferia.

### Ciclo de vida continuo

El Núcleo tiene un ciclo interno constante. No es reactivo — vive. Similar al latido del corazón: mantiene el sistema activo aunque no haya estímulos externos.

### Memoria estructurada

Cuatro tipos:

- **Memoria de trabajo:** capacidad limitada, contenido activo ahora
- **Memoria episódica:** eventos concretos con contexto temporal
- **Memoria semántica:** conocimiento abstraído sin contexto temporal
- **Memoria procedural:** cómo hacer cosas

Consolidación durante períodos de baja actividad: episódica se procesa, patrones se transfieren a semántica.

### Estados internos dinámicos

Variables con inercia real que representan el estado interno de ABEL: humor, energía, curiosidad, coherencia, etc. Influyen decisiones. Momentum: los cambios se sostienen, no vuelven al reposo en segundos.

### Modelo del mundo

Representación interna de la realidad conocida por ABEL: entidades (personas, lugares, apps, conceptos), relaciones entre ellas, patrones observados. Es la comprensión estructurada de todo lo que ha visto.

### Modelo del usuario

Sub-modelo específico y detallado sobre el usuario: patrones de comportamiento, preferencias, historial, estado emocional aparente, contexto actual.

### Toma de decisiones

Cuando llega información o pedido, ABEL decide qué hacer. Considera: contexto, estado interno, propósito, historial. No es solo cálculo — incluye componentes análogos a intuición y preferencia.

### Metacognición

ABEL sabe (o intenta saber) qué sabe y qué no. Puede identificar gaps de conocimiento. Puede decidir cuándo investigar. Es la base para el aprendizaje continuo.

### Aprendizaje continuo

Todo lo que ABEL vive va modificándolo. Cada interacción, cada observación, cada decisión afecta memoria y patrones. No hay fase de "entrenamiento" separada — el aprendizaje es constante.

## Componentes de un Nodo

### Captura sensorial

Cada Nodo captura lo que pasa en su dispositivo. Qué exactamente depende del dispositivo:

- **Nodo PC:** apps activas, foco de ventana, notificaciones, teclado (opcional), pantalla (opcional), micrófono (opcional), cámara (opcional)
- **Nodo móvil:** ubicación, notificaciones, apps activas, cámara, micrófono, sensores de movimiento

### Comunicación con Núcleo

Reporta eventos al Núcleo, recibe órdenes. Comunicación bidireccional, cifrada, autenticada.

### Ejecución de acciones

Cuando el Núcleo ordena una acción sobre el dispositivo, el Nodo la ejecuta. Ejemplos: abrir una app, mandar una notificación, cambiar una configuración.

### Estado propio mínimo

El Nodo mantiene solo el estado necesario para funcionar en su dispositivo. La memoria "real" está en el Núcleo. Si un Nodo se reinicia, no pierde nada crítico.

## Capas conceptuales

### Capa 0: Sustrato heredado

Herramientas que ABEL usa sin haberlas construido, análogas a órganos:

- Modelo de embeddings para procesar significado en texto/imágenes
- LLM local para comprensión y generación de lenguaje natural
- APIs del sistema operativo para acción en el entorno
- Motores especializados que ABEL pueda usar (evaluado caso por caso, filosofía preferencial: aprender antes que integrar motor externo)

### Capa 1: Percepción y acción (Nodos)

Los sentidos y las manos distribuidas.

### Capa 2: Cerebro (Núcleo)

Memoria, estados, procesamiento central, cognición.

### Capa 3: Aprendizaje continuo

Cómo ABEL incorpora conocimiento nuevo del mundo.

### Capa 4: Metacognición

Cómo ABEL sabe lo que sabe. Cómo decide investigar. Cómo se ajusta a sí mismo.

### Capa 5: Propósito y valores

Lo que orienta las decisiones cuando ABEL tiene autonomía. Ver `docs/filosofia/vision.md` para el propósito actual.

## Decisiones tecnológicas base

Ver `docs/decisiones/` para el registro detallado de cada decisión. Resumen de las principales:

- **Lenguaje principal:** Python (extensiones en Rust o C++ para módulos específicos que lo requieran)
- **Base de datos:** combinación — PostgreSQL para estructurado, Qdrant para vectorial, Neo4j evaluándose para grafos, SQLite local en Nodos
- **Comunicación Núcleo-Nodos:** WebSocket sobre TLS
- **Ejecución del Núcleo:** servicio de Windows en background + interfaz gráfica opcional para interacción
- **Sistema operativo del Núcleo (actual):** Windows 10

## Fases de desarrollo

Ver README.md para el plan actual de fases.
