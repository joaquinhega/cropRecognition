import json
from pathlib import Path

ZONE_CONFIG_PATH = Path("config/zone.json")
IMAGERY_CONFIG_PATH = Path("config/imagery.json")
LABELS_CONFIG_PATH = Path("config/labels.json")
SPLIT_CONFIG_PATH = Path("config/split.json")
SERIES_CONFIG_PATH = Path("config/series.json")
INVENTORY_CONFIG_PATH = Path("config/inventory.json")
SOURCES_CONFIG_PATH = Path("config/sources.json")
ZONES_CONFIG_PATH = Path("config/zones.json")
CATALOG_CONFIG_PATH = Path("config/catalog.json")
LAYERS_CONFIG_PATH = Path("config/layers.json")
PARCELS_CONFIG_PATH = Path("config/parcels.json")
PROCESSING_CONFIG_PATH = Path("config/processing.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_zone_config() -> dict:
    return _load(ZONE_CONFIG_PATH)


def load_imagery_config() -> dict:
    return _load(IMAGERY_CONFIG_PATH)


def load_labels_config() -> dict:
    return _load(LABELS_CONFIG_PATH)


def load_split_config() -> dict:
    return _load(SPLIT_CONFIG_PATH)


def load_series_config() -> dict:
    return _load(SERIES_CONFIG_PATH)


def load_inventory_config() -> dict:
    return _load(INVENTORY_CONFIG_PATH)


def load_sources_config() -> dict:
    return _load(SOURCES_CONFIG_PATH)


def load_zones_config() -> dict:
    return _load(ZONES_CONFIG_PATH)


def load_catalog_config() -> dict:
    return _load(CATALOG_CONFIG_PATH)


def load_layers_config() -> dict:
    return _load(LAYERS_CONFIG_PATH)


def load_parcels_config() -> dict:
    return _load(PARCELS_CONFIG_PATH)


def load_processing_config() -> dict:
    return _load(PROCESSING_CONFIG_PATH)
