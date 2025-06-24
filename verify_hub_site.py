#!/usr/bin/env python
"""
Verify Hub Site Properties
==========================
Script to verify that a cloned Hub site has all required properties and data.
"""

import sys
import json
from pathlib import Path
from arcgis.gis import GIS
import requests
from datetime import datetime

# Add solution_cloner to path
sys.path.insert(0, str(Path(__file__).parent))
from solution_cloner.utils.auth import connect_to_gis

def verify_hub_site(site_id: str, gis: GIS):
    """Verify all properties of a Hub site."""
    print(f"\n{'='*60}")
    print(f"Verifying Hub Site: {site_id}")
    print(f"{'='*60}\n")
    
    # Get the site item
    site_item = gis.content.get(site_id)
    if not site_item:
        print(f"❌ ERROR: Site item not found: {site_id}")
        return False
        
    # 1. Basic item properties
    print("1. ITEM PROPERTIES:")
    print(f"   Title: {site_item.title}")
    print(f"   Type: {site_item.type}")
    print(f"   Owner: {site_item.owner}")
    print(f"   URL: {site_item.url}")
    print(f"   ID: {site_item.id}")
    print(f"   Created: {datetime.fromtimestamp(site_item.created/1000)}")
    print(f"   Modified: {datetime.fromtimestamp(site_item.modified/1000)}")
    
    # 2. Check typeKeywords
    print("\n2. TYPE KEYWORDS:")
    for keyword in site_item.typeKeywords:
        print(f"   - {keyword}")
    
    # 3. Check item properties
    print("\n3. ITEM PROPERTIES OBJECT:")
    if hasattr(site_item, 'properties') and site_item.properties:
        for key, value in site_item.properties.items():
            print(f"   {key}: {value}")
    else:
        print("   ❌ No properties found!")
        
    # 4. Get and analyze site data
    print("\n4. SITE DATA ANALYSIS:")
    site_data = site_item.get_data()
    
    if not site_data:
        print("   ❌ ERROR: No site data found! This causes 'page not found' error.")
        return False
        
    # Save site data for analysis
    output_dir = Path(__file__).parent / "json_files"
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(output_dir / f"verify_site_data_{site_id}_{timestamp}.json", 'w') as f:
        json.dump(site_data, f, indent=2)
    print(f"   ✓ Site data saved to: verify_site_data_{site_id}_{timestamp}.json")
    
    # Check essential fields
    has_values = 'values' in site_data
    print(f"   Has 'values' section: {'✓' if has_values else '❌'}")
    
    if has_values:
        values = site_data['values']
        essential_fields = [
            'subdomain', 'defaultHostname', 'internalUrl', 'clientId',
            'updatedAt', 'updatedBy', 'layout', 'theme'
        ]
        
        print("   Essential fields in 'values':")
        for field in essential_fields:
            has_field = field in values
            value = values.get(field, 'NOT FOUND')
            if isinstance(value, dict):
                value = f"<dict with {len(value)} keys>"
            elif isinstance(value, list):
                value = f"<list with {len(value)} items>"
            print(f"     {field}: {'✓' if has_field else '❌'} - {value}")
            
        # Check catalog
        if 'catalog' in site_data:
            groups = site_data.get('catalog', {}).get('groups', [])
            print(f"\n   Catalog groups: {len(groups)} groups")
            for group_id in groups[:3]:  # Show first 3
                print(f"     - {group_id}")
        else:
            print("\n   ❌ No catalog section found!")
            
    # 5. Check domain registration
    print("\n5. DOMAIN REGISTRATION:")
    if site_item.url:
        print(f"   Item URL: {site_item.url}")
        
        # Try to access the URL
        try:
            response = requests.get(site_item.url, timeout=5, allow_redirects=True)
            print(f"   HTTP Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✓ Site is accessible")
            else:
                print(f"   ❌ Site returned status: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error accessing site: {str(e)}")
            
    # 6. Check groups
    print("\n6. ASSOCIATED GROUPS:")
    content_group_id = site_item.properties.get('contentGroupId') if hasattr(site_item, 'properties') else None
    collab_group_id = site_item.properties.get('collaborationGroupId') if hasattr(site_item, 'properties') else None
    
    if content_group_id:
        content_group = gis.groups.get(content_group_id)
        if content_group:
            print(f"   ✓ Content Group: {content_group.title} ({content_group_id})")
        else:
            print(f"   ❌ Content Group not found: {content_group_id}")
    else:
        print("   ❌ No content group ID in properties")
        
    if collab_group_id:
        collab_group = gis.groups.get(collab_group_id)
        if collab_group:
            print(f"   ✓ Collaboration Group: {collab_group.title} ({collab_group_id})")
        else:
            print(f"   ❌ Collaboration Group not found: {collab_group_id}")
    else:
        print("   ⚠️  No collaboration group ID (may be okay if not admin)")
        
    # 7. Check subdomain vs URL consistency
    print("\n7. URL CONSISTENCY CHECK:")
    if has_values and 'subdomain' in values:
        subdomain = values['subdomain']
        expected_hostname = values.get('defaultHostname', '')
        item_url = site_item.url or ''
        
        print(f"   Subdomain: {subdomain}")
        print(f"   Default Hostname: {expected_hostname}")
        print(f"   Item URL: {item_url}")
        
        # Check if they match
        if subdomain in item_url and subdomain in expected_hostname:
            print("   ✓ URLs are consistent")
        else:
            print("   ❌ URL mismatch detected! This can cause 'page not found'")
            
    return True

def main():
    """Main function to verify hub sites."""
    # Get most recent cloned site from ID mapping
    json_dir = Path(__file__).parent / "json_files"
    
    # Find most recent ID mapping file
    mapping_files = sorted(json_dir.glob("id_mapping_*.json"))
    if not mapping_files:
        print("No ID mapping files found. Please run the cloner first.")
        return
        
    latest_mapping = mapping_files[-1]
    print(f"Using mapping file: {latest_mapping.name}")
    
    with open(latest_mapping) as f:
        mappings = json.load(f)
        
    # Connect to destination org to verify
    from dotenv import load_dotenv
    import os
    
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    
    dest_gis = connect_to_gis(
        url=os.getenv('DEST_URL'),
        username=os.getenv('DEST_USERNAME'),
        password=os.getenv('DEST_PASSWORD')
    )
    
    print(f"Connected to: {dest_gis.url} as {dest_gis.users.me.username}")
    
    # Find hub sites in the mapping
    hub_sites = []
    for old_id, new_id in mappings.get('ids', {}).items():
        item = dest_gis.content.get(new_id)
        if item and item.type in ['Hub Site Application', 'Site Application']:
            hub_sites.append((old_id, new_id, item))
            
    if not hub_sites:
        print("No Hub sites found in the latest cloning session.")
        return
        
    # Verify each hub site
    for old_id, new_id, item in hub_sites:
        verify_hub_site(new_id, dest_gis)
        
if __name__ == "__main__":
    main()