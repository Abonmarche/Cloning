"""
View Cloner - Clone ArcGIS Online View Layers
"""

import json
import logging
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayerCollection

from ..base.base_cloner import BaseCloner
from ..utils.json_handler import save_json

# Configure logger
logger = logging.getLogger(__name__)


class ViewCloner(BaseCloner):
    """Clone View Layers with field visibility and layer filtering."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the View cloner."""
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
        Clone a view layer.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            **kwargs: Additional arguments
            
        Returns:
            Cloned view item or None if failed
        """
        try:
            # Get source item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item:
                logger.error(f"Item {source_item['id']} not found")
                return None
                
            # Wrap in FeatureLayerCollection
            src_flc = FeatureLayerCollection.fromitem(src_item)
            if not getattr(src_flc.properties, "isView", False):
                logger.error(f"Item {source_item['id']} is not a view layer")
                return None
                
            logger.info(f"Cloning view layer: {src_item.title}")
            
            # Extract view configuration
            view_config = self._extract_view_config(src_item, src_flc)
            
            # Get parent item ID (not layer ID)
            parent_id = self._get_parent_item_id(source_gis, src_item, src_flc)
            if not parent_id:
                logger.error("Could not find parent hosted feature layer")
                return None
                
            # Check if parent has been cloned
            logger.info(f"Looking for parent item {parent_id} in id_mapping")
            logger.debug(f"Current id_mapping keys: {list(id_mapping.keys())}")
            new_parent_id = id_mapping.get(parent_id)
            if not new_parent_id:
                logger.warning(f"Parent item {parent_id} not found in id_mapping")
                
                # Check if we can use the original parent from source
                parent_item = source_gis.content.get(parent_id)
                if not parent_item:
                    logger.error(f"Parent layer {parent_id} not found in source. Cannot create view without parent layer.")
                    return None
                    
                # Check if creating a cross-org view is allowed (usually not)
                if source_gis._url != dest_gis._url:
                    logger.error("Cannot create view from parent in different organization. Parent must be cloned first.")
                    return None
                    
                logger.warning(f"Using original parent layer from source - this may fail if cross-org views are not allowed")
                new_parent_id = parent_id
                parent_flc = FeatureLayerCollection.fromitem(parent_item)
                parent_gis = source_gis
            else:
                logger.info(f"Using cloned parent layer: {new_parent_id}")
                parent_item = dest_gis.content.get(new_parent_id)
                if not parent_item:
                    logger.error(f"Cloned parent layer {new_parent_id} not found in destination")
                    return None
                parent_flc = FeatureLayerCollection.fromitem(parent_item)
                parent_gis = dest_gis
                
            logger.info(f"Parent layer: {parent_item.title} ({parent_item.id})")
            
            # Get item data for visualization
            item_data = src_item.get_data()
            
            # Save original configurations
            save_json(
                view_config,
                self.json_output_dir / f"view_config_{src_item.id}.json"
            )
            
            # Use original title (no need to make unique since we're in a different folder/org)
            new_title = src_item.title
            
            # Map layer IDs to layer objects
            view_layer_objects = self._map_layer_objects(
                view_config.get('view_layers', []),
                parent_flc.layers,
                "layer"
            )
            
            view_table_objects = self._map_layer_objects(
                view_config.get('view_tables', []),
                parent_flc.tables,
                "table"
            )
            
            # Create the view
            logger.info(f"Creating view: {new_title}")
            
            new_view_item = parent_flc.manager.create_view(
                name=new_title,
                spatial_reference=view_config.get('spatial_reference'),
                extent=view_config.get('extent'),
                allow_schema_changes=view_config.get('allow_schema_changes', True),
                updateable=view_config.get('updateable', True),
                capabilities=view_config.get('capabilities', 'Query'),
                view_layers=view_layer_objects,
                view_tables=view_table_objects,
                description=view_config.get('description'),
                tags=view_config.get('tags'),
                snippet=view_config.get('snippet'),
                preserve_layer_ids=True
            )
            
            if not new_view_item:
                logger.error("Failed to create view")
                return None
                
            logger.info(f"View created: {new_view_item.id}")
            
            # Move to destination folder
            if dest_folder:
                try:
                    new_view_item.move(dest_folder)
                    logger.info(f"Moved view to folder: {dest_folder}")
                except Exception as e:
                    logger.warning(f"Could not move view to folder {dest_folder}: {e}")
            
            # Copy item-level visualization
            try:
                new_view_item.update(data=item_data)
                logger.info("Item-level visualization copied")
            except Exception as e:
                logger.warning(f"Could not copy item data: {e}")
                
            # Copy additional metadata
            self._copy_metadata(src_item, new_view_item)
            
            # Apply field visibility
            self._apply_field_visibility(
                src_flc, 
                new_view_item,
                view_config.get('layer_definitions', {})
            )
            
            # Track URL mappings
            self._track_service_urls(src_item, new_view_item, src_flc, new_view_item)
            
            # Copy thumbnail
            if src_item.thumbnail:
                try:
                    new_view_item.update(thumbnail=src_item.thumbnail)
                except Exception as e:
                    logger.warning(f"Failed to copy thumbnail: {e}")
                    
            return new_view_item
            
        except Exception as e:
            logger.error(f"Error cloning view layer: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    def _extract_view_config(self, src_item: Item, src_flc: FeatureLayerCollection) -> Dict:
        """Extract view configuration."""
        config = {}
        
        # Extract service-level properties
        svc_props = src_flc.properties
        
        config['allow_schema_changes'] = svc_props.get('allowGeometryUpdates', True)
        config['updateable'] = 'Update' in svc_props.get('capabilities', '')
        config['capabilities'] = svc_props.get('capabilities', 'Query')
        
        # Spatial reference and extent
        if 'spatialReference' in svc_props:
            config['spatial_reference'] = svc_props['spatialReference']
            
        if 'initialExtent' in svc_props:
            config['extent'] = svc_props['initialExtent']
        elif 'fullExtent' in svc_props:
            config['extent'] = svc_props['fullExtent']
            
        # Process layers
        view_layers = []
        layer_definitions = {}
        
        for lyr in src_flc.layers:
            layer_id = self._get_source_layer_id(lyr)
            view_layers.append(layer_id)
            
            # Store layer configuration
            layer_config = {
                'query': None,
                'visible_fields': [],
                'view_definition': None
            }
            
            # Extract view definition
            if hasattr(lyr.properties, 'viewLayerDefinition'):
                view_def = lyr.properties.viewLayerDefinition
                layer_config['view_definition'] = view_def
                
                # Extract query
                if 'filter' in view_def and 'where' in view_def['filter']:
                    layer_config['query'] = view_def['filter']['where']
                    
            # Extract visible fields
            if hasattr(lyr.properties, 'fields'):
                visible_fields = []
                for field in lyr.properties.fields:
                    if isinstance(field, dict):
                        visible_fields.append(field['name'])
                    else:
                        visible_fields.append(field.name if hasattr(field, 'name') else str(field))
                layer_config['visible_fields'] = visible_fields
                logger.debug(f"Layer {lyr.properties.name}: {len(visible_fields)} fields visible")
                
            layer_definitions[layer_id] = layer_config
            
        # Process tables
        view_tables = []
        for tbl in src_flc.tables:
            table_id = self._get_source_layer_id(tbl)
            view_tables.append(table_id)
            
        config['view_layers'] = view_layers if view_layers else None
        config['view_tables'] = view_tables if view_tables else None
        config['layer_definitions'] = layer_definitions
        
        # Extract metadata
        config['description'] = src_item.description
        config['tags'] = ','.join(src_item.tags) if src_item.tags else None
        config['snippet'] = src_item.snippet
        
        return config
        
    def _get_parent_item_id(self, gis, view_item, view_flc=None):
        """Get parent item ID for a view layer."""
        # Method 1: Try related_items
        relationships = view_item.related_items(rel_type="Service2Data")
        if relationships:
            parent = relationships[0]
            logger.debug(f"Found parent via related_items: {parent.title} ({parent.id})")
            return parent.id
            
        # Method 2: Try /sources endpoint
        sources_url = f"{view_item.url}/sources"
        params = {"f": "json"}
        if hasattr(gis._con, 'token') and gis._con.token:
            params["token"] = gis._con.token
            
        try:
            r = requests.get(sources_url, params=params)
            if r.ok:
                resp = r.json()
                services = resp.get("services", [])
                if services:
                    service = services[0]
                    parent_id = service.get("serviceItemId")
                    if parent_id:
                        logger.debug(f"Found parent via /sources: {service.get('name')} ({parent_id})")
                        return parent_id
        except Exception as e:
            logger.debug(f"Error getting sources: {e}")
            
        # Method 3: Try to find by matching URLs
        if view_flc:
            try:
                # Get the source layer ID from the view properties
                source_layer_id = None
                if hasattr(view_flc, 'layers') and view_flc.layers:
                    layer = view_flc.layers[0]
                    if hasattr(layer.properties, 'viewLayerDefinition'):
                        source_layer_id = layer.properties.viewLayerDefinition.get("sourceLayerId")
                        
                if source_layer_id:
                    # Search for feature services that might contain this layer
                    search_results = gis.content.search(
                        query='type:"Feature Service"',
                        max_items=100
                    )
                    
                    for item in search_results:
                        try:
                            test_flc = FeatureLayerCollection.fromitem(item)
                            for lyr in test_flc.layers:
                                if hasattr(lyr.properties, 'id') and lyr.properties.id == source_layer_id:
                                    logger.debug(f"Found parent by layer ID match: {item.title} ({item.id})")
                                    return item.id
                        except:
                            continue
            except Exception as e:
                logger.debug(f"Error in URL matching method: {e}")
                
        logger.warning("Could not determine parent item ID")
        return None
    
    def _get_source_layer_id(self, layer_or_gis, view_item=None):
        """Get source layer ID for a view layer."""
        # If called with a layer object
        if hasattr(layer_or_gis, 'properties'):
            try:
                return layer_or_gis.properties.viewLayerDefinition["sourceLayerId"]
            except:
                return layer_or_gis.properties.get("sourceLayerId", layer_or_gis.properties.id)
                
        # If called with GIS and view_item (for finding parent)
        if view_item:
            gis = layer_or_gis
            
            # Method 1: Try related_items
            relationships = view_item.related_items(rel_type="Service2Data")
            if relationships:
                parent = relationships[0]
                logger.debug(f"Found parent via related_items: {parent.title} ({parent.id})")
                return parent.id
                
            # Method 2: Try /sources endpoint
            sources_url = f"{view_item.url}/sources"
            data = {"f": "json"}
            if hasattr(gis._con, 'token') and gis._con.token:
                data["token"] = gis._con.token
                
            r = requests.post(sources_url, data=data)
            
            if r.ok:
                resp = r.json()
                services = resp.get("services", [])
                if services:
                    service = services[0]
                    parent_id = service.get("serviceItemId")
                    logger.debug(f"Found parent via /sources: {service.get('name')} ({parent_id})")
                    return parent_id
                    
        return None
        
    def _map_layer_objects(self, layer_ids: List[int], layers: List, layer_type: str) -> List:
        """Map layer IDs to layer objects."""
        if not layer_ids:
            return None
            
        objects = []
        for layer_id in layer_ids:
            for lyr in layers:
                if lyr.properties.id == layer_id:
                    objects.append(lyr)
                    logger.debug(f"Including {layer_type} {layer_id}: {lyr.properties.name}")
                    break
        return objects
        
    def _apply_field_visibility(self, src_flc: FeatureLayerCollection, new_view_item: Item, layer_definitions: Dict):
        """Apply field visibility using ViewManager."""
        try:
            # Get visible fields from source
            src_visible_fields = {}
            for src_lyr in src_flc.layers:
                source_id = self._get_source_layer_id(src_lyr)
                visible_fields = []
                
                if hasattr(src_lyr.properties, 'fields'):
                    for field in src_lyr.properties.fields:
                        if isinstance(field, dict):
                            visible_fields.append(field['name'])
                        else:
                            visible_fields.append(field.name if hasattr(field, 'name') else str(field))
                            
                src_visible_fields[source_id] = visible_fields
                logger.debug(f"Source layer {source_id} has {len(visible_fields)} visible fields")
                
            # Wait for view to be ready
            time.sleep(3)
            
            # Get ViewManager
            view_manager = new_view_item.view_manager
            view_layer_definitions = None
            
            # Retry getting definitions
            for attempt in range(3):
                view_layer_definitions = view_manager.get_definitions(new_view_item)
                if view_layer_definitions:
                    break
                logger.info(f"Waiting for view to be ready... (attempt {attempt + 1}/3)")
                time.sleep(2)
                
            if view_layer_definitions:
                logger.info(f"Found {len(view_layer_definitions)} view layer definitions")
                
                for idx, view_layer_def in enumerate(view_layer_definitions):
                    sub_layer = view_layer_def.layer
                    
                    # Get all fields
                    all_fields = []
                    if hasattr(sub_layer.properties, 'fields'):
                        for field in sub_layer.properties.fields:
                            if isinstance(field, dict):
                                all_fields.append(field['name'])
                            else:
                                all_fields.append(field.name if hasattr(field, 'name') else str(field))
                                
                    # Determine visible fields
                    visible_field_names = src_visible_fields.get(idx, src_visible_fields.get(0, []))
                    
                    # Build update
                    fields_update = []
                    for field_name in all_fields:
                        fields_update.append({
                            "name": field_name,
                            "visible": field_name in visible_field_names
                        })
                        
                    visible_count = sum(1 for f in fields_update if f['visible'])
                    hidden_count = len(fields_update) - visible_count
                    logger.info(f"Updating layer {idx}: {visible_count} visible, {hidden_count} hidden")
                    
                    # Apply update
                    update_dict = {"fields": fields_update}
                    update_result = sub_layer.manager.update_definition(update_dict)
                    
                    if update_result.get('success', False):
                        logger.info(f"Successfully updated field visibility for layer {idx}")
                    else:
                        logger.warning(f"Field visibility update failed: {update_result}")
                        
                    # Apply query if exists
                    if idx in layer_definitions:
                        layer_config = layer_definitions[idx]
                        if layer_config.get('query'):
                            query_update = {"viewDefinitionQuery": layer_config['query']}
                            query_result = sub_layer.manager.update_definition(query_update)
                            logger.info(f"Applied query filter: {query_result}")
                            
            else:
                logger.warning("No view layer definitions found after 3 attempts")
                
        except Exception as e:
            logger.error(f"Error updating field visibility: {e}")
            
    def _copy_metadata(self, src_item: Item, new_item: Item):
        """Copy additional metadata."""
        try:
            meta = {
                "licenseInfo": getattr(src_item, "licenseInfo", None),
                "accessInformation": getattr(src_item, "accessInformation", None)
            }
            if any(meta.values()):
                new_item.update(item_properties={k: v for k, v in meta.items() if v})
                logger.debug("Additional metadata copied")
        except Exception as e:
            logger.warning(f"Could not copy metadata: {e}")
            
    def _track_service_urls(self, src_item: Item, new_item: Item, src_flc: FeatureLayerCollection, new_flc):
        """Track service and sublayer URL mappings."""
        try:
            new_flc = FeatureLayerCollection.fromitem(new_item)
            
            mapping_data = {
                'id': new_item.id,
                'url': new_item.url,
                'sublayer_urls': {}
            }
            
            # Track main service URL
            if src_item.url and new_item.url:
                logger.debug(f"Service URL mapping: {src_item.url} -> {new_item.url}")
                
                # Track layer URLs
                for i, (src_layer, new_layer) in enumerate(zip(src_flc.layers, new_flc.layers)):
                    src_layer_url = f"{src_item.url}/{i}"
                    new_layer_url = f"{new_item.url}/{i}"
                    mapping_data['sublayer_urls'][src_layer_url] = new_layer_url
                    logger.debug(f"Layer {i} URL mapping: {src_layer_url} -> {new_layer_url}")
                    
                # Track table URLs
                for i, (src_table, new_table) in enumerate(zip(src_flc.tables, new_flc.tables)):
                    table_idx = len(src_flc.layers) + i
                    src_table_url = f"{src_item.url}/{table_idx}"
                    new_table_url = f"{new_item.url}/{table_idx}"
                    mapping_data['sublayer_urls'][src_table_url] = new_table_url
                    logger.debug(f"Table {table_idx} URL mapping: {src_table_url} -> {new_table_url}")
                    
            self._last_mapping_data = mapping_data
        except Exception as e:
            logger.warning(f"Could not track service URLs: {e}")
            
    def get_last_mapping_data(self) -> Optional[Dict[str, Any]]:
        """Get the mapping data from the last clone operation."""
        return self._last_mapping_data
        
    def _get_unique_title(self, title: str, gis: GIS) -> str:
        """Generate a unique title."""
        import uuid
        import re
        
        base_title = re.sub(r'_[a-f0-9]{8}$', '', title)
        search_result = gis.content.search(f'title:"{base_title}"', max_items=1)
        if not search_result:
            return base_title
            
        unique_suffix = uuid.uuid4().hex[:8]
        return f"{base_title}_{unique_suffix}"
        
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Extract the complete definition of a view."""
        try:
            item = gis.content.get(item_id)
            if not item:
                logger.error(f"Item {item_id} not found")
                return {}
                
            flc = FeatureLayerCollection.fromitem(item)
            if not getattr(flc.properties, "isView", False):
                logger.error(f"Item {item_id} is not a view")
                return {}
                
            # Extract configuration
            config = self._extract_view_config(item, flc)
            
            # Get parent layer
            parent_id = self._get_source_layer_id(gis, item)
            config['parent_layer_id'] = parent_id
            
            # Get item data
            item_data = item.get_data()
            
            definition = {
                'item_properties': {
                    'id': item.id,
                    'title': item.title,
                    'snippet': item.snippet,
                    'description': item.description,
                    'tags': item.tags,
                    'typeKeywords': item.typeKeywords,
                    'thumbnail': item.thumbnail
                },
                'view_configuration': config,
                'item_data': item_data,
                'service_properties': dict(flc.properties)
            }
            
            if save_path:
                save_json(
                    definition,
                    save_path / f"view_definition_{item_id}.json"
                )
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting view definition: {str(e)}")
            return {}
            
    def update_references(
        self,
        item: Item,
        id_mapping: Dict[str, Dict[str, str]],
        gis: GIS
    ) -> bool:
        """
        Update references in a view layer.
        
        Views reference their parent layer, which may have been cloned.
        This would require recreating the view with the new parent.
        """
        # Views are created from their parent, so references are handled during creation
        logger.info(f"View {item.title} references are handled during creation")
        return True