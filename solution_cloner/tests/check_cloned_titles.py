"""
Script to check the titles of cloned items in ArcGIS Online
"""

from arcgis.gis import GIS
import json
from datetime import datetime

# Item IDs from the id_mapping
CLONED_ITEM_IDS = {
    "view_1": "fc0f560250d84daeab19a47de1fcfa1b",
    "join_view": "4d7d9a3b9798419b944c5d043b20a49e", 
    "view_2": "3be85308e80a49b8a1a61adbe0c2cb08"
}

def main():
    print("=" * 80)
    print("CHECKING CLONED ITEM TITLES")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Connect to ArcGIS Online
    print("Connecting to ArcGIS Online...")
    gis = GIS("https://aci-dev.maps.arcgis.com", username="gogarcia", password="xxx")
    print(f"✓ Connected as: {gis.properties.user.username}")
    print()
    
    # Check each cloned item
    print("Checking cloned items:")
    print("-" * 60)
    
    for item_type, item_id in CLONED_ITEM_IDS.items():
        try:
            # Get the item
            item = gis.content.get(item_id)
            
            if item:
                print(f"\n{item_type.upper()}:")
                print(f"  ID:    {item.id}")
                print(f"  Title: {item.title}")
                print(f"  Type:  {item.type}")
                print(f"  Owner: {item.owner}")
                
                # Check if title has any suffixes
                if "_clone" in item.title or "clone" in item.title.lower():
                    print(f"  ⚠️  Title contains 'clone' suffix")
                else:
                    print(f"  ✓ Title appears clean (no clone suffix)")
                    
            else:
                print(f"\n{item_type.upper()}: ❌ Item not found (ID: {item_id})")
                
        except Exception as e:
            print(f"\n{item_type.upper()}: ❌ Error accessing item (ID: {item_id})")
            print(f"  Error: {str(e)}")
    
    print("\n" + "=" * 80)
    print("TITLE CHECK COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()