# cropRecognition

Plataforma intermediaria de datos satelitales para el agro: se conecta a fuentes gratuitas y pagas con adaptadores, guarda todo en un catálogo propio (STAC), procesa zonas y parcelas, reconoce cultivos y lo expone por API y por un visor web. Mendoza primero.

## Estado

- **A · Reconocedor de vid (Agrelo):** cerrado. Etiquetas, series de NDVI y tablas de entrenamiento.
- **B · Datos y fuentes:** cerrado. Catálogo propio (eoAPI), adaptadores de Earth Search (Sentinel-2), NASA POWER (clima) y CONAE (SAOCOM, solo búsqueda), visor con modos Explorar y Etiquetar.
- **C · Parcelas:** en curso. Parcelas en PostGIS, dibujadas o subidas (GeoJSON, KML, KMZ), en el modo Mi parcela. Procesamiento en segundo plano: índices mensuales (NDVI, NDRE, NDMI, EVI) y clima por campaña. Ficha de parcela con curvas, clima y comparación entre campañas.
- **D a F:** reconocimiento, API pública e interfaz final, fuentes pagas.

## Servicios

| Servicio | Qué hace | Dirección local |
|---|---|---|
| `web` | Visor (React + Vite + Leaflet) | http://localhost:5173 |
| `api` | Nuestra API (FastAPI): zonas, fuentes, búsqueda, catálogo, clima, parcelas, tareas, etiquetas | http://localhost:8000/docs |
| `worker` | Ejecuta las tareas en segundo plano (procesamiento de parcelas); se reinicia solo al cambiar el código | `docker compose logs -f worker` |
| `stac` | Catálogo STAC propio (STAC-FastAPI) | http://localhost:8081 |
| `raster` | Teselas de las imágenes del catálogo (TiTiler) | http://localhost:8082/api.html |
| `database` | Postgres con pgSTAC (catálogo) y PostGIS (parcelas, esquema `platform`) | `localhost:5439` |

El visor llama a la API en `/api` y a TiTiler en `/raster` (Vite hace de intermediario).

## Cómo ejecutar

Requisitos: Docker Desktop abierto.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

La primera vez descarga las imágenes de eoAPI y crea la base. Para detener: `Ctrl+C` y luego `docker compose down`. La base queda guardada en el volumen `pgstac-data`; `docker compose down -v` la borra.

### Primeros pasos

```powershell
# Recortes de Agrelo (subproyecto A) al catálogo, para el modo Etiquetar
docker compose run --rm api python -m cultivos.catalog.load_clips

# Buscar Sentinel-2 y SAOCOM en Agrelo para los últimos 90 días y guardarlos en el catálogo
curl "http://localhost:8000/search?zone=agrelo"

# Clima de Agrelo (NASA POWER)
curl "http://localhost:8000/climate?zone=agrelo&start=2026-01-01&end=2026-03-31"
```

También se puede buscar desde el visor: panel **Zona y búsqueda** → **Buscar en las fuentes y guardar**.

### Parcelas (C1)

En el visor, modo **Mi parcela**: dibujar una parcela o subir un GeoJSON, KML o KMZ (cada polígono del archivo es una parcela). Por la API:

```powershell
# Listar (GeoJSON) con los límites de tamaño
curl "http://localhost:8000/parcels"

# Subir un archivo: el cuerpo de la petición es el archivo
curl.exe -X POST "http://localhost:8000/parcels/import?filename=parcels_sample.kml" --data-binary "@tests/fixtures/parcels_sample.kml"
```

La tabla `platform.parcels` se crea sola la primera vez que se usa. Superficie geodésica en hectáreas; máximo y mínimo en `config/parcels.json`.

### Procesamiento de parcelas (C2)

En **Mi parcela**, elegir una parcela y **Procesar parcela**: el `worker` busca las imágenes Sentinel-2 de la campaña en curso y las tres anteriores (julio a junio), elige una por mes (la que deja más superficie limpia), calcula NDVI, NDRE, NDMI y EVI sobre los píxeles limpios y trae el clima mensual de NASA POWER. La primera vez tarda unos minutos; al volver a procesar solo calcula los meses abiertos o nuevos. Por la API:

