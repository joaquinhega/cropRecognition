import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def earth_search_item() -> dict:
    return json.loads((FIXTURES / "earth_search_item.json").read_text(encoding="utf-8"))


@pytest.fixture
def power_payload() -> dict:
    return json.loads((FIXTURES / "power_daily.json").read_text(encoding="utf-8"))


@pytest.fixture
def saocom_page() -> dict:
    return json.loads((FIXTURES / "saocom_catalog.json").read_text(encoding="utf-8"))
