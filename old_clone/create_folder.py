"""
Create an ArcGIS Online folder under the signed-in user account.

⚠️  Security reminder
Hard-coding credentials is fine for quick tests, but use environment
variables or a secure vault in production code.
"""

from arcgis.gis import GIS


# ───── EDIT THESE ONLY ────────────────────────────────────────────────────
URL          = "https://www.arcgis.com" 
USER      = "xxx"           # AGOL username
PASS      = "xxx"          # AGOL password
FOLDER   = "My New Folder"         # Folder title you want to create
# ──────────────────────────────────────────────────────────────────────────

gis  = GIS(URL, USER, PASS)
me   = gis.users.me

def folder_id(obj):
    """Return a folder’s ID from a Folder object or any dict shape."""
    if obj is None:
        return None
    if hasattr(obj, "id"):
        return obj.id
    if isinstance(obj, dict):
        if "id" in obj:
            return obj["id"]
        if "folder" in obj and isinstance(obj["folder"], dict):
            return obj["folder"].get("id")
    return None

def create_folder(title):
    """Create folder with whichever API call exists, return its ID."""
    try:
        # Newer API (2.3+) — returns a Folder object
        return folder_id(gis.content.folders.create(title, owner=me.username))
    except AttributeError:
        # Older API (<2.3) — returns a dict
        return folder_id(gis.content.create_folder(title, owner=me.username))

try:
    fid = create_folder(FOLDER)
    print(f"✅  Folder '{FOLDER}' ready (ID: {fid})")

except Exception as exc:
    # Duplicate-name error?  Tell the user the existing folder’s ID.
    msg = str(exc).lower()
    if "exists" in msg or "duplicate" in msg:
        existing = next(
            (f for f in me.folders
             if (getattr(f, "title", f.get("title", None)) == FOLDER)), None)
        print(f"⚠️  Folder '{FOLDER}' already exists "
              f"(ID: {folder_id(existing) or 'unknown'}).")
    else:
        raise  # some other unexpected problem