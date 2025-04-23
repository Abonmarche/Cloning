from pathlib import Path
import yaml
from arcgis.gis import GIS

# --- GIS functions ---
def load_config(path: str | Path) -> dict:
    """Read YAML with portal credentials."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def connect(city: str, cfg: dict) -> GIS:
    """Return an authenticated GIS object for *city*."""
    creds = cfg["cities"][city]
    gis = GIS(creds["url"], creds["username"], creds["password"])
    print(f"✓ Connected to {city} ({gis.properties.portalName})")
    return gis


def gather_items(gis_src: GIS, ids: list[str]):
    """Retrieve a list of Item objects; raise if any ID is missing."""
    missing = [i for i in ids if gis_src.content.get(i) is None]
    if missing:
        raise ValueError(f"IDs not found in source: {missing}")
    return [gis_src.content.get(i) for i in ids]

# --- main ---
def clone(
    source: GIS,
    target: GIS,
    item_ids: list[str],
    *,
    folder: str | None = None,
    owner: str | None = None,
    search_existing: bool = False,
    copy_data: bool = True,
    preserve_ids: bool = False,
    export_data: bool = False,
    preserve_editing: bool = False
):
    """Clone *item_ids* from *source* to *target* in one call."""
    items = gather_items(source, item_ids)

    portal_label = (
        getattr(target.properties, "urlKey", None)         
        or getattr(target.properties, "portalHostname", "")
        or target.url                                      
    )

    print(
        f"Cloning {len(items)} items → {portal_label} "
        f"(folder={folder or 'root'}, owner={owner or target.users.me.username})"
    )

    cloned = target.content.clone_items(
        items=items,
        folder=folder,
        owner=owner,
        search_existing_items=search_existing,
        copy_data=copy_data,
        preserve_item_id=preserve_ids,
        export_service=export_data,
        preserve_editing_info=preserve_editing
    )
    print(f"✓ {len(cloned)} items cloned successfully")
    return cloned


# --- execute ----
if __name__ == "__main__":
    cfg = load_config("../CityLogins.yaml")

    src_gis  = connect("Abonmarche",      cfg)
    dest_gis = connect("AbonmarcheDemo",  cfg)

    items_to_clone = [
        "1b7309fdb0a7470bb7efbae847f2abc3"
        # add more IDs here
    ]

    cloned_items = clone(
        src_gis,
        dest_gis,
        items_to_clone,
        folder="Testing",      # or None for root
        search_existing=False,
        copy_data=True,
        preserve_ids=False,    # Enterprise only
        export_data=False, 
        preserve_editing=False
    )
