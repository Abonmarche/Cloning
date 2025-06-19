#!/usr/bin/env python
"""
Test the fixed feature layer cloner
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from arcgis.gis import GIS
from solution_cloner.cloners.feature_layer_cloner import FeatureLayerCloner
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_fixed_cloner():
    """Test cloning with the fixed exclude properties"""
    
    # Test with the same problematic item
    ITEM_ID = "fe7f19431cbc495ba71871a07b25db19"  # Test Relationship
    USERNAME = "xxx"  # Replace with actual username
    PASSWORD = "xxx"  # Replace with actual password
    
    print("Testing fixed feature layer cloner...")
    print("=" * 60)
    
    # Connect
    gis = GIS("https://www.arcgis.com", USERNAME, PASSWORD)
    print(f"Connected as: {gis.users.me.username}")
    
    # Get the item
    item = gis.content.get(ITEM_ID)
    if not item:
        print(f"Could not find item: {ITEM_ID}")
        return
    
    print(f"\nItem: {item.title} ({item.type})")
    print(f"Description: {item.description}")
    
    # Create cloner
    cloner = FeatureLayerCloner()
    
    # Show excluded properties count
    print(f"\nExcluding {len(cloner.EXCLUDE_PROPS)} server-managed properties")
    
    # Create source item dict
    source_item = {
        'id': item.id,
        'title': item.title,
        'type': item.type
    }
    
    # Test cloning
    print("\nAttempting to clone...")
    try:
        new_item = cloner.clone(
            source_item=source_item,
            source_gis=gis,
            dest_gis=gis,
            dest_folder=None,
            id_mapping={},
            clone_data=False,
            create_dummy_features=False  # Skip dummy features for now
        )
        
        if new_item:
            print(f"\n✓ SUCCESS! Cloned to: {new_item.title}")
            print(f"✓ Item ID: {new_item.id}")
            print(f"✓ View at: {new_item.homepage}")
            
            # Clean up test item
            try:
                print("\nCleaning up test item...")
                new_item.delete()
                print("✓ Test item deleted")
            except:
                print("⚠️  Could not delete test item")
        else:
            print("\n✗ Clone returned None")
            
    except Exception as e:
        print(f"\n✗ Clone failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fixed_cloner()