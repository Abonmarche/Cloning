"""
View-Layer Recreation Script - Updated
──────────────────────────────────────
Handles view layers that exclude certain layers from the source
and properly applies field visibility per layer
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from arcgis.gis import ViewLayerDefParameter  # For complex view updates
import json, os, sys, time
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
        
        # Extract field visibility from the layer properties
        # Views store field visibility in the fields array
        if hasattr(lyr.properties, 'fields'):
            visible_fields = []
            # In a view, the fields that exist ARE the visible fields
            for field in lyr.properties.fields:
                if isinstance(field, dict):
                    visible_fields.append(field['name'])
                else:
                    visible_fields.append(field.name if hasattr(field, 'name') else str(field))
            
            # Store the visible fields
            if visible_fields:
                layer_config['visible_fields'] = visible_fields
                logging.info(f"  📊 Layer {lyr.properties.name}: {len(visible_fields)} fields visible")
        
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
        
        # Debug: Check for field visibility in the layer
        if hasattr(lyr, 'properties') and hasattr(lyr.properties, 'fields'):
            field_count = len(lyr.properties.fields)
            visible_count = sum(1 for f in lyr.properties.fields 
                               if isinstance(f, dict) and f.get('visible', True))
            if visible_count < field_count:
                logging.info(f"  📊 Layer {lyr.properties.name} has field visibility: {visible_count}/{field_count} visible")

    # 5️⃣a - Try to get view definitions using ViewManager (more reliable for field visibility)
    src_view_defs = None
    try:
        src_view_manager = src_item.view_manager
        src_view_defs = src_view_manager.get_definitions(src_item)
        if src_view_defs:
            logging.info(f"📊 Found {len(src_view_defs)} view layer definitions via ViewManager")
    except Exception as e:
        logging.warning(f"⚠ Could not get view definitions via ViewManager: {e}")

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
    
    # 7️⃣a - If we got ViewManager definitions, use them for more accurate field info
    if src_view_defs:
        for idx, view_def in enumerate(src_view_defs):
            try:
                # Get the view definition as JSON
                view_def_json = view_def.as_json()
                
                # Try to determine source layer ID
                source_id = idx  # Default to index
                
                # Check if we can get source ID from the view definition
                if 'viewLayerDefinition' in view_def_json:
                    source_id = view_def_json['viewLayerDefinition'].get('sourceLayerId', idx)
                
                # Extract fields if present
                if 'fields' in view_def_json:
                    visible_fields = [f['name'] for f in view_def_json['fields'] if f.get('visible', True)]
                    hidden_fields = [f['name'] for f in view_def_json['fields'] if not f.get('visible', True)]
                    
                    if hidden_fields:
                        logging.info(f"  📊 Layer {idx} has {len(hidden_fields)} hidden fields via ViewManager")
                        if source_id in view_config['layer_definitions']:
                            view_config['layer_definitions'][source_id]['visible_fields'] = visible_fields
                            view_config['layer_definitions'][source_id]['view_manager_def'] = view_def_json
            except Exception as e:
                # Use debug level for this non-critical error
                pass  # Silently ignore - this is expected for some view types
    
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

    # 1️⃣3️⃣ apply field visibility using ViewManager (following reference script pattern)
    new_flc = FeatureLayerCollection.fromitem(new_view_item)
    
    # Helper to get source layer ID
    def _source_id(lyr):
        try:
            return lyr.properties.viewLayerDefinition["sourceLayerId"]
        except Exception:
            return lyr.properties.get("sourceLayerId", lyr.properties.id)
    
    # Get the visible field names from the source view
    src_visible_fields = {}
    for src_lyr in src_flc.layers:
        source_id = _source_id(src_lyr)
        visible_fields = []
        # Get field names that exist in the source view
        if hasattr(src_lyr.properties, 'fields'):
            for field in src_lyr.properties.fields:
                if isinstance(field, dict):
                    visible_fields.append(field['name'])
                else:
                    visible_fields.append(field.name if hasattr(field, 'name') else str(field))
        src_visible_fields[source_id] = visible_fields
        logging.info(f"  📊 Source layer {source_id} visible fields: {visible_fields}")
    
    # Apply field visibility using ViewManager approach from reference script
    try:
        # Wait for view to be fully created
        time.sleep(3)
        
        # Get the ViewManager from the view layer item
        view_manager = new_view_item.view_manager
        view_layer_definitions = None
        
        # Retry getting definitions a few times as view might not be ready immediately
        for attempt in range(3):
            view_layer_definitions = view_manager.get_definitions(new_view_item)
            if view_layer_definitions:
                break
            logging.info(f"  ⏳ Waiting for view to be ready... (attempt {attempt + 1}/3)")
            time.sleep(2)
        
        if view_layer_definitions is not None:
            logging.info(f"  📊 Found {len(view_layer_definitions)} view layer definitions")
            
            for idx, view_layer_def in enumerate(view_layer_definitions):
                # Get the sub-layer
                sub_layer = view_layer_def.layer
                
                # Get all field names from the new view layer
                all_fields = []
                if hasattr(sub_layer.properties, 'fields'):
                    for field in sub_layer.properties.fields:
                        if isinstance(field, dict):
                            all_fields.append(field['name'])
                        else:
                            all_fields.append(field.name if hasattr(field, 'name') else str(field))
                
                # Determine which fields should be visible based on source
                # The source view only had 4 fields visible
                visible_field_names = src_visible_fields.get(0, [])  # Using 0 as the source layer ID
                
                # Build the fields update dictionary
                fields_update = []
                for field_name in all_fields:
                    fields_update.append({
                        "name": field_name,
                        "visible": field_name in visible_field_names
                    })
                
                # Log what we're updating
                visible_count = sum(1 for f in fields_update if f['visible'])
                hidden_count = len(fields_update) - visible_count
                logging.info(f"  • Updating layer {idx} field visibility: {visible_count} visible, {hidden_count} hidden")
                logging.info(f"    Visible fields: {[f['name'] for f in fields_update if f['visible']]}")
                logging.info(f"    Hidden fields: {[f['name'] for f in fields_update if not f['visible']]}")
                
                # Prepare the update dictionary (following reference script pattern)
                update_dict = {
                    "fields": fields_update
                }
                
                # Apply the update
                update_result = sub_layer.manager.update_definition(update_dict)
                
                if update_result.get('success', False):
                    logging.info(f"    ✓ Successfully updated field visibility for layer {idx}")
                else:
                    logging.warning(f"    ⚠ Field visibility update failed: {update_result}")
                    
                # Apply any queries from the source
                if 0 in view_config.get('layer_definitions', {}):
                    layer_config = view_config['layer_definitions'][0]
                    if layer_config.get('query'):
                        query_update = {"viewDefinitionQuery": layer_config['query']}
                        query_result = sub_layer.manager.update_definition(query_update)
                        logging.info(f"  • Applied query filter: {query_result}")
                        
        else:
            logging.warning('⚠ No view layer definitions found to update after 3 attempts.')
            logging.warning('  Field visibility may not be applied correctly.')
            
    except Exception as e:
        logging.error(f"❌ Error updating field visibility: {e}")
        import traceback
        logging.error(traceback.format_exc())

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