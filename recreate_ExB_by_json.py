"""
Experience Builder Recreation Script
This script takes an Experience Builder application item ID, extracts its JSON definition,
and creates a new Experience Builder app with the same configuration.
"""

from arcgis.gis import GIS
import json
from datetime import datetime
import os

# ===== PARAMETERS TO MODIFY =====
username = "gargarcia"
password = "GOGpas5252***"
item_id = "2472a5b0900a4d45840f8b3b838fe5e9"
# ================================

def recreate_experience_builder(username, password, item_id):
    """
    Recreates an Experience Builder application by extracting its JSON and creating a new app with the same configuration.
    
    Args:
        username: ArcGIS Online username
        password: ArcGIS Online password
        item_id: The item ID of the Experience Builder app to recreate
    
    Returns:
        The newly created Experience Builder item
    """
    
    # Step 1: Connect to ArcGIS Online
    print("Connecting to ArcGIS Online...")
    gis = GIS("https://www.arcgis.com", username, password)
    print(f"Successfully connected as {gis.properties.user.username}")
    
    # Step 2: Get the original Experience Builder item
    print(f"\nFetching Experience Builder app with ID: {item_id}")
    original_item = gis.content.get(item_id)
    
    if not original_item:
        raise ValueError(f"No item found with ID: {item_id}")
    
    # Experience Builder apps can have different type names
    valid_types = ["Web Experience", "StoryMap", "Web Experience Template"]
    if original_item.type not in valid_types:
        print(f"Warning: Item type '{original_item.type}' may not be an Experience Builder app")
        print("Proceeding anyway...")
    
    print(f"Found Experience Builder app: {original_item.title}")
    print(f"Type: {original_item.type}")
    
    # Step 3: Extract the complete Experience Builder JSON
    print("\nExtracting Experience Builder JSON...")
    experience_json = original_item.get_data()
    
    # Save JSON to file for reference
    json_filename = f"experience_builder_{item_id}_backup.json"
    with open(json_filename, 'w') as f:
        json.dump(experience_json, f, indent=2)
    print(f"Saved Experience Builder JSON to: {json_filename}")
    
    # Print some info about the Experience structure
    if experience_json:
        # Experience Builder structure varies, but commonly has these elements
        if 'pages' in experience_json:
            page_count = len(experience_json.get('pages', {}))
            print(f"\nExperience contains {page_count} pages")
        
        if 'widgets' in experience_json:
            widget_count = len(experience_json.get('widgets', {}))
            print(f"Experience contains {widget_count} widgets")
            
            # Count widget types if available
            widget_types = {}
            for widget_id, widget_data in experience_json.get('widgets', {}).items():
                if isinstance(widget_data, dict):
                    widget_type = widget_data.get('manifest', {}).get('name', 'Unknown')
                    widget_types[widget_type] = widget_types.get(widget_type, 0) + 1
            
            if widget_types:
                print("Widget breakdown:")
                for wtype, count in widget_types.items():
                    print(f"  - {wtype}: {count}")
        
        if 'dataSources' in experience_json:
            datasource_count = len(experience_json.get('dataSources', {}))
            print(f"Experience uses {datasource_count} data sources")
        
        if 'themes' in experience_json:
            theme_count = len(experience_json.get('themes', {}))
            print(f"Experience has {theme_count} theme(s)")
    
    # Step 4: Prepare item properties with JSON as text
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{original_item.title}_recreated_{timestamp}"
    
    # Create item properties dictionary with the JSON passed as 'text'
    item_properties_dict = {
        "type": original_item.type,  # Use the same type as original
        "title": new_title,
        "tags": original_item.tags if original_item.tags else ["python", "recreated", "experience builder"],
        "snippet": original_item.snippet if original_item.snippet else f"Recreated from {original_item.title}",
        "description": original_item.description if original_item.description else f"This Experience Builder app was programmatically recreated from item {item_id}",
        "text": json.dumps(experience_json)  # Pass the JSON as text - this is the key!
    }
    
    # Copy additional properties if they exist
    property_list = ['accessInformation', 'licenseInfo', 'culture', 'access', 'properties']
    for prop in property_list:
        if hasattr(original_item, prop) and getattr(original_item, prop) is not None:
            item_properties_dict[prop] = getattr(original_item, prop)
    
    # Add extent if available
    if hasattr(original_item, 'extent') and original_item.extent:
        item_properties_dict['extent'] = original_item.extent
    
    # Add typeKeywords if available (critical for Experience Builder functionality)
    if hasattr(original_item, 'typeKeywords') and original_item.typeKeywords:
        item_properties_dict['typeKeywords'] = original_item.typeKeywords
    
    # Add url if available (some Experience Builder apps have custom URLs)
    if hasattr(original_item, 'url') and original_item.url:
        item_properties_dict['url'] = original_item.url
    
    # Step 5: Create the new Experience Builder app using gis.content.add
    print(f"\nCreating new Experience Builder app: {new_title}")
    new_item = gis.content.add(item_properties=item_properties_dict)

    # Step 5.1: Write the Builder-draft config
    print("Writing draft config for Experience Builder…")
    new_item.resources.add(
        folder_name="config",       # creates the folder if it doesn’t exist
        file_name="config.json",
        text=json.dumps(experience_json)   # same JSON you put in item.text
    )
    print("✓ Draft config written to resources/config/config.json")

    print(f"\nSuccess! New Experience Builder app created:")
    print(f"  Title: {new_item.title}")
    print(f"  ID: {new_item.id}")
    print(f"  URL: {new_item.homepage}")
    
    # Step 6: Verify the JSON matches
    print("\nVerifying JSON copy...")
    new_item_json = new_item.get_data()
    
    # Save the new JSON for comparison
    new_json_filename = f"experience_builder_{new_item.id}_created.json"
    with open(new_json_filename, 'w') as f:
        json.dump(new_item_json, f, indent=2)
    print(f"Saved new Experience Builder JSON to: {new_json_filename}")
    
    # Compare structure
    original_keys = set(experience_json.keys())
    new_keys = set(new_item_json.keys())
    
    if original_keys == new_keys:
        print("✓ All top-level JSON properties successfully copied")
    else:
        if original_keys - new_keys:
            print(f"⚠ Missing keys in new experience: {original_keys - new_keys}")
        if new_keys - original_keys:
            print(f"⚠ Additional keys in new experience: {new_keys - original_keys}")
    
    # Check key components
    components_to_check = ['pages', 'widgets', 'dataSources', 'themes', 'layouts']
    for component in components_to_check:
        if component in experience_json and component in new_item_json:
            original_count = len(experience_json.get(component, {}))
            new_count = len(new_item_json.get(component, {}))
            if original_count == new_count:
                print(f"✓ {component}: {original_count} items successfully copied")
            else:
                print(f"⚠ {component}: Original had {original_count}, new has {new_count}")
    
    return new_item

# Main execution
if __name__ == "__main__":
    try:
        # Run the recreation process
        new_experience_item = recreate_experience_builder(username, password, item_id)
        
        print("\n" + "="*50)
        print("Experience Builder recreation completed successfully!")
        print("="*50)
        
        # Additional notes
        print("\nIMPORTANT NOTES:")
        print("1. The recreated Experience references the same data sources as the original")
        print("2. Custom widgets or extensions must be available in your organization")
        print("3. If the original used custom themes, ensure they're accessible")
        print("4. The new Experience may need to be opened in Experience Builder to")
        print("   fully activate all functionality")
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()