```powershell
# Encolar (responde enseguida con la tarea)
curl.exe -X POST "http://localhost:8000/parcels/1/process"

# Estado y avance de la tarea
curl "http://localhost:8000/jobs/1"

# Resultados
curl "http://localhost:8000/parcels/1/series"
curl "http://localhost:8000/parcels/1/climate"
```

Las tareas viven en `platform.jobs`; si el worker se corta, la tarea vuelve a la cola. Campañas, índices y umbrales en `config/processing.json`.

### Ficha de parcela (C3)

Al elegir una parcela procesada en **Mi parcela** se abre su ficha a la derecha: un titular que compara el último mes con dato de la campaña en curso con el mismo mes de las anteriores, las curvas del índice elegido (una por campaña, de julio a junio), la lluvia y la temperatura por campaña, y la línea de tiempo por mes. Al elegir un mes, el mapa muestra la imagen usada (color real, infrarrojo, NDVI o nubes) sobre la parcela. La comparación sale de `GET /parcels/{id}/series` (campo `comparison`) y sus umbrales están en `config/processing.json` (`comparison`).

### Prueba rápida del catálogo (B1)

```powershell
docker compose run --rm api python -m cultivos.catalog.seed_test
```

Carga un NDVI de prueba por la API STAC y muestra el enlace del visor de TiTiler.

## Tests

```powershell
docker compose run --rm api pytest -q
```

Los tests de adaptadores usan respuestas grabadas de las fuentes; los del catálogo, de parcelas y de procesamiento usan la base de `docker compose` y borran lo que crean. El procesamiento se prueba con escenas sintéticas en disco, sin llamar a las fuentes.

## Configuración

Todo lo ajustable está en `config/`:

- `sources.json`: fuentes, estado (activa o postergada), licencia, atribución y límites.
- `zones.json`: zonas con nombre y superficie máxima de búsqueda.
- `layers.json`: capas de cada colección (bandas, fórmula, colores) y cómo leerlas.
- `catalog.json`: valores por defecto de búsqueda y de los recortes de A.
- `parcels.json`: superficie máxima y mínima de una parcela, formatos y tamaño de archivo admitidos.
- `processing.json`: campañas, bandas e índices, mínimo de superficie limpia por mes, textos de estado y ritmo del worker.
- `zone.json`, `imagery.json`, `labels.json`, `split.json`, `series.json`, `inventory.json`: subproyecto A y B0.

Puertos y credenciales de la base, en `.env` (ver `.env.example`).

## Estructura

```
src/cultivos/
├── adapters/      # una fuente por archivo, mismo contrato (base.py)
├── catalog/       # pgSTAC: conexión, ingesta, consultas, carga de recortes
├── parcels/       # parcelas en PostGIS: validación, lectura de archivos, tabla
├── modules/       # procesamiento por parcela: campañas, escenas, índices, clima, resultados
├── jobs/          # cola de tareas en Postgres y worker
├── api/           # main.py (etiquetas, A), platform.py (B), parcels.py y jobs.py (C)
├── zones.py       # zonas y recuadros
└── ...            # scripts del subproyecto A (recorte, NDVI, etiquetas, series)
web/src/
├── explore/       # modo Explorar: capas, búsqueda, línea de tiempo, clima
├── parcels/       # modo Mi parcela: dibujar, subir, listar, renombrar, borrar, procesar; sheet/ es la ficha (C3)
├── label/         # modo Etiquetar (herramienta de A)
└── map/           # mapas base y utilidades de Leaflet
tests/             # pytest
```

## Comandos del subproyecto A y B0

```powershell
docker compose run --rm api python -m cultivos.fetch_boundary
docker compose run --rm api python -m cultivos.clip_scene --date AAAA-MM-DD
docker compose run --rm api python -m cultivos.compute_ndvi --date AAAA-MM-DD
docker compose run --rm api python -m cultivos.osm_inventory
docker compose run --rm api python -m cultivos.mnc_coverage
```

## Fuentes y atribución

Contiene datos modificados de Copernicus Sentinel. Datos de clima de NASA Langley Research Center (LaRC) POWER Project. Metadatos de productos SAOCOM® de CONAE. Mapas base de © OpenStreetMap, © CARTO y Esri (solo referencia visual). El detalle de licencias está en el visor, en **Fuentes y límites**.
