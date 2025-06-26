"""
Notebook Cloner
===============
Clones ArcGIS Notebook items and updates all references to items, service URLs, and portal URLs.

This cloner handles Jupyter notebook files, updating references in both code and markdown cells
to point to cloned items in the destination organization.
"""

import json
import re
import logging
from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime

from arcgis.gis import GIS, Item

from ..base.base_cloner import BaseCloner, ItemCloneResult
from ..utils.json_handler import save_json
from ..utils.id_mapper import IDMapper

logger = logging.getLogger(__name__)


class NotebookCloner(BaseCloner):
    """Cloner for ArcGIS Notebook items."""
    
    def __init__(self, source_gis: GIS, dest_gis: GIS):
        """Initialize the notebook cloner."""
        super().__init__(source_gis, dest_gis)
        
    def clone(self, item_id: str, folder: str = None, title_suffix: str = None, 
              id_mapper: IDMapper = None) -> ItemCloneResult:
        """
        Clone a notebook item.
        
        Args:
            item_id: Source notebook item ID
            folder: Destination folder name (None for root)
            title_suffix: Optional suffix for the title
            id_mapper: ID mapper for tracking references
            
        Returns:
            ItemCloneResult with success status and new item details
        """
        try:
            # Get source item
            source_item = self.source_gis.content.get(item_id)
            if not source_item:
                raise Exception(f"Source item {item_id} not found")
                
            if source_item.type != 'Notebook':
                raise Exception(f"Item {item_id} is not a Notebook (type: {source_item.type})")
                
            logger.info(f"Cloning notebook: {source_item.title} ({item_id})")
            
            # Extract notebook definition
            notebook_json = self.extract_definition(item_id)
            
            # Save original notebook for debugging
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_json(
                notebook_json, 
                f"notebook_{item_id}_original_{timestamp}.json",
                description=f"Original notebook: {source_item.title}"
            )
            
            # Update references if ID mapper provided
            if id_mapper:
                notebook_json = self._update_notebook_references(
                    notebook_json, 
                    id_mapper,
                    source_item.id
                )
                
                # Save updated notebook for debugging
                save_json(
                    notebook_json,
                    f"notebook_{item_id}_updated_{timestamp}.json",
                    description=f"Updated notebook: {source_item.title}"
                )
            
            # Prepare item properties
            item_properties = {
                'title': source_item.title + (title_suffix or ''),
                'snippet': source_item.snippet or '',
                'description': source_item.description or '',
                'tags': source_item.tags or [],
                'type': 'Notebook',
                'typeKeywords': source_item.typeKeywords or [],
                'text': json.dumps(notebook_json)  # Notebook content as JSON string
            }
            
            # Add item to destination
            logger.info(f"Creating notebook item in destination: {item_properties['title']}")
            new_item = self.dest_gis.content.add(
                item_properties=item_properties,
                folder=folder
            )
            
            if not new_item:
                raise Exception("Failed to create notebook item")
                
            logger.info(f"Successfully created notebook: {new_item.title} ({new_item.id})")
            logger.info(f"Notebook URL: {new_item.homepage}")
            
            # Add ID mapping
            if id_mapper:
                id_mapper.add_mapping(
                    source_item.id,
                    new_item.id,
                    source_item.homepage if hasattr(source_item, 'homepage') else None,
                    new_item.homepage
                )
                
            # Copy thumbnail if exists
            try:
                self._copy_thumbnail(source_item, new_item)
            except Exception as e:
                logger.warning(f"Failed to copy thumbnail: {str(e)}")
                
            return ItemCloneResult(
                success=True,
                new_item=new_item,
                new_id=new_item.id,
                new_url=new_item.homepage
            )
            
        except Exception as e:
            logger.error(f"Error cloning notebook {item_id}: {str(e)}")
            return ItemCloneResult(
                success=False,
                error=str(e)
            )
            
    def extract_definition(self, item_id: str) -> Dict:
        """
        Extract the notebook definition.
        
        Args:
            item_id: Source notebook item ID
            
        Returns:
            Notebook JSON content
        """
        source_item = self.source_gis.content.get(item_id)
        if not source_item:
            raise Exception(f"Item {item_id} not found")
            
        # Get notebook content
        notebook_data = source_item.get_data()
        
        if not notebook_data:
            raise Exception(f"Failed to extract notebook data for {item_id}")
            
        return notebook_data
        
    def _update_notebook_references(self, notebook_json: Dict, id_mapper: IDMapper, 
                                   source_item_id: str) -> Dict:
        """
        Update all references in the notebook JSON.
        
        Args:
            notebook_json: Notebook JSON to update
            id_mapper: ID mapper for reference tracking
            source_item_id: Source notebook item ID
            
        Returns:
            Updated notebook JSON
        """
        if 'cells' not in notebook_json:
            logger.warning("Notebook has no cells to update")
            return notebook_json
            
        logger.info(f"Updating references in {len(notebook_json['cells'])} cells")
        
        for i, cell in enumerate(notebook_json['cells']):
            cell_type = cell.get('cell_type', '')
            
            if cell_type == 'code':
                # Update code cells
                self._update_code_cell(cell, id_mapper, i)
            elif cell_type == 'markdown':
                # Update markdown cells
                self._update_markdown_cell(cell, id_mapper, i)
                
        # Update organization URLs throughout the notebook
        if hasattr(id_mapper, 'portal_mapping'):
            notebook_str = json.dumps(notebook_json)
            for source_url, dest_url in id_mapper.portal_mapping.items():
                notebook_str = notebook_str.replace(source_url, dest_url)
            notebook_json = json.loads(notebook_str)
            
        return notebook_json
        
    def _update_code_cell(self, cell: Dict, id_mapper: IDMapper, cell_index: int):
        """Update references in a code cell."""
        if 'source' not in cell:
            return
            
        # Handle source as list of strings or single string
        if isinstance(cell['source'], list):
            source_lines = cell['source']
        else:
            source_lines = [cell['source']]
            
        updated_lines = []
        was_updated = False
        
        for line in source_lines:
            updated_line = line
            
            # Update item IDs in common patterns
            patterns = [
                # gis.content.get('id')
                (r'gis\.content\.get\s*\(\s*[\'"]([a-f0-9]{32})[\'"]\s*\)', 'gis.content.get'),
                # Item(gis, 'id')
                (r'Item\s*\(\s*\w+\s*,\s*[\'"]([a-f0-9]{32})[\'"]\s*\)', 'Item'),
                # String literals with 32-char hex IDs
                (r'[\'"]([a-f0-9]{32})[\'"]', 'string'),
            ]
            
            for pattern, context in patterns:
                matches = re.finditer(pattern, updated_line)
                for match in matches:
                    old_id = match.group(1)
                    new_id = id_mapper.get_new_id(old_id)
                    if new_id:
                        updated_line = updated_line.replace(old_id, new_id)
                        was_updated = True
                        logger.debug(f"Updated {context} reference in cell {cell_index}: {old_id} -> {new_id}")
            
            # Update service URLs
            service_urls = re.findall(r'https://[^/]+/[^/]+/rest/services/[^\s\'"]+/FeatureServer(?:/\d+)?', updated_line)
            for url in service_urls:
                new_url = id_mapper.get_new_url(url)
                if new_url:
                    updated_line = updated_line.replace(url, new_url)
                    was_updated = True
                    logger.debug(f"Updated service URL in cell {cell_index}: {url} -> {new_url}")
                    
            # Update portal URLs in GIS connections
            gis_pattern = r'GIS\s*\(\s*[\'"]([^\'\"]+)[\'"]\s*,'
            gis_matches = re.finditer(gis_pattern, updated_line)
            for match in gis_matches:
                old_url = match.group(1)
                # Check if this URL is in our portal mapping
                for source_portal, dest_portal in id_mapper.portal_mapping.items():
                    if old_url.startswith(source_portal):
                        new_url = old_url.replace(source_portal, dest_portal)
                        updated_line = updated_line.replace(old_url, new_url)
                        was_updated = True
                        logger.debug(f"Updated GIS URL in cell {cell_index}: {old_url} -> {new_url}")
                        
            updated_lines.append(updated_line)
            
        if was_updated:
            # Restore original format (list or string)
            if isinstance(cell['source'], list):
                cell['source'] = updated_lines
            else:
                cell['source'] = ''.join(updated_lines)
            logger.info(f"Updated code cell {cell_index}")
            
    def _update_markdown_cell(self, cell: Dict, id_mapper: IDMapper, cell_index: int):
        """Update references in a markdown cell."""
        if 'source' not in cell:
            return
            
        # Handle source as list of strings or single string
        if isinstance(cell['source'], list):
            source_text = ''.join(cell['source'])
        else:
            source_text = cell['source']
            
        updated_text = source_text
        was_updated = False
        
        # Update item URLs
        item_url_pattern = r'https://[^/]+/home/item\.html\?id=([a-f0-9]{32})'
        matches = re.finditer(item_url_pattern, updated_text)
        for match in matches:
            old_id = match.group(1)
            new_id = id_mapper.get_new_id(old_id)
            if new_id:
                old_url = match.group(0)
                # Reconstruct URL with destination portal
                if hasattr(id_mapper, 'dest_gis') and id_mapper.dest_gis:
                    new_url = f"{id_mapper.dest_gis.url}/home/item.html?id={new_id}"
                else:
                    new_url = old_url.replace(old_id, new_id)
                updated_text = updated_text.replace(old_url, new_url)
                was_updated = True
                logger.debug(f"Updated item URL in cell {cell_index}: {old_id} -> {new_id}")
                
        # Update web map viewer URLs
        viewer_patterns = [
            r'/apps/mapviewer/index\.html\?webmap=([a-f0-9]{32})',
            r'/apps/webappviewer/index\.html\?id=([a-f0-9]{32})',
            r'/apps/dashboards/#/([a-f0-9]{32})',
            r'/apps/instant/app\.html\?appid=([a-f0-9]{32})'
        ]
        
        for pattern in viewer_patterns:
            matches = re.finditer(pattern, updated_text)
            for match in matches:
                old_id = match.group(1)
                new_id = id_mapper.get_new_id(old_id)
                if new_id:
                    updated_text = updated_text.replace(old_id, new_id)
                    was_updated = True
                    logger.debug(f"Updated app URL in cell {cell_index}: {old_id} -> {new_id}")
                    
        # Update service URLs
        service_urls = re.findall(r'https://[^/]+/[^/]+/rest/services/[^\s<>\"]+/FeatureServer(?:/\d+)?', updated_text)
        for url in service_urls:
            new_url = id_mapper.get_new_url(url)
            if new_url:
                updated_text = updated_text.replace(url, new_url)
                was_updated = True
                logger.debug(f"Updated service URL in cell {cell_index}")
                
        # Update portal URLs
        for source_portal, dest_portal in id_mapper.portal_mapping.items():
            if source_portal in updated_text:
                updated_text = updated_text.replace(source_portal, dest_portal)
                was_updated = True
                
        if was_updated:
            # Restore original format (list or string)
            if isinstance(cell['source'], list):
                # Split back into lines preserving original line breaks
                lines = updated_text.split('\n')
                # Add newline characters back except for the last line
                cell['source'] = [line + '\n' for line in lines[:-1]] + [lines[-1]] if lines else []
            else:
                cell['source'] = updated_text
            logger.info(f"Updated markdown cell {cell_index}")
            
    def update_references(self, item: Item, id_mapper: IDMapper) -> bool:
        """
        Update references in an already cloned notebook.
        
        This is typically not needed for notebooks as references are updated during cloning,
        but provided for consistency with other cloners.
        
        Args:
            item: The cloned notebook item
            id_mapper: ID mapper with reference mappings
            
        Returns:
            True if references were updated, False otherwise
        """
        try:
            # Get current notebook content
            notebook_json = item.get_data()
            if not notebook_json:
                logger.warning(f"No data found for notebook {item.id}")
                return False
                
            # Update references
            updated_json = self._update_notebook_references(notebook_json, id_mapper, item.id)
            
            # Check if anything changed
            if json.dumps(notebook_json) == json.dumps(updated_json):
                logger.info(f"No references needed updating in notebook {item.id}")
                return False
                
            # Update the item with new content
            item_properties = {
                'text': json.dumps(updated_json)
            }
            
            success = item.update(item_properties=item_properties)
            if success:
                logger.info(f"Successfully updated references in notebook {item.id}")
                return True
            else:
                logger.error(f"Failed to update notebook {item.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating references for notebook {item.id}: {str(e)}")
            return False