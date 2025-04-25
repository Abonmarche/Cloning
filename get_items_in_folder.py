"""
get_items_in_folder.py
Helper usage examples
--------------------
# 1) Re-use an existing GIS
gis = get_gis("Abonmarche")
ids = get_items_in_folder("Testing", gis)

# 2) Let the helper log in (must pass city name explicitly)
ids = get_items_in_folder("Testing", "Abonmarche")
"""

from typing import List, Union
from arcgis.gis import GIS
from log_into_gis import get_gis


# ------------------------------------------------------------------
# Internal: given a logged-in GIS, return item IDs in *folder*
# ------------------------------------------------------------------
def _item_ids_in_folder(gis: GIS, folder: str) -> List[str]:
    user = gis.users.me

    if folder.lower() in {"", "/", "root"}:
        items = user.items()
    else:
        if folder not in (f["title"] for f in user.folders):
            raise ValueError(f"Folder '{folder}' not found for user {user.username}")
        items = user.items(folder=folder)

    return [itm.itemid for itm in items]


# ------------------------------------------------------------------
# Public helper: no keyword-only args, no silent defaults
# ------------------------------------------------------------------
def get_items_in_folder(folder: str, conn: Union[GIS, str]) -> List[str]:
    """
    Return a list of item IDs in *folder*.

    Parameters
    ----------
    folder : str
        Folder title (use "" or "root" for the root folder).
    conn : Union[GIS, str]
        • Pass a logged-in `GIS` object to reuse it, **or**
        • Pass a city-name string to have the helper log in via `get_gis(city)`.

    Examples
    --------
    >>> gis = get_gis("Abonmarche")
    >>> ids = get_items_in_folder("Testing", gis)        # uses existing GIS
    >>> ids = get_items_in_folder("Testing", "Abonmarche")  # logs in internally
    """
    if isinstance(conn, GIS):
        gis = conn
    elif isinstance(conn, str):
        gis = get_gis(conn)          # explicit login—no default city
    else:
        raise TypeError("Second argument must be a GIS object or a city-name string.")

    return _item_ids_in_folder(gis, folder)


__all__ = ["get_items_in_folder"]
