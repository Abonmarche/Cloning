"""
log_into_gis.py
Minimal helper with two opt-in functions:

    get_gis(city)        -> GIS
    is_enterprise(city)  -> bool
"""

from pathlib import Path
import yaml
from arcgis.gis import GIS

# -------------------------------------------------
# Config file:  ../CityLogins.yaml   (one level up)
# -------------------------------------------------
CONFIG_PATH = (Path(__file__).parent / ".." / "CityLogins.yaml").resolve()


# -------------------------------------------------
# Internal config loader (cached after first read)
# -------------------------------------------------
def _load_config(path: Path = CONFIG_PATH) -> dict:
    if not hasattr(_load_config, "_cache"):
        with path.open(encoding="utf-8") as f:
            _load_config._cache = yaml.safe_load(f)
    return _load_config._cache


# -------------------------------------------------
# Public helpers
# -------------------------------------------------
def get_gis(city: str) -> GIS:
    """Return an authenticated GIS object for *city*."""
    cfg = _load_config()
    creds = cfg["cities"][city]
    gis = GIS(creds["url"], creds["username"], creds["password"])
    print(f"✓ Connected to {city} ({gis.properties.portalName})")
    return gis


def is_enterprise(city: str) -> bool:
    """Return True if *city* entry is Enterprise; else False."""
    cfg = _load_config()
    return bool(cfg["cities"][city].get("is_enterprise", False))


__all__ = ["get_gis", "is_enterprise"]   # only export the two helpers
