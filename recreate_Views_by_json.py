"""
Complete View Recreation Script
─────────────────────────────────────────────────────────────────────────────
Recreates both basic and join views with all fields properly mapped.
Based on the Test_Relationship service structure.
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection, FeatureLayer, Table
from datetime import datetime
import json, os, re

# ── CONFIGURATION ─────────────────────────────────────────────────────────
USERNAME = "gargarcia"
PASSWORD = "GOGpas5252***"

# Source service - Test_Relationship
SOURCE_ITEM_ID = "fe7f19431cbc495ba71871a07b25db19"

# Views to recreate
BASIC_VIEW_ITEM_ID = "604b386212074e129c0ebbe5e12cd2bd"  
JOIN_VIEW_ITEM_ID = "0aef75cb383448c5a94efa802bfe6954"

# Base URLs for the source layers
BASE_URL = "https://services5.arcgis.com/S5JQ6TlhA1BbeUBC/arcgis/rest/services/Test_Relationship/FeatureServer"
MAIN_LAYER_URL = f"{BASE_URL}/0"  # Main feature layer
RELATED_TABLE_URL = f"{BASE_URL}/1"  # Related table

CLONE_SUFFIX = "_Recreated"
# ───────────────────────────────────────────────────────────────────────────


def _safe_filename(base, suffix=".json"):
    """Generate a safe filename with timestamp"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean = re.sub(r"[^0-9A-Za-z_\-]", "_", base)[:40]
    return f"{clean}_{ts}{suffix}"


def _add_timestamp_to_name(original_name, suffix=""):
    """Add timestamp and optional suffix to a name"""
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    base_name = re.sub(r"_\d{8}_\d{4}$", "", original_name)[:40]
    return f"{base_name}{suffix}_{ts}"


def _get_service_name(url):
    """Extract service name from URL"""
    try:
        if "/rest/services/" in url:
            parts = url.split("/rest/services/")[1]
            return parts.split("/")[0]
    except:
        return None


