"""
View-Layer Recreation Script
────────────────────────────
Takes the **item ID** of an ArcGIS Online *view* layer (Feature Layer (View)),
dumps every JSON definition it relies on, and builds a brand-new view with all
the same layers / tables, field visibility, filters, capabilities, and pop-ups.

• All JSON blobs it touches are written to ./json_files with a timestamp
• Hard-coded creds & item-ID are *only* for testing; swap in env-vars or
  argparse later.
• Does NOT copy sharing/group permissions - only creates the view structure
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import json, os, sys
from datetime import datetime
from copy import deepcopy
import logging
import requests

# ═════ MODIFY FOR TESTING ════════════════════════════════════════════════════
USERNAME   = "xxx"
PASSWORD   = "xxx"
SRC_VIEWID = "f2cc9a9d588446309eafb81698621ed5"   # ← the view layer to clone
# ════════════════════════════════════════════════════════════════════════════

# ───── helper ▸ timestamped JSON dump ────────────────────────────────────────
TS      = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTDIR  = "json_files"
os.makedirs(OUTDIR, exist_ok=True)

def jdump(obj, label):
    """Write obj to ./json_files/<label>_<timestamp>.json and return that path."""
    path = f"{OUTDIR}/{label}_{TS}.json"
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, indent=2)
    logging.info(f"📄 dumped {label} → {path}")
    return path

# ───── helper ▸ get source layer ID ──────────────────────────────────────────
def get_source_layer_id(gis, view_item):
    """Get the parent hosted feature layer ID for a view layer."""
    # Method 1: Try related_items first
    relationships = view_item.related_items(rel_type="Service2Data")
    if relationships:
        parent = relationships[0]
        logging.info(f"↪ found parent via related_items: {parent.title} ({parent.id})")
        return parent.id
    
    # Method 2: Fallback to /sources endpoint
    sources_url = f"{view_item.url}/sources"
    data = {"token": gis._con.token, "f": "json"}
    r = requests.post(sources_url, data=data)
    
    if r.ok:
        resp = r.json()
        services = resp.get("services", [])
        if services:
            service = services[0]
            parent_id = service.get("serviceItemId")
            logging.info(f"↪ found parent via /sources endpoint: {service.get('name')} ({parent_id})")
            return parent_id
    
    # If both methods fail
    logging.error("Could not determine source (parent) layer item ID")
    return None

# ───── helper ▸ extract view configuration ───────────────────────────────────
def extract_view_config(src_item, src_flc):
    """Extract all configuration from source view for use in create() method."""
    config = {}
    
    # Extract service-level properties
    svc_props = src_flc.properties
    
    # Basic configuration
    config['allow_schema_changes'] = svc_props.get('allowGeometryUpdates', True)
    config['updateable'] = 'Update' in svc_props.get('capabilities', '')
    config['capabilities'] = svc_props.get('capabilities', 'Query')
    
    # Spatial reference and extent
    if 'spatialReference' in svc_props:
        config['spatial_reference'] = svc_props['spatialReference']
    
    if 'initialExtent' in svc_props:
        config['extent'] = svc_props['initialExtent']
    elif 'fullExtent' in svc_props:
        config['extent'] = svc_props['fullExtent']
    
    # Extract layer and table information
    view_layer_ids = []
    view_table_ids = []
    
    # Helper to get source layer ID
    def _source_id(lyr):
        try:
            return lyr.properties.viewLayerDefinition["sourceLayerId"]
        except Exception:
            return lyr.properties.get("sourceLayerId", lyr.properties.id)
    
    # Process layers - collect which layers to include in view
    view_layers = []
    view_tables = []
    visible_fields = []
    query = None
    
    for lyr in src_flc.layers:
        layer_id = _source_id(lyr)
        view_layers.append(layer_id)  # Just the integer ID
        
        # Extract view definition if it exists
        if hasattr(lyr.properties, 'viewLayerDefinition'):
            view_def = lyr.properties.viewLayerDefinition
            
            # Extract query
            if 'filter' in view_def and 'where' in view_def['filter'] and not query:
                query = view_def['filter']['where']
            
            # Extract visible fields
            if 'fields' in view_def:
                for field in view_def['fields']:
                    if field.get('visible', True) and field['name'] not in visible_fields:
                        visible_fields.append(field['name'])
    
    # Process tables
    for tbl in src_flc.tables:
        table_id = _source_id(tbl)
        view_tables.append(table_id)  # Just the integer ID
    
    config['view_layers'] = view_layers if view_layers else None
    config['view_tables'] = view_tables if view_tables else None
    config['visible_fields'] = visible_fields if visible_fields else None
    config['query'] = query
    
    # Extract metadata
    config['description'] = src_item.description
    config['tags'] = ','.join(src_item.tags) if src_item.tags else None
    config['snippet'] = src_item.snippet
    
    return config

# ───── core workflow ─────────────────────────────────────────────────────────
def recreate_view(username, password, view_id):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    logging.info("🔐 connecting to ArcGIS Online…")
    gis = GIS("https://www.arcgis.com", username, password)
    logging.info(f"✓ signed in as: {gis.users.me.username}")

    # 1️⃣ fetch template item
    src_item = gis.content.get(view_id)
    if not src_item:
        logging.error(f"⚠ no item with id {view_id}")
        sys.exit(1)

    # 2️⃣ wrap in FeatureLayerCollection *before* validation
    src_flc = FeatureLayerCollection.fromitem(src_item)
    if not getattr(src_flc.properties, "isView", False):
        logging.error(f"⚠ item {view_id} is not a Feature Layer (View)")
        sys.exit(1)
    logging.info(f"👁 cloning view: {src_item.title} ({view_id})")

    # 3️⃣ dump item-level JSON (pop-ups, renderers, etc.)
    item_data = src_item.get_data()
    jdump(item_data, f"view_item_{view_id}")

    # 4️⃣ dump service JSON
    svc_def = dict(src_flc.properties)
    jdump(svc_def, f"view_service_{view_id}")

    # 5️⃣ dump each sub-layer / table JSON
    for lyr in src_flc.layers + src_flc.tables:
        ldef = dict(lyr.properties)
        label = f"view_layer{lyr.properties.id}_{view_id}"
        jdump(ldef, label)

    # 6️⃣ find parent hosted layer using proper methods
    parent_id = get_source_layer_id(gis, src_item)
    if not parent_id:
        logging.error("⚠ Could not find parent hosted feature layer")
        sys.exit(1)
    
    parent_item = gis.content.get(parent_id)
    parent_flc = FeatureLayerCollection.fromitem(parent_item)
    logging.info(f"↪ parent hosted layer: {parent_item.title} ({parent_id})")

    # 7️⃣ extract view configuration
    view_config = extract_view_config(src_item, src_flc)
    
    # 8️⃣ create new view name with timestamp
    ts_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{src_item.title}_clone_{ts_suffix}"
    
    # 9️⃣ create view using FeatureLayerCollection manager (like Esri blog)
    logging.info(f"🛠 creating view: {new_title}")
    
    # Create the view using the same approach as the Esri blog
    # Don't specify view_layers/view_tables - let it include all layers
    new_view_item = parent_flc.manager.create_view(
        name=new_title,
        spatial_reference=view_config.get('spatial_reference'),
        extent=view_config.get('extent'),
        allow_schema_changes=view_config.get('allow_schema_changes', True),
        updateable=view_config.get('updateable', True),
        capabilities=view_config.get('capabilities', 'Query'),
        description=view_config.get('description'),
        tags=view_config.get('tags'),
        snippet=view_config.get('snippet'),
        preserve_layer_ids=True
        # Not specifying view_layers/view_tables - will include all
    )
    
    logging.info(f"✓ view created: {new_view_item.id}")

    # 1️⃣0️⃣ copy item-level visualisation (pop-ups, symbology)
    # This is still needed as the view_manager.create doesn't handle these
    new_view_item.update(data=item_data)
    logging.info("✓ item-level pop-ups & renderers copied")

    # 1️⃣1️⃣ copy additional metadata that might not be in create()
    meta = {
        "licenseInfo": getattr(src_item, "licenseInfo", None),
        "accessInformation": getattr(src_item, "accessInformation", None)
    }
    if any(meta.values()):
        new_view_item.update(item_properties={k: v for k, v in meta.items() if v})
        logging.info("✓ additional metadata copied")

    # 1️⃣3️⃣ apply view definitions (queries, field visibility)
    # Since we create with all layers, we need to apply the extracted settings
    new_flc = FeatureLayerCollection.fromitem(new_view_item)
    
    # Apply query and field visibility from our extracted config
    if view_config.get('query') or view_config.get('visible_fields'):
        for new_lyr in new_flc.layers:
            update_def = {}
            
            # Apply query if we have one
            if view_config.get('query'):
                update_def['viewDefinitionQuery'] = view_config['query']
            
            # Apply field visibility if we have it
            if view_config.get('visible_fields'):
                # Build field visibility definition
                fields = []
                for field in new_lyr.properties.fields:
                    fields.append({
                        "name": field['name'],
                        "visible": field['name'] in view_config['visible_fields']
                    })
                update_def['fields'] = fields
            
            if update_def:
                try:
                    new_lyr.manager.update_definition(update_def)
                    logging.info(f"  • layer {new_lyr.properties.name}: basic view settings applied")
                except Exception as e:
                    logging.warning(f"  • Could not apply view settings to {new_lyr.properties.name}: {e}")
    
    # Apply any additional layer-specific complex filters
    for i, src_lyr in enumerate(src_flc.layers):
        if hasattr(src_lyr.properties, 'viewLayerDefinition'):
            view_def = src_lyr.properties.viewLayerDefinition
            
            # Check for complex spatial filters or other advanced settings
            if 'filter' in view_def and ('geometry' in view_def['filter'] or 
                                          'geometryType' in view_def['filter']):
                try:
                    new_lyr = new_flc.layers[i]
                    # Apply the full viewLayerDefinition for complex filters
                    update_def = {"viewLayerDefinition": view_def}
                    new_lyr.manager.update_definition(update_def)
                    logging.info(f"  • layer {new_lyr.properties.name}: complex filters applied")
                except Exception as e:
                    logging.warning(f"  • Could not apply complex view definition: {e}")

    # 1️⃣4️⃣ dump the new service JSON for diff-checking
    jdump(dict(new_flc.properties), f"new_view_service_{new_view_item.id}")

    # 1️⃣5️⃣ final summary
    logging.info("\n🎉 View layer recreation complete!")
    logging.info(f"Title : {new_view_item.title}")
    logging.info(f"ItemID: {new_view_item.id}")
    logging.info(f"URL   : {new_view_item.homepage}")
    logging.info(f"Editable: {view_config.get('updateable', True)} (capabilities: {view_config.get('capabilities', 'Query')})")

    return new_view_item

# ── run as script ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        recreate_view(USERNAME, PASSWORD, SRC_VIEWID)
    except Exception as exc:
        logging.exception(f"❌ Error: {exc}")