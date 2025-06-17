"""
Prints the source (parent) layer's item ID for a given ArcGIS Online view layer.
Uses the same login and variable method as recreate_Views_by_json.py.
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import sys
import logging
import requests

# ═════ MODIFY FOR TESTING ════════════════════════════════════════════════════
USERNAME   = "xxx"
PASSWORD   = "xxx"
SRC_VIEWID = "604b386212074e129c0ebbe5e12cd2bd"   # ← the view layer to check
# ════════════════════════════════════════════════════════════════════════════

def print_source_layer_id(username, password, view_id):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    logging.info("🔐 connecting to ArcGIS Online…")
    gis = GIS("https://www.arcgis.com", username, password)
    logging.info(f"✓ signed in as: {gis.users.me.username}")

    src_item = gis.content.get(view_id)
    if not src_item:
        logging.error(f"⚠ no item with id {view_id}")
        sys.exit(1)

    # Try to get the source item via related_items (Service2Data relationship)
    relationships = src_item.related_items(rel_type="Service2Data")
    if relationships:
        parent = relationships[0]
        print(f"Source (parent) layer item ID: {parent.id}")
        print(f"Source (parent) layer title: {parent.title}")
        print(f"Source (parent) layer URL: {parent.url}")
        return

    # If not found, try the /sources endpoint
    sources_url = f"{src_item.url}/sources"
    data = {"token": gis._con.token, "f": "json"}
    r = requests.post(sources_url, data=data)
    if r.ok:
        resp = r.json()
        services = resp.get("services", [])
        if services:
            service = services[0]
            print(f"Source (parent) layer item ID: {service.get('serviceItemId')}")
            print(f"Source (parent) layer name: {service.get('name')}")
            print(f"Source (parent) layer URL: {service.get('url')}")
            return
        else:
            print("No services found in /sources endpoint response.")
    else:
        print(f"Failed to query /sources endpoint: {r.status_code}")
    print("Could not determine source (parent) layer item ID.")

if __name__ == "__main__":
    try:
        print_source_layer_id(USERNAME, PASSWORD, SRC_VIEWID)
    except Exception as exc:
        logging.exception(f"❌ Error: {exc}")
