"""
List every item ID and item type in a specific ArcGIS Online folder.

⚠️  Hard-coded credentials are handy for quick tests only.
"""

from arcgis.gis import GIS
import sys, inspect

# ───── EDIT THESE ONLY ───────────────────────────────────────────────────
USERNAME    = "xxx"
PASSWORD    = "xxx"
FOLDER_NAME = "json clone content"        # root folder? use ""
# ─────────────────────────────────────────────────────────────────────────

def folders_to_dict(folder_list):
    """
    Accepts either:
      • list[dict]  → [{'title': ..., 'id': ...}, …]
      • list[Folder] → objects with .title / .id
    Returns {title: id}
    """
    mapping = {}
    for f in folder_list:
        if isinstance(f, dict):            # old API shape
            mapping[f["title"]] = f["id"]
        else:                              # Folder object
            mapping[f.title] = f.id
    return mapping


def main():
    print("🔐  Connecting to ArcGIS Online…", end=" ", flush=True)
    gis = GIS("https://www.arcgis.com", USERNAME, PASSWORD)
    print(f"✓ Signed in as: {gis.users.me.username}")

    me = gis.users.me

    # --- Locate folder ---------------------------------------------------
    if FOLDER_NAME in ("", None):                          # root content
        items = list(me.items())                           # 👈 wrap in list()
    else:
        try:
            items = list(me.items(folder=FOLDER_NAME))     # 👈 wrap in list()
        except TypeError:
            folders = {f.title: f.id for f in me.folders}
            if FOLDER_NAME not in folders:
                sys.exit(f"❌ Folder '{FOLDER_NAME}' not found.")
            items = list(me.items(folder=folders[FOLDER_NAME]))   # 👈

    if not items:
        print(f"⚠️  Folder '{FOLDER_NAME or '[root]'}' is empty.")
        return

    # --- Display table ---------------------------------------------------
    print(f"\n📂 Contents of '{FOLDER_NAME or '[root]'}':")
    print(f"{'Item ID':<36}  Item Type")
    print(f"{'-'*36}  {'-'*30}")
    for itm in items:
        print(f"{itm.itemid:<36}  {itm.type}")
    print(f"\n✓ {len(items)} item(s) listed.")


if __name__ == "__main__":
    main()
