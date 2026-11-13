import json
import sys
import unicodedata
import urllib.request
from pathlib import Path

from cultivos.config import load_zone_config


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.casefold().strip()


def property_values(properties: dict) -> set[str]:
    values = set()
    for value in properties.values():
        if isinstance(value, str):
            values.add(normalize(value))
        elif isinstance(value, dict):
            values |= property_values(value)
    return values


def matches(feature: dict, department: str, province: str) -> bool:
    values = property_values(feature.get("properties", {}))
    wanted = {normalize(department), normalize(f"Departamento {department}")}
    return bool(values & wanted) and normalize(province) in values


def download(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "cropRecognition"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main() -> None:
    config = load_zone_config()
    collection = download(config["boundary_source_url"])
    selected = [
        feature
        for feature in collection["features"]
        if matches(feature, config["department"], config["province"])
    ]
    if not selected:
        example = collection["features"][0].get("properties", {})
        sys.exit(f"No feature matched. Example properties: {example}")

    output = Path(config["boundary_path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {"type": "FeatureCollection", "features": selected}
    output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(selected)} feature(s) to {output}")


if __name__ == "__main__":
    main()