def recreate_complete_view(gis):
    """
    Recreate the basic view that includes both the layer and table
    """
    print("\n▶ Recreating complete view with all layers and tables")
    
    # Get original view for naming
    orig_item = gis.content.get(BASIC_VIEW_ITEM_ID)
    if not orig_item:
        print("  • Using default name for basic view")
        orig_title = "Test Relationship View"
    else:
        orig_title = orig_item.title
    
    # Get the source service
    src_item = gis.content.get(SOURCE_ITEM_ID)
    if not src_item:
        raise ValueError(f"Source item {SOURCE_ITEM_ID} not found")
    
    src_flc = FeatureLayerCollection.fromitem(src_item)
    src_service_name = _get_service_name(src_flc.url)
    
    # Create new view
    new_name = _add_timestamp_to_name(orig_title, CLONE_SUFFIX)
    print(f"  • Creating new view: {new_name}")
    
    # Get spatial reference from the first layer
    wkid = 4326
    if src_flc.layers:
        wkid = src_flc.layers[0].properties.extent.spatialReference.get("wkid", 4326)
    
    view_item = gis.content.create_service(
        name=new_name,
        is_view=True,
        wkid=wkid,
        tags=["view", "complete", "recreated"],
        snippet=f"Complete view recreated from {orig_title}"
    )
    
    print(f"  ✓ Created view: {view_item.id}")
    
    # Define fields for the main layer
    main_layer_fields = [
        {"name": "OBJECTID", "alias": "OBJECTID", "source": "OBJECTID"},
        {"name": "FACILITYID", "alias": "Facility ID", "source": "FACILITYID"},
        {"name": "ASSEMTYPE", "alias": "Assembly Type", "source": "ASSEMTYPE"},
        {"name": "MANUFACTURER", "alias": "Manufacturer", "source": "MANUFACTURER"},
        {"name": "MODEL", "alias": "Model", "source": "MODEL"},
        {"name": "OWNER", "alias": "Owner", "source": "OWNER"},
        {"name": "INSTALLDATE", "alias": "Install Date", "source": "INSTALLDATE"},
        {"name": "GlobalID", "alias": "Global ID", "source": "GlobalID"}
    ]
    
    # Define fields for the related table
    related_table_fields = [
        {"name": "OBJECTID", "alias": "OBJECTID", "source": "OBJECTID"},
        {"name": "FACILITYID", "alias": "Facility ID", "source": "FACILITYID"},
        {"name": "DATE", "alias": "Inspection Date", "source": "DATE"},
        {"name": "INSPECTOR", "alias": "Inspector", "source": "INSPECTOR"},
        {"name": "CONDITION", "alias": "Condition", "source": "CONDITION"},
        {"name": "VAL1PSI", "alias": "Valve 1 PSI", "source": "VAL1PSI"},
        {"name": "VAL1LEAK", "alias": "Valve 1 Leak", "source": "VAL1LEAK"},
        {"name": "VAL1CLOSE", "alias": "Valve 1 Close", "source": "VAL1CLOSE"},
        {"name": "VAL1CLEAN", "alias": "Valve 1 Clean", "source": "VAL1CLEAN"},
        {"name": "VAL1REPAIR", "alias": "Valve 1 Repair", "source": "VAL1REPAIR"},
        {"name": "VAL2PSI", "alias": "Valve 2 PSI", "source": "VAL2PSI"},
        {"name": "VAL2LEAK", "alias": "Valve 2 Leak", "source": "VAL2LEAK"},
        {"name": "VAL2CLOSE", "alias": "Valve 2 Close", "source": "VAL2CLOSE"},
        {"name": "VAL2CLEAN", "alias": "Valve 2 Clean", "source": "VAL2CLEAN"},
        {"name": "VAL2REPAIR", "alias": "Valve 2 Repair", "source": "VAL2REPAIR"},
        {"name": "INLETPSI", "alias": "Inlet PSI", "source": "INLETPSI"},
        {"name": "INLETCLEAN", "alias": "Inlet Clean", "source": "INLETCLEAN"},
        {"name": "INREPAIR", "alias": "In Repair", "source": "INREPAIR"},
        {"name": "RELPSI", "alias": "Relief PSI", "source": "RELPSI"},
        {"name": "RELCLEAN", "alias": "Relief Clean", "source": "RELCLEAN"},
        {"name": "RELREPAIR", "alias": "Relief Repair", "source": "RELREPAIR"},
        {"name": "COMMENTS", "alias": "Comments", "source": "COMMENTS"},
        {"name": "ASSETGUID", "alias": "Asset GUID", "source": "ASSETGUID"},
        {"name": "GlobalID", "alias": "Global ID", "source": "GlobalID"}
    ]
    
    # Build view definition
    view_def = {
        "layers": [{
            "name": src_flc.layers[0].properties.name,
            "displayField": "FACILITYID",
            "description": "Main feature layer",
            "adminLayerInfo": {
                "viewLayerDefinition": {
                    "table": {
                        "name": "MainLayer",
                        "sourceServiceName": src_service_name,
                        "sourceLayerId": 0,
                        "sourceLayerFields": main_layer_fields,
                        "materialized": False
                    }
                },
                "geometryField": {"name": f"{src_service_name}.Shape"}
            }
        }],
        "tables": [{
            "name": src_flc.tables[0].properties.name,
            "displayField": "FACILITYID",
            "description": "Related inspection table",
            "adminLayerInfo": {
                "viewLayerDefinition": {
                    "table": {
                        "name": "RelatedTable",
                        "sourceServiceName": src_service_name,
                        "sourceLayerId": 1,
                        "sourceLayerFields": related_table_fields,
                        "materialized": False
                    }
                }
            }
        }]
    }
    
    # Apply definition
    view_flc = FeatureLayerCollection.fromitem(view_item)
    view_flc.manager.add_to_definition(view_def)
    
    print(f"  ✓ View recreated with 1 layer and 1 table")
    
    # Save definition
    fn = _safe_filename(f"{new_name}_definition")
    with open(fn, "w") as f:
        json.dump(view_def, f, indent=2)
    print(f"  • Definition saved to: {fn}")
    
    return view_item


