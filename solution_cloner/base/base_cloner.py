"""
Base Cloner Abstract Class
==========================
Defines the common interface for all item type cloners.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from arcgis.gis import GIS, Item
from pathlib import Path
import logging
import json
from datetime import datetime


class BaseCloner(ABC):
    """Abstract base class for all ArcGIS Online item cloners."""
    
    def __init__(self):
        """Initialize the base cloner."""
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
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
        Clone an item from source to destination.
        
        Args:
            source_item: Dictionary containing source item information
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder name
            id_mapping: Dictionary mapping old IDs to new IDs
            **kwargs: Additional cloner-specific arguments
            
        Returns:
            Created Item object or None if failed
        """
        pass
        
    @abstractmethod
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract the complete definition of an item.
        
        Args:
            item_id: ID of the item to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the item definition
        """
        pass
        
    def update_references(
        self,
        item: Item,
        id_mapping: Dict[str, str],
        gis: GIS
    ) -> bool:
        """
        Update all references in an item to point to new IDs.
        
        Args:
            item: Item to update
            id_mapping: Dictionary mapping old IDs to new IDs
            gis: GIS connection for the item
            
        Returns:
            True if successful, False otherwise
        """
        # Default implementation - override in subclasses that need it
        return True
        
    def validate_clone(
        self,
        source_item: Dict[str, Any],
        cloned_item: Item,
        source_gis: GIS,
        dest_gis: GIS
    ) -> bool:
        """
        Validate that an item was cloned correctly.
        
        Args:
            source_item: Original source item dictionary
            cloned_item: Newly created item
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation - can be overridden for specific types
        if not cloned_item:
            return False
            
        # Check basic properties
        if cloned_item.type != source_item.get('type'):
            self.logger.warning(f"Type mismatch: {source_item.get('type')} != {cloned_item.type}")
            return False
            
        return True
        
    def save_json(self, data: Dict[str, Any], filepath: Path, description: str = ""):
        """
        Save JSON data with timestamp and description.
        
        Args:
            data: Data to save
            filepath: Base filepath (timestamp will be added)
            description: Optional description for the file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Add timestamp to filename
        if filepath.suffix == '.json':
            final_path = filepath.parent / f"{filepath.stem}_{timestamp}{filepath.suffix}"
        else:
            final_path = filepath.parent / f"{filepath.name}_{timestamp}.json"
            
        # Ensure directory exists
        final_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save with pretty formatting
        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        self.logger.debug(f"Saved JSON to: {final_path}")
        
        if description:
            self.logger.info(f"Saved {description} to {final_path.name}")
            
    def update_json_references(
        self,
        json_data: Any,
        id_mapping: Dict[str, str]
    ) -> Any:
        """
        Recursively update all ID references in JSON data.
        
        Args:
            json_data: JSON data (dict, list, or primitive)
            id_mapping: Dictionary mapping old IDs to new IDs
            
        Returns:
            Updated JSON data
        """
        if isinstance(json_data, dict):
            updated = {}
            for key, value in json_data.items():
                # Common ID fields to check
                if key in ['itemId', 'webmap', 'portalItemId', 'sourceItemId', 
                          'targetItemId', 'id', 'layerId', 'serviceItemId']:
                    if isinstance(value, str) and value in id_mapping:
                        updated[key] = id_mapping[value]
                        self.logger.debug(f"Updated {key}: {value} -> {id_mapping[value]}")
                    else:
                        updated[key] = value
                else:
                    updated[key] = self.update_json_references(value, id_mapping)
            return updated
            
        elif isinstance(json_data, list):
            return [self.update_json_references(item, id_mapping) for item in json_data]
            
        elif isinstance(json_data, str):
            # Check for IDs in URLs
            for old_id, new_id in id_mapping.items():
                if isinstance(old_id, str) and old_id in json_data:
                    json_data = json_data.replace(old_id, new_id)
                    self.logger.debug(f"Updated string reference: {old_id} -> {new_id}")
            return json_data
            
        else:
            return json_data
            
    def update_json_references_complete(
        self,
        json_data: Any,
        id_mapper: Any  # Import avoided by using Any
    ) -> Any:
        """
        Update all ID and URL references in JSON data using the IDMapper.
        
        Args:
            json_data: JSON data to update
            id_mapper: IDMapper instance with all mappings
            
        Returns:
            Updated JSON data
        """
        # First update IDs
        updated = self.update_json_references(json_data, id_mapper.id_mapping)
        
        # Then update URLs using the IDMapper's specialized method
        if hasattr(id_mapper, 'update_json_urls'):
            updated = id_mapper.update_json_urls(updated)
            
        return updated
            
    def get_item_safely(self, item_id: str, gis: GIS) -> Optional[Item]:
        """
        Safely get an item by ID with error handling.
        
        Args:
            item_id: Item ID to retrieve
            gis: GIS connection
            
        Returns:
            Item object or None if not found/error
        """
        try:
            item = gis.content.get(item_id)
            if not item:
                self.logger.warning(f"Item not found: {item_id}")
            return item
        except Exception as e:
            self.logger.error(f"Error retrieving item {item_id}: {str(e)}")
            return None
            
    def create_item_in_folder(
        self,
        item_properties: Dict[str, Any],
        data: Optional[str] = None,
        thumbnail: Optional[str] = None,
        folder: Optional[str] = None,
        gis: Optional[GIS] = None
    ) -> Optional[Item]:
        """
        Create an item in a specific folder with error handling.
        
        Args:
            item_properties: Dictionary of item properties
            data: Optional data file path or URL
            thumbnail: Optional thumbnail file path
            folder: Folder name (None for root)
            gis: GIS connection
            
        Returns:
            Created Item object or None if failed
        """
        try:
            # Ensure required properties
            if 'title' not in item_properties:
                self.logger.error("Missing required 'title' property")
                return None
                
            # Create the item
            item = gis.content.add(
                item_properties=item_properties,
                data=data,
                thumbnail=thumbnail,
                folder=folder
            )
            
            if item:
                self.logger.info(f"Created item: {item.title} ({item.id})")
            else:
                self.logger.error(f"Failed to create item: {item_properties.get('title')}")
                
            return item
            
        except Exception as e:
            self.logger.error(f"Error creating item: {str(e)}")
            return None