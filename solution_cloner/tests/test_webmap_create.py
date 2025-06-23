#!/usr/bin/env python
"""
Test script to debug web map creation issue
"""

from arcgis.gis import GIS
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_webmap_creation():
    """Test creating a simple web map"""
    
    # Connect to ArcGIS Online
    print("Connecting to ArcGIS Online...")
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
    
    # Create item properties exactly as in recreate_WebMap_by_json.py
    item_properties_dict = {
        "type": "Web Map",
        "title": "Test Web Map Debug",
        "tags": ["test", "debug"],
        "snippet": "Testing web map creation",
        "description": "Debug test for web map creation issue",
        "text": json.dumps(webmap_json)  # Pass JSON as text
    }
    
    try:
        print("\nAttempting to create web map...")
        print(f"JSON length: {len(item_properties_dict['text'])}")
        
        # Try the exact same call as in recreate_WebMap_by_json.py
        new_item = gis.content.add(item_properties=item_properties_dict)
        
        print(f"\nSuccess! Created web map:")
        print(f"  ID: {new_item.id}")
        print(f"  Title: {new_item.title}")
        print(f"  URL: {new_item.homepage}")
        
        # Clean up
        print("\nDeleting test item...")
        new_item.delete()
        print("Test item deleted")
        
    except Exception as e:
        print(f"\nError creating web map: {e}")
        import traceback
        traceback.print_exc()
        
        # Try alternate approach
        print("\n\nTrying alternate approach without item_properties parameter name...")
        try:
            new_item = gis.content.add(item_properties_dict)
            print("Success with alternate approach!")
            new_item.delete()
        except Exception as e2:
            print(f"Alternate approach also failed: {e2}")

if __name__ == "__main__":
    test_webmap_creation()