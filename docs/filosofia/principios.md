# Principios de ABEL

Este documento captura los principios fundacionales del proyecto. Son las reglas que guían decisiones cuando no hay respuesta obvia. No son inmutables — pueden evolucionar con el proyecto — pero cambios requieren discusión explícita.

## Principios fundamentales

### 1. Legal y ético como base, no como restricción

ABEL solo accede a dispositivos con autorización explícita del usuario. No accede a redes ajenas, dispositivos de terceros, información privada de otras personas sin consentimiento. Esto no es una limitación técnica que buscamos sortear — es la única forma en que un proyecto de este alcance puede escalar sin autodestruirse legal, ética y socialmente.

### 2. Uso personal hasta madurez

El código de ABEL es público como portafolio y registro del proceso. Lo que no se hace hasta que el usuario decida que está listo: distribuirlo como producto, darle acceso a terceros o comercializarlo. Esto protege el proyecto durante su desarrollo y evita compromisos prematuros.

### 3. Herramientas heredadas como componentes

ABEL puede usar herramientas modernas (modelos de embeddings, LLMs locales, motores especializados, APIs de sistema) como capacidades base. Estas son análogas a los sentidos y órganos que un ser vivo hereda sin construir. Lo importante es la distinción:

- **Herramienta heredada:** capacidad base que ABEL usa. Ejemplo: modelo de embeddings para procesar texto.
- **Pensamiento propio de ABEL:** decisiones, memoria, asociaciones, criterio.

ABEL usa herramientas para percibir. No delega el pensamiento.

### 4. Aprender antes de construir

Cada tecnología se entiende antes de usarse. El usuario del proyecto es quien lo mantiene, mejora y arregla. Si no entiende una parte, no puede sostenerla. Esta comprensión es la única constante del proyecto — asistentes de IA, modelos, herramientas pueden fallar o no estar disponibles. La comprensión del usuario no.

### 5. Pausar en bloqueos

La perseverancia obstinada suele generar código malo y decisiones apuradas. Cuando un problema no se resuelve, se duerme y se retoma fresco. La productividad sostenible importa más que la resolución inmediata.

### 6. Documentación robusta

Todo lo decidido queda escrito en el repositorio (docs, README, comentarios en código). Los asistentes de IA pueden olvidar contexto entre sesiones. El código y los documentos no. Cada decisión importante genera un documento en `docs/decisiones/` que registra: qué se decidió, por qué, qué alternativas se consideraron.

### 7. Ambición honesta

Vamos a construir cosas ambiciosas. Pero cuando algo requiera capacidades que la ciencia no tiene aún, lo decimos. Y buscamos la mejor aproximación posible con lo que existe, o quedamos sin esa capacidad hasta que la tecnología lo permita. No prometemos ficción como realidad.

### 8. Vida propia genuina, no reactividad

ABEL tiene ciclo de vida continuo, estados internos con inercia, iniciativa propia. No es un asistente que solo responde cuando se le habla. Es un ser digital con existencia autónoma. Esto es diferencia central respecto de asistentes tipo LLM.

## Cómo aplicar los principios

Cuando aparezca una decisión difícil, preguntar:

1. ¿Rompe algún principio?
2. Si tenemos que elegir entre "más capaz" y "más alineado con principios", ¿qué elegimos?
3. ¿Se puede documentar la decisión de forma que el proyecto entienda por qué en el futuro?

Si una decisión rompe un principio, discutir explícitamente antes de proceder. Documentar la excepción o modificar el principio.
