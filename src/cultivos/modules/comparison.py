"""C3-T1: compare the latest month of the campaign in progress with the same month of the previous campaigns."""

from statistics import mean


def _month_values(campaign: dict, index: str) -> dict[str, float]:
    """Mean of `index` for each calendar month (MM) of a campaign that has data."""
    values = {}
    for month in campaign["months"]:
        summary = (month.get("indices") or {}).get(index)
        if month["status"] == "ok" and summary:
            values[month["month"][5:]] = summary["mean"]
    return values


def _trend(difference: float, percent: float | None, rules: dict) -> str:
    similar = abs(percent) < rules["similar_percent"] if percent is not None else abs(difference) < rules["similar_absolute"]
    if similar:
        return "similar"
    return "above" if difference > 0 else "below"


def compare_latest(campaigns: list[dict], index: str, rules: dict) -> dict | None:
    """Latest month with data of the last campaign against the average of that month in the earlier ones.

    `campaigns` come oldest first, as the series endpoint returns them. Returns None when the
    campaign in progress has no month with data yet.
    """
    if not campaigns:
        return None
    current = campaigns[-1]
    latest = next(
        (month for month in reversed(current["months"]) if month["status"] == "ok" and (month.get("indices") or {}).get(index)),
        None,
    )
    if latest is None:
        return {"campaign": current["campaign"], "month": None}

    key = latest["month"][5:]
    value = latest["indices"][index]["mean"]
    earlier = [
        {"campaign": campaign["campaign"], "value": values[key]}
        for campaign in campaigns[:-1]
        if key in (values := _month_values(campaign, index))
    ]
    result = {
        "campaign": current["campaign"],
        "month": latest["month"],
        "complete": latest["complete"],
        "value": value,
        "earlier": earlier,
        "baseline": None,
        "difference": None,
        "percent": None,
        "trend": None,
    }
    if not earlier:
        return result

    decimals = rules["decimals"]
    baseline = mean(entry["value"] for entry in earlier)
    difference = value - baseline
    percent = 100 * difference / abs(baseline) if abs(baseline) >= rules["min_baseline_for_percent"] else None
    result.update(
        baseline=round(baseline, decimals),
        difference=round(difference, decimals),
        percent=round(percent, 1) if percent is not None else None,
        trend=_trend(difference, percent, rules),
    )
    return result


def compare_all(campaigns: list[dict], indices: list[str], rules: dict) -> dict[str, dict | None]:
    return {index: compare_latest(campaigns, index, rules) for index in indices}
