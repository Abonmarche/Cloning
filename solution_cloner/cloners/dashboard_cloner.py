"""
Dashboard Cloner
================
Clones ArcGIS Dashboard items with support for data expressions and embed widgets.
Based on recreate_Dashboard_by_json.py
"""

import logging
import json
from typing import Dict, Optional, Any, List
from datetime import datetime
import re
from pathlib import Path

from arcgis.gis import GIS

from ..base.base_cloner import BaseCloner, ItemCloneResult
from ..utils.id_mapper import IDMapper
from ..utils.json_handler import save_json
from ..utils.url_utils import extract_portal_url_from_gis, ensure_url_consistency

logger = logging.getLogger(__name__)


class DashboardCloner(BaseCloner):
    """Handles cloning of ArcGIS Dashboards with data expression and embed support."""
    
    def __init__(self, source_gis: GIS, dest_gis: GIS, json_output_dir=None):
        """
        Initialize the Dashboard cloner.
        
        Args:
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            json_output_dir: Directory for JSON output (optional)
        """
        super().__init__(source_gis, dest_gis)
        self.json_output_dir = json_output_dir or Path("json_files")
        
    def clone(self, item_id: str, folder: str = None, id_mapper: IDMapper = None, **kwargs) -> ItemCloneResult:
        """
        Clone a dashboard item.
        
        Args:
            item_id: Source dashboard item ID
            folder: Destination folder name
            id_mapper: ID mapper for reference updates
            **kwargs: Additional cloning options
                - update_refs_before_create: Update references before creating (always True for dashboards)
                
        Returns:
            ItemCloneResult with success status and new item
        """
        try:
            # Get source item
            source_item = self.source_gis.content.get(item_id)
            if not source_item:
                return ItemCloneResult(
                    success=False,
                    error=f"Source dashboard not found: {item_id}"
                )
                
            # Verify item type
            if source_item.type != "Dashboard":
                return ItemCloneResult(
                    success=False,
                    error=f"Item is not a Dashboard: {source_item.type}"
                )
                
            logger.info(f"Cloning dashboard: {source_item.title} ({item_id})")
            
            # Extract dashboard JSON
            dashboard_json = source_item.get_data()
            
            # Save original JSON for reference
            save_json(
                dashboard_json,
                self.json_output_dir / f"dashboard_{item_id}_source"
            )
            
            # Log dashboard structure
            self._log_dashboard_structure(dashboard_json)
            
            # Create a copy of the JSON for modification
            updated_json = json.loads(json.dumps(dashboard_json))
            
            # Update references if ID mapper provided
            if id_mapper:
                logger.info("Updating dashboard references...")
                
                # Get normalized portal URLs
                source_org_url = extract_portal_url_from_gis(self.source_gis)
                dest_org_url = extract_portal_url_from_gis(self.dest_gis)
                
                # Add portal mapping
                id_mapper.add_portal_mapping(source_org_url, dest_org_url)
                
                try:
                    # Update references
                    updated_json = self._update_references(
                        updated_json, 
                        id_mapper,
                        source_org_url,
                        dest_org_url,
                        source_item.id
                    )
                except Exception as e:
                    logger.error(f"Error in _update_references: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise
                
            # Save updated JSON
            save_json(
                updated_json,
                self.json_output_dir / f"dashboard_{item_id}_updated"
            )
            
            # Prepare item properties
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_title = kwargs.get('title', source_item.title)
            
            item_properties = {
                "type": "Dashboard",
                "title": new_title,
                "tags": source_item.tags if source_item.tags else ["python", "cloned", "dashboard"],
                "snippet": source_item.snippet if source_item.snippet else f"Cloned from {source_item.title}",
                "description": source_item.description if source_item.description else f"Dashboard cloned from item {item_id}",
                "text": json.dumps(updated_json)  # Pass updated JSON as text
            }
            
            # Copy additional properties
            for prop in ['accessInformation', 'licenseInfo', 'culture', 'access']:
                if hasattr(source_item, prop) and getattr(source_item, prop):
                    item_properties[prop] = getattr(source_item, prop)
                    
            # Add extent if available
            if hasattr(source_item, 'extent') and source_item.extent:
                item_properties['extent'] = source_item.extent
                
            # Add typeKeywords
            if hasattr(source_item, 'typeKeywords') and source_item.typeKeywords:
                item_properties['typeKeywords'] = source_item.typeKeywords
                
            # Create the dashboard
            logger.info(f"Creating dashboard: {new_title}")
            new_item = self.dest_gis.content.add(
                item_properties=item_properties,
                folder=folder
            )
            
            logger.info(f"Successfully created dashboard: {new_item.title} ({new_item.id})")
            logger.info(f"Dashboard URL: {new_item.homepage}")
            
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
                
            # Verify the cloned dashboard
            self._verify_dashboard(source_item, new_item)
            
            return ItemCloneResult(
                success=True,
                new_item=new_item,
                new_id=new_item.id,
                new_url=new_item.homepage
            )
            
        except Exception as e:
            logger.error(f"Error cloning dashboard {item_id}: {str(e)}")
            return ItemCloneResult(
                success=False,
                error=str(e)
            )
            
    def _log_dashboard_structure(self, dashboard_json: Dict):
        """Log information about the dashboard structure."""
        if 'widgets' in dashboard_json:
            widgets = dashboard_json['widgets']
            
            # Handle both list and dict formats
            if isinstance(widgets, list):
                widget_list = widgets
                widget_count = len(widgets)
            elif isinstance(widgets, dict):
                widget_list = list(widgets.values())
                widget_count = len(widgets)
            else:
                widget_list = []
                widget_count = 0
                
            logger.info(f"Dashboard contains {widget_count} widgets")
            
            # Count widget types
            widget_types = {}
            for widget in widget_list:
                widget_type = widget.get('type', 'Unknown')
                widget_types[widget_type] = widget_types.get(widget_type, 0) + 1
                
            logger.info("Widget breakdown:")
            for wtype, count in widget_types.items():
                logger.info(f"  - {wtype}: {count}")
                
        # Check for data expressions (arcadeDataSourceItems in newer dashboards)
        arcade_sources_key = 'arcadeDataSourceItems' if 'arcadeDataSourceItems' in dashboard_json else 'dataExpressions'
        if arcade_sources_key in dashboard_json:
            expr_count = len(dashboard_json[arcade_sources_key])
            logger.info(f"Dashboard contains {expr_count} arcade data sources")
            
    def _update_references(self, dashboard_json: Dict, id_mapper: IDMapper, 
                          source_org_url: str, dest_org_url: str, source_item_id: str) -> Dict:
        """
        Update all references in the dashboard JSON.
        
        Args:
            dashboard_json: Dashboard JSON to update
            id_mapper: ID mapper for reference tracking
            source_org_url: Source organization URL
            dest_org_url: Destination organization URL
            source_item_id: Source dashboard item ID (for pending updates)
            
        Returns:
            Updated dashboard JSON
        """
        # Update data expressions (arcadeDataSourceItems in newer dashboards)
        arcade_sources_key = 'arcadeDataSourceItems' if 'arcadeDataSourceItems' in dashboard_json else 'dataExpressions'
        if arcade_sources_key in dashboard_json:
            arcade_sources = dashboard_json[arcade_sources_key]
            logger.info(f"Updating {len(arcade_sources)} arcade data sources...")
            for i, item in enumerate(arcade_sources):
                # The expression might be in different fields depending on dashboard version
                # Check for 'script' (newer dashboards) or 'expression' (older dashboards)
                expr_key = None
                if 'script' in item:
                    expr_key = 'script'
                elif 'expression' in item:
                    expr_key = 'expression'
                elif 'dataSource' in item and isinstance(item['dataSource'], dict) and 'expression' in item['dataSource']:
                    # Nested expression
                    original = item['dataSource']['expression']
                    item['dataSource']['expression'] = id_mapper.update_arcade_expressions(
                        item['dataSource']['expression'],
                        source_org_url,
                        dest_org_url
                    )
                    if original != item['dataSource']['expression']:
                        logger.debug(f"Updated arcade data source {i}")
                    continue
                
                if expr_key and isinstance(item[expr_key], str):
                    original = item[expr_key]
                    
                    # Log the original expression for debugging
                    logger.debug(f"Updating arcade expression in field '{expr_key}' for data source {i}")
                    logger.debug(f"Original expression preview: {original[:200]}...")
                    
                    # Update the expression/script
                    item[expr_key] = id_mapper.update_arcade_expressions(
                        item[expr_key],
                        source_org_url,
                        dest_org_url
                    )
                    
                    if original != item[expr_key]:
                        logger.info(f"Updated arcade data source {i} - field '{expr_key}'")
                        logger.debug(f"Updated expression preview: {item[expr_key][:200]}...")
                    else:
                        logger.debug(f"No changes needed for arcade data source {i}")
                        
        # Update data sources
        if 'dataSources' in dashboard_json:
            # Check if dataSources is a dict or list
            if isinstance(dashboard_json['dataSources'], dict):
                for ds_id, data_source in dashboard_json['dataSources'].items():
                    if 'itemId' in data_source:
                        old_id = data_source['itemId']
                        new_id = id_mapper.get_new_id(old_id)
                        if new_id:
                            data_source['itemId'] = new_id
                            logger.debug(f"Updated data source {ds_id}: {old_id} -> {new_id}")
                            
                    # Update URLs in data sources
                    if 'url' in data_source:
                        new_url = id_mapper.get_new_url(data_source['url'])
                        if new_url:
                            data_source['url'] = new_url
            elif isinstance(dashboard_json['dataSources'], list):
                for data_source in dashboard_json['dataSources']:
                    if 'itemId' in data_source:
                        old_id = data_source['itemId']
                        new_id = id_mapper.get_new_id(old_id)
                        if new_id:
                            data_source['itemId'] = new_id
                            logger.debug(f"Updated data source: {old_id} -> {new_id}")
                            
                    # Update URLs in data sources
                    if 'url' in data_source:
                        new_url = id_mapper.get_new_url(data_source['url'])
                        if new_url:
                            data_source['url'] = new_url
                        
        # Update widgets
        if 'widgets' in dashboard_json:
            for widget in dashboard_json['widgets']:
                self._update_widget_references(widget, id_mapper, source_item_id)
                
        # Update desktop view widgets
        if 'desktopView' in dashboard_json and 'widgets' in dashboard_json['desktopView']:
            widgets = dashboard_json['desktopView']['widgets']
            if isinstance(widgets, dict):
                for widget_id, widget in widgets.items():
                    self._update_widget_references(widget, id_mapper, source_item_id)
            elif isinstance(widgets, list):
                for widget in widgets:
                    self._update_widget_references(widget, id_mapper, source_item_id)
                
        # Update mobile view if present
        if 'mobileView' in dashboard_json and 'widgets' in dashboard_json['mobileView']:
            widgets = dashboard_json['mobileView']['widgets']
            if isinstance(widgets, dict):
                for widget_id, widget in widgets.items():
                    self._update_widget_references(widget, id_mapper, source_item_id)
            elif isinstance(widgets, list):
                for widget in widgets:
                    self._update_widget_references(widget, id_mapper, source_item_id)
                
        # Update organization URLs throughout
        dashboard_str = json.dumps(dashboard_json)
        dashboard_str = dashboard_str.replace(source_org_url, dest_org_url)
        dashboard_json = json.loads(dashboard_str)
        
        return dashboard_json
        
    def _update_widget_references(self, widget: Dict, id_mapper: IDMapper, source_item_id: str):
        """Update references within a widget."""
        widget_type = widget.get('type', '')
        
        # Handle embed widgets
        if widget_type == 'embedWidget' or 'embed' in widget_type.lower():
            self._update_embed_widget(widget, id_mapper, source_item_id)
            
        # Handle map widgets
        elif widget_type == 'mapWidget':
            if 'itemId' in widget:
                old_id = widget['itemId']
                new_id = id_mapper.get_new_id(old_id)
                if new_id:
                    widget['itemId'] = new_id
                    logger.debug(f"Updated map widget item: {old_id} -> {new_id}")
                    
        # Handle data-driven widgets (indicators, charts, etc.)
        if 'datasets' in widget:
            for dataset in widget['datasets']:
                if 'dataSource' in dataset:
                    data_source = dataset['dataSource']
                    if 'itemId' in data_source:
                        old_id = data_source['itemId']
                        new_id = id_mapper.get_new_id(old_id)
                        if new_id:
                            data_source['itemId'] = new_id
                            logger.debug(f"Updated widget dataset: {old_id} -> {new_id}")
                            
        # Handle layer references in widgets
        if 'layerId' in widget:
            # This might be a reference to a specific layer in a service
            # Check if we need to update based on service URL mappings
            pass
            
    def _update_embed_widget(self, widget: Dict, id_mapper: IDMapper, source_item_id: str):
        """Update embed widget URLs, handling circular references."""
        # Common fields that might contain embed URLs
        url_fields = ['url', 'src', 'embedUrl', 'iframeSrc']
        
        for field in url_fields:
            if field in widget and widget[field]:
                original_url = widget[field]
                
                # Check if it's an instant app URL first
                instant_app_pattern = r'/apps/instant/(?:manager/index|app)\.html\?appid=([a-f0-9]{32})'
                instant_match = re.search(instant_app_pattern, original_url, re.IGNORECASE)
                if instant_match:
                    old_app_id = instant_match.group(1)
                    new_app_id = id_mapper.get_new_id(old_app_id)
                    if new_app_id:
                        widget[field] = original_url.replace(old_app_id, new_app_id)
                        logger.info(f"Updated instant app reference in embed widget: {old_app_id} -> {new_app_id}")
                        continue
                
                # Try general embed URL update
                updated_url, was_updated = id_mapper.update_embed_urls(original_url)
                
                if was_updated:
                    widget[field] = updated_url
                    logger.info(f"Updated embed URL in widget: {field}")
                else:
                    # Check if this references an item type that hasn't been cloned yet
                    # Extract potential item ID from URL
                    item_id_patterns = [
                        r'/apps/experiencebuilder/experience/\?id=([a-f0-9]{32})',
                        r'/apps/storymap/\?id=([a-f0-9]{32})',
                        r'/apps/instant/(?:manager/index|app)\.html\?appid=([a-f0-9]{32})'
                    ]
                    
                    for pattern in item_id_patterns:
                        match = re.search(pattern, original_url, re.IGNORECASE)
                        if match:
                            ref_item_id = match.group(1)
                            # Add pending update for phase 2
                            id_mapper.add_pending_update(
                                source_item_id,
                                'embed_url',
                                {
                                    'field': field,
                                    'widget_path': self._get_widget_path(widget),
                                    'original_url': original_url,
                                    'referenced_item': ref_item_id
                                }
                            )
                            logger.info(f"Added pending update for embed URL referencing unclonable item: {ref_item_id}")
                            break
                            
    def _get_widget_path(self, widget: Dict) -> str:
        """Get a path identifier for a widget (for pending updates)."""
        # Try to create a unique identifier for the widget
        if 'id' in widget:
            return f"widget_{widget['id']}"
        elif 'name' in widget:
            return f"widget_{widget['name']}"
        else:
            return f"widget_{widget.get('type', 'unknown')}"
            
    def _verify_dashboard(self, source_item, new_item):
        """Verify the cloned dashboard matches the source."""
        try:
            new_json = new_item.get_data()
            source_json = source_item.get_data()
            
            # Compare structure
            source_keys = set(source_json.keys())
            new_keys = set(new_json.keys())
            
            if source_keys == new_keys:
                logger.info("✓ All top-level dashboard properties successfully cloned")
            else:
                if source_keys - new_keys:
                    logger.warning(f"Missing keys in cloned dashboard: {source_keys - new_keys}")
                if new_keys - source_keys:
                    logger.warning(f"Additional keys in cloned dashboard: {new_keys - source_keys}")
                    
            # Check widget count
            if 'widgets' in source_json and 'widgets' in new_json:
                source_widgets = len(source_json.get('widgets', []))
                new_widgets = len(new_json.get('widgets', []))
                if source_widgets == new_widgets:
                    logger.info(f"✓ All {source_widgets} widgets successfully cloned")
                else:
                    logger.warning(f"Widget count mismatch: {source_widgets} -> {new_widgets}")
                    
            # Check data expressions
            if 'dataExpressions' in source_json:
                source_exprs = len(source_json.get('dataExpressions', []))
                new_exprs = len(new_json.get('dataExpressions', []))
                if source_exprs == new_exprs:
                    logger.info(f"✓ All {source_exprs} data expressions successfully cloned")
                else:
                    logger.warning(f"Data expression count mismatch: {source_exprs} -> {new_exprs}")
                    
        except Exception as e:
            logger.warning(f"Could not verify dashboard: {str(e)}")
            
    def extract_definition(self, item_id: str, gis: GIS, save_path=None) -> Dict[str, Any]:
        """
        Extract the complete definition of a dashboard.
        
        Args:
            item_id: ID of the dashboard to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the dashboard definition
        """
        try:
            item = gis.content.get(item_id)
            if not item:
                raise ValueError(f"Dashboard not found: {item_id}")
                
            # Get the dashboard JSON
            dashboard_json = item.get_data()
            
            # Save if path provided
            if save_path:
                save_json(dashboard_json, save_path, f"Dashboard definition for {item.title}")
                
            return dashboard_json
            
        except Exception as e:
            logger.error(f"Error extracting dashboard definition: {str(e)}")
            return {}
            
    def update_references(self, item, id_mapper: 'IDMapper', dest_gis: GIS):
        """
        Update references in an already cloned dashboard.
        
        Args:
            item: The cloned dashboard item
            id_mapper: IDMapper instance with all mappings
            dest_gis: Destination GIS connection
        """
        try:
            # Get current dashboard data
            dashboard_json = item.get_data()
            if not dashboard_json:
                return
            
            # Get normalized portal URLs
            source_org_url = extract_portal_url_from_gis(self.source_gis) if hasattr(self, 'source_gis') else "https://www.arcgis.com"
            dest_org_url = extract_portal_url_from_gis(dest_gis)
            
            # Update references
            updated_json = self._update_references(
                dashboard_json,
                id_mapper,
                source_org_url,
                dest_org_url,
                item.id
            )
            
            # Check if anything was actually updated
            if json.dumps(dashboard_json) != json.dumps(updated_json):
                # Update the item data
                item.update(item_properties={'text': json.dumps(updated_json)})
                logger.info(f"Updated dashboard references for: {item.title}")
                    
        except Exception as e:
            logger.error(f"Error updating dashboard references: {str(e)}")