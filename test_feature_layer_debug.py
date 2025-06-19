#!/usr/bin/env python
"""
Debug test for feature layer cloner
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from arcgis.gis import GIS
from solution_cloner.cloners.feature_layer_cloner import FeatureLayerCloner
import logging
import json

# Configure logging to see all debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feature_layer_debug.log'),
        logging.StreamHandler()
    ]
)

def test_feature_layer_clone():
    """Test cloning a feature layer with debug output"""
    
    # Use the same item that works in the test script
    ITEM_ID = "59ad9d29b3c444c888e921db6ea7f092"
    USERNAME = "xxx"  # Replace with actual username
    PASSWORD = "xxx"  # Replace with actual password
    
    print("Connecting to ArcGIS Online...")
    gis = GIS("https://www.arcgis.com", USERNAME, PASSWORD)
    print(f"Connected as: {gis.users.me.username}")
    
    # Get the item
    item = gis.content.get(ITEM_ID)
    if not item:
        print(f"Could not find item: {ITEM_ID}")
        return
    
    print(f"\nTesting with item: {item.title} ({item.type})")
    
    # Create cloner
    cloner = FeatureLayerCloner()
    
    # Create source item dict
    source_item = {
        'id': item.id,
        'title': item.title,
        'type': item.type
    }
    
    # Test extraction first
    print("\n1. Testing definition extraction...")
    try:
        definition = cloner.extract_definition(ITEM_ID, gis)
        print(f"   ✓ Extracted definition with {len(definition.get('layers', []))} layers, {len(definition.get('tables', []))} tables")
        
        # Save for inspection
        with open(f'debug_extracted_definition_{ITEM_ID}.json', 'w') as f:
            json.dump(definition, f, indent=2)
        print(f"   ✓ Saved definition to debug_extracted_definition_{ITEM_ID}.json")
    except Exception as e:
        print(f"   ✗ Extraction failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Test cloning
    print("\n2. Testing cloning...")
    try:
        new_item = cloner.clone(
            source_item=source_item,
            source_gis=gis,
            dest_gis=gis,
            dest_folder=None,
            id_mapping={},
            clone_data=False,
            create_dummy_features=True
        )
        
        if new_item:
            print(f"   ✓ Successfully cloned to: {new_item.title} ({new_item.id})")
            print(f"   ✓ View at: {new_item.homepage}")
        else:
            print("   ✗ Clone returned None")
            
    except Exception as e:
        print(f"   ✗ Clone failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Check if there's a saved payload
        import glob
        payloads = glob.glob(f"json_files/add_to_definition_payload_{ITEM_ID}_*.json")
        if payloads:
            latest = max(payloads)
            print(f"\n   Check the payload that was sent: {latest}")

if __name__ == "__main__":
    test_feature_layer_clone()