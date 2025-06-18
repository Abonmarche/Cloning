"""
Test script to extract join view configuration from ArcGIS Online.
This script focuses on the /admin endpoint to get detailed join parameters.
"""

from arcgis.gis import GIS
import sys
import logging
import requests

# ═════ MODIFY FOR TESTING ════════════════════════════════════════════════════
USERNAME   = "gargarcia"
PASSWORD   = "GOGpas5252***"
SRC_VIEWID = "0aef75cb383448c5a94efa802bfe6954"   # ← the join view layer to check
# ════════════════════════════════════════════════════════════════════════════

def get_join_view_details(username, password, view_id):
    """
    Connects to ArcGIS Online, inspects a join view, and prints its
    source layers and detailed join parameters by using the admin API.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    
    try:
        logging.info("🔐 Connecting to ArcGIS Online…")
        gis = GIS("https://www.arcgis.com", username, password)
        logging.info(f"✓ Signed in as: {gis.users.me.username}")
    except Exception as e:
        logging.error(f"❌ Failed to connect to ArcGIS Online: {e}")
        sys.exit(1)

    # Get the view item
    src_item = gis.content.get(view_id)
    if not src_item:
        logging.error(f"⚠ No item found with ID: {view_id}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"Inspecting View: {src_item.title}")
    print(f"Item ID: {src_item.id}")
    print(f"Type: {src_item.type}")
    print(f"{'='*60}\n")

    # --- Step 1: Get Source Layer URLs (for context) ---
    print("🔎 Step 1: Finding Source Layers (from /sources endpoint)")
    print("-" * 60)
    
    sources_url = f"{src_item.url}/0/sources"
    params = {"f": "json", "token": gis._con.token}
    
    try:
        r = requests.get(sources_url, params=params)
        r.raise_for_status()
        sources_data = r.json()
        
        if "layers" in sources_data and sources_data["layers"]:
            print(f"✓ Found {len(sources_data['layers'])} source layers.")
        else:
            print("  - No source layers found at this endpoint.")
            
    except requests.exceptions.HTTPError as e:
        logging.warning(f"⚠ Could not query the /sources endpoint: {e}")
    
    # --- Step 2: Get Detailed Join Definition from the Administrative REST API ---
    print("\n🔎 Step 2: Reading Detailed Join Definition (from admin API path)")
    print("-" * 60)

    # The item.url points to the public '/rest/services/' endpoint.
    # We must construct the '/rest/admin/services/' URL to get detailed info.
    if "/rest/services/" not in src_item.url:
        logging.error("❌ Cannot construct admin URL. '/rest/services/' not found in item URL.")
        return
        
    admin_url = src_item.url.replace("/rest/services/", "/rest/admin/services/") + "/0"
    logging.info(f"Querying admin endpoint: {admin_url}")
    
    try:
        r = requests.get(admin_url, params=params)
        r.raise_for_status()
        admin_data = r.json()

        # The join definition is nested inside the 'adminLayerInfo' object
        if "adminLayerInfo" in admin_data and admin_data["adminLayerInfo"]:
            admin_info = admin_data["adminLayerInfo"]
            
            if 'viewLayerDefinition' in admin_info:
                vld = admin_info['viewLayerDefinition']
                if 'table' in vld:
                    primary_table = vld['table']
                    primary_service = primary_table.get('sourceServiceName') #
                    primary_layer_id = primary_table.get('sourceLayerId') #
                    
                    print("✓ Successfully retrieved view definition.")
                    print("\n=== Primary Layer (Left Side) ===")
                    print(f"  Source Service Name: {primary_service}") #
                    print(f"  Source Layer ID: {primary_layer_id}") #

                    if 'relatedTables' in primary_table and primary_table['relatedTables']:
                        print("\n=== Joined Tables/Layers (Right Side) ===")
                        for i, rt in enumerate(primary_table['relatedTables']): #
                            print(f"\n--- Join {i+1} ---")
                            join_type = rt.get('type', 'N/A') #
                            parent_keys = rt.get('parentKeyFields', []) #
                            child_keys = rt.get('keyFields', []) #
                            
                            print(f"  Join Type: {join_type}") #
                            print(f"  Source Service Name: {rt.get('sourceServiceName')}") #
                            print(f"  Source Layer ID: {rt.get('sourceLayerId')}") #
                            print(f"  Join Condition: {primary_service}({parent_keys[0]}) → {rt.get('sourceServiceName')}({child_keys[0]})") #
                            
                            if 'topFilter' in rt: #
                                top_filter = rt['topFilter'] #
                                print("\n  Cardinality (One-to-One):")
                                print(f"    - Group By Field: {top_filter.get('groupByFields')}") #
                                print(f"    - Record to Keep: Based on rule '{top_filter.get('orderByFields')}'") #
                                print(f"    - Count: {top_filter.get('topCount')}") #
                            else:
                                 print("\n  Cardinality: One-to-Many (no topFilter defined)")

                    else:
                        print("\n- No related/joined tables found in the definition.")
                else:
                     logging.warning("⚠ 'viewLayerDefinition' found, but it contains no 'table' object.")
            else:
                logging.warning("⚠ 'adminLayerInfo' found, but it contains no 'viewLayerDefinition' object.")
        else:
            logging.error("❌ 'adminLayerInfo' object not found in the response from the admin endpoint.")
            if 'error' in admin_data:
                 logging.error(f"  ArcGIS API Error: {admin_data['error'].get('message', 'Unknown error')}")


    except requests.exceptions.HTTPError as e:
        logging.error(f"❌ HTTP Error querying the admin endpoint: {e}")
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    get_join_view_details(USERNAME, PASSWORD, SRC_VIEWID)