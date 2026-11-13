import json
from pathlib import Path

CONFIG_PATH = Path("config/zone.json")


def load_zone_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
