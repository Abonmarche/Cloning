"""
Join View Recreation Script
──────────────────────────────
Reads an existing join view definition and recreates it dynamically
Handles view layers that join two sources (layers/tables)

Saves these JSON files for reference:
- Original view item, service, and layer definitions
- Admin endpoint response with full join configuration
- Sublayer sources information
- Extracted join configuration
- Definition applied to create new view
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import json, os, sys, time
from datetime import datetime
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
    
    # Convert PropertyMap objects to dictionaries
    def convert_to_serializable(item):
        if hasattr(item, '__dict__'):
            # Try to convert objects with __dict__ to dict
            try:
                return dict(item)
            except:
                # If that fails, try to get its string representation
                return str(item)
        elif isinstance(item, dict):
            return {k: convert_to_serializable(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [convert_to_serializable(i) for i in item]
        else:
            return item
    
    serializable_obj = convert_to_serializable(obj)
    
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(serializable_obj, fp, indent=2, default=str)
    logging.info(f"📄 dumped {label} → {path}")
    return path

# ───── helper ▸ get source layers from sublayer ─────────────────────────────
def get_sublayer_sources(gis, view_item):
    """Get the source layers from the sublayer /0/sources endpoint."""
    sources_url = f"{view_item.url}/0/sources"
    params = {"f": "json"}
    
    # Add token if available
    if hasattr(gis._con, 'token') and gis._con.token:
        params["token"] = gis._con.token
    
    r = requests.get(sources_url, params=params)
    
    if r.ok:
        resp = r.json()
        # Save the sublayer sources for reference
        jdump(resp, f"sublayer_sources_{view_item.id}")
        
        layers = resp.get("layers", [])
        
        source_info = []
        for layer in layers:
            # Extract layer number from URL
            url = layer.get('url', '')
            layer_num = None
            if '/FeatureServer/' in url:
                layer_num = int(url.split('/FeatureServer/')[-1])
            
            info = {
                'name': layer.get('name'),
                'service_item_id': layer.get('serviceItemId'),
                'url': url,
                'layer_num': layer_num
            }
            source_info.append(info)
            logging.info(f"↪ found source layer: {info['name']} (Layer {layer_num})")
        
        return source_info
    else:
        logging.error(f"Failed to get sublayer sources: {r.status_code}")
        return []

# ───── helper ▸ extract join definition from admin endpoint ──────────────────
def extract_join_definition_from_admin(gis, view_item):
    """Extract join definition from the administrative REST API endpoint."""
    
    # Convert regular REST URL to admin URL
    if "/rest/services/" not in view_item.url:
        logging.error("Cannot construct admin URL. '/rest/services/' not found in item URL.")
        return None
    
    admin_url = view_item.url.replace("/rest/services/", "/rest/admin/services/") + "/0"
    params = {"f": "json"}
    if hasattr(gis._con, 'token') and gis._con.token:
        params["token"] = gis._con.token
    
    logging.info(f"Querying admin endpoint: {admin_url}")
    
    try:
        r = requests.get(admin_url, params=params)
        r.raise_for_status()
        admin_data = r.json()
        
        # Save the raw admin response for reference
        jdump(admin_data, f"admin_endpoint_response_{view_item.id}")
        
        if "adminLayerInfo" not in admin_data:
            logging.error("No adminLayerInfo found in admin response")
            return None
        
        admin_info = admin_data["adminLayerInfo"]
        if "viewLayerDefinition" not in admin_info:
            logging.error("No viewLayerDefinition found in adminLayerInfo")
            return None
        
        view_def = admin_info["viewLayerDefinition"]
        if "table" not in view_def:
            logging.error("No table found in viewLayerDefinition")
            return None
        
        # Extract the complete table definition
        table_def = view_def["table"]
        
        # Build config from the definition
        config = {
            'table_name': table_def.get('name'),
            'main_source': {
                'service_name': table_def.get('sourceServiceName'),
                'layer_id': table_def.get('sourceLayerId'),
                'fields': table_def.get('sourceLayerFields', [])
            }
        }
        
        # Extract join information
        if 'relatedTables' in table_def and table_def['relatedTables']:
            related = table_def['relatedTables'][0]  # Usually only one join
            config['joined_source'] = {
                'service_name': related.get('sourceServiceName'),
                'layer_id': related.get('sourceLayerId'),
                'fields': related.get('sourceLayerFields', [])
            }
            config['join_definition'] = {
                'parent_key_fields': related.get('parentKeyFields'),
                'key_fields': related.get('keyFields'),
                'join_type': related.get('type', 'INNER'),
                'top_filter': related.get('topFilter')
            }
            
            logging.info(f"✓ Found join definition: {config['join_definition']['parent_key_fields']} → {config['join_definition']['key_fields']}")
            
        # Also get geometry field if present
        if 'geometryField' in admin_info:
            config['geometry_field'] = admin_info['geometryField'].get('name')
        
        # Get other layer properties
        config['layer_name'] = admin_data.get('name')
        config['display_field'] = admin_data.get('displayField')
        
        return config
        
    except Exception as e:
        logging.error(f"Failed to query admin endpoint: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None

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

    # 4️⃣ extract join configuration from admin endpoint
    join_config = extract_join_definition_from_admin(gis, src_item)
    if not join_config:
        logging.error("Failed to extract join configuration from admin endpoint")
        sys.exit(1)
    
    # Get source layer info from sublayer
    source_layers = get_sublayer_sources(gis, src_item)
    if len(source_layers) < 2:
        logging.error("Expected at least 2 source layers in join view")
        sys.exit(1)
    
    # Match source layers with the config
    for src_layer in source_layers:
        if src_layer['layer_num'] == join_config['main_source']['layer_id']:
            join_config['main_source']['item_id'] = src_layer['service_item_id']
        elif src_layer['layer_num'] == join_config['joined_source']['layer_id']:
            join_config['joined_source']['item_id'] = src_layer['service_item_id']
    
    # Add view metadata
    join_config['view_title'] = src_item.title
    join_config['view_description'] = src_item.description
    join_config['view_snippet'] = src_item.snippet
    join_config['view_tags'] = src_item.tags
    
    # Get service properties
    svc_props = src_flc.properties
    join_config['capabilities'] = svc_props.get('capabilities', 'Query')
    join_config['allow_schema_changes'] = svc_props.get('allowGeometryUpdates', True)
    
    # Get spatial reference
    if src_flc.layers and hasattr(src_flc.layers[0].properties, 'extent') and src_flc.layers[0].properties.extent:
        extent = src_flc.layers[0].properties.extent
        # Convert PropertyMap to dict if needed
        if hasattr(extent, '__dict__'):
            try:
                join_config['extent'] = dict(extent)
                if 'spatialReference' in join_config['extent']:
                    join_config['spatial_reference'] = dict(join_config['extent']['spatialReference'])
            except:
                # Fallback to getting individual properties
                join_config['extent'] = {
                    'xmin': getattr(extent, 'xmin', None),
                    'ymin': getattr(extent, 'ymin', None),
                    'xmax': getattr(extent, 'xmax', None),
                    'ymax': getattr(extent, 'ymax', None)
                }
                if hasattr(extent, 'spatialReference'):
                    sr = extent.spatialReference
                    join_config['spatial_reference'] = {
                        'wkid': getattr(sr, 'wkid', 102100),
                        'latestWkid': getattr(sr, 'latestWkid', None)
                    }
        else:
            join_config['spatial_reference'] = extent.get('spatialReference') if isinstance(extent, dict) else None
            join_config['extent'] = extent
    
    jdump(join_config, f"join_config_{view_id}")
    
    logging.info(f"📋 Join configuration extracted:")
    logging.info(f"   Main source: {join_config['main_source']['service_name']} (layer {join_config['main_source']['layer_id']})")
    logging.info(f"   Joined source: {join_config['joined_source']['service_name']} (layer {join_config['joined_source']['layer_id']})")
    logging.info(f"   Join: {join_config['join_definition']['parent_key_fields']} → {join_config['join_definition']['key_fields']}")

    # 5️⃣ Verify we have join fields
    join_def = join_config['join_definition']
    if not join_def.get('parent_key_fields') or not join_def.get('key_fields'):
        logging.error("❌ Join fields are missing")
        sys.exit(1)

    # 6️⃣ create new view using the extracted definition
    ts_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{src_item.title}_clone_{ts_suffix}"
    
    logging.info(f"🛠 creating join view: {new_title}")
    
    try:
        # Determine spatial reference from config or default
        wkid = 102100  # Default
        if join_config.get('spatial_reference'):
            wkid = join_config['spatial_reference'].get('wkid', 102100)
        
        # Create empty view service (following notebook pattern)
        view_service = gis.content.create_service(
            name=new_title,
            is_view=True,
            wkid=wkid
        )
        view_flc = FeatureLayerCollection.fromitem(view_service)
        logging.info(f"✓ empty view service created: {view_service.id}")
        
        # Build the join definition following the exact notebook pattern
        definition_to_add = {
            "layers": [
                {
                    "name": join_config.get('layer_name', new_title),
                    "displayField": join_config.get('display_field', ''),
                    "description": "AttributeJoin",
                    "adminLayerInfo": {
                        "viewLayerDefinition": {
                            "table": {
                                "name": "Target_fl",
                                "sourceServiceName": join_config['main_source']['service_name'],
                                "sourceLayerId": join_config['main_source']['layer_id'],
                                "sourceLayerFields": join_config['main_source']['fields'],
                                "relatedTables": [
                                    {
                                        "name": "JoinedTable",
                                        "sourceServiceName": join_config['joined_source']['service_name'],
                                        "sourceLayerId": join_config['joined_source']['layer_id'],
                                        "sourceLayerFields": join_config['joined_source']['fields'],
                                        "type": join_def['join_type'],
                                        "parentKeyFields": join_def['parent_key_fields'],
                                        "keyFields": join_def['key_fields']
                                    }
                                ],
                                "materialized": False
                            }
                        },
                        "geometryField": {
                            "name": join_config.get('geometry_field', f"{join_config['main_source']['service_name']}.Shape")
                        }
                    }
                }
            ]
        }
        
        # Add top filter if present (for one-to-one joins)
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

    # 7️⃣ copy item-level visualization
    if new_view:
        try:
            new_view.update(data=item_data)
            logging.info("✓ item-level pop-ups & renderers copied")
        except Exception as e:
            logging.warning(f"⚠ Could not copy item data: {e}")
        
        # Copy additional metadata
        try:
            meta = {
                "description": join_config.get('view_description'),
                "snippet": join_config.get('view_snippet'),
                "tags": ','.join(join_config.get('view_tags', [])) if join_config.get('view_tags') else None
            }
            if any(meta.values()):
                new_view.update(item_properties={k: v for k, v in meta.items() if v})
                logging.info("✓ metadata copied")
        except Exception as e:
            logging.warning(f"⚠ Could not copy metadata: {e}")
        
        # Save the new view's service definition for comparison
        try:
            new_flc = FeatureLayerCollection.fromitem(new_view)
            new_svc_props = dict(new_flc.properties)
            jdump(new_svc_props, f"new_join_view_service_{new_view.id}")
            logging.info("📄 saved new view service definition")
        except Exception as e:
            logging.warning(f"⚠ Could not save new service definition: {e}")

    # 8️⃣ final summary
    logging.info("\n🎉 Join view recreation complete!")
    logging.info(f"Title : {new_view.title}")
    logging.info(f"ItemID: {new_view.id}")
    logging.info(f"URL   : {new_view.homepage}")
    logging.info(f"Main source: {join_config['main_source']['service_name']} (layer {join_config['main_source']['layer_id']})")
    logging.info(f"Joined to: {join_config['joined_source']['service_name']} (layer {join_config['joined_source']['layer_id']})")
    logging.info(f"Join fields: {join_def['parent_key_fields']} → {join_def['key_fields']}")
    logging.info(f"Join type: {join_def['join_type']}")
    if join_def.get('top_filter'):
        logging.info(f"Cardinality: One-to-One (top filter applied)")
    else:
        logging.info(f"Cardinality: One-to-Many")
    
    logging.info(f"\n📁 JSON files saved to: ./{OUTDIR}/")
    logging.info("   Files created:")
    logging.info("   • join_view_item_{id} - Original item metadata")
    logging.info("   • join_view_service_{id} - Original service properties")
    logging.info("   • join_view_layer_{id} - Original layer properties")
    logging.info("   • admin_endpoint_response_{id} - Full admin API response")
    logging.info("   • sublayer_sources_{id} - Source layers information")
    logging.info("   • join_config_{id} - Extracted configuration")
    logging.info("   • join_definition_to_apply_{name} - Definition applied")
    logging.info("   • new_join_view_service_{id} - New view service properties")

    return new_view

# ── run as script ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        recreate_join_view(USERNAME, PASSWORD, SRC_VIEWID)
    except Exception as exc:
        logging.exception(f"❌ Error: {exc}")