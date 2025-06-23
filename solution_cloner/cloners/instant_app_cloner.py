"""
Instant App Cloner - Clone ArcGIS Online Instant Apps with reference updates.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from copy import deepcopy
from arcgis.gis import GIS, Item

from ..base.base_cloner import BaseCloner
from ..utils.json_handler import save_json

# Configure logger
logger = logging.getLogger(__name__)


class InstantAppCloner(BaseCloner):
    """Clone Instant Apps (Web Mapping Applications) with reference updates."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the Instant App cloner."""
        super().__init__()
        self.supported_types = ['Web Mapping Application']
        self.json_output_dir = json_output_dir or Path("json_files")
        
    def clone(
        self,
        source_item: Dict[str, Any],
        source_gis: GIS,
        dest_gis: GIS,
        dest_folder: str,
        id_mapping: Dict[str, str],
        **kwargs
    ) -> Optional[Item]:
        """
        Clone an Instant App.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            **kwargs: Additional arguments
            
        Returns:
            Cloned instant app item or None if failed
        """
        try:
            # Get source instant app item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item or src_item.type != 'Web Mapping Application':
                logger.error(f"Item {source_item['id']} is not a Web Mapping Application")
                return None
                
            # Check if it's actually an Instant App based on type keywords
            type_keywords = src_item.typeKeywords or []
            # Instant Apps typically have keywords like "Instant App", "instantApp", or specific app template keywords
            is_instant_app = any(
                keyword.lower() in ['instant app', 'instantapp'] or 
                'Template' in keyword or
                'Web AppBuilder' not in keyword  # Exclude Web AppBuilder apps
                for keyword in type_keywords
            )
            
            if not is_instant_app:
                logger.warning(f"Item {src_item.title} doesn't appear to be an Instant App based on type keywords")
                # Continue anyway as it might still be an instant app
                
            logger.info(f"Cloning instant app: {src_item.title}")
            logger.debug(f"Type keywords: {type_keywords}")
            
            # Get the instant app JSON definition
            src_json = src_item.get_data() or {}
            
            # Save original JSON for reference
            save_json(
                src_json,
                self.json_output_dir / f"instantapp_original_{src_item.id}.json"
            )
            
            # Log web map count
            wm_count = len(src_json.get("values", {}).get("mapItemCollection", []))
            logger.info(f"Instant app contains {wm_count} web map(s)")
            
            # Create a scrubbed copy for the new item
            scrubbed = deepcopy(src_json)
            
            # Remove unique keys (but KEEP 'source' so Builder loads properly)
            for key in ("datePublished", "id"):
                scrubbed.pop(key, None)
            
            # Update references if ID mapping provided
            if id_mapping:
                logger.info("Updating references in instant app")
                scrubbed = self._update_instantapp_references(scrubbed, id_mapping, source_gis, dest_gis)
                
                # Save updated JSON for reference
                save_json(
                    scrubbed,
                    self.json_output_dir / f"instantapp_updated_{src_item.id}.json"
                )
            
            # Update internal title to match what we'll use
            if "values" in scrubbed:
                scrubbed["values"]["title"] = src_item.title
            
            # Create item properties
            item_properties = {
                'type': 'Web Mapping Application',
                'title': src_item.title,  # Use original title, no suffix
                'snippet': src_item.snippet or '',
                'description': src_item.description or '',
                'tags': src_item.tags or [],
                'typeKeywords': src_item.typeKeywords or [],
                'extent': src_item.extent,
                'text': json.dumps(scrubbed)  # Pass the JSON as text
            }
            
            # Copy additional properties if they exist
            for prop in ['accessInformation', 'licenseInfo', 'culture', 'access']:
                if hasattr(src_item, prop) and getattr(src_item, prop):
                    item_properties[prop] = getattr(src_item, prop)
            
            # Create the new instant app
            logger.info(f"Creating instant app: {item_properties['title']}")
            new_item = dest_gis.content.add(
                item_properties,
                folder=dest_folder
            )
            
            if new_item:
                logger.info(f"Successfully created instant app: {new_item.id}")
                
                # Build and set URL so "View" button appears
                if src_item.url:
                    base_url = src_item.url.split("?appid=")[0]  # Get template path only
                    new_url = f"{base_url}?appid={new_item.id}"
                    try:
                        new_item.update(item_properties={"url": new_url})
                        logger.info(f"Set instant app URL: {new_url}")
                    except Exception as e:
                        logger.warning(f"Failed to set URL: {str(e)}")
                else:
                    logger.warning("Source item had no URL; skipping URL configuration")
                
                # Copy thumbnail if exists
                if src_item.thumbnail:
                    try:
                        new_item.update(thumbnail=src_item.thumbnail)
                    except Exception as e:
                        logger.warning(f"Failed to copy thumbnail: {str(e)}")
                        
                # Copy metadata if exists
                if hasattr(src_item, 'metadata') and src_item.metadata:
                    try:
                        new_item.update(metadata=src_item.metadata)
                    except Exception as e:
                        logger.warning(f"Failed to copy metadata: {str(e)}")
                        
                # Verify the JSON was properly saved
                try:
                    new_json = new_item.get_data() or {}
                    new_wm_count = len(new_json.get('values', {}).get('mapItemCollection', []))
                    logger.info(f"Verified instant app - original maps: {wm_count}, cloned maps: {new_wm_count}")
                except Exception as e:
                    logger.warning(f"Could not verify cloned JSON: {str(e)}")
                    
                return new_item
            else:
                logger.error("Failed to create instant app")
                return None
                
        except Exception as e:
            logger.error(f"Error cloning instant app: {str(e)}")
            return None
            
            
    def _update_instantapp_references(self, app_json: Dict, id_mapping: Dict[str, str], source_gis: GIS, dest_gis: GIS) -> Dict:
        """
        Update all references in instant app JSON.
        
        Args:
            app_json: Instant app JSON definition
            id_mapping: Dictionary of ID mappings
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            
        Returns:
            Updated instant app JSON
        """
        # Deep copy to avoid modifying original
        updated = json.loads(json.dumps(app_json))
        
        # Handle different mapping structures
        if isinstance(id_mapping, dict) and 'ids' in id_mapping:
            # Full mapping structure from get_mapping()
            id_map = id_mapping.get('ids', {})
        else:
            # Simple ID mapping
            id_map = id_mapping
            
        # Get source and destination organization URLs
        source_org_url = source_gis.url
        dest_org_url = dest_gis.url
        
        # Extract the actual portal URL patterns
        source_portal_url = None
        dest_portal_url = None
        
        # Find a URL in the source JSON to extract the source organization's URL pattern
        def find_url_in_json(obj):
            """Find any URL in the JSON to determine the organization URL pattern."""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "url" and isinstance(v, str) and ("maps.arcgis.com" in v or "arcgis.com" in v):
                        return v
                    result = find_url_in_json(v)
                    if result:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_url_in_json(item)
                    if result:
                        return result
            return None
        
        # Extract source portal URL from the JSON
        sample_url = find_url_in_json(app_json)
        if sample_url:
            import re
            # Match both ArcGIS Online and Enterprise patterns
            match = re.match(r'(https?://[^/]+)', sample_url)
            if match:
                base_url = match.group(1)
                # For ArcGIS Online URLs, extract the organization-specific portal URL
                if ".maps.arcgis.com" in base_url:
                    source_portal_url = base_url
                else:
                    # For other patterns, use the base URL
                    source_portal_url = base_url
                    
        # Determine destination portal URL based on destination GIS properties
        if "www.arcgis.com" in dest_org_url:
            # For ArcGIS Online, we need to get the organization's portal URL
            # This is typically available from the portal properties
            try:
                # Get the organization's URL key
                portal_info = dest_gis.properties
                if 'urlKey' in portal_info and portal_info['urlKey']:
                    # Build the organization's portal URL
                    dest_portal_url = f"https://{portal_info['urlKey']}.maps.arcgis.com"
                else:
                    # Fallback to using the organization short name
                    org_id = portal_info.get('id', '')
                    if org_id:
                        # Try to get org info
                        dest_portal_url = f"https://{dest_gis.users.me.orgId}.maps.arcgis.com"
                    else:
                        # Last resort - use the base URL
                        dest_portal_url = dest_org_url
            except:
                # If we can't get portal info, use the base URL
                dest_portal_url = dest_org_url
        else:
            # For Enterprise portals, use the base URL as-is
            dest_portal_url = dest_org_url
            
        # Fallback if we couldn't determine URLs
        if not source_portal_url:
            source_portal_url = source_org_url
        if not dest_portal_url:
            dest_portal_url = dest_org_url
        
        logger.debug(f"Organization URL mapping: {source_portal_url} -> {dest_portal_url}")
        
        # Update map item collection
        if "values" in updated and "mapItemCollection" in updated["values"]:
            map_collection = updated["values"]["mapItemCollection"]
            logger.debug(f"Found {len(map_collection)} items in mapItemCollection")
            logger.debug(f"ID mapping contains: {list(id_map.keys())}")
            
            for i, map_ref in enumerate(map_collection):
                if isinstance(map_ref, str) and map_ref in id_map:
                    old_id = map_ref
                    updated["values"]["mapItemCollection"][i] = id_map[old_id]
                    logger.debug(f"Updated map reference: {old_id} -> {id_map[old_id]}")
                elif isinstance(map_ref, dict):
                    logger.debug(f"Processing map_ref dict with keys: {list(map_ref.keys())}")
                    # Update ID if present
                    if "id" in map_ref:
                        old_id = map_ref["id"]
                        logger.debug(f"Checking if {old_id} is in id_map")
                        if old_id in id_map:
                            new_id = id_map[old_id]
                            map_ref["id"] = new_id
                            logger.info(f"Updated map object ID: {old_id} -> {new_id}")
                            
                            # Update URL if present - need to replace both org URL and ID
                            if "url" in map_ref:
                                old_url = map_ref["url"]
                                # Replace organization URL first
                                new_url = old_url.replace(source_portal_url, dest_portal_url)
                                # Then replace the ID
                                if old_id in new_url:
                                    new_url = new_url.replace(old_id, new_id)
                                map_ref["url"] = new_url
                                logger.info(f"Updated map object URL: {old_url} -> {new_url}")
                        else:
                            logger.warning(f"Map ID {old_id} not found in id_map")
        
        # Update any web map references in other parts of the JSON
        # This handles various app configurations that might store map IDs elsewhere
        def update_ids_recursive(obj):
            """Recursively update IDs in nested structures."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ["webmap", "webmapId", "mapId", "itemId", "portalItemId"] and isinstance(value, str):
                        if value in id_map:
                            logger.debug(f"Updated {key}: {value} -> {id_map[value]}")
                            obj[key] = id_map[value]
                    # Also check for URL fields that might contain item IDs and org URLs
                    elif key == "url" and isinstance(value, str):
                        # First replace organization URL
                        new_url = value.replace(source_portal_url, dest_portal_url)
                        # Then replace any item IDs
                        for old_id, new_id in id_map.items():
                            if isinstance(old_id, str) and old_id in new_url:
                                new_url = new_url.replace(old_id, new_id)
                        if new_url != value:
                            obj[key] = new_url
                            logger.debug(f"Updated URL field: {value} -> {new_url}")
                    else:
                        update_ids_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    update_ids_recursive(item)
        
        # Update IDs throughout the JSON structure
        update_ids_recursive(updated)
        
        # Do a final pass to replace any remaining organization URLs in string values
        def replace_org_urls_recursive(obj):
            """Recursively replace organization URLs in all string values."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str) and isinstance(source_portal_url, str) and source_portal_url in value:
                        obj[key] = value.replace(source_portal_url, dest_portal_url)
                        logger.debug(f"Replaced org URL in {key}: {source_portal_url} -> {dest_portal_url}")
                    else:
                        replace_org_urls_recursive(value)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, str) and isinstance(source_portal_url, str) and source_portal_url in item:
                        obj[i] = item.replace(source_portal_url, dest_portal_url)
                        logger.debug(f"Replaced org URL in list: {source_portal_url} -> {dest_portal_url}")
                    else:
                        replace_org_urls_recursive(item)
        
        replace_org_urls_recursive(updated)
        
        # Update source references if present
        if "source" in updated and isinstance(updated["source"], str):
            # Check if source is an item ID that needs updating
            if updated["source"] in id_map:
                old_source = updated["source"]
                updated["source"] = id_map[old_source]
                logger.debug(f"Updated source reference: {old_source} -> {updated['source']}")
                
        return updated
        
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract the complete definition of an instant app.
        
        Args:
            item_id: ID of the instant app to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the instant app definition
        """
        try:
            # Get the item
            item = gis.content.get(item_id)
            if not item or item.type != 'Web Mapping Application':
                logger.error(f"Item {item_id} is not a Web Mapping Application")
                return {}
                
            # Extract definition
            definition = {
                'item_properties': {
                    'id': item.id,
                    'title': item.title,
                    'snippet': item.snippet,
                    'description': item.description,
                    'tags': item.tags,
                    'typeKeywords': item.typeKeywords,
                    'extent': item.extent,
                    'thumbnail': item.thumbnail,
                    'url': item.url,
                    'metadata': getattr(item, 'metadata', None)
                },
                'app_definition': item.get_data() or {}
            }
            
            # Save if requested
            if save_path:
                save_json(
                    definition,
                    save_path / f"instantapp_definition_{item_id}.json"
                )
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting instant app definition: {str(e)}")
            return {}