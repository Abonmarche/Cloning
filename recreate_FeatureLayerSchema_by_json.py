"""
Hosted Feature-Service • Minimal Schema Cloner
---------------------------------------------
Creates an EMPTY hosted feature service whose schema (layers, tables,
fields, domains, relationships) mirrors a source hosted Feature Service.
No features or rendering are copied.

New clone is titled:
    <SourceTitle>_schemaCopy_<YYYYMMDD_HHMMSS>
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from arcgis._impl.common._mixins import PropertyMap
import json, re, uuid
from datetime import datetime

# ── EDIT THESE ────────────────────────────────────────────────────────────────
USERNAME = "<your_username>"
PASSWORD = "<your_password>"
ITEM_ID  = "59ad9d29b3c444c888e921db6ea7f092"   # source hosted layer
# ──────────────────────────────────────────────────────────────────────────────


# --- helpers ------------------------------------------------------------------
def _pm_to_dict(o):
    """Recursively convert PropertyMap → plain dict."""
    if isinstance(o, PropertyMap):
        o = dict(o)
    if isinstance(o, dict):
        return {k: _pm_to_dict(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_pm_to_dict(i) for i in o]
    return o


def _safe_name(title, length=24):
    """Generate URL-safe internal service name (≤30 chars) + UUID suffix."""
    core = re.sub(r"[^0-9A-Za-z]", "_", title).strip("_").lower()
    core = re.sub(r"__+", "_", core)[:length]
    return f"{core}_{uuid.uuid4().hex[:8]}"


# --- main ---------------------------------------------------------------------
def clone_schema_only(username, password, item_id):
    gis = GIS("https://www.arcgis.com", username, password)
    print(f"✓ Signed in as {gis.users.me.username}")

    src_item = gis.content.get(item_id)
    if not src_item or src_item.type.lower() != "feature service":
        raise ValueError("Source item must be a hosted Feature Service")
    print(f"Cloning schema from: {src_item.title}")

    src_flc = FeatureLayerCollection.fromitem(src_item)
    layer_defs = [_pm_to_dict(l.properties) for l in src_flc.layers]
    table_defs = [_pm_to_dict(t.properties) for t in src_flc.tables]
    print(f"• Layers: {len(layer_defs)} | Tables: {len(table_defs)}")

    # 1. create empty service with safe internal name
    internal_name = _safe_name(src_item.title)
    create_params = {
        "name"               : internal_name,
        "serviceDescription" : "",
        # convert spatialReference to plain dict  ← FIX
        "spatialReference"   : _pm_to_dict(src_flc.properties.spatialReference),
        "hasStaticData"      : False,
        "capabilities"       : "Query",
    }

    new_item = gis.content.create_service(
        name=internal_name,
        service_type="featureService",
        create_params=create_params,
        tags=src_item.tags or ["schema copy"],
        snippet=f"Schema copy of {src_item.title}"
    )
    print("✓ Empty service created")

    # 2. post schema
    FeatureLayerCollection.fromitem(new_item).manager.add_to_definition(
        {"layers": layer_defs, "tables": table_defs}
    )
    print("✓ Schema posted to clone")

    # 3. rename item to <Title>_schemaCopy_<YYYYMMDD_HHMMSS>
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{src_item.title}_schemaCopy_{ts}"
    new_item.update(item_properties={"title": new_title})
    print(f"✓ Renamed clone → {new_title}")

    print(f"\nClone ready → {new_item.homepage}")
    return new_item


# --- run ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        clone_schema_only(USERNAME, PASSWORD, ITEM_ID)
    except Exception as e:
        print(f"\nError: {e}")