def recreate_join_view_with_all_fields(gis):
    """
    Recreate the join view with ALL fields from both sources
    """
    print("\n▶ Recreating join view with all fields")
    
    # Get original view for naming
    orig_item = gis.content.get(JOIN_VIEW_ITEM_ID)
    if not orig_item:
        print("  • Using default name for join view")
        orig_title = "Test Relationship Join View"
    else:
        orig_title = orig_item.title
    
    # Create new view
    new_name = _add_timestamp_to_name(orig_title, CLONE_SUFFIX)
    print(f"  • Creating new join view: {new_name}")
    
    # Get the layers
    gravity_fl = FeatureLayer(MAIN_LAYER_URL, gis)
    cctv_tbl = Table(RELATED_TABLE_URL, gis)
    
    wkid = gravity_fl.properties.extent.spatialReference.get("wkid", 4326)
    
    view_item = gis.content.create_service(
        name=new_name,
        is_view=True,
        wkid=wkid,
        tags=["join", "view", "recreated"],
        snippet=f"Join view recreated from {orig_title}"
    )
    
    print(f"  ✓ Created view: {view_item.id}")
    
    # Define ALL fields from the main layer (with source prefix)
    main_fields = [
        {"name": "MainLayer.OBJECTID", "alias": "Main OBJECTID", "source": "OBJECTID"},
        {"name": "MainLayer.FACILITYID", "alias": "Facility ID", "source": "FACILITYID"},
        {"name": "MainLayer.ASSEMTYPE", "alias": "Assembly Type", "source": "ASSEMTYPE"},
        {"name": "MainLayer.MANUFACTURER", "alias": "Manufacturer", "source": "MANUFACTURER"},
        {"name": "MainLayer.MODEL", "alias": "Model", "source": "MODEL"},
        {"name": "MainLayer.OWNER", "alias": "Owner", "source": "OWNER"},
        {"name": "MainLayer.INSTALLDATE", "alias": "Install Date", "source": "INSTALLDATE"},
        {"name": "MainLayer.GlobalID", "alias": "Main Global ID", "source": "GlobalID"}
    ]
    
    # Define ALL fields from the related table (with source prefix)
    related_fields = [
        {"name": "RelatedTable.OBJECTID", "alias": "Related OBJECTID", "source": "OBJECTID"},
        {"name": "RelatedTable.FACILITYID", "alias": "Related Facility ID", "source": "FACILITYID"},
        {"name": "RelatedTable.DATE", "alias": "Inspection Date", "source": "DATE"},
        {"name": "RelatedTable.INSPECTOR", "alias": "Inspector", "source": "INSPECTOR"},
        {"name": "RelatedTable.CONDITION", "alias": "Condition", "source": "CONDITION"},
        {"name": "RelatedTable.VAL1PSI", "alias": "Valve 1 PSI", "source": "VAL1PSI"},
        {"name": "RelatedTable.VAL1LEAK", "alias": "Valve 1 Leak", "source": "VAL1LEAK"},
        {"name": "RelatedTable.VAL1CLOSE", "alias": "Valve 1 Close", "source": "VAL1CLOSE"},
        {"name": "RelatedTable.VAL1CLEAN", "alias": "Valve 1 Clean", "source": "VAL1CLEAN"},
        {"name": "RelatedTable.VAL1REPAIR", "alias": "Valve 1 Repair", "source": "VAL1REPAIR"},
        {"name": "RelatedTable.VAL2PSI", "alias": "Valve 2 PSI", "source": "VAL2PSI"},
        {"name": "RelatedTable.VAL2LEAK", "alias": "Valve 2 Leak", "source": "VAL2LEAK"},
        {"name": "RelatedTable.VAL2CLOSE", "alias": "Valve 2 Close", "source": "VAL2CLOSE"},
        {"name": "RelatedTable.VAL2CLEAN", "alias": "Valve 2 Clean", "source": "VAL2CLEAN"},
        {"name": "RelatedTable.VAL2REPAIR", "alias": "Valve 2 Repair", "source": "VAL2REPAIR"},
        {"name": "RelatedTable.INLETPSI", "alias": "Inlet PSI", "source": "INLETPSI"},
        {"name": "RelatedTable.INLETCLEAN", "alias": "Inlet Clean", "source": "INLETCLEAN"},
        {"name": "RelatedTable.INREPAIR", "alias": "In Repair", "source": "INREPAIR"},
        {"name": "RelatedTable.RELPSI", "alias": "Relief PSI", "source": "RELPSI"},
        {"name": "RelatedTable.RELCLEAN", "alias": "Relief Clean", "source": "RELCLEAN"},
        {"name": "RelatedTable.RELREPAIR", "alias": "Relief Repair", "source": "RELREPAIR"},
        {"name": "RelatedTable.COMMENTS", "alias": "Comments", "source": "COMMENTS"},
        {"name": "RelatedTable.ASSETGUID", "alias": "Asset GUID", "source": "ASSETGUID"},
        {"name": "RelatedTable.GlobalID", "alias": "Related Global ID", "source": "GlobalID"}
    ]
    
    # Build join definition with explicit fields
    join_def = {
        "layers": [{
            "name": new_name,
            "displayField": "MainLayer.FACILITYID",
            "description": "Join view with all fields",
            "adminLayerInfo": {
                "viewLayerDefinition": {
                    "table": {
                        "name": "MainLayer",
                        "sourceServiceName": _get_service_name(MAIN_LAYER_URL),
                        "sourceLayerId": 0,
                        "sourceLayerFields": main_fields,
                        "relatedTables": [{
                            "name": "RelatedTable",
                            "sourceServiceName": _get_service_name(RELATED_TABLE_URL),
                            "sourceLayerId": 1,
                            "sourceLayerFields": related_fields,
                            "type": "INNER",
                            "parentKeyFields": ["GlobalID"],
                            "keyFields": ["ASSETGUID"],
                            "topFilter": {
                                "groupByFields": "ASSETGUID",
                                "orderByFields": "DATE DESC",
                                "topCount": 1
                            }
                        }],
                        "materialized": False
                    }
                },
                "geometryField": {"name": f"{_get_service_name(MAIN_LAYER_URL)}.Shape"}
            }
        }]
    }
    
    # Apply definition
    view_flc = FeatureLayerCollection.fromitem(view_item)
    view_flc.manager.add_to_definition(join_def)
    
    print(f"  ✓ Join view recreated with all fields from both sources")
    
    # Save definition
    fn = _safe_filename(f"{new_name}_definition")
    with open(fn, "w") as f:
        json.dump(join_def, f, indent=2)
    print(f"  • Definition saved to: {fn}")
    
    return view_item


