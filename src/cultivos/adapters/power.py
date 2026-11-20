"""NASA POWER: daily weather for the center of a zone, public API without account."""

from collections.abc import Callable
from datetime import date
from urllib.parse import urlencode

import httpx

from cultivos.adapters.base import (
    SOURCE_COLLECTION_PROPERTY,
    SOURCE_PROPERTY,
    Adapter,
    SearchRequest,
    SourceError,
    collection_template,
)

COLLECTION_KEY = "daily-point"
POINT_DECIMALS = 3


class PowerAdapter(Adapter):
    def __init__(self, source_id: str, config: dict, http_get: Callable[..., httpx.Response] | None = None):
        super().__init__(source_id, config)
        self._http_get = http_get or httpx.get

    @property
    def _collection(self) -> dict:
        return self.config["collections"][COLLECTION_KEY]

    def data_url(self, lon: float, lat: float, start: date, end: date, data_format: str = "JSON") -> str:
        query = urlencode(
            {
                "parameters": ",".join(self.config["parameters"]),
                "community": self.config["community"],
                "longitude": f"{lon:.{POINT_DECIMALS}f}",
                "latitude": f"{lat:.{POINT_DECIMALS}f}",
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": data_format,
            }
        )
        return f"{self.config['url']}/daily/point?{query}"

    def fetch(self, lon: float, lat: float, start: date, end: date) -> dict:
        url = self.data_url(lon, lat, start, end)
        try:
            response = self._http_get(url, timeout=self.config["timeout_s"])
        except httpx.HTTPError as error:
            raise SourceError(f"NASA POWER no responde: {error}") from error
        if response.status_code != 200:
            raise SourceError(f"NASA POWER respondió {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as error:
            raise SourceError("NASA POWER devolvió una respuesta que no es JSON.") from error

    def parse_series(self, payload: dict) -> list[dict]:
        """Daily rows {'date': 'YYYY-MM-DD', 'T2M': 21.3, ...}; missing values become None."""
        parameters = payload["properties"]["parameter"]
        fill = payload.get("header", {}).get("fill_value", self.config["fill_value"])
        days = sorted(next(iter(parameters.values())).keys())
        rows = []
        for day in days:
            row = {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}"}
            for name in self.config["parameters"]:
                value = parameters.get(name, {}).get(day)
                row[name] = None if value is None or value == fill else value
            rows.append(row)
        return rows

    def build_item(self, lon: float, lat: float, start: date, end: date, rows: list[dict]) -> dict:
        lon, lat = round(lon, POINT_DECIMALS), round(lat, POINT_DECIMALS)
        item_id = f"power-{lat:.{POINT_DECIMALS}f}_{lon:.{POINT_DECIMALS}f}-{start:%Y%m%d}-{end:%Y%m%d}"
        valid_days = [row for row in rows if any(row[name] is not None for name in self.config["parameters"])]
        assets = {
            "data": {
                "href": self.data_url(lon, lat, start, end, "JSON"),
                "type": "application/json",
                "roles": ["data"],
                "title": "Serie diaria (JSON)",
            },
            "csv": {
                "href": self.data_url(lon, lat, start, end, "CSV"),
                "type": "text/csv",
                "roles": ["data"],
                "title": "Serie diaria (CSV)",
            },
        }
        return {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": item_id,
            "collection": self._collection["catalog_id"],
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "bbox": [lon, lat, lon, lat],
            "properties": {
                "datetime": None,
                "start_datetime": _utc(start),
                "end_datetime": _utc(end, end_of_day=True),
                SOURCE_PROPERTY: self.source_id,
                SOURCE_COLLECTION_PROPERTY: COLLECTION_KEY,
                "cultivos:parameters": list(self.config["parameters"]),
                "cultivos:valid_days": len(valid_days),
            },
            "assets": assets,
            "links": [],
        }

    def search(self, request: SearchRequest) -> list[dict]:
        lon, lat = bbox_center(request.bbox)
        payload = self.fetch(lon, lat, request.start, request.end)
        rows = self.parse_series(payload)
        return [self.build_item(lon, lat, request.start, request.end, rows)]

    def climate(self, bbox: list[float], start: date, end: date) -> dict:
        """Daily series and its catalog item for the center of a bbox."""
        lon, lat = bbox_center(bbox)
        rows = self.parse_series(self.fetch(lon, lat, start, end))
        return {
            "item": self.build_item(lon, lat, start, end, rows),
            "daily": rows,
            "monthly": monthly(rows, self.config["parameters"]),
        }

    def get_item(self, catalog_collection: str, item_id: str) -> dict:
        raise SourceError("NASA POWER no tiene ítems propios: se generan al buscar una zona y un período.")

    def collections(self) -> list[dict]:
        parameters = {name: f"{meta['title']} ({meta['unit']})" for name, meta in self.config["parameters"].items()}
        return [collection_template(self.source_id, self.config, self._collection, {"cultivos:parameters": parameters})]


def bbox_center(bbox: list[float]) -> tuple[float, float]:
    west, south, east, north = bbox
    return (west + east) / 2, (south + north) / 2


def monthly(rows: list[dict], parameters: dict) -> list[dict]:
    """Monthly value per parameter ('mean' or 'sum' as configured), ignoring missing days."""
    months: dict[str, list[dict]] = {}
    for row in rows:
        months.setdefault(row["date"][:7], []).append(row)
    result = []
    for month, days in sorted(months.items()):
        entry = {"month": month, "days": len(days)}
        for name, meta in parameters.items():
            values = [day[name] for day in days if day.get(name) is not None]
            if not values:
                entry[name] = None
            elif meta["monthly"] == "sum":
                entry[name] = round(sum(values), 1)
            else:
                entry[name] = round(sum(values) / len(values), 1)
        result.append(entry)
    return result


def _utc(day: date, end_of_day: bool = False) -> str:
    return f"{day.isoformat()}T{'23:59:59' if end_of_day else '00:00:00'}Z"
