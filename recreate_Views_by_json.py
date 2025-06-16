"""
Hosted Feature Layer View • Definition Copier
------------------------------------------------
Reads the full service and item JSON from an existing
feature layer view and recreates a new view with the
same configuration.  All fields, view definitions and
item visualization are preserved.  Inspired by
`recreate_FeatureLayer_by_json.py`.
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from arcgis._impl.common._mixins import PropertyMap
from datetime import datetime
import re
import json
import uuid

# ---------------------------------------------------------------------
# Configuration - edit these before running
# ---------------------------------------------------------------------
USERNAME = "gargarcia"
PASSWORD = "GOGpas5252***"
SOURCE_VIEW_ITEM_ID = "604b386212074e129c0ebbe5e12cd2bd"  # id of view to copy
# ---------------------------------------------------------------------


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _pm_to_dict(o):
    """Recursively convert Esri PropertyMap objects to plain dicts."""
    if isinstance(o, PropertyMap):
        o = dict(o)
    if isinstance(o, dict):
        return {k: _pm_to_dict(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_pm_to_dict(i) for i in o]
    return o


def _safe_name(title, uid=8, max_len=30):
    core_max = max_len - uid - 1
    core = re.sub(r"[^0-9A-Za-z]", "_", title).strip("_").lower()
    core = re.sub(r"__+", "_", core)[:core_max]
    return f"{core}_{uuid.uuid4().hex[:uid]}"


# ---------------------------------------------------------------------
# Main cloning logic
# ---------------------------------------------------------------------
def clone_view(username: str, password: str, view_item_id: str):
    gis = GIS("https://www.arcgis.com", username, password)
    print(f"✓ Signed in as {gis.users.me.username}")

    src_item = gis.content.get(view_item_id)
    if not src_item:
        raise ValueError(f"Item {view_item_id} not found")
    print(f"Cloning view: {src_item.title} ({src_item.id})")

    src_flc = FeatureLayerCollection.fromitem(src_item)

    # --- download current service definition ---
    svc_def = _pm_to_dict(src_flc.manager.generate_service_definition())
    layers = svc_def.pop("layers", [])
    tables = svc_def.pop("tables", [])
    for lyr in layers:
        lyr.pop("id", None)
    for tbl in tables:
        tbl.pop("id", None)

    # --- get item visualization (item JSON) ---
    item_data = None
    try:
        item_data = src_item.get_data()
    except Exception:
        pass

    wkid = svc_def.get("spatialReference", {}).get("wkid", 4326)
    new_name = _safe_name(src_item.title)
    new_item = gis.content.create_service(
        name=new_name,
        is_view=True,
        wkid=wkid,
        tags=src_item.tags or ["view", "clone"],
        snippet=f"Clone of {src_item.title}"
    )
    new_flc = FeatureLayerCollection.fromitem(new_item)
    print("✓ Empty view created")

    add_def = {}
    if layers:
        add_def["layers"] = layers
    if tables:
        add_def["tables"] = tables
    if add_def:
        new_flc.manager.add_to_definition(add_def)
        print("✓ Layer and table definitions applied")

    if svc_def:
        new_flc.manager.update_definition(svc_def)
        print("✓ Service properties updated")

    if item_data:
        try:
            new_item.update(data=item_data)
            print("✓ Item visualization copied")
        except Exception as e:
            print(f"⚠ Could not update item visualization: {e}")

    title = f"{src_item.title}_clone_{datetime.now():%Y%m%d_%H%M%S}"
    new_item.update(item_properties={"title": title})
    print(f"Clone ready → {new_item.homepage}")
    return new_item


if __name__ == "__main__":
    try:
        clone_view(USERNAME, PASSWORD, SOURCE_VIEW_ITEM_ID)
    except Exception as e:
        print(f"Error: {e}")