def main():
    """Main execution"""
    print("Connecting to ArcGIS Online...")
    gis = GIS("https://www.arcgis.com", USERNAME, PASSWORD)
    print(f"Connected as: {gis.users.me.username}")
    
    results = []
    
    # Recreate basic view with all layers and tables
    try:
        print("\n" + "="*60)
        print("RECREATING COMPLETE VIEW (WITH LAYER AND TABLE)")
        print("="*60)
        basic_view = recreate_complete_view(gis)
        results.append(("Complete View", basic_view))
    except Exception as e:
        print(f"\n❌ Failed to recreate complete view: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Recreate join view with all fields
    try:
        print("\n" + "="*60)
        print("RECREATING JOIN VIEW (WITH ALL FIELDS)")
        print("="*60)
        join_view = recreate_join_view_with_all_fields(gis)
        results.append(("Join View", join_view))
    except Exception as e:
        print(f"\n❌ Failed to recreate join view: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Summary
    if results:
        print("\n" + "="*60)
        print("RECREATION SUMMARY")
        print("="*60)
        for name, item in results:
            print(f"✓ {name}: {item.homepage}")
        print("="*60)
        print("\nNOTE: The join view now includes ALL fields from both sources.")
        print("Fields are prefixed with 'MainLayer.' or 'RelatedTable.' to avoid conflicts.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Script failed: {str(e)}")
        import traceback
        traceback.print_exc()