"""
Form Cloner - Clone ArcGIS Online Survey123 Forms
"""

import json
import logging
import zipfile
import tempfile
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from io import BytesIO

from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayerCollection

from ..base.base_cloner import BaseCloner
from ..utils.json_handler import save_json

# Configure logger
logger = logging.getLogger(__name__)


class FormCloner(BaseCloner):
    """Clone Survey123 Forms with feature service reference updates."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the Form cloner."""
        super().__init__()
        self.json_output_dir = json_output_dir or Path("json_files")
        self._last_mapping_data = None
        
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
        Clone a Survey123 form.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            **kwargs: Additional arguments
            
        Returns:
            Cloned form item or None if failed
        """
        try:
            # Get source item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item:
                logger.error(f"Item {source_item['id']} not found")
                return None
                
            # Verify it's a form
            if src_item.type != 'Form':
                logger.error(f"Item {source_item['id']} is not a Form item")
                return None
                
            logger.info(f"Cloning Survey123 form: {src_item.title}")
            
            # Extract form configuration and referenced service
            form_info = self._extract_form_info(src_item, source_gis)
            
            # Update references in form configuration
            updated_form_info = self._update_form_references(form_info, id_mapping)
            
            # Create the cloned form
            new_item = self._create_form_item(
                src_item,
                updated_form_info,
                dest_gis,
                dest_folder
            )
            
            if new_item:
                logger.info(f"Successfully cloned form: {src_item.title} -> {new_item.id}")
                
                # Store mapping data for reference updates
                self._last_mapping_data = {
                    'source_service_id': form_info.get('service_item_id'),
                    'source_service_url': form_info.get('service_url')
                }
            else:
                logger.error(f"Failed to clone form: {src_item.title}")
                
            return new_item
            
        except Exception as e:
            logger.error(f"Error cloning form {source_item.get('title', 'Unknown')}: {str(e)}")
            return None
            
    def _extract_form_info(self, item: Item, gis: GIS) -> Dict[str, Any]:
        """
        Extract form configuration and identify referenced feature service.
        
        Args:
            item: Form item
            gis: GIS connection
            
        Returns:
            Dictionary containing form info and references
        """
        form_info = {
            'item_id': item.id,
            'title': item.title,
            'description': item.description,
            'tags': item.tags,
            'snippet': item.snippet,
            'type_keywords': item.typeKeywords,
            'properties': item.properties,
            'service_item_id': None,
            'service_url': None,
            'service_layer_id': None
        }
        
        try:
            # Method 1: Check item relationships
            related_items = item.related_items('Survey2Service', 'forward')
            if related_items:
                service_item = related_items[0]
                form_info['service_item_id'] = service_item.id
                form_info['service_url'] = service_item.url
                logger.info(f"Found related feature service: {service_item.title} ({service_item.id})")
                
                # Extract layer ID from URL if present
                if service_item.url and '/FeatureServer/' in service_item.url:
                    parts = service_item.url.split('/FeatureServer/')
                    if len(parts) > 1 and parts[1].isdigit():
                        form_info['service_layer_id'] = int(parts[1])
                        
            # Method 2: Check form properties for submission URL
            if not form_info['service_url'] and item.properties:
                # Look for submission URL in properties
                if 'submissionUrl' in item.properties:
                    form_info['service_url'] = item.properties['submissionUrl']
                elif 'serviceUrl' in item.properties:
                    form_info['service_url'] = item.properties['serviceUrl']
                    
                # Extract item ID from service URL
                if form_info['service_url']:
                    # Pattern: /services/<id>/FeatureServer
                    match = re.search(r'/services/([a-f0-9]+)/FeatureServer', form_info['service_url'])
                    if match:
                        potential_id = match.group(1)
                        # Verify this is a valid item
                        service_item = gis.content.get(potential_id)
                        if service_item:
                            form_info['service_item_id'] = potential_id
                            logger.info(f"Found feature service from URL: {service_item.title}")
                            
            # Save extracted info for debugging
            save_json(
                form_info,
                self.json_output_dir / f"form_info_{item.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
        except Exception as e:
            logger.warning(f"Error extracting form relationships: {str(e)}")
            
        return form_info
        
    def _update_form_references(self, form_info: Dict[str, Any], id_mapping) -> Dict[str, Any]:
        """
        Update feature service references in form configuration.
        
        Args:
            form_info: Form information dictionary
            id_mapping: ID mapping (can be dict or IDMapper object)
            
        Returns:
            Updated form information
        """
        # Handle IDMapper object
        if hasattr(id_mapping, 'id_mapping') and hasattr(id_mapping, 'url_mapping'):
            # It's an IDMapper object
            id_map = id_mapping.id_mapping
            url_map = id_mapping.url_mapping
        elif isinstance(id_mapping, dict):
            # Handle dictionary format (both old and new)
            id_map = id_mapping.get('ids', {}) if 'ids' in id_mapping else id_mapping
            url_map = id_mapping.get('urls', {}) if 'urls' in id_mapping else {}
        else:
            # Fallback
            id_map = {}
            url_map = {}
        
        # Update service item ID if we have a mapping
        if form_info['service_item_id'] and form_info['service_item_id'] in id_map:
            old_id = form_info['service_item_id']
            new_id = id_map[old_id]
            form_info['new_service_item_id'] = new_id
            logger.info(f"Updating form service reference: {old_id} -> {new_id}")
        else:
            form_info['new_service_item_id'] = form_info['service_item_id']
            
        # Update service URL if we have a mapping
        if form_info['service_url']:
            new_url = form_info['service_url']
            
            # Try direct URL mapping first
            if form_info['service_url'] in url_map:
                new_url = url_map[form_info['service_url']]
            else:
                # Try to update based on ID mapping
                for old_id, new_id in id_map.items():
                    if old_id in form_info['service_url']:
                        new_url = form_info['service_url'].replace(old_id, new_id)
                        break
                        
            form_info['new_service_url'] = new_url
            if new_url != form_info['service_url']:
                logger.info(f"Updated form service URL: {form_info['service_url']} -> {new_url}")
        else:
            form_info['new_service_url'] = form_info['service_url']
            
        return form_info
        
    def _create_form_item(
        self,
        source_item: Item,
        form_info: Dict[str, Any],
        dest_gis: GIS,
        dest_folder: str
    ) -> Optional[Item]:
        """
        Create a new form item in the destination.
        
        Args:
            source_item: Source form item
            form_info: Updated form information
            dest_gis: Destination GIS
            dest_folder: Destination folder
            
        Returns:
            Created form item or None if failed
        """
        try:
            # Download the form ZIP file
            logger.info("Downloading form package...")
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download to temp directory
                download_path = source_item.download(save_path=temp_dir)
                if not download_path:
                    logger.error("Failed to download form package")
                    return None
                    
                # Rename the downloaded file to avoid conflicts
                # Use timestamp and title to ensure uniqueness
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_title = re.sub(r'[^\w\s-]', '', source_item.title).strip()[:50]
                new_filename = f"{safe_title}_{timestamp}.zip"
                new_path = os.path.join(temp_dir, new_filename)
                os.rename(download_path, new_path)
                download_path = new_path
                    
                # Process the ZIP file if we need to update internal references
                if form_info.get('new_service_url') != form_info.get('service_url'):
                    logger.info("Updating references in form package...")
                    download_path = self._update_form_package(
                        download_path,
                        form_info,
                        temp_dir
                    )
                
                # Prepare item properties
                item_props = {
                    'title': source_item.title,
                    'type': 'Form',
                    'typeKeywords': list(source_item.typeKeywords),
                    'description': source_item.description or '',
                    'snippet': source_item.snippet or '',
                    'tags': source_item.tags or []
                }
                
                # Update properties with new service reference
                if hasattr(source_item, 'properties') and source_item.properties:
                    new_properties = dict(source_item.properties)
                    
                    # Update submission URL if present
                    if 'submissionUrl' in new_properties and form_info.get('new_service_url'):
                        new_properties['submissionUrl'] = form_info['new_service_url']
                    if 'serviceUrl' in new_properties and form_info.get('new_service_url'):
                        new_properties['serviceUrl'] = form_info['new_service_url']
                        
                    item_props['properties'] = new_properties
                
                # Create the form item
                logger.info(f"Creating form item in folder: {dest_folder}")
                new_item = dest_gis.content.add(
                    item_properties=item_props,
                    data=download_path,
                    folder=dest_folder
                )
                
                if new_item:
                    # Update item relationship if we have a new service
                    if form_info.get('new_service_item_id') and form_info['new_service_item_id'] != form_info.get('service_item_id'):
                        try:
                            new_service_item = dest_gis.content.get(form_info['new_service_item_id'])
                            if new_service_item:
                                # Add Survey2Service relationship
                                new_item.add_relationship(new_service_item, 'Survey2Service')
                                logger.info(f"Added Survey2Service relationship to {new_service_item.title}")
                        except Exception as e:
                            logger.warning(f"Failed to add item relationship: {str(e)}")
                    
                    # Copy thumbnail if exists
                    try:
                        self._copy_thumbnail(source_item, new_item)
                    except:
                        pass
                        
                return new_item
                
        except Exception as e:
            logger.error(f"Error creating form item: {str(e)}")
            return None
            
    def _update_form_package(self, zip_path: str, form_info: Dict[str, Any], temp_dir: str) -> str:
        """
        Update references inside the form ZIP package.
        
        Args:
            zip_path: Path to the downloaded ZIP file
            form_info: Form information with old and new references
            temp_dir: Temporary directory for processing
            
        Returns:
            Path to updated ZIP file
        """
        try:
            # Create extraction directory
            extract_dir = os.path.join(temp_dir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            # Extract ZIP contents
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                
            # Update references in extracted files
            updated = False
            
            # Look for .webform JSON files
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.endswith('.webform'):
                        file_path = os.path.join(root, file)
                        logger.info(f"Updating references in {file}")
                        
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        # Update service URLs and IDs
                        original_content = content
                        
                        if form_info.get('service_url') and form_info.get('new_service_url'):
                            content = content.replace(
                                form_info['service_url'],
                                form_info['new_service_url']
                            )
                            
                        if form_info.get('service_item_id') and form_info.get('new_service_item_id'):
                            content = content.replace(
                                form_info['service_item_id'],
                                form_info['new_service_item_id']
                            )
                            
                        if content != original_content:
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            updated = True
                            
            # If no updates were needed, return original
            if not updated:
                return zip_path
                
            # Create new ZIP with updated contents
            updated_zip_path = os.path.join(temp_dir, 'updated_form.zip')
            with zipfile.ZipFile(updated_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, extract_dir)
                        zip_ref.write(file_path, arc_path)
                        
            logger.info("Created updated form package")
            return updated_zip_path
            
        except Exception as e:
            logger.warning(f"Error updating form package: {str(e)}")
            # Return original if update fails
            return zip_path
            
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract the complete definition of a form.
        
        Args:
            item_id: ID of the form to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the form definition
        """
        try:
            item = gis.content.get(item_id)
            if not item:
                logger.error(f"Form item {item_id} not found")
                return {}
                
            # Extract form info
            form_info = self._extract_form_info(item, gis)
            
            # Add item properties
            definition = {
                'item': {
                    'id': item.id,
                    'title': item.title,
                    'type': item.type,
                    'typeKeywords': list(item.typeKeywords),
                    'description': item.description,
                    'snippet': item.snippet,
                    'tags': item.tags,
                    'properties': dict(item.properties) if item.properties else {}
                },
                'form_info': form_info
            }
            
            if save_path:
                save_json(definition, save_path)
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting form definition: {str(e)}")
            return {}
            
    def get_last_mapping_data(self) -> Optional[Dict[str, Any]]:
        """Get mapping data from the last clone operation."""
        return self._last_mapping_data