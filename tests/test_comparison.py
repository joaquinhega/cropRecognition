import pytest

from cultivos.modules.comparison import compare_all, compare_latest

RULES = {"similar_percent": 5, "similar_absolute": 0.02, "min_baseline_for_percent": 0.1, "decimals": 4}


def month(key, ndvi=None, status="ok", complete=True):
    indices = {"NDVI": {"mean": ndvi, "p25": ndvi, "p75": ndvi}, "NDMI": None} if ndvi is not None else None
    return {"month": key, "status": status if ndvi is not None else "cloudy", "complete": complete, "indices": indices}


def campaign(label, *months):
    return {"campaign": label, "months": list(months)}


def test_latest_month_against_the_same_month_of_earlier_campaigns():
    campaigns = [
        campaign("2024/25", month("2025-01", 0.50), month("2025-02", 0.40)),
        campaign("2025/26", month("2026-01", 0.60), month("2026-02")),
        campaign("2026/27", month("2027-01", 0.66), month("2027-02", complete=False)),
    ]
    result = compare_latest(campaigns, "NDVI", RULES)
    assert result["month"] == "2027-01"
    assert [entry["campaign"] for entry in result["earlier"]] == ["2024/25", "2025/26"]
    assert result["baseline"] == pytest.approx(0.55)
    assert result["difference"] == pytest.approx(0.11)
    assert result["percent"] == pytest.approx(20.0)
    assert result["trend"] == "above"


def test_small_differences_read_as_similar():
    campaigns = [campaign("2025/26", month("2025-10", 0.30)), campaign("2026/27", month("2026-10", 0.31))]
    assert compare_latest(campaigns, "NDVI", RULES)["trend"] == "similar"


def test_near_zero_baseline_uses_the_absolute_difference():
    campaigns = [campaign("2025/26", month("2025-10", 0.05)), campaign("2026/27", month("2026-10", 0.01))]
    result = compare_latest(campaigns, "NDVI", RULES)
    assert result["percent"] is None
    assert result["trend"] == "below"


def test_without_earlier_data_there_is_no_baseline():
    result = compare_latest([campaign("2026/27", month("2026-07", 0.2))], "NDVI", RULES)
    assert result["baseline"] is None
    assert result["trend"] is None


def test_campaign_without_data_and_missing_index():
    campaigns = [campaign("2026/27", month("2026-07"))]
    assert compare_latest(campaigns, "NDVI", RULES) == {"campaign": "2026/27", "month": None}
    assert compare_all([campaign("2026/27", month("2026-07", 0.3))], ["NDMI"], RULES)["NDMI"]["month"] is None
    assert compare_latest([], "NDVI", RULES) is None
