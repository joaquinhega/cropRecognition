"""D1-T1: files of a training dataset (pixels, monthly observations and summary) under data/training/<dataset_id>/."""

import csv
import json
from datetime import date
from pathlib import Path

from cultivos.modules.campaigns import Month, add_months, campaign_label, month_end

PIXEL_FIELDS = ["pixel_id", "class", "map_value", "lon", "lat"]
PIXEL_ID_FORMAT = "P-{:05d}"


def folder(config: dict) -> Path:
    return Path(config["output_dir"]) / config["dataset_id"]


def campaign_months(start: date, count: int) -> list[Month]:
    label = campaign_label(start.year)
    months = []
    for offset in range(count):
        first = add_months(start, offset)
        months.append(Month(f"{first:%Y-%m}", label, first, month_end(first)))
    return months


def observation_fields(band_roles: list[str], index_names: list[str]) -> list[str]:
    return ["pixel_id", "month", "scene_id", "scene_date", *band_roles, *(name.lower() for name in index_names)]


def write_pixels(path: Path, pixels: list[dict]) -> list[dict]:
    rows = [{"pixel_id": PIXEL_ID_FORMAT.format(number), **pixel} for number, pixel in enumerate(pixels, 1)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PIXEL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def read_pixels(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {**row, "map_value": int(row["map_value"]), "lon": float(row["lon"]), "lat": float(row["lat"])}
            for row in csv.DictReader(handle)
        ]


def write_rows(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: ("" if value is None else value) for key, value in row.items()} for row in rows)


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
