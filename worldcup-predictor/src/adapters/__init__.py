"""External-source adapters and their shared contract."""
from .api_football import ApiFootballAdapter
from .base import (
    AdapterError,
    AdapterMethodNotSupported,
    BaseDataSourceAdapter,
    DataFetchError,
)
from .fbref import FBrefAdapter
from .odds_api import OddsApiAdapter
from .odds_portal import OddsPortalAdapter
from .static_data import StaticDataAdapter
from .transfermarkt import TransfermarktAdapter

__all__ = [
    "AdapterError",
    "AdapterMethodNotSupported",
    "ApiFootballAdapter",
    "BaseDataSourceAdapter",
    "DataFetchError",
    "FBrefAdapter",
    "OddsApiAdapter",
    "OddsPortalAdapter",
    "StaticDataAdapter",
    "TransfermarktAdapter",
]
