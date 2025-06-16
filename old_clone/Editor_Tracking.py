import json
from pathlib import Path
import datetime
import yaml
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import re

# --- gis functions ---

def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def connect(city: str, cfg: dict):
    creds = cfg["cities"][city]
    gis = GIS(creds["url"], creds["username"], creds["password"])
    print(f"Connected to {city} ({gis.url})")
    return gis, creds.get("is_enterprise", False)

# --- Editor tracking functions ---

def record_editor_tracking(gis: GIS, item_id: str, output_folder: Path = Path(".")) -> Path:
    """
    Reads and saves editor-tracking settings and returns the Path to the backup JSON.
    """
    item = gis.content.get(item_id)
    flc  = FeatureLayerCollection.fromitem(item)

    # create a safe timestamped filename
    now        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^\w\-]", "_", item.title)
    backup_file = output_folder / "json_files" / f"{safe_title}_{now}.json"

    # service-level settings
    root = flc.properties.editorTrackingInfo
    root_cfg = {
        "enableEditorTracking":         root.enableEditorTracking,
        "enableOwnershipAccessControl": root.enableOwnershipAccessControl,
        "allowOthersToQuery":           root.allowOthersToQuery,
        "allowOthersToUpdate":          root.allowOthersToUpdate,
        "allowOthersToDelete":          root.allowOthersToDelete,
        "allowAnonymousToQuery":        root.allowAnonymousToQuery,
        "allowAnonymousToUpdate":       root.allowAnonymousToUpdate,
        "allowAnonymousToDelete":       root.allowAnonymousToDelete
    }

    # sublayer editFieldsInfo to dict
    sublayers = {}
    for lyr in flc.layers:
        info_pm = lyr.properties.editFieldsInfo
        if info_pm:
            sublayers[str(lyr.properties.id)] = dict(info_pm)

    cfg = {"root": root_cfg, "sublayers": sublayers}

    backup_file.write_text(json.dumps(cfg, indent=2))
    print(f"Recorded editor tracking to {backup_file}")
    return backup_file


def disable_editor_tracking(gis: GIS, item_id: str) -> None:
    item = gis.content.get(item_id)
    flc  = FeatureLayerCollection.fromitem(item)

    flc.manager.update_definition({"editorTrackingInfo": {"enableEditorTracking": False}})
    for lyr in flc.layers:
        lyr.manager.update_definition({"editFieldsInfo": {}})
    print("Editor tracking disabled")


def enable_editor_tracking(gis: GIS, item_id: str, backup_file: Path) -> None:
    """
    Restores editor-tracking settings from the given backup_file.
    """
    item = gis.content.get(item_id)
    flc  = FeatureLayerCollection.fromitem(item)

    cfg = json.loads(backup_file.read_text())
    flc.manager.update_definition({"editorTrackingInfo": cfg["root"]})

    for lyr in flc.layers:
        sid = str(lyr.properties.id)
        if sid in cfg["sublayers"]:
            lyr.manager.update_definition({"editFieldsInfo": cfg["sublayers"][sid]})
    print(f"Editor tracking restored from {backup_file}")

# ---- execute ---

if __name__ == "__main__":
    cfg = load_config("../CityLogins.yaml")
    gis, _ = connect("Abonmarche", cfg)

    ITEM_ID = "22c30f724910461e9c16ff438c1bf848"

    backup_path = record_editor_tracking(gis, ITEM_ID)

    disable_editor_tracking(gis, ITEM_ID)

    enable_editor_tracking(gis, ITEM_ID, backup_path)

    # delete the backup file
    backup_path.unlink(missing_ok=True)
    
