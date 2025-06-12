"""
Dashboard Recreation Script
This script takes a dashboard item ID, extracts its JSON definition,
and creates a new dashboard with the same configuration.
"""

from arcgis.gis import GIS
import json
from datetime import datetime
import os

# ===== PARAMETERS TO MODIFY =====
username = "<your_username>"
password = "<your_password>"
item_id = "5086516b807b46c39ec0236aaba46a1c"
# ================================

def recreate_dashboard(username, password, item_id):
    """
    Recreates a dashboard by extracting its JSON and creating a new dashboard with the same configuration.
    
    Args:
        username: ArcGIS Online username
        password: ArcGIS Online password
        item_id: The item ID of the dashboard to recreate
    
    Returns:
        The newly created dashboard item
    """
    
    # Step 1: Connect to ArcGIS Online
    print("Connecting to ArcGIS Online...")
    gis = GIS("https://www.arcgis.com", username, password)
    print(f"Successfully connected as {gis.properties.user.username}")
    
    # Step 2: Get the original dashboard item
    print(f"\nFetching dashboard with ID: {item_id}")
    original_item = gis.content.get(item_id)
    
    if not original_item:
        raise ValueError(f"No item found with ID: {item_id}")
    
    if original_item.type != "Dashboard":
        raise ValueError(f"Item {item_id} is not a Dashboard. It's a {original_item.type}")
    
    print(f"Found dashboard: {original_item.title}")
    
    # Step 3: Extract the complete dashboard JSON
    print("\nExtracting dashboard JSON...")
    dashboard_json = original_item.get_data()
    
    # Save JSON to file for reference
    json_filename = f"dashboard_{item_id}_backup.json"
    with open(json_filename, 'w') as f:
        json.dump(dashboard_json, f, indent=2)
    print(f"Saved dashboard JSON to: {json_filename}")
    
    # Print some info about the dashboard structure
    if 'widgets' in dashboard_json:
        widget_count = len(dashboard_json['widgets'])
        print(f"\nDashboard contains {widget_count} widgets")
        
        # Count widget types
        widget_types = {}
        for widget in dashboard_json['widgets']:
            widget_type = widget.get('type', 'Unknown')
            widget_types[widget_type] = widget_types.get(widget_type, 0) + 1
        
        print("Widget breakdown:")
        for wtype, count in widget_types.items():
            print(f"  - {wtype}: {count}")
    
    # Step 4: Prepare item properties with JSON as text
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_title = f"{original_item.title}_recreated_{timestamp}"
    
    # Create item properties dictionary with the JSON passed as 'text'
    item_properties_dict = {
        "type": "Dashboard",
        "title": new_title,
        "tags": original_item.tags if original_item.tags else ["python", "recreated", "dashboard"],
        "snippet": original_item.snippet if original_item.snippet else f"Recreated from {original_item.title}",
        "description": original_item.description if original_item.description else f"This dashboard was programmatically recreated from item {item_id}",
        "text": json.dumps(dashboard_json)  # Pass the JSON as text - this is the key!
    }
    
    # Copy additional properties if they exist
    property_list = ['accessInformation', 'licenseInfo', 'culture', 'access']
    for prop in property_list:
        if hasattr(original_item, prop) and getattr(original_item, prop) is not None:
            item_properties_dict[prop] = getattr(original_item, prop)
    
    # Add extent if available (some dashboards may have extent)
    if hasattr(original_item, 'extent') and original_item.extent:
        item_properties_dict['extent'] = original_item.extent
    
    # Add typeKeywords if available (important for dashboard functionality)
    if hasattr(original_item, 'typeKeywords') and original_item.typeKeywords:
        item_properties_dict['typeKeywords'] = original_item.typeKeywords
    
    # Step 5: Create the new dashboard using gis.content.add
    print(f"\nCreating new dashboard: {new_title}")
    new_item = gis.content.add(item_properties=item_properties_dict)
    
    print(f"\nSuccess! New dashboard created:")
    print(f"  Title: {new_item.title}")
    print(f"  ID: {new_item.id}")
    print(f"  URL: {new_item.homepage}")
    
    # Step 6: Verify the JSON matches
    print("\nVerifying JSON copy...")
    new_item_json = new_item.get_data()
    
    # Save the new JSON for comparison
    new_json_filename = f"dashboard_{new_item.id}_created.json"
    with open(new_json_filename, 'w') as f:
        json.dump(new_item_json, f, indent=2)
    print(f"Saved new dashboard JSON to: {new_json_filename}")
    
    # Compare structure
    original_keys = set(dashboard_json.keys())
    new_keys = set(new_item_json.keys())
    
    if original_keys == new_keys:
        print("✓ All top-level JSON properties successfully copied")
    else:
        if original_keys - new_keys:
            print(f"⚠ Missing keys in new dashboard: {original_keys - new_keys}")
        if new_keys - original_keys:
            print(f"⚠ Additional keys in new dashboard: {new_keys - original_keys}")
    
    # Check widgets
    if 'widgets' in dashboard_json and 'widgets' in new_item_json:
        original_widgets = len(dashboard_json.get('widgets', []))
        new_widgets = len(new_item_json.get('widgets', []))
        print(f"\nWidget count - Original: {original_widgets}, New: {new_widgets}")
        
        if original_widgets == new_widgets:
            print("✓ All widgets successfully copied")
    
    # Check data sources
    if 'dataSources' in dashboard_json and 'dataSources' in new_item_json:
        original_sources = len(dashboard_json.get('dataSources', {}))
        new_sources = len(new_item_json.get('dataSources', {}))
        print(f"\nData source count - Original: {original_sources}, New: {new_sources}")
    
    return new_item

# Main execution
if __name__ == "__main__":
    try:
        # Run the recreation process
        new_dashboard_item = recreate_dashboard(username, password, item_id)
        
        print("\n" + "="*50)
        print("Dashboard recreation completed successfully!")
        print("="*50)
        
        # Additional notes
        print("\nNOTE: The recreated dashboard references the same data sources")
        print("as the original. If you need to update data sources, you'll")
        print("need to modify the JSON before creating the new dashboard.")
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()