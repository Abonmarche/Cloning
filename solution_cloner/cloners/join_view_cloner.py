"""
Join View Cloner - Clone ArcGIS Online Join View Layers
"""

import json
import logging
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


class JoinViewCloner(BaseCloner):
    """Clone Join View Layers using admin endpoint for join definitions."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the Join View cloner."""
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
        Clone a join view layer.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            **kwargs: Additional arguments
            
        Returns:
            Cloned join view item or None if failed
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
                
            logger.info(f"Cloning join view: {src_item.title}")
            
            # Extract join configuration from admin endpoint
            join_config = self._extract_join_definition_from_admin(source_gis, src_item)
            if not join_config:
                logger.error("Failed to extract join configuration")
                return None
                
            # Check if it's actually a join view
            if not join_config.get('join_definition'):
                logger.error(f"Item {source_item['id']} is not a join view")
                return None
                
            # Get source layer info
            source_layers = self._get_sublayer_sources(source_gis, src_item)
            if len(source_layers) < 2:
                logger.error("Expected at least 2 source layers in join view")
                return None
                
            # Match source layers with config
            for src_layer in source_layers:
                if src_layer['layer_num'] == join_config['main_source']['layer_id']:
                    join_config['main_source']['item_id'] = src_layer['service_item_id']
                elif src_layer['layer_num'] == join_config['joined_source']['layer_id']:
                    join_config['joined_source']['item_id'] = src_layer['service_item_id']
                    
            # Map source items to cloned items
            id_map = id_mapping.get('ids', {})
            
            # Update main source
            main_item_id = join_config['main_source']['item_id']
            new_main_id = id_map.get(main_item_id, main_item_id)
            if new_main_id != main_item_id:
                logger.info(f"Using cloned main source: {new_main_id}")
                # Update service name to match cloned item
                main_item = dest_gis.content.get(new_main_id)
                if main_item:
                    join_config['main_source']['service_name'] = main_item.title
            else:
                logger.warning(f"Main source {main_item_id} not yet cloned")
                
            # Update joined source
            joined_item_id = join_config['joined_source']['item_id']
            new_joined_id = id_map.get(joined_item_id, joined_item_id)
            if new_joined_id != joined_item_id:
                logger.info(f"Using cloned joined source: {new_joined_id}")
                # Update service name to match cloned item
                joined_item = dest_gis.content.get(new_joined_id)
                if joined_item:
                    join_config['joined_source']['service_name'] = joined_item.title
            else:
                logger.warning(f"Joined source {joined_item_id} not yet cloned")
                    
            # Get item data for visualization
            item_data = src_item.get_data()
            
            # Add view metadata
            join_config['view_title'] = src_item.title
            join_config['view_description'] = src_item.description
            join_config['view_snippet'] = src_item.snippet
            join_config['view_tags'] = src_item.tags
            
            # Get service properties
            svc_props = src_flc.properties
            join_config['capabilities'] = svc_props.get('capabilities', 'Query')
            join_config['allow_schema_changes'] = svc_props.get('allowGeometryUpdates', True)
            
            # Get spatial reference
            self._extract_spatial_reference(src_flc, join_config)
            
            # Save configuration
            save_json(
                join_config,
                self.json_output_dir / f"join_config_{src_item.id}.json"
            )
            
            logger.info(f"Join configuration extracted:")
            logger.info(f"  Main: {join_config['main_source']['service_name']} (layer {join_config['main_source']['layer_id']})")
            logger.info(f"  Joined: {join_config['joined_source']['service_name']} (layer {join_config['joined_source']['layer_id']})")
            logger.info(f"  Join: {join_config['join_definition']['parent_key_fields']} → {join_config['join_definition']['key_fields']}")
            
            # Create unique name
            new_title = self._get_unique_title(src_item.title, dest_gis)
            
            # Create the join view
            new_view = self._create_join_view(dest_gis, new_title, join_config)
            
            if not new_view:
                logger.error("Failed to create join view")
                return None
                
            logger.info(f"Join view created: {new_view.id}")
            
            # Copy item-level visualization
            try:
                new_view.update(data=item_data)
                logger.info("Item-level visualization copied")
            except Exception as e:
                logger.warning(f"Could not copy item data: {e}")
                
            # Copy metadata
            try:
                meta = {
                    "description": join_config.get('view_description'),
                    "snippet": join_config.get('view_snippet'),
                    "tags": ','.join(join_config.get('view_tags', [])) if join_config.get('view_tags') else None
                }
                if any(meta.values()):
                    new_view.update(item_properties={k: v for k, v in meta.items() if v})
                    logger.info("Metadata copied")
            except Exception as e:
                logger.warning(f"Could not copy metadata: {e}")
                
            # Track URL mappings
            self._track_service_urls(src_item, new_view)
            
            # Copy thumbnail
            if src_item.thumbnail:
                try:
                    new_view.update(thumbnail=src_item.thumbnail)
                except Exception as e:
                    logger.warning(f"Failed to copy thumbnail: {e}")
                    
            return new_view
            
        except Exception as e:
            logger.error(f"Error cloning join view: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    def _extract_join_definition_from_admin(self, gis: GIS, view_item: Item) -> Optional[Dict]:
        """Extract join definition from the administrative REST API endpoint."""
        
        # Convert regular REST URL to admin URL
        if "/rest/services/" not in view_item.url:
            logger.error("Cannot construct admin URL. '/rest/services/' not found in item URL.")
            return None
            
        admin_url = view_item.url.replace("/rest/services/", "/rest/admin/services/") + "/0"
        params = {"f": "json"}
        if hasattr(gis._con, 'token') and gis._con.token:
            params["token"] = gis._con.token
            
        logger.debug(f"Querying admin endpoint: {admin_url}")
        
        try:
            r = requests.get(admin_url, params=params)
            r.raise_for_status()
            admin_data = r.json()
            
            # Save the raw admin response
            save_json(
                admin_data,
                self.json_output_dir / f"admin_endpoint_{view_item.id}.json"
            )
            
            if "adminLayerInfo" not in admin_data:
                logger.debug("No adminLayerInfo found - not a join view")
                return None
                
            admin_info = admin_data["adminLayerInfo"]
            if "viewLayerDefinition" not in admin_info:
                logger.debug("No viewLayerDefinition found - not a join view")
                return None
                
            view_def = admin_info["viewLayerDefinition"]
            if "table" not in view_def:
                logger.debug("No table found in viewLayerDefinition - not a join view")
                return None
                
            # Extract the complete table definition
            table_def = view_def["table"]
            
            # Check if it has related tables (join definition)
            if 'relatedTables' not in table_def or not table_def['relatedTables']:
                logger.debug("No relatedTables found - not a join view")
                return None
                
            # Build config from the definition
            config = {
                'table_name': table_def.get('name'),
                'main_source': {
                    'service_name': table_def.get('sourceServiceName'),
                    'layer_id': table_def.get('sourceLayerId'),
                    'fields': table_def.get('sourceLayerFields', [])
                }
            }
            
            # Extract join information
            related = table_def['relatedTables'][0]  # Usually only one join
            config['joined_source'] = {
                'service_name': related.get('sourceServiceName'),
                'layer_id': related.get('sourceLayerId'),
                'fields': related.get('sourceLayerFields', [])
            }
            config['join_definition'] = {
                'parent_key_fields': related.get('parentKeyFields'),
                'key_fields': related.get('keyFields'),
                'join_type': related.get('type', 'INNER'),
                'top_filter': related.get('topFilter')
            }
            
            logger.info(f"Found join definition: {config['join_definition']['parent_key_fields']} → {config['join_definition']['key_fields']}")
            
            # Get geometry field if present
            if 'geometryField' in admin_info:
                config['geometry_field'] = admin_info['geometryField'].get('name')
                
            # Get other layer properties
            config['layer_name'] = admin_data.get('name')
            config['display_field'] = admin_data.get('displayField')
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to query admin endpoint: {e}")
            return None
            
    def _get_sublayer_sources(self, gis: GIS, view_item: Item) -> List[Dict]:
        """Get the source layers from the sublayer /0/sources endpoint."""
        sources_url = f"{view_item.url}/0/sources"
        params = {"f": "json"}
        
        if hasattr(gis._con, 'token') and gis._con.token:
            params["token"] = gis._con.token
            
        r = requests.get(sources_url, params=params)
        
        if r.ok:
            resp = r.json()
            save_json(
                resp,
                self.json_output_dir / f"sublayer_sources_{view_item.id}.json"
            )
            
            layers = resp.get("layers", [])
            
            source_info = []
            for layer in layers:
                # Extract layer number from URL
                url = layer.get('url', '')
                layer_num = None
                if '/FeatureServer/' in url:
                    layer_num = int(url.split('/FeatureServer/')[-1])
                    
                info = {
                    'name': layer.get('name'),
                    'service_item_id': layer.get('serviceItemId'),
                    'url': url,
                    'layer_num': layer_num
                }
                source_info.append(info)
                logger.debug(f"Found source layer: {info['name']} (Layer {layer_num})")
                
            return source_info
        else:
            logger.error(f"Failed to get sublayer sources: {r.status_code}")
            return []
            
    def _extract_spatial_reference(self, src_flc: FeatureLayerCollection, config: Dict):
        """Extract spatial reference and extent from the source."""
        if src_flc.layers and hasattr(src_flc.layers[0].properties, 'extent') and src_flc.layers[0].properties.extent:
            extent = src_flc.layers[0].properties.extent
            
            # Convert PropertyMap to dict if needed
            if hasattr(extent, '__dict__'):
                try:
                    config['extent'] = dict(extent)
                    if 'spatialReference' in config['extent']:
                        config['spatial_reference'] = dict(config['extent']['spatialReference'])
                except:
                    # Fallback
                    config['extent'] = {
                        'xmin': getattr(extent, 'xmin', None),
                        'ymin': getattr(extent, 'ymin', None),
                        'xmax': getattr(extent, 'xmax', None),
                        'ymax': getattr(extent, 'ymax', None)
                    }
                    if hasattr(extent, 'spatialReference'):
                        sr = extent.spatialReference
                        config['spatial_reference'] = {
                            'wkid': getattr(sr, 'wkid', 102100),
                            'latestWkid': getattr(sr, 'latestWkid', None)
                        }
            else:
                config['spatial_reference'] = extent.get('spatialReference') if isinstance(extent, dict) else None
                config['extent'] = extent
                
    def _create_join_view(self, gis: GIS, title: str, config: Dict) -> Optional[Item]:
        """Create a join view using the extracted configuration."""
        try:
            # Determine spatial reference
            wkid = 102100  # Default
            if config.get('spatial_reference'):
                wkid = config['spatial_reference'].get('wkid', 102100)
                
            # Create empty view service
            view_service = gis.content.create_service(
                name=title,
                is_view=True,
                wkid=wkid
            )
            view_flc = FeatureLayerCollection.fromitem(view_service)
            logger.info(f"Empty view service created: {view_service.id}")
            
            # Build the join definition
            join_def = config['join_definition']
            definition_to_add = {
                "layers": [
                    {
                        "name": config.get('layer_name', title),
                        "displayField": config.get('display_field', ''),
                        "description": "AttributeJoin",
                        "adminLayerInfo": {
                            "viewLayerDefinition": {
                                "table": {
                                    "name": "Target_fl",
                                    "sourceServiceName": config['main_source']['service_name'],
                                    "sourceLayerId": config['main_source']['layer_id'],
                                    "sourceLayerFields": config['main_source']['fields'],
                                    "relatedTables": [
                                        {
                                            "name": "JoinedTable",
                                            "sourceServiceName": config['joined_source']['service_name'],
                                            "sourceLayerId": config['joined_source']['layer_id'],
                                            "sourceLayerFields": config['joined_source']['fields'],
                                            "type": join_def['join_type'],
                                            "parentKeyFields": join_def['parent_key_fields'],
                                            "keyFields": join_def['key_fields']
                                        }
                                    ],
                                    "materialized": False
                                }
                            },
                            "geometryField": {
                                "name": config.get('geometry_field', f"{config['main_source']['service_name']}.Shape")
                            }
                        }
                    }
                ]
            }
            
            # Add top filter if present (for one-to-one joins)
            if join_def.get('top_filter'):
                related_table = definition_to_add["layers"][0]["adminLayerInfo"]["viewLayerDefinition"]["table"]["relatedTables"][0]
                related_table["topFilter"] = join_def['top_filter']
                
            # Save the definition
            save_json(
                definition_to_add,
                self.json_output_dir / f"join_definition_to_apply_{title}.json"
            )
            
            # Apply the join definition
            result = view_flc.manager.add_to_definition(definition_to_add)
            logger.info("Join view definition applied successfully")
            
            return view_service
            
        except Exception as e:
            logger.error(f"Failed to create join view: {e}")
            return None
            
    def _track_service_urls(self, src_item: Item, new_item: Item):
        """Track service and sublayer URL mappings."""
        try:
            mapping_data = {
                'id': new_item.id,
                'url': new_item.url,
                'sublayer_urls': {}
            }
            
            # Join views typically have only one layer
            if src_item.url and new_item.url:
                src_layer_url = f"{src_item.url}/0"
                new_layer_url = f"{new_item.url}/0"
                mapping_data['sublayer_urls'][src_layer_url] = new_layer_url
                logger.debug(f"Join view URL mapping: {src_layer_url} -> {new_layer_url}")
                
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
        """Extract the complete definition of a join view."""
        try:
            item = gis.content.get(item_id)
            if not item:
                logger.error(f"Item {item_id} not found")
                return {}
                
            flc = FeatureLayerCollection.fromitem(item)
            if not getattr(flc.properties, "isView", False):
                logger.error(f"Item {item_id} is not a view")
                return {}
                
            # Extract join configuration
            join_config = self._extract_join_definition_from_admin(gis, item)
            if not join_config or not join_config.get('join_definition'):
                logger.error(f"Item {item_id} is not a join view")
                return {}
                
            # Get source layers
            source_layers = self._get_sublayer_sources(gis, item)
            
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
                'join_configuration': join_config,
                'source_layers': source_layers,
                'item_data': item_data,
                'service_properties': dict(flc.properties)
            }
            
            if save_path:
                save_json(
                    definition,
                    save_path / f"join_view_definition_{item_id}.json"
                )
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting join view definition: {str(e)}")
            return {}
            
    def update_references(
        self,
        item: Item,
        id_mapping: Dict[str, Dict[str, str]],
        gis: GIS
    ) -> bool:
        """
        Update references in a join view layer.
        
        Join views reference their source layers, which may have been cloned.
        This would require recreating the join view with the new sources.
        """
        # Join views are created from their sources, so references are handled during creation
        logger.info(f"Join view {item.title} references are handled during creation")
        return True
        
    def is_join_view(self, item: Item, gis: GIS) -> bool:
        """
        Check if an item is a join view by querying the admin endpoint.
        
        Args:
            item: Item to check
            gis: GIS connection
            
        Returns:
            True if item is a join view, False otherwise
        """
        try:
            flc = FeatureLayerCollection.fromitem(item)
            if not getattr(flc.properties, "isView", False):
                return False
                
            # Try to extract join definition
            join_config = self._extract_join_definition_from_admin(gis, item)
            return join_config is not None and 'join_definition' in join_config
            
        except Exception as e:
            logger.debug(f"Error checking if item is join view: {e}")
            return False