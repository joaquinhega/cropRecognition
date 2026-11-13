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

- `src/cultivos/`: API y lógica en Python
- `web/`: interfaz en React
- `docs/`: guías del proyecto
- `data/`: datos locales (no se versionan)

## Cómo ejecutar

Requisitos: Docker Desktop abierto.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- Web: http://localhost:5173
- API: http://localhost:8000/health (documentación en /docs)

Para detener: `Ctrl+C` y luego `docker compose down`.
