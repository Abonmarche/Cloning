"""
Experience Builder Cloner
=========================
Clones ArcGIS Experience Builder applications with embed widget support.
Based on recreate_ExB_by_json.py
"""

import logging
import json
from typing import Dict, Optional, Any, List
from datetime import datetime
import re
import time
from pathlib import Path

from arcgis.gis import GIS

from ..base.base_cloner import BaseCloner, ItemCloneResult
from ..utils.id_mapper import IDMapper
from ..utils.json_handler import save_json

logger = logging.getLogger(__name__)


class ExperienceBuilderCloner(BaseCloner):
    """Handles cloning of ArcGIS Experience Builder applications."""
    
    def __init__(self, source_gis: GIS, dest_gis: GIS):
        """
        Initialize the Experience Builder cloner.
        
        Args:
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
        """
        super().__init__(source_gis, dest_gis)
        
    def clone(self, item_id: str, folder: str = None, id_mapper: IDMapper = None, **kwargs) -> ItemCloneResult:
        """
        Clone an Experience Builder application.
        
        Args:
            item_id: Source experience item ID
            folder: Destination folder name
            id_mapper: ID mapper for reference updates
            **kwargs: Additional cloning options
                
        Returns:
            ItemCloneResult with success status and new item
        """
        try:
            # Get source item
            source_item = self.source_gis.content.get(item_id)
            if not source_item:
                return ItemCloneResult(
                    success=False,
                    error=f"Source experience not found: {item_id}"
                )
                
            # Verify item type (Experience Builder can have different type names)
            valid_types = ["Web Experience", "StoryMap", "Web Experience Template"]
            if source_item.type not in valid_types:
                # Check typeKeywords as fallback
                if not any(kw in source_item.typeKeywords for kw in ['Experience', 'ExB', 'Web Experience']):
                    logger.warning(f"Item type '{source_item.type}' may not be an Experience Builder app")
                
            logger.info(f"Cloning Experience Builder app: {source_item.title} ({item_id})")
            logger.info(f"Type: {source_item.type}")
            
            # Extract experience JSON
            experience_json = source_item.get_data()
            
            # Save original JSON for reference
            save_json(
                experience_json,
                Path("json_files") / f"experience_builder_{item_id}_source"
            )
            
            # Log experience structure
            self._log_experience_structure(experience_json)
            
            # Create a copy of the JSON for modification
            updated_json = json.loads(json.dumps(experience_json))
            
            # Update references if ID mapper provided
            if id_mapper:
                logger.info("Updating experience references...")
                
                # Get portal URLs
                source_org_url = f"https://{self.source_gis.url.split('//')[1].split('/')[0]}"
                dest_org_url = f"https://{self.dest_gis.url.split('//')[1].split('/')[0]}"
                
                # Add portal mapping
                id_mapper.add_portal_mapping(source_org_url, dest_org_url)
                
                # Update references
                updated_json = self._update_references(
                    updated_json,
                    id_mapper,
                    source_org_url,
                    dest_org_url,
                    source_item.id
                )
                
            # Save updated JSON
            save_json(
                updated_json,
                Path("json_files") / f"experience_builder_{item_id}_updated"
            )
            
            # Prepare item properties
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_title = kwargs.get('title', source_item.title)
            
            item_properties = {
                "type": source_item.type,  # Use the same type as original
                "title": new_title,
                "tags": source_item.tags if source_item.tags else ["python", "cloned", "experience builder"],
                "snippet": source_item.snippet if source_item.snippet else f"Cloned from {source_item.title}",
                "description": source_item.description if source_item.description else f"Experience Builder app cloned from item {item_id}",
                "text": json.dumps(updated_json)  # Pass updated JSON as text
            }
            
            # Copy additional properties
            for prop in ['accessInformation', 'licenseInfo', 'culture', 'access', 'properties']:
                if hasattr(source_item, prop) and getattr(source_item, prop):
                    item_properties[prop] = getattr(source_item, prop)
                    
            # Add extent if available
            if hasattr(source_item, 'extent') and source_item.extent:
                item_properties['extent'] = source_item.extent
                
            # Add typeKeywords (critical for Experience Builder functionality)
            if hasattr(source_item, 'typeKeywords') and source_item.typeKeywords:
                item_properties['typeKeywords'] = source_item.typeKeywords
                
            # Add URL if available
            if hasattr(source_item, 'url') and source_item.url:
                item_properties['url'] = source_item.url
                
            # Create the experience
            logger.info(f"Creating Experience Builder app: {new_title}")
            new_item = self.dest_gis.content.add(
                item_properties=item_properties,
                folder=folder
            )
            
            # Write the Builder draft config (critical for Experience Builder)
            logger.info("Writing draft config for Experience Builder...")
            try:
                new_item.resources.add(
                    folder_name="config",
                    file_name="config.json",
                    text=json.dumps(updated_json)
                )
                logger.info("✓ Draft config written to resources/config/config.json")
            except Exception as e:
                logger.warning(f"Failed to write draft config: {str(e)}")
            
            logger.info(f"Successfully created Experience Builder app: {new_item.title} ({new_item.id})")
            logger.info(f"Experience URL: {new_item.homepage}")
            
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
                
            # Verify the cloned experience
            self._verify_experience(source_item, new_item)
            
            return ItemCloneResult(
                success=True,
                new_item=new_item,
                new_id=new_item.id,
                new_url=new_item.homepage
            )
            
        except Exception as e:
            logger.error(f"Error cloning Experience Builder app {item_id}: {str(e)}")
            return ItemCloneResult(
                success=False,
                error=str(e)
            )
            
    def _log_experience_structure(self, experience_json: Dict):
        """Log information about the experience structure."""
        if not experience_json:
            return
            
        # Pages
        if 'pages' in experience_json:
            page_count = len(experience_json.get('pages', {}))
            logger.info(f"Experience contains {page_count} pages")
            
        # Widgets
        if 'widgets' in experience_json:
            widget_count = len(experience_json.get('widgets', {}))
            logger.info(f"Experience contains {widget_count} widgets")
            
            # Count widget types
            widget_types = {}
            for widget_id, widget_data in experience_json.get('widgets', {}).items():
                if isinstance(widget_data, dict):
                    widget_type = widget_data.get('manifest', {}).get('name', 'Unknown')
                    widget_types[widget_type] = widget_types.get(widget_type, 0) + 1
                    
            if widget_types:
                logger.info("Widget breakdown:")
                for wtype, count in widget_types.items():
                    logger.info(f"  - {wtype}: {count}")
                    
        # Data sources
        if 'dataSources' in experience_json:
            datasource_count = len(experience_json.get('dataSources', {}))
            logger.info(f"Experience uses {datasource_count} data sources")
            
        # Themes
        if 'themes' in experience_json:
            theme_count = len(experience_json.get('themes', {}))
            logger.info(f"Experience has {theme_count} theme(s)")
            
    def _update_references(self, experience_json: Dict, id_mapper: IDMapper,
                          source_org_url: str, dest_org_url: str, source_item_id: str) -> Dict:
        """
        Update all references in the experience JSON.
        
        Args:
            experience_json: Experience JSON to update
            id_mapper: ID mapper for reference tracking
            source_org_url: Source organization URL
            dest_org_url: Destination organization URL
            source_item_id: Source experience item ID (for pending updates)
            
        Returns:
            Updated experience JSON
        """
        # Update data sources
        if 'dataSources' in experience_json:
            logger.debug(f"Updating {len(experience_json['dataSources'])} data sources")
            for ds_id, data_source in experience_json['dataSources'].items():
                logger.debug(f"Updating data source {ds_id}")
                # Add parent item ID for pending updates
                data_source['_parent_item_id'] = source_item_id
                self._update_data_source(data_source, id_mapper)
                
        # Update dataSourcesInfo if present (maps old IDs to new ones)
        if 'dataSourcesInfo' in experience_json:
            ds_info = experience_json['dataSourcesInfo']
            if isinstance(ds_info, dict):
                for old_id, info in list(ds_info.items()):
                    new_id = id_mapper.get_new_id(old_id)
                    if new_id and new_id != old_id:
                        # Move the info to the new ID key
                        ds_info[new_id] = info
                        del ds_info[old_id]
                        logger.debug(f"Updated dataSourcesInfo key: {old_id} -> {new_id}")
                
        # Update widgets
        if 'widgets' in experience_json:
            for widget_id, widget_data in experience_json['widgets'].items():
                if isinstance(widget_data, dict):
                    self._update_widget_references(widget_data, id_mapper, source_item_id)
                    
        # Update pages (may contain widget references)
        if 'pages' in experience_json:
            for page_id, page_data in experience_json['pages'].items():
                if isinstance(page_data, dict):
                    self._update_page_references(page_data, id_mapper)
                    
        # Update organization URLs throughout
        experience_str = json.dumps(experience_json)
        experience_str = experience_str.replace(source_org_url, dest_org_url)
        experience_json = json.loads(experience_str)
        
        return experience_json
        
    def _update_data_source(self, data_source: Dict, id_mapper: IDMapper):
        """Update references in a data source."""
        # Item-based data source
        if 'itemId' in data_source:
            old_id = data_source['itemId']
            new_id = id_mapper.get_new_id(old_id)
            if new_id:
                data_source['itemId'] = new_id
                logger.info(f"Updated data source item: {old_id} -> {new_id}")
            else:
                logger.warning(f"No mapping found for data source item: {old_id}")
                
        # URL-based data source
        if 'url' in data_source:
            new_url = id_mapper.get_new_url(data_source['url'])
            if new_url:
                data_source['url'] = new_url
                logger.debug(f"Updated data source URL")
                
        # Portal item reference
        if 'portalItem' in data_source and isinstance(data_source['portalItem'], dict):
            if 'id' in data_source['portalItem']:
                old_id = data_source['portalItem']['id']
                new_id = id_mapper.get_new_id(old_id)
                if new_id:
                    data_source['portalItem']['id'] = new_id
                    logger.debug(f"Updated portal item reference: {old_id} -> {new_id}")
                    
        # Update child data sources (for web map data sources)
        if 'childDataSourceJsons' in data_source and isinstance(data_source['childDataSourceJsons'], dict):
            for child_id, child_ds in data_source['childDataSourceJsons'].items():
                self._update_data_source(child_ds, id_mapper)
                    
    def _update_widget_references(self, widget: Dict, id_mapper: IDMapper, source_item_id: str):
        """Update references within a widget."""
        # Get widget type from uri or manifest
        widget_uri = widget.get('uri', '')
        if widget_uri:
            # Extract widget type from URI like "widgets/common/embed/"
            widget_parts = widget_uri.strip('/').split('/')
            if len(widget_parts) >= 2:
                widget_type = widget_parts[-1]
            else:
                widget_type = ''
        else:
            # Fallback to manifest name
            widget_type = widget.get('manifest', {}).get('name', '')
        
        logger.debug(f"Processing widget type: {widget_type} (uri: {widget_uri})")
        
        # Handle embed widgets
        if 'embed' in widget_type.lower() or widget_type == 'arcgis-embed' or 'embed' in widget_uri:
            self._update_embed_widget(widget, id_mapper, source_item_id)
            
        # Handle map widgets
        elif 'map' in widget_type.lower() or 'map' in widget_uri:
            if 'config' in widget and isinstance(widget['config'], dict):
                config = widget['config']
                
                # Update item references in config
                if 'itemId' in config:
                    old_id = config['itemId']
                    new_id = id_mapper.get_new_id(old_id)
                    if new_id:
                        config['itemId'] = new_id
                        logger.debug(f"Updated map widget item: {old_id} -> {new_id}")
                        
                # Update map references
                if 'maps' in config and isinstance(config['maps'], dict):
                    for map_id, map_config in config['maps'].items():
                        if 'itemId' in map_config:
                            old_id = map_config['itemId']
                            new_id = id_mapper.get_new_id(old_id)
                            if new_id:
                                map_config['itemId'] = new_id
                                
        # Handle data source references in widget config
        if 'config' in widget and isinstance(widget['config'], dict):
            config = widget['config']
            
            # Update data source references
            if 'dataSourceId' in config:
                # This references a data source in the dataSources section
                # which should already be updated
                pass
                
            # Update any embedded item IDs
            self._update_embedded_ids(config, id_mapper)
            
        # Some widgets may have direct references at the widget level
        # Update any top-level item references
        if 'itemId' in widget:
            old_id = widget['itemId']
            new_id = id_mapper.get_new_id(old_id)
            if new_id:
                widget['itemId'] = new_id
                logger.debug(f"Updated widget-level item reference: {old_id} -> {new_id}")
            
    def _update_embed_widget(self, widget: Dict, id_mapper: IDMapper, source_item_id: str):
        """Update embed widget URLs, handling circular references."""
        if 'config' not in widget:
            return
            
        config = widget['config']
        url_updated = False
        
        # Common fields that might contain embed URLs
        url_fields = ['url', 'src', 'embedUrl', 'embedCode', 'content', 'expression']
        
        for field in url_fields:
            if field in config:
                if field == 'embedCode':
                    # Embed code might contain HTML with URLs
                    original_code = config[field]
                    updated_code = self._update_embed_code(original_code, id_mapper)
                    if updated_code != original_code:
                        config[field] = updated_code
                        url_updated = True
                elif field == 'expression' and isinstance(config[field], str):
                    # Expression field often contains HTML-wrapped URLs
                    original_expr = config[field]
                    updated_expr = original_expr
                    
                    # Extract URL from HTML if present
                    url_in_html_pattern = r'<[^>]*>([^<]+)</[^>]*>'
                    html_match = re.search(url_in_html_pattern, original_expr)
                    if html_match:
                        inner_content = html_match.group(1)
                        if 'http' in inner_content:
                            # This is likely a URL wrapped in HTML
                            updated_url = self._update_single_url(inner_content, id_mapper)
                            if updated_url != inner_content:
                                updated_expr = original_expr.replace(inner_content, updated_url)
                                config[field] = updated_expr
                                logger.info(f"Updated URL in expression field: {field}")
                                url_updated = True
                    else:
                        # Try updating the whole expression as a URL
                        updated_expr = self._update_single_url(original_expr, id_mapper)
                        if updated_expr != original_expr:
                            config[field] = updated_expr
                            logger.info(f"Updated expression field: {field}")
                            url_updated = True
                else:
                    # Direct URL field
                    original_url = config[field]
                    updated_url = self._update_single_url(original_url, id_mapper)
                    
                    if updated_url != original_url:
                        config[field] = updated_url
                        logger.info(f"Updated embed URL in widget: {field}")
                        url_updated = True
                                
    def _update_single_url(self, url: str, id_mapper: IDMapper) -> str:
        """Update a single URL with proper dashboard and item ID handling."""
        if not url or not isinstance(url, str) or 'http' not in url:
            return url
            
        # Check if this is a dashboard reference
        dashboard_patterns = [
            r'/apps/dashboards/#/([a-f0-9]{32})',
            r'/apps/dashboards/([a-f0-9]{32})'
        ]
        
        for pattern in dashboard_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                ref_item_id = match.group(1)
                # Dashboards should already be cloned, try to update now
                new_id = id_mapper.get_new_id(ref_item_id)
                if new_id:
                    updated_url = url.replace(ref_item_id, new_id)
                    logger.info(f"Updated dashboard reference: {ref_item_id} -> {new_id}")
                    return updated_url
                    
        # Try general embed URL update
        updated_url, was_updated = id_mapper.update_embed_urls(url)
        if was_updated:
            return updated_url
            
        return url
        
    def _update_embed_code(self, embed_code: str, id_mapper: IDMapper) -> str:
        """Update URLs within HTML embed code."""
        updated_code = embed_code
        
        # Find all URLs in the embed code
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+)'
        urls = re.findall(url_pattern, embed_code)
        
        for url in urls:
            updated_url = self._update_single_url(url, id_mapper)
            if updated_url != url:
                updated_code = updated_code.replace(url, updated_url)
                
        return updated_code
        
    def _update_page_references(self, page: Dict, id_mapper: IDMapper):
        """Update references within a page configuration."""
        # Pages might reference widgets or have their own configurations
        if 'config' in page and isinstance(page['config'], dict):
            self._update_embedded_ids(page['config'], id_mapper)
            
    def _update_embedded_ids(self, obj: Any, id_mapper: IDMapper):
        """Recursively update any embedded item IDs in an object."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Common ID field names
                if key in ['itemId', 'webmap', 'portalItemId', 'id', 'sourceItemId']:
                    if isinstance(value, str) and len(value) == 32:
                        new_id = id_mapper.get_new_id(value)
                        if new_id:
                            obj[key] = new_id
                            logger.debug(f"Updated embedded ID in {key}: {value} -> {new_id}")
                else:
                    self._update_embedded_ids(value, id_mapper)
                    
        elif isinstance(obj, list):
            for item in obj:
                self._update_embedded_ids(item, id_mapper)
                
    def _verify_experience(self, source_item, new_item):
        """Verify the cloned experience matches the source."""
        try:
            new_json = new_item.get_data()
            source_json = source_item.get_data()
            
            # Compare structure
            source_keys = set(source_json.keys())
            new_keys = set(new_json.keys())
            
            if source_keys == new_keys:
                logger.info("✓ All top-level experience properties successfully cloned")
            else:
                if source_keys - new_keys:
                    logger.warning(f"Missing keys in cloned experience: {source_keys - new_keys}")
                if new_keys - source_keys:
                    logger.warning(f"Additional keys in cloned experience: {new_keys - source_keys}")
                    
            # Check key components
            components_to_check = ['pages', 'widgets', 'dataSources', 'themes', 'layouts']
            for component in components_to_check:
                if component in source_json and component in new_json:
                    source_count = len(source_json.get(component, {}))
                    new_count = len(new_json.get(component, {}))
                    if source_count == new_count:
                        logger.info(f"✓ {component}: {source_count} items successfully cloned")
                    else:
                        logger.warning(f"{component}: Original had {source_count}, cloned has {new_count}")
                        
        except Exception as e:
            logger.warning(f"Could not verify experience: {str(e)}")
            
    def extract_definition(self, item_id: str, gis: GIS, save_path=None) -> Dict[str, Any]:
        """
        Extract the complete definition of an Experience Builder app.
        
        Args:
            item_id: ID of the experience to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the experience definition
        """
        try:
            item = gis.content.get(item_id)
            if not item:
                raise ValueError(f"Experience not found: {item_id}")
                
            # Get the experience JSON
            experience_json = item.get_data()
            
            # Save if path provided
            if save_path:
                save_json(experience_json, save_path, f"Experience definition for {item.title}")
                
            return experience_json
            
        except Exception as e:
            logger.error(f"Error extracting experience definition: {str(e)}")
            return {}
            
    def update_draft_config(self, item, updated_json: Dict) -> bool:
        """
        Update the draft configuration in Experience Builder resources.
        
        Args:
            item: The Experience Builder item
            updated_json: The updated JSON configuration
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First, try to list existing resources
            resources = item.resources.list()
            config_exists = any(r.get('resource') == 'config/config.json' for r in resources)
            
            if config_exists:
                # Resource exists, we need to update it
                # Try the update method if available
                if hasattr(item.resources, 'update'):
                    try:
                        # Some versions of the API require different parameter names
                        success = False
                        
                        # Try method 1: Direct update with file path
                        try:
                            item.resources.update(
                                file="config/config.json",
                                text=json.dumps(updated_json)
                            )
                            success = True
                            logger.debug("Updated using file parameter")
                        except:
                            pass
                            
                        # Try method 2: Update with folder and file name
                        if not success:
                            try:
                                item.resources.update(
                                    folder_name="config",
                                    file_name="config.json",
                                    text=json.dumps(updated_json)
                                )
                                success = True
                                logger.debug("Updated using folder_name/file_name parameters")
                            except:
                                pass
                        
                        # Try method 3: Update with resource parameter
                        if not success:
                            try:
                                item.resources.update(
                                    resource="config/config.json",
                                    text=json.dumps(updated_json)
                                )
                                success = True
                                logger.debug("Updated using resource parameter")
                            except:
                                pass
                                
                        if success:
                            logger.info("✓ Updated Experience Builder draft config")
                            return True
                        else:
                            logger.debug("All update methods failed")
                            
                    except Exception as e:
                        logger.debug(f"Update methods failed: {e}")
                
                # If update failed, try remove and add
                # This approach works around the "Resource already present" error
                try:
                    # Remove the existing resource
                    remove_success = False
                    
                    # Try different removal approaches
                    try:
                        item.resources.remove(file="config/config.json")
                        remove_success = True
                        logger.debug("Removed using file parameter")
                    except:
                        pass
                        
                    if not remove_success:
                        try:
                            item.resources.remove(resource="config/config.json")
                            remove_success = True
                            logger.debug("Removed using resource parameter")
                        except:
                            pass
                            
                    if not remove_success:
                        try:
                            item.resources.remove(folder_name="config", file_name="config.json")
                            remove_success = True
                            logger.debug("Removed using folder_name/file_name parameters")
                        except:
                            pass
                    
                    if remove_success:
                        # Wait a moment for the removal to process
                        time.sleep(2)
                        
                        # Add the updated config
                        item.resources.add(
                            folder_name="config",
                            file_name="config.json",
                            text=json.dumps(updated_json)
                        )
                        logger.info("✓ Updated Experience Builder draft config using remove/add")
                        return True
                    else:
                        logger.warning("Could not remove existing draft config")
                        
                except Exception as e:
                    logger.error(f"Remove/add approach failed: {str(e)}")
                    
            else:
                # Resource doesn't exist, just add it
                try:
                    item.resources.add(
                        folder_name="config",
                        file_name="config.json",
                        text=json.dumps(updated_json)
                    )
                    logger.info("✓ Added Experience Builder draft config (did not exist)")
                    return True
                except Exception as e:
                    logger.error(f"Failed to add draft config: {str(e)}")
                    
            # If we get here, all approaches failed
            # As a last resort, try to overwrite by using the item's update method
            # to update the entire experience data
            try:
                # Get current item data
                current_data = item.get_data()
                
                # If the published data is different from what we want, update it
                if json.dumps(current_data) != json.dumps(updated_json):
                    item.update(item_properties={'text': json.dumps(updated_json)})
                    logger.info("✓ Updated published experience data (draft update failed)")
                    
                logger.warning("Could not update draft config directly, but published version is current")
                return True
                
            except Exception as e:
                logger.error(f"Final fallback failed: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to update draft config: {str(e)}")
            return False
            
    def update_references(self, item, id_mapper: 'IDMapper', dest_gis: GIS):
        """
        Update references in an already cloned experience.
        
        Args:
            item: The cloned experience item
            id_mapper: IDMapper instance with all mappings
            dest_gis: Destination GIS connection
        """
        try:
            # Get current experience data
            experience_json = item.get_data()
            if not experience_json:
                return
            
            # Get portal URLs
            source_org_url = f"https://www.arcgis.com"  # Default
            dest_org_url = f"https://{dest_gis.url.split('//')[1].split('/')[0]}"
            
            # Update references
            updated_json = self._update_references(
                experience_json,
                id_mapper,
                source_org_url,
                dest_org_url,
                item.id
            )
            
            # Check if anything was actually updated
            if json.dumps(experience_json) != json.dumps(updated_json):
                # Update the item data
                item.update(item_properties={'text': json.dumps(updated_json)})
                logger.info(f"Updated experience published config for: {item.title}")
                
                # Also update the draft config in resources
                self.update_draft_config(item, updated_json)
                    
        except Exception as e:
            logger.error(f"Error updating experience references: {str(e)}")