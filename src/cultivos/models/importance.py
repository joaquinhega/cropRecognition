"""D2-T2: which variables the model relies on. Variables that say almost the same (NDVI, EVI and NDRE of one month)
cover for each other, so shuffling one at a time shows nothing. Here whole groups are shuffled together on the test
pixels: every variable of one month, or every variable of one kind, and the drop in the score is the importance."""

import re

import numpy as np
from sklearn.metrics import get_scorer

MONTHLY = re.compile(r"^(?P<kind>.+)_m(?P<position>\d{2})$")
PHENOLOGY_KIND = "phenology"


def groups(columns: list[str], month_keys: list[str]) -> dict[str, dict[str, list[int]]]:
    """Column positions per month (monthly variables only) and per kind (each band, each index, the curve shape)."""
    by_month = {month: [] for month in month_keys}
    by_kind: dict[str, list[int]] = {}
    for position, column in enumerate(columns):
        match = MONTHLY.match(column)
        kind = match["kind"] if match else PHENOLOGY_KIND
        if match:
            by_month[month_keys[int(match["position"]) - 1]].append(position)
        by_kind.setdefault(kind, []).append(position)
    return {"by_month": by_month, "by_kind": {kind: found for kind, found in by_kind.items()}}


def group_drops(model, values: np.ndarray, truth: np.ndarray, grouping: dict, scoring: str, repeats: int, seed: int) -> dict:
    """Score drop when the rows of each group are shuffled together (the same order for all its columns)."""
    scorer = get_scorer(scoring)
    rng = np.random.default_rng(seed)
    base = scorer(model, values, truth)
    result = {}
    for family, members in grouping.items():
        result[family] = {}
        for name, positions in members.items():
            if not positions:
                result[family][name] = 0.0
                continue
            drops = []
            for _ in range(repeats):
                shuffled = values.copy()
                order = rng.permutation(len(values))
                shuffled[:, positions] = values[order][:, positions]
                drops.append(base - scorer(model, shuffled, truth))
            result[family][name] = float(np.mean(drops))
    return result


def average(rounds: list[dict], decimals: int) -> dict:
    """Mean drop over the rounds; kinds sorted from most to least important."""
    by_month = {name: np.mean([item["by_month"][name] for item in rounds]) for name in rounds[0]["by_month"]}
    by_kind = {name: np.mean([item["by_kind"][name] for item in rounds]) for name in rounds[0]["by_kind"]}
    return {
        "by_month": [{"month": month, "value": round(float(value), decimals)} for month, value in by_month.items()],
        "by_kind": [
            {"kind": kind, "value": round(float(value), decimals)}
            for kind, value in sorted(by_kind.items(), key=lambda item: item[1], reverse=True)
        ],
    }
