"""
Instant App Recreation Script
This script takes an Instant-App item ID, extracts its JSON definition,
and publishes a brand-new Instant App with the same configuration.

Workflow:
  1. sign in
  2. fetch the original item's description & data JSON
  3. scrub only truly unique keys (leave `source`)
  4. post the JSON as the new item's `text`
  5. patch the item's `url` so AGOL shows the View button
  6. save before/after JSON for verification
"""

from arcgis.gis import GIS
import json
from copy import deepcopy
from datetime import datetime

# ─── PARAMETERS TO MODIFY ─────────────────────────────────────────────────────
username = "gargarcia"
password = "GOGpas5252***"
item_id  = "63fb774ada734dc0af6673485ea94a27"
# ──────────────────────────────────────────────────────────────────────────────


def recreate_instant_app(username: str, password: str, item_id: str):
    """
    Recreates an Instant-App (Web Mapping Application) item.

    Returns
    -------
    arcgis.gis.Item
        The newly created Instant-App item.
    """

    # STEP 1 ─ Sign in
    print("Connecting to ArcGIS Online …")
    gis = GIS("https://www.arcgis.com", username, password)
    print(f"✓ Signed in as: {gis.users.me.username}")

    # STEP 2 ─ Get source item
    print(f"\nFetching Instant App with ID: {item_id}")
    src_item = gis.content.get(item_id)
    if not src_item:
        raise ValueError(f"No item found with ID {item_id}")

    if src_item.type != "Web Mapping Application":
        raise ValueError(
            f"Item {item_id} is not a Web Mapping Application "
            f"(it's a {src_item.type})"
        )

    print(f"Found Instant App: {src_item.title}")
    print(f"Type keywords: {src_item.typeKeywords}")

    # STEP 3 ─ Extract data JSON
    print("\nExtracting Instant-App data JSON …")
    src_json = src_item.get_data() or {}
    backup_fn = f"instantapp_{item_id}_backup.json"
    with open(backup_fn, "w", encoding="utf-8") as f:
        json.dump(src_json, f, indent=2)
    print(f"• Saved source JSON → {backup_fn}")

    wm_count = len(src_json.get("values", {}).get("mapItemCollection", []))
    print(f"• Contains {wm_count} web map(s)")

    # STEP 4 ─ Scrub unique keys (KEEP `source` so Builder loads)
    scrubbed = deepcopy(src_json)
    for key in ("datePublished", "id"):  # only truly unique keys
        scrubbed.pop(key, None)

    # bump internal title so builder UI matches AGOL title
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{src_item.title}_recreated_{ts}"
    scrubbed.setdefault("values", {})["title"] = new_title

    # STEP 5 ─ Prepare item properties
    item_props = {
        "type"       : "Web Mapping Application",
        "title"      : new_title,
        "tags"       : src_item.tags or ["python", "recreated", "instant app"],
        "snippet"    : src_item.snippet
                       or f"Recreated from {src_item.title}",
        "description": src_item.description
                       or f"Cloned from item {item_id}",
        "text"       : json.dumps(scrubbed)  # <─ core payload
    }

    for field in ("accessInformation", "licenseInfo", "culture",
                  "access", "typeKeywords", "extent"):
        if getattr(src_item, field, None):
            item_props[field] = getattr(src_item, field)

    # STEP 6 ─ Publish the new item
    print(f"\nCreating new Instant App: {new_title}")
    new_item = gis.content.add(item_properties=item_props)
    print("✓ New Instant-App item created")
    print(f"  • ID : {new_item.id}")

    # STEP 6a ─ Build & set URL so “View” button appears
    if src_item.url:
        base_url = src_item.url.split("?appid=")[0]  # template path only
        new_url  = f"{base_url}?appid={new_item.id}"
        new_item.update(item_properties={"url": new_url})
        print(f"  • URL: {new_url}")
    else:
        print("  • Source item had no URL; skipping URL patch")

    # STEP 7 ─ Verify
    print("\nVerifying JSON …")
    new_json = new_item.get_data() or {}
    missing = set(src_json) - set(new_json)
    extra   = set(new_json) - set(src_json)
    if missing:
        print(f"⚠ Keys missing in clone: {missing}")
    if extra:
        print(f"⚠ Extra keys in clone: {extra}")
    if not missing and not extra:
        print("✓ Top-level keys match")

    new_backup = f"instantapp_{new_item.id}_created.json"
    with open(new_backup, "w", encoding="utf-8") as f:
        json.dump(new_json, f, indent=2)
    print(f"• Saved clone JSON → {new_backup}")

    print(f"\nMap count — original: {wm_count} | new: "
          f"{len(new_json.get('values', {}).get('mapItemCollection', []))}")

    return new_item


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        recreated_item = recreate_instant_app(username, password, item_id)

        print("\n" + "=" * 50)
        print("Instant App recreation completed successfully!")
        print("=" * 50)

        print("\nNOTE:")
        print("• The cloned app references the same data sources as the original.")
        print("  Update the JSON if you need to repoint maps or layers.")
        print("• If the original used premium or subscriber content, ensure the")
        print("  new owner has equivalent privileges.")

    except Exception as err:
        print(f"\nError: {err}")
        import traceback
        traceback.print_exc()
