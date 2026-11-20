"""Registry of data sources. Active sources get an adapter; postponed ones only describe themselves."""

from cultivos.adapters.base import Adapter, source_info
from cultivos.adapters.conae import ConaeSaocomAdapter
from cultivos.adapters.earth_search import EarthSearchAdapter
from cultivos.adapters.power import PowerAdapter
from cultivos.config import load_sources_config

ACTIVE_STATUS = "activa"
ADAPTER_TYPES: dict[str, type[Adapter]] = {
    "earth-search": EarthSearchAdapter,
    "nasa-power": PowerAdapter,
    "conae-saocom": ConaeSaocomAdapter,
}


class UnknownSource(LookupError):
    pass


def active_adapters() -> dict[str, Adapter]:
    sources = load_sources_config()
    return {
        source_id: ADAPTER_TYPES[source_id](source_id, config)
        for source_id, config in sources.items()
        if config["status"] == ACTIVE_STATUS and source_id in ADAPTER_TYPES
    }


def get_adapter(source_id: str) -> Adapter:
    adapters = active_adapters()
    if source_id not in adapters:
        raise UnknownSource(f"La fuente {source_id} no existe o no está activa.")
    return adapters[source_id]


def all_sources_info() -> list[dict]:
    return [source_info(source_id, config) for source_id, config in load_sources_config().items()]


def adapter_for_collection(catalog_collection: str) -> Adapter:
    for adapter in active_adapters().values():
        if any(collection["catalog_id"] == catalog_collection for collection in adapter.config["collections"].values()):
            return adapter
    raise UnknownSource(f"Ninguna fuente activa escribe la colección {catalog_collection}.")
