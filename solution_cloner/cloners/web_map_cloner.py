"""
Web Map Cloner - Clone ArcGIS Online Web Maps with reference updates.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from arcgis.gis import GIS, Item

from ..base.base_cloner import BaseCloner
from ..utils.json_handler import save_json
from ..utils.id_mapper import IDMapper

# Configure logger
logger = logging.getLogger(__name__)


def _patch_arcgis_geo():
    """
    Apply monkey patch to fix missing _is_geoenabled in arcgis.features.geo.
    This is a workaround for a compatibility issue in the ArcGIS Python API.
    """
    try:
        import arcgis.features.geo
        
        if not hasattr(arcgis.features.geo, '_is_geoenabled'):
            def _is_geoenabled(data):
                """Dummy implementation that always returns False"""
                return False
            
            arcgis.features.geo._is_geoenabled = _is_geoenabled
            logger.debug("Applied _is_geoenabled patch to arcgis.features.geo")
    except Exception as e:
        logger.warning(f"Could not apply arcgis patch: {e}")


class WebMapCloner(BaseCloner):
    """Clone Web Maps with reference updates for layers."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the Web Map cloner."""
        super().__init__()
        self.supported_types = ['Web Map']
        self.json_output_dir = json_output_dir or Path("json_files")
        
        # Apply patch for missing _is_geoenabled
        _patch_arcgis_geo()
        
    def clone(
        self,
        source_item: Dict[str, Any],
        source_gis: GIS,
        dest_gis: GIS,
        dest_folder: str,
        id_mapping: Union[IDMapper, Dict[str, str]],
        **kwargs
    ) -> Optional[Item]:
        """
        Clone a Web Map.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            **kwargs: Additional arguments
            
        Returns:
            Cloned web map item or None if failed
        """
        try:
            # Get source web map item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item or src_item.type != 'Web Map':
                logger.error(f"Item {source_item['id']} is not a web map")
                return None
                
            logger.info(f"Cloning web map: {src_item.title}")
            
            # Get the web map JSON definition
            webmap_json = src_item.get_data()
            
            # Save original JSON for reference
            save_json(
                webmap_json,
                self.json_output_dir / f"webmap_original_{src_item.id}.json"
            )
            
            # Always update references before creation since layers are cloned first
            if id_mapping:
                logger.info("Updating references before creating web map")
                webmap_json = self._update_webmap_references(webmap_json, id_mapping)
                
                # Save updated JSON for reference
                save_json(
                    webmap_json,
                    self.json_output_dir / f"webmap_updated_{src_item.id}.json"
                )
            
            # Create item properties
            item_properties = {
                'title': src_item.title,  # Use original title, no suffix
                'snippet': src_item.snippet or '',
                'description': src_item.description or '',
                'tags': src_item.tags or [],
                'type': 'Web Map',
                'typeKeywords': src_item.typeKeywords or [],
                'extent': src_item.extent
            }
            
            # Add the web map JSON as text
            item_properties['text'] = json.dumps(webmap_json)
            
            # Create the new web map
            logger.info(f"Creating web map: {item_properties['title']}")
            new_item = dest_gis.content.add(
                item_properties,
                folder=dest_folder
            )
            
            if new_item:
                logger.info(f"Successfully created web map: {new_item.id}")
                
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
                        
                return new_item
            else:
                logger.error("Failed to create web map")
                return None
                
        except Exception as e:
            logger.error(f"Error cloning web map: {str(e)}")
            return None
            
            
    def _update_webmap_references(self, webmap_json: Dict, id_mapping) -> Dict:
        """
        Update all references in web map JSON.
        
        Args:
            webmap_json: Web map JSON definition
            id_mapping: IDMapper object or dictionary of ID mappings
            
        Returns:
            Updated web map JSON
        """
        # Deep copy to avoid modifying original
        updated = json.loads(json.dumps(webmap_json))
        
        # Handle both IDMapper object and dictionary
        if hasattr(id_mapping, 'id_mapping'):
            # It's an IDMapper object
            id_map = id_mapping.id_mapping
            url_map = id_mapping.url_mapping
            sublayer_map = id_mapping.sublayer_mapping
            service_map = id_mapping.service_mapping
        else:
            # It's a dictionary (legacy support)
            id_map = id_mapping.get('ids', {})
            url_map = id_mapping.get('urls', {})
            sublayer_map = id_mapping.get('sublayers', {})
            service_map = id_mapping.get('services', {})
        
        # Update operational layers
        if 'operationalLayers' in updated:
            for layer in updated['operationalLayers']:
                # Update layer URL - check all mapping types
                if 'url' in layer:
                    old_url = layer['url']
                    new_url = None
                    
                    # Check direct URL mapping first
                    if old_url in url_map:
                        new_url = url_map[old_url]
                        logger.debug(f"Updated layer URL: {old_url} -> {new_url}")
                    # Check sublayer mapping
                    elif old_url in sublayer_map:
                        new_url = sublayer_map[old_url]
                        logger.debug(f"Updated sublayer URL: {old_url} -> {new_url}")
                    # Check service mapping (for base service URLs)
                    else:
                        for old_service, new_service in service_map.items():
                            if old_url.startswith(old_service):
                                new_url = old_url.replace(old_service, new_service)
                                logger.debug(f"Updated service URL: {old_url} -> {new_url}")
                                break
                    
                    # Fallback: Try to update URL based on item ID
                    if not new_url and 'itemId' in layer and layer['itemId'] in id_map:
                        new_item_id = id_map[layer['itemId']]
                        logger.warning(f"URL not found in mappings for layer {layer.get('title', 'Unknown')}, using item ID fallback")
                        # Try to get the new item's URL
                        if hasattr(id_mapping, 'dest_gis'):
                            try:
                                new_item = id_mapping.dest_gis.content.get(new_item_id)
                                if new_item and hasattr(new_item, 'url'):
                                    # Check if we need to append sublayer index
                                    if old_url.endswith('/0') or old_url.endswith('/1') or old_url.endswith('/2'):
                                        sublayer_idx = old_url.split('/')[-1]
                                        new_url = f"{new_item.url}/{sublayer_idx}"
                                    else:
                                        new_url = new_item.url
                                    logger.info(f"Resolved URL via item lookup: {old_url} -> {new_url}")
                            except Exception as e:
                                logger.error(f"Failed to lookup item for URL fallback: {e}")
                    
                    if new_url:
                        layer['url'] = new_url
                    else:
                        logger.error(f"Failed to update URL for layer: {layer.get('title', 'Unknown')} - {old_url}")
                    
                # Update item ID
                if 'itemId' in layer and layer['itemId'] in id_map:
                    old_id = layer['itemId']
                    layer['itemId'] = id_map[old_id]
                    logger.debug(f"Updated layer itemId: {old_id} -> {layer['itemId']}")
                    
                # Update feature collection item ID
                if 'featureCollection' in layer:
                    fc = layer['featureCollection']
                    if 'itemId' in fc and fc['itemId'] in id_map:
                        old_id = fc['itemId']
                        fc['itemId'] = id_map[old_id]
                        logger.debug(f"Updated feature collection itemId: {old_id} -> {fc['itemId']}")
                        
                    # Update feature collection layers
                    if 'layers' in fc:
                        for fc_layer in fc['layers']:
                            if 'url' in fc_layer:
                                old_url = fc_layer['url']
                                new_url = None
                                
                                # Check all mapping types
                                if old_url in url_map:
                                    new_url = url_map[old_url]
                                    logger.debug(f"Updated FC layer URL: {old_url} -> {new_url}")
                                elif old_url in sublayer_map:
                                    new_url = sublayer_map[old_url]
                                    logger.debug(f"Updated FC sublayer URL: {old_url} -> {new_url}")
                                else:
                                    for old_service, new_service in service_map.items():
                                        if old_url.startswith(old_service):
                                            new_url = old_url.replace(old_service, new_service)
                                            logger.debug(f"Updated FC service URL: {old_url} -> {new_url}")
                                            break
                                
                                if new_url:
                                    fc_layer['url'] = new_url
                                
        # Update basemap layers
        if 'baseMap' in updated and 'baseMapLayers' in updated['baseMap']:
            for layer in updated['baseMap']['baseMapLayers']:
                if 'url' in layer:
                    old_url = layer['url']
                    new_url = None
                    
                    # Check all mapping types
                    if old_url in url_map:
                        new_url = url_map[old_url]
                        logger.debug(f"Updated basemap URL: {old_url} -> {new_url}")
                    elif old_url in sublayer_map:
                        new_url = sublayer_map[old_url]
                        logger.debug(f"Updated basemap sublayer URL: {old_url} -> {new_url}")
                    else:
                        for old_service, new_service in service_map.items():
                            if old_url.startswith(old_service):
                                new_url = old_url.replace(old_service, new_service)
                                logger.debug(f"Updated basemap service URL: {old_url} -> {new_url}")
                                break
                    
                    if new_url:
                        layer['url'] = new_url
                    
                if 'itemId' in layer and layer['itemId'] in id_map:
                    old_id = layer['itemId']
                    layer['itemId'] = id_map[old_id]
                    logger.debug(f"Updated basemap itemId: {old_id} -> {layer['itemId']}")
                    
        # Update tables
        if 'tables' in updated:
            for table in updated['tables']:
                if 'url' in table:
                    old_url = table['url']
                    new_url = None
                    
                    # Check all mapping types
                    if old_url in url_map:
                        new_url = url_map[old_url]
                        logger.debug(f"Updated table URL: {old_url} -> {new_url}")
                    elif old_url in sublayer_map:
                        new_url = sublayer_map[old_url]
                        logger.debug(f"Updated table sublayer URL: {old_url} -> {new_url}")
                    else:
                        for old_service, new_service in service_map.items():
                            if old_url.startswith(old_service):
                                new_url = old_url.replace(old_service, new_service)
                                logger.debug(f"Updated table service URL: {old_url} -> {new_url}")
                                break
                    
                    if new_url:
                        table['url'] = new_url
                    
                if 'itemId' in table and table['itemId'] in id_map:
                    old_id = table['itemId']
                    table['itemId'] = id_map[old_id]
                    logger.debug(f"Updated table itemId: {old_id} -> {table['itemId']}")
                    
        return updated
        
    def set_id_mapper(self, id_mapper):
        """Set the ID mapper for pre-creation reference updates."""
        self._id_mapper = id_mapper
        
    def _get_unique_title(self, title: str, gis: GIS) -> str:
        """Generate a unique title that doesn't exist in the GIS."""
        import uuid
        import re
        
        # Clean the title
        base_title = re.sub(r'_[a-f0-9]{8}$', '', title)  # Remove existing UUID suffix if any
        
        # Check if title already exists
        search_result = gis.content.search(f'title:"{base_title}"', max_items=1)
        if not search_result:
            return base_title
            
        # Generate unique title with UUID suffix
        unique_suffix = uuid.uuid4().hex[:8]
        return f"{base_title}_{unique_suffix}"
        
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract the complete definition of a web map.
        
        Args:
            item_id: ID of the web map to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the web map definition
        """
        try:
            # Get the item
            item = gis.content.get(item_id)
            if not item or item.type != 'Web Map':
                logger.error(f"Item {item_id} is not a web map")
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
                    'metadata': getattr(item, 'metadata', None)
                },
                'webmap_definition': json.loads(item.get_data())
            }
            
            # Save if requested
            if save_path:
                save_json(
                    definition,
                    save_path / f"webmap_definition_{item_id}.json"
                )
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting web map definition: {str(e)}")
            return {}