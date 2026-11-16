import csv
from pathlib import Path

import numpy as np

from cultivos.config import load_labels_config, load_series_config

NDVI_PREFIX = "ndvi_"
PERCENTILES = (25, 50, 75)


def summarize_series() -> dict:
    path = Path(load_series_config()["train_path"])
    if not path.exists():
        return {"available": False}

    classes = load_labels_config()["classes"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = [name for name in reader.fieldnames if name.startswith(NDVI_PREFIX)]
        values: dict[str, list[list[float]]] = {clase: [] for clase in classes}
        for row in reader:
            values[row["clase"]].append([float(row[name]) if row[name] else np.nan for name in columns])

    summary = {}
    for clase, rows in values.items():
        if not rows:
            continue
        p25, median, p75 = (np.nanpercentile(np.array(rows), q, axis=0).round(3).tolist() for q in PERCENTILES)
        summary[clase] = {"pixels": len(rows), "p25": p25, "median": median, "p75": p75}
    return {"available": True, "dates": [name[len(NDVI_PREFIX):] for name in columns], "classes": summary}
