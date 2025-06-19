"""
Web Map Cloner - Clone ArcGIS Online Web Maps with reference updates.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from arcgis.gis import GIS, Item

from ..base.base_cloner import BaseCloner
from ..utils.json_handler import save_json

# Configure logger
logger = logging.getLogger(__name__)


class WebMapCloner(BaseCloner):
    """Clone Web Maps with reference updates for layers."""
    
    def __init__(self, json_output_dir=None, update_refs_before_create=False):
        """Initialize the Web Map cloner."""
        super().__init__()
        self.supported_types = ['Web Map']
        self.json_output_dir = json_output_dir or Path("json_files")
        self.update_refs_before_create = update_refs_before_create
        
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
            webmap_json = json.loads(src_item.get_data())
            
            # Save original JSON for reference
            save_json(
                webmap_json,
                self.json_output_dir / f"webmap_original_{src_item.id}.json"
            )
            
            # Update references if configured to do so before creation
            if self.update_refs_before_create and id_mapping:
                logger.info("Updating references before creating web map")
                webmap_json = self._update_webmap_references(webmap_json, id_mapping)
                
                # Save updated JSON for reference
                save_json(
                    webmap_json,
                    self.json_output_dir / f"webmap_updated_{src_item.id}.json"
                )
            
            # Create item properties
            item_properties = {
                'title': self._get_unique_title(src_item.title, dest_gis),
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
                if source_item.thumbnail:
                    try:
                        new_item.update(thumbnail=source_item.thumbnail)
                    except Exception as e:
                        logger.warning(f"Failed to copy thumbnail: {str(e)}")
                        
                # Copy metadata if exists
                if hasattr(source_item, 'metadata') and source_item.metadata:
                    try:
                        new_item.update(metadata=source_item.metadata)
                    except Exception as e:
                        logger.warning(f"Failed to copy metadata: {str(e)}")
                        
                return new_item
            else:
                logger.error("Failed to create web map")
                return None
                
        except Exception as e:
            logger.error(f"Error cloning web map: {str(e)}")
            return None
            
    def update_references(
        self,
        item: Item,
        id_mapping: Dict[str, Dict[str, str]],
        gis: GIS
    ) -> bool:
        """
        Update references in a web map to point to cloned items.
        
        Args:
            item: Web map item to update
            id_mapping: Dictionary of ID mappings
            gis: GIS connection
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Skip if we already updated before creation
            if self.update_refs_before_create:
                logger.info(f"References already updated for web map: {item.title}")
                return True
                
            # Get the web map JSON
            webmap_json = json.loads(item.get_data())
            
            # Update references
            updated_json = self._update_webmap_references(webmap_json, id_mapping)
            
            # Check if anything changed
            if json.dumps(webmap_json) != json.dumps(updated_json):
                # Update the web map
                item_properties = {
                    'text': json.dumps(updated_json)
                }
                
                success = item.update(item_properties)
                if success:
                    logger.info(f"Successfully updated references in web map: {item.title}")
                    
                    # Save updated JSON for reference
                    save_json(
                        updated_json,
                        self.json_output_dir / f"webmap_updated_refs_{item.id}.json"
                    )
                else:
                    logger.error(f"Failed to update web map: {item.title}")
                    
                return success
            else:
                logger.info(f"No references to update in web map: {item.title}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating references in web map {item.title}: {str(e)}")
            return False
            
    def _update_webmap_references(self, webmap_json: Dict, id_mapping: Dict[str, Dict[str, str]]) -> Dict:
        """
        Update all references in web map JSON.
        
        Args:
            webmap_json: Web map JSON definition
            id_mapping: Dictionary of ID mappings
            
        Returns:
            Updated web map JSON
        """
        # Deep copy to avoid modifying original
        updated = json.loads(json.dumps(webmap_json))
        
        # Get mappings
        id_map = id_mapping.get('ids', {})
        url_map = id_mapping.get('urls', {})
        sublayer_map = id_mapping.get('sublayers', {})
        
        # Update operational layers
        if 'operationalLayers' in updated:
            for layer in updated['operationalLayers']:
                # Update layer URL
                if 'url' in layer and layer['url'] in url_map:
                    old_url = layer['url']
                    layer['url'] = url_map[old_url]
                    logger.debug(f"Updated layer URL: {old_url} -> {layer['url']}")
                elif 'url' in layer and layer['url'] in sublayer_map:
                    old_url = layer['url']
                    layer['url'] = sublayer_map[old_url]
                    logger.debug(f"Updated sublayer URL: {old_url} -> {layer['url']}")
                    
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
                            if 'url' in fc_layer and fc_layer['url'] in url_map:
                                old_url = fc_layer['url']
                                fc_layer['url'] = url_map[old_url]
                                logger.debug(f"Updated FC layer URL: {old_url} -> {fc_layer['url']}")
                                
        # Update basemap layers
        if 'baseMap' in updated and 'baseMapLayers' in updated['baseMap']:
            for layer in updated['baseMap']['baseMapLayers']:
                if 'url' in layer and layer['url'] in url_map:
                    old_url = layer['url']
                    layer['url'] = url_map[old_url]
                    logger.debug(f"Updated basemap URL: {old_url} -> {layer['url']}")
                    
                if 'itemId' in layer and layer['itemId'] in id_map:
                    old_id = layer['itemId']
                    layer['itemId'] = id_map[old_id]
                    logger.debug(f"Updated basemap itemId: {old_id} -> {layer['itemId']}")
                    
        # Update tables
        if 'tables' in updated:
            for table in updated['tables']:
                if 'url' in table and table['url'] in url_map:
                    old_url = table['url']
                    table['url'] = url_map[old_url]
                    logger.debug(f"Updated table URL: {old_url} -> {table['url']}")
                elif 'url' in table and table['url'] in sublayer_map:
                    old_url = table['url']
                    table['url'] = sublayer_map[old_url]
                    logger.debug(f"Updated table sublayer URL: {old_url} -> {table['url']}")
                    
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