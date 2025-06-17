"""
View-Layer Recreation Script - Updated
──────────────────────────────────────
Handles view layers that exclude certain layers from the source
and properly applies field visibility per layer
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import json, os, sys
from datetime import datetime
from copy import deepcopy
import logging
import requests

# ═════ MODIFY FOR TESTING ════════════════════════════════════════════════════
USERNAME   = "gargarcia"
PASSWORD   = "GOGpas5252***"
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
    
    # Helper to get source layer ID
    def _source_id(lyr):
        try:
            return lyr.properties.viewLayerDefinition["sourceLayerId"]
        except Exception:
            return lyr.properties.get("sourceLayerId", lyr.properties.id)
    
    # Process layers - collect which layers to include in view
    view_layers = []
    layer_definitions = {}  # Store layer-specific configurations
    
    for lyr in src_flc.layers:
        layer_id = _source_id(lyr)
        view_layers.append(layer_id)
        
        # Store layer-specific configuration
        layer_config = {
            'query': None,
            'visible_fields': [],
            'view_definition': None
        }
        
        # Extract view definition if it exists
        if hasattr(lyr.properties, 'viewLayerDefinition'):
            view_def = lyr.properties.viewLayerDefinition
            layer_config['view_definition'] = view_def
            
            # Extract query
            if 'filter' in view_def and 'where' in view_def['filter']:
                layer_config['query'] = view_def['filter']['where']
            
            # Extract visible fields
            if 'fields' in view_def:
                for field in view_def['fields']:
                    if field.get('visible', True):
                        layer_config['visible_fields'].append(field['name'])
        
        layer_definitions[layer_id] = layer_config
    
    # Process tables
    view_tables = []
    for tbl in src_flc.tables:
        table_id = _source_id(tbl)
        view_tables.append(table_id)
    
    config['view_layers'] = view_layers if view_layers else None
    config['view_tables'] = view_tables if view_tables else None
    config['layer_definitions'] = layer_definitions
    
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
    
    # Log which layers are included in the view
    if view_config.get('view_layers'):
        logging.info(f"📋 View includes layer IDs: {view_config['view_layers']}")
    if view_config.get('view_tables'):
        logging.info(f"📋 View includes table IDs: {view_config['view_tables']}")

    # 8️⃣ create new view name with timestamp
    ts_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{src_item.title}_clone_{ts_suffix}"
    
    # 9️⃣ Map layer IDs to actual layer objects from parent
    view_layer_objects = None
    view_table_objects = None
    
    if view_config.get('view_layers'):
        view_layer_objects = []
        for layer_id in view_config['view_layers']:
            # Find the layer object with matching ID
            for lyr in parent_flc.layers:
                if lyr.properties.id == layer_id:
                    view_layer_objects.append(lyr)
                    logging.info(f"  • Including layer {layer_id}: {lyr.properties.name}")
                    break
    
    if view_config.get('view_tables'):
        view_table_objects = []
        for table_id in view_config['view_tables']:
            # Find the table object with matching ID
            for tbl in parent_flc.tables:
                if tbl.properties.id == table_id:
                    view_table_objects.append(tbl)
                    logging.info(f"  • Including table {table_id}: {tbl.properties.name}")
                    break
    
    # 1️⃣0️⃣ create view using FeatureLayerCollection manager
    logging.info(f"🛠 creating view: {new_title}")
    
    new_view_item = parent_flc.manager.create_view(
        name=new_title,
        spatial_reference=view_config.get('spatial_reference'),
        extent=view_config.get('extent'),
        allow_schema_changes=view_config.get('allow_schema_changes', True),
        updateable=view_config.get('updateable', True),
        capabilities=view_config.get('capabilities', 'Query'),
        view_layers=view_layer_objects,  # Pass layer objects, not IDs
        view_tables=view_table_objects,  # Pass table objects, not IDs
        description=view_config.get('description'),
        tags=view_config.get('tags'),
        snippet=view_config.get('snippet'),
        preserve_layer_ids=True
    )
    
    logging.info(f"✓ view created: {new_view_item.id}")

    # 1️⃣1️⃣ copy item-level visualisation (pop-ups, symbology)
    new_view_item.update(data=item_data)
    logging.info("✓ item-level pop-ups & renderers copied")

    # 1️⃣2️⃣ copy additional metadata that might not be in create()
    meta = {
        "licenseInfo": getattr(src_item, "licenseInfo", None),
        "accessInformation": getattr(src_item, "accessInformation", None)
    }
    if any(meta.values()):
        new_view_item.update(item_properties={k: v for k, v in meta.items() if v})
        logging.info("✓ additional metadata copied")

    # 1️⃣3️⃣ apply layer-specific view definitions
    new_flc = FeatureLayerCollection.fromitem(new_view_item)
    layer_definitions = view_config.get('layer_definitions', {})
    
    # Map source layer IDs to new view layers
    for new_lyr in new_flc.layers:
        # Find source layer ID for this layer
        source_id = None
        if hasattr(new_lyr.properties, 'viewLayerDefinition'):
            source_id = new_lyr.properties.viewLayerDefinition.get('sourceLayerId')
        else:
            # For newly created views, the layer ID might match
            source_id = new_lyr.properties.id
        
        # Apply configuration if we have it for this source layer
        if source_id in layer_definitions:
            layer_config = layer_definitions[source_id]
            update_def = {}
            
            # Apply query if present
            if layer_config.get('query'):
                update_def['viewDefinitionQuery'] = layer_config['query']
            
            # Apply field visibility if present
            if layer_config.get('visible_fields'):
                fields = []
                for field in new_lyr.properties.fields:
                    fields.append({
                        "name": field['name'],
                        "visible": field['name'] in layer_config['visible_fields']
                    })
                update_def['fields'] = fields
            
            # Apply complex view definition if present
            if layer_config.get('view_definition'):
                view_def = layer_config['view_definition']
                # Check for complex spatial filters or other advanced settings
                if 'filter' in view_def and ('geometry' in view_def['filter'] or 
                                              'geometryType' in view_def['filter']):
                    update_def['viewLayerDefinition'] = view_def
            
            if update_def:
                try:
                    new_lyr.manager.update_definition(update_def)
                    logging.info(f"  • layer {new_lyr.properties.name}: view settings applied")
                except Exception as e:
                    logging.warning(f"  • Could not apply view settings to {new_lyr.properties.name}: {e}")

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