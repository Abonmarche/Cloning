"""
Join View Recreation Script
──────────────────────────────
Reads an existing join view definition and recreates it dynamically
Handles view layers that join two sources (layers/tables)
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection, FeatureLayer, Table
import json, os, sys, time
from datetime import datetime
from copy import deepcopy
import logging
import requests

# ═════ MODIFY FOR TESTING ════════════════════════════════════════════════════
USERNAME   = "xxx"
PASSWORD   = "xxx"
SRC_VIEWID = "0aef75cb383448c5a94efa802bfe6954"   # ← the join view layer to clone
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

# ───── helper ▸ get source layers from view ──────────────────────────────────
def get_source_layers(gis, view_item):
    """Get the parent hosted feature layers for a join view using /sources endpoint."""
    sources_url = f"{view_item.url}/sources"
    params = {"f": "json"}
    
    # Add token if available
    if hasattr(gis._con, 'token') and gis._con.token:
        params["token"] = gis._con.token
    
    r = requests.get(sources_url, params=params)
    
    if r.ok:
        resp = r.json()
        services = resp.get("services", [])
        
        source_info = []
        for service in services:
            info = {
                'service_item_id': service.get('serviceItemId'),
                'service_name': service.get('name'),
                'service_url': service.get('url'),
                'layer_id': service.get('layerId', 0)
            }
            source_info.append(info)
            logging.info(f"↪ found source: {info['service_name']} (ID: {info['service_item_id']}, Layer: {info['layer_id']})")
        
        return source_info
    else:
        logging.error(f"Failed to get sources: {r.status_code} - {r.text}")
        return []

# ───── helper ▸ extract join definition from view ────────────────────────────
def extract_join_definition(gis, view_item, view_flc):
    """Extract join definition using ViewManager and service properties."""
    
    config = {}
    join_definition_found = False
    
    # Method 1: Try to get view definitions using ViewManager
    try:
        view_manager = view_item.view_manager
        view_defs = view_manager.get_definitions(view_item)
        
        if view_defs:
            logging.info(f"📊 Found {len(view_defs)} view layer definitions via ViewManager")
            # Save and inspect the definitions
            for idx, vdef in enumerate(view_defs):
                vdef_json = vdef.as_json()
                jdump(vdef_json, f"view_def_{idx}_{view_item.id}")
                
                # Look for join definition in viewLayerDefinition
                if 'viewLayerDefinition' in vdef_json:
                    vld = vdef_json['viewLayerDefinition']
                    if 'table' in vld and 'relatedTables' in vld['table']:
                        # Found join definition!
                        table_def = vld['table']
                        related_tables = table_def['relatedTables']
                        if related_tables:
                            join_def = related_tables[0]  # Usually only one join
                            config['join_definition'] = {
                                'parent_key_fields': join_def.get('parentKeyFields'),
                                'key_fields': join_def.get('keyFields'),
                                'join_type': join_def.get('type', 'INNER'),
                                'top_filter': join_def.get('topFilter')
                            }
                            config['main_source_fields'] = table_def.get('sourceLayerFields', [])
                            config['joined_source_fields'] = join_def.get('sourceLayerFields', [])
                            join_definition_found = True
                            logging.info(f"✓ Found join definition: {config['join_definition']['parent_key_fields']} → {config['join_definition']['key_fields']}")
    except Exception as e:
        logging.warning(f"Could not get view definitions via ViewManager: {e}")
    
    # Method 2: Check layer properties directly
    if not join_definition_found and view_flc.layers:
        layer = view_flc.layers[0]
        layer_props = dict(layer.properties)
        
        # Deep inspection of layer properties
        if 'adminLayerInfo' in layer_props:
            admin_info = layer_props['adminLayerInfo']
            if 'viewLayerDefinition' in admin_info:
                vld = admin_info['viewLayerDefinition']
                if 'table' in vld:
                    table_def = vld['table']
                    if 'relatedTables' in table_def:
                        related_tables = table_def['relatedTables']
                        if related_tables:
                            join_def = related_tables[0]
                            config['join_definition'] = {
                                'parent_key_fields': join_def.get('parentKeyFields'),
                                'key_fields': join_def.get('keyFields'),
                                'join_type': join_def.get('type', 'INNER'),
                                'top_filter': join_def.get('topFilter')
                            }
                            config['main_source_fields'] = table_def.get('sourceLayerFields', [])
                            config['joined_source_fields'] = join_def.get('sourceLayerFields', [])
                            join_definition_found = True
                            logging.info(f"✓ Found join definition in layer properties: {config['join_definition']['parent_key_fields']} → {config['join_definition']['key_fields']}")
    
    # Method 3: Try REST API endpoint for admin info
    if not join_definition_found:
        try:
            # Query the layer's admin endpoint
            admin_url = f"{view_item.url}/0/adminLayerInfo"
            params = {"f": "json"}
            if hasattr(gis._con, 'token') and gis._con.token:
                params["token"] = gis._con.token
            
            r = requests.get(admin_url, params=params)
            if r.ok:
                admin_data = r.json()
                jdump(admin_data, f"admin_layer_info_{view_item.id}")
                
                if 'viewLayerDefinition' in admin_data:
                    vld = admin_data['viewLayerDefinition']
                    if 'table' in vld and 'relatedTables' in vld['table']:
                        table_def = vld['table']
                        related_tables = table_def['relatedTables']
                        if related_tables:
                            join_def = related_tables[0]
                            config['join_definition'] = {
                                'parent_key_fields': join_def.get('parentKeyFields'),
                                'key_fields': join_def.get('keyFields'),
                                'join_type': join_def.get('type', 'INNER'),
                                'top_filter': join_def.get('topFilter')
                            }
                            config['main_source_fields'] = table_def.get('sourceLayerFields', [])
                            config['joined_source_fields'] = join_def.get('sourceLayerFields', [])
                            join_definition_found = True
                            logging.info(f"✓ Found join definition via REST API: {config['join_definition']['parent_key_fields']} → {config['join_definition']['key_fields']}")
        except Exception as e:
            logging.warning(f"Could not query admin endpoint: {e}")
    
    if not join_definition_found:
        logging.error("❌ Could not extract join definition from view")
        logging.error("   Unable to determine join fields - cannot proceed")
        return None
    
    # Get sources information
    sources = get_source_layers(gis, view_item)
    if len(sources) < 2:
        logging.error("Join view should have at least 2 sources")
        return None
    
    config['sources'] = sources
    
    # Extract basic info from the view
    config['view_title'] = view_item.title
    config['view_description'] = view_item.description
    config['view_snippet'] = view_item.snippet
    config['view_tags'] = view_item.tags
    
    # Get the first layer properties
    if view_flc.layers:
        layer = view_flc.layers[0]
        layer_props = layer.properties
        
        config['layer_name'] = layer_props.get('name', 'JoinView')
        config['display_field'] = layer_props.get('displayField')
        
        # Try to extract spatial reference
        if hasattr(layer_props, 'extent') and layer_props.extent:
            config['spatial_reference'] = layer_props.extent.get('spatialReference')
            config['extent'] = layer_props.extent
    
    # Get service properties
    svc_props = view_flc.properties
    config['capabilities'] = svc_props.get('capabilities', 'Query')
    config['allow_schema_changes'] = svc_props.get('allowGeometryUpdates', True)
    
    return config

# ───── helper ▸ get layer object from service ────────────────────────────────
def get_layer_or_table(flc, layer_id):
    """Get a layer or table object from a FeatureLayerCollection by ID."""
    # Check layers
    for lyr in flc.layers:
        if lyr.properties.id == layer_id:
            return lyr, 'layer'
    
    # Check tables
    for tbl in flc.tables:
        if tbl.properties.id == layer_id:
            return tbl, 'table'
    
    return None, None

# ───── core workflow ─────────────────────────────────────────────────────────
def recreate_join_view(username, password, view_id):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    logging.info("🔐 connecting to ArcGIS Online…")
    gis = GIS("https://www.arcgis.com", username, password)
    logging.info(f"✓ signed in as: {gis.users.me.username}")

    # 1️⃣ fetch template item
    src_item = gis.content.get(view_id)
    if not src_item:
        logging.error(f"⚠ no item with id {view_id}")
        sys.exit(1)

    # 2️⃣ wrap in FeatureLayerCollection
    src_flc = FeatureLayerCollection.fromitem(src_item)
    if not getattr(src_flc.properties, "isView", False):
        logging.error(f"⚠ item {view_id} is not a Feature Layer (View)")
        sys.exit(1)
    logging.info(f"👁 cloning join view: {src_item.title} ({view_id})")

    # 3️⃣ dump JSON for debugging
    item_data = src_item.get_data()
    jdump(item_data, f"join_view_item_{view_id}")
    
    svc_def = dict(src_flc.properties)
    jdump(svc_def, f"join_view_service_{view_id}")
    
    for lyr in src_flc.layers:
        ldef = dict(lyr.properties)
        jdump(ldef, f"join_view_layer_{view_id}")

    # 4️⃣ extract join configuration
    join_config = extract_join_definition(gis, src_item, src_flc)
    if not join_config:
        logging.error("Failed to extract join configuration")
        sys.exit(1)
    
    jdump(join_config, f"join_config_{view_id}")

    # 5️⃣ get parent items and create layer/table objects
    if len(join_config['sources']) < 2:
        logging.error("Need at least 2 sources for a join view")
        sys.exit(1)
    
    # Get the main (first) source
    main_source = join_config['sources'][0]
    main_item = gis.content.get(main_source['service_item_id'])
    if not main_item:
        logging.error(f"Could not find main source item: {main_source['service_item_id']}")
        sys.exit(1)
    
    main_flc = FeatureLayerCollection.fromitem(main_item)
    main_obj, main_type = get_layer_or_table(main_flc, main_source.get('layer_id', 0))
    if not main_obj:
        # If layer_id is not found, try first layer/table
        if main_flc.layers:
            main_obj = main_flc.layers[0]
            main_type = 'layer'
        elif main_flc.tables:
            main_obj = main_flc.tables[0]
            main_type = 'table'
        else:
            logging.error("Could not find main layer/table")
            sys.exit(1)
    
    logging.info(f"📊 Main source: {main_item.title} ({main_type} {main_obj.properties.id})")
    
    # Get the joined (second) source
    joined_source = join_config['sources'][1]
    joined_item = gis.content.get(joined_source['service_item_id'])
    if not joined_item:
        logging.error(f"Could not find joined source item: {joined_source['service_item_id']}")
        sys.exit(1)
    
    joined_flc = FeatureLayerCollection.fromitem(joined_item)
    joined_obj, joined_type = get_layer_or_table(joined_flc, joined_source.get('layer_id', 0))
    if not joined_obj:
        # If layer_id is not found, try first layer/table
        if joined_flc.layers:
            joined_obj = joined_flc.layers[0]
            joined_type = 'layer'
        elif joined_flc.tables:
            joined_obj = joined_flc.tables[0]
            joined_type = 'table'
        else:
            logging.error("Could not find joined layer/table")
            sys.exit(1)
    
    logging.info(f"📊 Joined source: {joined_item.title} ({joined_type} {joined_obj.properties.id})")

    # 6️⃣ Extract join fields from the configuration
    if 'join_definition' not in join_config:
        logging.error("❌ No join definition found in configuration")
        logging.error("   Cannot proceed without knowing the exact join fields")
        sys.exit(1)
    
    join_def = join_config['join_definition']
    target_join_fields = join_def['parent_key_fields']
    join_fields = join_def['key_fields']
    join_type = join_def['join_type']
    
    if not target_join_fields or not join_fields:
        logging.error("❌ Join fields are empty or missing")
        logging.error(f"   Parent key fields: {target_join_fields}")
        logging.error(f"   Join key fields: {join_fields}")
        sys.exit(1)
    
    logging.info(f"📋 Join configuration:")
    logging.info(f"   Join type: {join_type}")
    logging.info(f"   Parent key fields: {target_join_fields}")
    logging.info(f"   Join key fields: {join_fields}")
    if join_def.get('top_filter'):
        logging.info(f"   Top filter: {join_def['top_filter']}")

    # 7️⃣ create new view using the extracted definition
    ts_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{src_item.title}_clone_{ts_suffix}"
    
    logging.info(f"🛠 creating join view: {new_title}")
    
    # Since we have the complete join definition, we can try to recreate it exactly
    # First, create an empty view service
    try:
        # Determine spatial reference from config or default
        wkid = 102100  # Default
        if join_config.get('spatial_reference'):
            wkid = join_config['spatial_reference'].get('wkid', 102100)
        
        view_service = gis.content.create_service(
            name=new_title,
            is_view=True,
            wkid=wkid
        )
        view_flc = FeatureLayerCollection.fromitem(view_service)
        logging.info(f"✓ empty view service created: {view_service.id}")
        
        # Build the complete join definition based on the notebook pattern
        definition_to_add = {
            "layers": [
                {
                    "name": join_config.get('layer_name', 'JoinView'),
                    "displayField": join_config.get('display_field'),
                    "description": "AttributeJoin",
                    "adminLayerInfo": {
                        "viewLayerDefinition": {
                            "table": {
                                "name": "Target_fl",
                                "sourceServiceName": main_source['service_name'],
                                "sourceLayerId": main_source.get('layer_id', 0),
                                "sourceLayerFields": join_config.get('main_source_fields', []),
                                "relatedTables": [
                                    {
                                        "name": "JoinedTable",
                                        "sourceServiceName": joined_source['service_name'],
                                        "sourceLayerId": joined_source.get('layer_id', 0),
                                        "sourceLayerFields": join_config.get('joined_source_fields', []),
                                        "type": join_type,
                                        "parentKeyFields": target_join_fields,
                                        "keyFields": join_fields
                                    }
                                ],
                                "materialized": False
                            }
                        }
                    }
                }
            ]
        }
        
        # Add geometry field if this is a spatial join
        if main_type == 'layer' and main_source.get('service_name'):
            definition_to_add["layers"][0]["adminLayerInfo"]["geometryField"] = {
                "name": f"{main_source['service_name']}.Shape"
            }
        
        # Add top filter if present
        if join_def.get('top_filter'):
            definition_to_add["layers"][0]["adminLayerInfo"]["viewLayerDefinition"]["table"]["relatedTables"][0]["topFilter"] = join_def['top_filter']
        
        # Save the definition for debugging
        jdump(definition_to_add, f"join_definition_to_apply_{new_title}")
        
        # Apply the join definition
        result = view_flc.manager.add_to_definition(definition_to_add)
        logging.info(f"✓ join view definition applied successfully")
        
        new_view = view_service
        
    except Exception as e:
        logging.error(f"❌ Failed to create join view: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

    # 8️⃣ copy item-level visualization if we have a view
    if new_view:
        try:
            new_view.update(data=item_data)
            logging.info("✓ item-level pop-ups & renderers copied")
        except Exception as e:
            logging.warning(f"⚠ Could not copy item data: {e}")

    # 9️⃣ final summary
    logging.info("\n🎉 Join view recreation complete!")
    logging.info(f"Title : {new_view.title}")
    logging.info(f"ItemID: {new_view.id}")
    logging.info(f"URL   : {new_view.homepage}")
    logging.info(f"Main source: {main_item.title}")
    logging.info(f"Joined to: {joined_item.title}")
    logging.info(f"Join fields: {target_join_fields} → {join_fields}")
    logging.info(f"Join type: {join_type}")

    return new_view

# ── run as script ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        recreate_join_view(USERNAME, PASSWORD, SRC_VIEWID)
    except Exception as exc:
        logging.exception(f"❌ Error: {exc}")