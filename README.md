# cropRecognition

Plataforma intermediaria de datos satelitales para el agro: se conecta a fuentes gratuitas y pagas con adaptadores, guarda todo en un catálogo propio (STAC), procesa zonas y parcelas, reconoce cultivos y lo expone por API y por un visor web. Mendoza primero.

## Estado

- **A · Reconocedor de vid (Agrelo):** cerrado. Etiquetas, series de NDVI y tablas de entrenamiento.
- **B · Datos y fuentes:** cerrado. Catálogo propio (eoAPI), adaptadores de Earth Search (Sentinel-2), NASA POWER (clima) y CONAE (SAOCOM, solo búsqueda), visor con modos Explorar y Etiquetar.
- **C · Parcelas:** cerrado. Parcelas en PostGIS, dibujadas o subidas (GeoJSON, KML, KMZ), en el modo Mi parcela. Procesamiento en segundo plano: índices mensuales (NDVI, NDRE, NDMI, EVI) y clima por campaña. Ficha de parcela con curvas, clima y comparación entre campañas.
- **D · Reconocimiento de cultivos:** en curso. La revisión manual de OSM dejó a Mendoza sin etiquetas confiables, así que el primer reconocimiento es en Pergamino (soja, maíz y otros) con el Mapa Nacional de Cultivos del INTA. Tabla de entrenamiento, variables, línea base medida por bloques y modo Reconocimiento.
- **E y F:** API pública e interfaz final, fuentes pagas.

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

### Revisión de OSM (D1-T0)

En **Etiquetar → Revisar viñedos de OSM** se recorren los 30 polígonos de la muestra (`data/inventory/osm-vineyard-muestra-revision.geojson`) sobre la foto de Esri y la imagen de Sentinel-2 más limpia de pleno verano, y se marca cada uno como coincide, parcial, no coincide o dudoso. Las respuestas se guardan en `data/inventory/osm-vineyard-revision.json`; si no coinciden más del 10 %, OSM queda como fuente dudosa. Período, límite y respuestas en `config/inventory.json` (`osm.review`).

### Datos de entrenamiento (D1-T1)

```powershell
docker compose run --rm api python -m cultivos.training.build_table
```

Recorta el Mapa Nacional de Cultivos 2024/25 (verano, INTA, CC BY 4.0) sobre la zona de entrenamiento, toma una muestra de píxeles por clase en manchas parejas y arma su serie mensual de Sentinel-2 de la campaña (julio a junio). Se puede cortar y volver a correr: reutiliza la muestra y los meses terminados. Deja todo en `data/training/<dataset>/` (`pixels.csv`, `observations.csv`, `summary.json`) y se ve en el modo **Reconocimiento**. Zona, campaña, clases y tamaño de la muestra en `config/training.json`.

### Variables del modelo (D1-T2)

```powershell
docker compose run --rm api python -m cultivos.training.features
```

A partir de la tabla de D1-T1 arma `features.csv` con una fila por píxel: las bandas y los índices de cada mes (`ndvi_m01` es julio, el primer mes de la campaña) y la forma de la curva de NDVI (pico, mes del pico, mes en que arranca y en que se seca, meses verdes, verdor de invierno y de verano, entre otras). Antes descarta los meses con firma de bruma: el verdor cae, el azul se aclara y el infrarrojo de onda corta no sube (si sube, es vegetación que se seca de verdad y se conserva). Reglas en `config/training.json` (`features`); el resumen se ve en **Reconocimiento → Variables del modelo**.

### Modelos y medición por bloques (D2)

```powershell
docker compose run --rm api python -m cultivos.models.evaluate baseline
```

Entrena y mide un modelo con validación cruzada por bloques: la zona se corta en cuadrados que se turnan como prueba, y en cada ronda se dejan fuera del entrenamiento los píxeles cercanos a los de prueba. `baseline` es la línea base, un árbol de dos preguntas sobre el NDVI de cada mes. Escribe en `data/training/<dataset>/models/` el informe (`baseline.json`), la ronda de cada píxel (`folds.csv`) y lo que predijo para cada píxel cuando estaba en prueba (`baseline-predictions.csv`). Tamaño de los bloques, rondas, franja y meta de F1 en `config/training.json` (`evaluation`); los modelos, en `models`. El resultado se ve en **Reconocimiento → Modelos**.

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
├── training/      # datos de entrenamiento (D1): mapa de etiquetas, muestra, series mensuales, variables del modelo
├── models/        # modelos (D2): bloques de la validación cruzada, línea base, medición
├── api/           # main.py (etiquetas, A), platform.py (B), parcels.py y jobs.py (C), osm_review.py y training.py (D)
├── zones.py       # zonas y recuadros
└── ...            # scripts del subproyecto A (recorte, NDVI, etiquetas, series)
web/src/
├── explore/       # modo Explorar: capas, búsqueda, línea de tiempo, clima
├── parcels/       # modo Mi parcela: dibujar, subir, listar, renombrar, borrar, procesar; sheet/ es la ficha (C3)
├── label/         # modo Etiquetar (herramienta de A) y revisión de OSM (D1-T0)
├── recognition/   # modo Reconocimiento: datos de entrenamiento (D1) y modelos (D2)
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
