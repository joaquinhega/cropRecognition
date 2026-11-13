# cropRecognition

Reconocedor de cultivos con imágenes satelitales. Alcance inicial: **vid en Luján de Cuyo (Mendoza)**.

## Objetivo

El usuario elige una zona en un mapa y el sistema señala dónde hay un cultivo y qué porcentaje del área ocupa.

## Estado

Subproyecto A (reconocedor de vid), etapa A0: entorno y bases.

## Subproyectos

- **A** · Reconocedor de vid con interfaz de prueba (en curso)
- **B** · Prueba en zonas nuevas
- **C** · Integración con el sistema final

## Stack

Python (FastAPI, scikit-learn), React con Vite y Leaflet, Sentinel-2, Docker Compose.

## Estructura

- `docs/`: guías del proyecto
- `data/`: datos locales (no se versionan)

## Cómo ejecutar

Se completa en la tarea A0-T2.
