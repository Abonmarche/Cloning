"""
Web Map Recreation Script
This script takes a web map item ID, extracts its JSON definition,
and creates a new web map with the same configuration.
"""

from arcgis.gis import GIS
from arcgis.map import Map
import json
from datetime import datetime
import os

# ===== PARAMETERS TO MODIFY =====
username = "gargarcia"
password = "GOGpas5252***"
item_id = "a7a672315bbc4955a03c407ca36d2f81"
# ================================

def recreate_webmap(username, password, item_id):
    """
    Recreates a web map by extracting its JSON and creating a new map with the same configuration.
    
    Args:
        username: ArcGIS Online username
        password: ArcGIS Online password
        item_id: The item ID of the web map to recreate
    
    Returns:
        The newly created web map item
    """
    
    # Step 1: Connect to ArcGIS Online
    print("Connecting to ArcGIS Online...")
    gis = GIS("https://www.arcgis.com", username, password)
    print(f"Successfully connected as {gis.properties.user.username}")
    
    # Step 2: Get the original web map item
    print(f"\nFetching web map with ID: {item_id}")
    original_item = gis.content.get(item_id)
    
    if not original_item:
        raise ValueError(f"No item found with ID: {item_id}")
    
    if original_item.type != "Web Map":
        raise ValueError(f"Item {item_id} is not a Web Map. It's a {original_item.type}")
    
    print(f"Found web map: {original_item.title}")
    
    # Step 3: Extract the complete web map JSON
    print("\nExtracting web map JSON...")
    webmap_json = original_item.get_data()
    
    # Save JSON to file for reference
    json_filename = f"webmap_{item_id}_backup.json"
    with open(json_filename, 'w') as f:
        json.dump(webmap_json, f, indent=2)
    print(f"Saved web map JSON to: {json_filename}")
    
    # Step 4: Prepare item properties with JSON as text
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{original_item.title}_recreated_{timestamp}"
    
    # Create item properties dictionary with the JSON passed as 'text'
    item_properties_dict = {
        "type": "Web Map",
        "title": new_title,
        "tags": original_item.tags if original_item.tags else ["python", "recreated"],
        "snippet": original_item.snippet if original_item.snippet else f"Recreated from {original_item.title}",
        "description": original_item.description if original_item.description else f"This web map was programmatically recreated from item {item_id}",
        "text": json.dumps(webmap_json)  # Pass the JSON as text - this is the key!
    }
    
    # Copy additional properties if they exist
    property_list = ['accessInformation', 'licenseInfo', 'culture', 'access']
    for prop in property_list:
        if hasattr(original_item, prop) and getattr(original_item, prop) is not None:
            item_properties_dict[prop] = getattr(original_item, prop)
    
    # Add extent if available
    if hasattr(original_item, 'extent') and original_item.extent:
        item_properties_dict['extent'] = original_item.extent
    
    # Add typeKeywords if available
    if hasattr(original_item, 'typeKeywords') and original_item.typeKeywords:
        item_properties_dict['typeKeywords'] = original_item.typeKeywords
    
    # Step 5: Create the new web map using gis.content.add
    print(f"\nCreating new web map: {new_title}")
    new_item = gis.content.add(item_properties=item_properties_dict)
    
    print(f"\nSuccess! New web map created:")
    print(f"  Title: {new_item.title}")
    print(f"  ID: {new_item.id}")
    print(f"  URL: {new_item.homepage}")
    
    # Step 6: Verify the JSON matches
    print("\nVerifying JSON copy...")
    new_item_json = new_item.get_data()
    
    # Save the new JSON for comparison
    new_json_filename = f"webmap_{new_item.id}_created.json"
    with open(new_json_filename, 'w') as f:
        json.dump(new_item_json, f, indent=2)
    print(f"Saved new web map JSON to: {new_json_filename}")
    
    # Compare structure
    original_keys = set(webmap_json.keys())
    new_keys = set(new_item_json.keys())
    
    if original_keys == new_keys:
        print("✓ All top-level JSON properties successfully copied")
    else:
        if original_keys - new_keys:
            print(f"⚠ Missing keys in new map: {original_keys - new_keys}")
        if new_keys - original_keys:
            print(f"⚠ Additional keys in new map: {new_keys - original_keys}")
    
    # Check operational layers
    original_layers = len(webmap_json.get('operationalLayers', []))
    new_layers = len(new_item_json.get('operationalLayers', []))
    print(f"\nLayer count - Original: {original_layers}, New: {new_layers}")
    
    # Check basemap
    if 'baseMap' in webmap_json and 'baseMap' in new_item_json:
        print("✓ Basemap configuration copied")
    
    return new_item

# Main execution
if __name__ == "__main__":
    try:
        # Run the recreation process
        new_webmap_item = recreate_webmap(username, password, item_id)
        
        print("\n" + "="*50)
        print("Web map recreation completed successfully!")
        print("="*50)
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()