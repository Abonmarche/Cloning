#!/usr/bin/env python
"""
Test web map creation with monkey patch for _is_geoenabled
"""

from arcgis.gis import GIS
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def patch_arcgis():
    """Apply monkey patch to fix missing _is_geoenabled"""
    import arcgis.features.geo
    
    # Add the missing function
    def _is_geoenabled(data):
        """Dummy implementation that always returns False"""
        return False
    
    # Patch it
    arcgis.features.geo._is_geoenabled = _is_geoenabled
    print("Applied _is_geoenabled patch")

def test_webmap_creation():
    """Test creating a simple web map with patch"""
    
    # Apply patch first
    patch_arcgis()
    
    # Connect to ArcGIS Online
    print("\nConnecting to ArcGIS Online...")
    gis = GIS(
        "https://www.arcgis.com",
        os.getenv('DEST_USERNAME'),
        os.getenv('DEST_PASSWORD')
    )
    print(f"Connected as: {gis.properties.user.username}")
    
    # Create minimal web map JSON
    webmap_json = {
        "operationalLayers": [],
        "baseMap": {
            "baseMapLayers": [{
                "id": "defaultBasemap",
                "layerType": "ArcGISTiledMapServiceLayer",
                "url": "https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer",
                "visibility": True
            }]
        },
        "version": "2.31"
    }
    
    # Create item properties
    item_properties_dict = {
        "type": "Web Map",
        "title": "Test Web Map with Patch",
        "tags": ["test", "patch"],
        "snippet": "Testing web map creation with patch",
        "description": "Debug test for web map creation with _is_geoenabled patch",
        "text": json.dumps(webmap_json)
    }
    
    try:
        print("\nAttempting to create web map with patch...")
        
        # Try creating the web map
        new_item = gis.content.add(item_properties=item_properties_dict)
        
        print(f"\nSuccess! Created web map:")
        print(f"  ID: {new_item.id}")
        print(f"  Title: {new_item.title}")
        print(f"  URL: {new_item.homepage}")
        
        # Verify it's a web map
        print(f"  Type: {new_item.type}")
        
        # Clean up
        print("\nDeleting test item...")
        new_item.delete()
        print("Test item deleted")
        
        return True
        
    except Exception as e:
        print(f"\nError creating web map even with patch: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_webmap_creation()
    if success:
        print("\n✅ Web map creation works with patch!")
        print("\nTo apply this fix to the solution cloner:")
        print("1. Add the patch_arcgis() function to web_map_cloner.py")
        print("2. Call it in the __init__ method")
    else:
        print("\n❌ Web map creation still failing")