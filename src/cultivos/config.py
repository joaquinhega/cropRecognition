import json
from pathlib import Path

ZONE_CONFIG_PATH = Path("config/zone.json")
IMAGERY_CONFIG_PATH = Path("config/imagery.json")
LABELS_CONFIG_PATH = Path("config/labels.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_zone_config() -> dict:
    return _load(ZONE_CONFIG_PATH)


def load_imagery_config() -> dict:
    return _load(IMAGERY_CONFIG_PATH)


def load_labels_config() -> dict:
    return _load(LABELS_CONFIG_PATH)
