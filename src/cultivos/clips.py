"""Local clips of the work area made in subproject A (data/raw and data/processed)."""

import re
from pathlib import Path

from cultivos.config import load_imagery_config

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def clip_paths(date: str, imagery: dict | None = None) -> tuple[Path, Path, Path]:
    """Paths of the band clip, its cloud mask (SCL) and its NDVI for a date."""
    imagery = imagery or load_imagery_config()
    if not DATE_PATTERN.fullmatch(date):
        raise FileNotFoundError(date)
    stem = f"{date}_{imagery['tile']}"
    raw_dir, processed_dir = Path(imagery["raw_dir"]), Path(imagery["processed_dir"])
    return raw_dir / f"{stem}.tif", raw_dir / f"{stem}_scl.tif", processed_dir / f"{stem}_ndvi.tif"


def list_dates() -> list[dict]:
    imagery = load_imagery_config()
    suffix = f"_{imagery['tile']}.tif"
    dates = []
    for path in sorted(Path(imagery["raw_dir"]).glob(f"*{suffix}")):
        date = path.name[: -len(suffix)]
        dates.append({"date": date, "has_ndvi": clip_paths(date, imagery)[2].exists()})
    return dates
