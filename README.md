# Chatbot Tutor para Programación Industrial

## Descripción

Proyecto de desarrollo de un chatbot conversacional basado en inteligencia artificial, orientado a apoyar el aprendizaje teórico y práctico de programación de computadores industriales (IPC).

La solución se enfoca inicialmente en **TwinCAT 3**, plataforma de automatización industrial desarrollada por Beckhoff, incorporando conocimiento especializado obtenido de documentación técnica y recursos educativos.

El proyecto contempla la implementación y evaluación de diferentes estrategias para mejorar las respuestas de modelos de lenguaje (LLM), incluyendo:

- **RAG (Retrieval-Augmented Generation):** recuperación de información relevante desde documentación técnica especializada.
- **Fine-Tuning mediante QLoRA:** adaptación eficiente de modelos de lenguaje a las necesidades del dominio.
- **Arquitectura híbrida:** posible combinación de RAG y QLoRA para aprovechar sus capacidades complementarias.

La estrategia definitiva será seleccionada mediante una evaluación comparativa de calidad de respuesta, utilidad educativa y requerimientos computacionales.

## Objetivo general

Desarrollar un chatbot conversacional basado en inteligencia artificial para apoyar la capacitación de estudiantes de ingeniería en programación de computadores industriales (IPC), evaluando RAG, Fine-Tuning mediante QLoRA y una posible arquitectura híbrida, con el fin de seleccionar la estrategia que ofrezca mejores resultados de respuesta dentro de la capacidad de cómputo disponible.

## Objetivos específicos

1. Recopilar, seleccionar y estructurar contenido educativo y documentación técnica confiable relacionados con programación industrial, conceptos de IPC y el uso de TwinCAT 3.
2. Definir e implementar configuraciones experimentales basadas en RAG y Fine-Tuning mediante QLoRA, considerando sus requerimientos de datos, memoria, GPU, tiempo de procesamiento y función dentro del chatbot tutor.
3. Evaluar comparativamente RAG, QLoRA y, cuando sea técnicamente viable, una arquitectura híbrida, utilizando criterios técnicos, educativos y computacionales.
4. Implementar el chatbot con la estrategia que presente el mejor equilibrio entre calidad de las respuestas y uso de recursos, y validar su funcionamiento mediante pruebas técnicas y revisión por parte de especialistas.

## Tecnologías y herramientas

Las tecnologías consideradas para el desarrollo incluyen:

- **Python:** procesamiento documental, implementación de modelos, experimentación e integración.
- **TwinCAT 3:** entorno de referencia para programación de IPC.
- **Modelos de lenguaje (LLM):** generación de respuestas especializadas.
- **RAG:** recuperación de conocimiento mediante embeddings e índices vectoriales.
- **QLoRA:** ajuste eficiente de modelos de lenguaje.
- **Git:** control de versiones y seguimiento del desarrollo.

Las bibliotecas, modelos y herramientas específicas se documentarán conforme avance la implementación.

## Metodología de desarrollo

El proyecto utiliza una metodología iterativa e incremental, organizada en las siguientes etapas:

1. Definición de criterios y estrategias candidatas.
2. Recopilación de documentación técnica y educativa.
3. Extracción, limpieza y estructuración de documentos.
4. Preparación de datos para RAG y QLoRA.
5. Implementación de RAG y Fine-Tuning mediante QLoRA.
6. Evaluación comparativa y análisis de factibilidad de una arquitectura híbrida.
7. Integración del chatbot, pruebas y validación.

## Estado actual del proyecto

**Fase inicial: recopilación y procesamiento documental.**

Los avances documentados incluyen:

- Recopilación y organización temática de documentación técnica sobre TwinCAT 3.
- Clasificación del contenido por áreas de programación industrial.
- Procesamiento y conversión de documentos HTML a Markdown estructurado.
- Preservación de títulos, secciones, ejemplos de código, tablas, imágenes, metadatos y referencias de origen.

Las siguientes etapas contemplan la preparación de conjuntos de datos, implementación de estrategias de especialización y evaluación experimental.

## Evaluación

Las estrategias implementadas se compararán utilizando los siguientes criterios:

- Precisión y calidad técnica de las respuestas.
- Utilidad educativa de las explicaciones.
- Trazabilidad hacia documentación especializada.
- Latencia de respuesta.
- Consumo de CPU, RAM, GPU y VRAM.
- Factibilidad de ejecución local.

## Alcance

El proyecto está orientado inicialmente al aprendizaje de programación de IPC mediante TwinCAT 3, considerando contenidos como Structured Text (ST), Function Block Diagram (FBD), Ladder Diagram (LD), tareas cíclicas, bloques de función, temporizadores, entradas y salidas y conceptos de ejecución en tiempo real.

El desarrollo corresponde a un prototipo educativo y experimental. No está destinado a sustituir procesos de validación, pruebas de seguridad o certificación de software de control industrial.

## Contexto académico

Proyecto desarrollado en el marco de la Actividad de Titulación de la carrera de Ingeniería Civil Informática de la Universidad de La Frontera, bajo la modalidad de Práctica Profesional Controlada.

**Unidad de desarrollo:** Centro de Excelencia de Modelación y Computación Científica (CEMCC), Universidad de La Frontera.

**Año:** 2026.

## Control de versiones

El repositorio utiliza Git para registrar los avances del desarrollo, mantener la trazabilidad de las modificaciones y administrar las versiones del prototipo.

Las versiones se identificarán mediante etiquetas conforme se completen los distintos hitos de implementación.

## Licencia

Licencia de distribución pendiente de definición. El uso y redistribución de documentación técnica de terceros estarán sujetos a sus respectivas condiciones de licencia y derechos de autor.
