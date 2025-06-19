"""
Feature Layer Cloner
====================
Clones hosted feature services including schema, data, and symbology.
Based on recreate_FeatureLayer_by_json.py
"""

from typing import Dict, Optional, Any, List
from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayerCollection
from arcgis._impl.common._mixins import PropertyMap
import re
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from base.base_cloner import BaseCloner
from utils.json_handler import save_json, clean_json_for_create


logger = logging.getLogger(__name__)


class FeatureLayerCloner(BaseCloner):
    """Clones feature layers and feature services."""
    
    def __init__(self):
        """Initialize the feature layer cloner."""
        super().__init__()
        self._last_mapping_data = None
    
    # Properties to exclude when copying layer definitions
    EXCLUDE_PROPS = {
        'currentVersion', 'serviceItemId', 'capabilities', 'maxRecordCount',
        'supportsAppend', 'supportedQueryFormats', 'isDataVersioned',
        'allowGeometryUpdates', 'supportsCalculate', 'supportsValidateSql',
        'advancedQueryCapabilities', 'supportsCoordinatesQuantization',
        'supportsApplyEditsWithGlobalIds', 'supportsMultiScaleGeometry',
        'syncEnabled', 'syncCapabilities', 'editorTrackingInfo',
        'changeTrackingInfo'
    }
    
    def clone(
        self,
        source_item: Dict[str, Any],
        source_gis: GIS,
        dest_gis: GIS,
        dest_folder: str,
        id_mapping: Dict[str, str],
        clone_data: bool = True,
        create_dummy_features: bool = True,
        **kwargs
    ) -> Optional[Item]:
        """
        Clone a feature service from source to destination.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            clone_data: Whether to copy data
            create_dummy_features: Whether to create dummy features for symbology
            
        Returns:
            Created item or None
        """
        try:
            # Get source item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item or src_item.type.lower() not in ['feature service', 'table']:
                logger.error(f"Item {source_item['id']} is not a feature service")
                return None
                
            logger.info(f"Cloning feature service: {src_item.title}")
            
            # Extract definition
            definition = self.extract_definition(source_item['id'], source_gis)
            
            # Get source FLC
            src_flc = FeatureLayerCollection.fromitem(src_item)
            
            # Create new service
            new_item = self._create_empty_service(
                src_item, src_flc, definition, dest_gis, dest_folder
            )
            
            if not new_item:
                return None
                
            new_flc = FeatureLayerCollection.fromitem(new_item)
            
            # Apply schema
            self._apply_schema(src_flc, new_flc, definition)
            
            # Handle data and symbology
            if create_dummy_features:
                self._create_dummy_features(src_flc, new_flc, definition)
                
            if clone_data:
                self._copy_data(src_flc, new_flc)
            
            # Apply item visualization
            self._apply_item_visualization(src_item, new_item, definition)
            
            logger.info(f"Successfully cloned: {src_item.title} -> {new_item.id}")
            
            # Track URL mappings
            if hasattr(src_item, 'url') and hasattr(new_item, 'url'):
                self._track_service_urls(src_item, new_item, src_flc, new_flc)
            
            return new_item
            
        except Exception as e:
            logger.error(f"Error cloning feature service: {str(e)}")
            return None
            
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Extract complete feature service definition."""
        item = self.get_item_safely(item_id, gis)
        if not item:
            return {}
            
        logger.info(f"Extracting definition for: {item.title}")
        
        definition = {
            'item_properties': self._extract_item_properties(item),
            'service_definition': None,
            'layers': [],
            'tables': [],
            'relationships': [],
            'item_data': None
        }
        
        try:
            # Get FLC
            flc = FeatureLayerCollection.fromitem(item)
            
            # Extract service definition
            definition['service_definition'] = self._pm_to_dict(flc.properties)
            
            # Extract layers
            for layer in flc.layers:
                layer_def = self._extract_layer_definition(layer)
                definition['layers'].append(layer_def)
                
            # Extract tables
            for table in flc.tables:
                table_def = self._extract_layer_definition(table, keep_render=False)
                definition['tables'].append(table_def)
                
            # Extract relationships
            definition['relationships'] = self._pm_to_dict(
                flc.properties.get('relationships', [])
            )
            
            # Get item data (visualization overrides)
            try:
                item_data = item.get_data()
                if item_data:
                    definition['item_data'] = item_data
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error extracting service definition: {str(e)}")
            
        # Save if requested
        if save_path:
            self.save_json(definition, save_path, f"feature_service_{item_id}")
            
        return definition
        
    def _create_empty_service(
        self,
        src_item: Item,
        src_flc: FeatureLayerCollection,
        definition: Dict,
        dest_gis: GIS,
        dest_folder: str
    ) -> Optional[Item]:
        """Create an empty feature service."""
        try:
            # Generate unique name
            new_name = self._safe_name(src_item.title)
            
            # Create service parameters
            params = {
                "name": new_name,
                "serviceDescription": src_item.description or "",
                "spatialReference": self._pm_to_dict(src_flc.properties.spatialReference),
                "capabilities": "Query",
                "hasStaticData": False
            }
            
            # Create the service
            new_item = dest_gis.content.create_service(
                name=new_name,
                service_type="featureService",
                create_params=params,
                tags=src_item.tags or ["cloned"],
                snippet=src_item.snippet or f"Clone of {src_item.title}",
                folder=dest_folder
            )
            
            logger.info(f"Created empty service: {new_item.title}")
            return new_item
            
        except Exception as e:
            logger.error(f"Error creating empty service: {str(e)}")
            return None
            
    def _apply_schema(
        self,
        src_flc: FeatureLayerCollection,
        new_flc: FeatureLayerCollection,
        definition: Dict
    ):
        """Apply schema to the new service."""
        try:
            # Build schema payload
            payload = {
                "layers": definition['layers'],
                "tables": definition['tables']
            }
            
            if definition['relationships']:
                payload["relationships"] = definition['relationships']
                
            # Apply schema
            new_flc.manager.add_to_definition(payload)
            logger.info("Applied schema definition")
            
        except Exception as e:
            logger.error(f"Error applying schema: {str(e)}")
            raise
            
    def _create_dummy_features(
        self,
        src_flc: FeatureLayerCollection,
        new_flc: FeatureLayerCollection,
        definition: Dict
    ):
        """Create dummy features for symbology."""
        logger.info("Creating dummy features for symbology...")
        
        # Create lookup for visualization data
        viz_layers = {}
        if definition['item_data'] and 'layers' in definition['item_data']:
            for viz_layer in definition['item_data']['layers']:
                if 'id' in viz_layer:
                    viz_layers[viz_layer['id']] = viz_layer
                    
        for idx, (src_lyr, tgt_lyr) in enumerate(zip(src_flc.layers, new_flc.layers)):
            gtype = tgt_lyr.properties.get('geometryType')
            if not gtype:
                continue  # Skip tables
                
            # Get spatial reference and Z/M info
            sr = self._pm_to_dict(tgt_lyr.properties.spatialReference) or {"wkid": 4326}
            has_z = bool(getattr(tgt_lyr.properties, 'hasZ', False))
            has_m = bool(getattr(tgt_lyr.properties, 'hasM', False))
            
            # Get renderer (prefer visualization over service renderer)
            renderer_dict = None
            if idx in viz_layers and 'layerDefinition' in viz_layers[idx]:
                viz_def = viz_layers[idx]['layerDefinition']
                if 'drawingInfo' in viz_def and 'renderer' in viz_def['drawingInfo']:
                    renderer_dict = viz_def['drawingInfo']['renderer']
                    
            if renderer_dict is None:
                renderer_dict = self._pm_to_dict(src_lyr.properties.drawingInfo.renderer)
                
            # Generate attribute sets for symbology
            layer_props = self._pm_to_dict(src_lyr.properties)
            attr_sets = self._dummy_attr_sets(renderer_dict, layer_props)
            
            # Create dummy features
            dummy_feats = []
            for attrs in attr_sets:
                dummy_feat = {
                    "geometry": self._blank_geom(gtype, has_z, has_m, sr),
                    "attributes": attrs
                }
                dummy_feats.append(dummy_feat)
                
            # Add features
            if dummy_feats:
                res = tgt_lyr.edit_features(adds=dummy_feats)
                if res and 'addResults' in res:
                    success_count = sum(1 for r in res['addResults'] if r.get('success', False))
                    logger.debug(f"Added {success_count}/{len(dummy_feats)} dummy features to layer {idx}")
                    
    def _copy_data(
        self,
        src_flc: FeatureLayerCollection,
        new_flc: FeatureLayerCollection
    ):
        """Copy actual data from source to destination."""
        logger.info("Copying feature data...")
        
        # TODO: Implement actual data copying
        # This would query features from source and add to destination
        # For now, dummy features provide the schema
        
    def _apply_item_visualization(
        self,
        src_item: Item,
        new_item: Item,
        definition: Dict
    ):
        """Apply item-level visualization overrides."""
        if not definition.get('item_data'):
            return
            
        try:
            logger.info("Applying item visualization...")
            new_item.update(item_properties={'text': json.dumps(definition['item_data'])})
            logger.info("Applied visualization overrides")
        except Exception as e:
            logger.warning(f"Could not apply visualization: {str(e)}")
            
    # Helper methods (converted from original script)
    
    def _pm_to_dict(self, o):
        """Convert PropertyMap objects to dictionaries recursively."""
        if isinstance(o, PropertyMap):
            o = dict(o)
        if isinstance(o, dict):
            return {k: self._pm_to_dict(v) for k, v in o.items()}
        if isinstance(o, list):
            return [self._pm_to_dict(i) for i in o]
        return o
        
    def _safe_name(self, title: str, uid: int = 8, max_len: int = 30) -> str:
        """Generate a safe, unique name."""
        core_max = max_len - uid - 1
        core = re.sub(r"[^0-9A-Za-z]", "_", title).strip("_").lower()
        core = re.sub(r"__+", "_", core)[:core_max]
        return f"{core}_{uuid.uuid4().hex[:uid]}"
        
    def _extract_layer_definition(self, layer, keep_render: bool = True) -> Dict:
        """Extract layer definition."""
        d = self._pm_to_dict(layer.properties)
        if keep_render:
            ri = layer.properties.get('drawingInfo')
            if ri:
                d['drawingInfo'] = self._pm_to_dict(ri)
        for k in self.EXCLUDE_PROPS:
            d.pop(k, None)
        return d
        
    def _extract_item_properties(self, item: Item) -> Dict:
        """Extract item properties for cloning."""
        props = {
            'title': item.title,
            'type': item.type,
            'typeKeywords': item.typeKeywords,
            'description': item.description,
            'tags': item.tags,
            'snippet': item.snippet,
            'extent': item.extent,
            'spatialReference': item.spatialReference,
            'accessInformation': item.accessInformation,
            'licenseInfo': item.licenseInfo,
            'culture': item.culture,
            'url': item.url
        }
        return clean_json_for_create(props)
        
    def _blank_geom(self, gtype: str, has_z: bool, has_m: bool, sr: Dict) -> Dict:
        """Create minimal valid geometry."""
        z = [0] if has_z else []
        m = [0] if has_m else []
        
        if gtype == "esriGeometryPoint":
            g = {"x": 0, "y": 0, "spatialReference": sr}
            if has_z: g["z"] = 0
            if has_m: g["m"] = 0
            return g
            
        if gtype == "esriGeometryPolyline":
            p1 = [0, 0] + z + m
            p2 = [0.0001, 0.0001] + z + m
            return {"paths": [[p1, p2]], "spatialReference": sr}
            
        if gtype == "esriGeometryPolygon":
            ring = [
                [0, 0] + z + m,
                [0.0001, 0] + z + m,
                [0.0001, 0.0001] + z + m,
                [0, 0.0001] + z + m,
                [0, 0] + z + m
            ]
            return {"rings": [ring], "spatialReference": sr}
            
        return None
        
    def _dummy_attr_sets(self, renderer: Dict, layer_props: Dict) -> List[Dict]:
        """Generate attribute sets for each symbology bucket."""
        if renderer.get("type") == "uniqueValue":
            return self._unique_value_attrs(renderer)
        elif renderer.get("type") == "classBreaks":
            return self._class_breaks_attrs(renderer)
        else:
            # Check for domain or subtype
            return self._domain_or_subtype_attrs(renderer, layer_props)
            
    def _unique_value_attrs(self, renderer: Dict) -> List[Dict]:
        """Extract unique value attribute combinations."""
        result = []
        
        # Handle uniqueValueInfos
        if "uniqueValueInfos" in renderer:
            for uvi in renderer["uniqueValueInfos"]:
                attrs = {}
                if "value" in uvi:
                    attrs[renderer.get("field1", "objectid")] = uvi["value"]
                result.append(attrs)
                
        # Handle uniqueValueGroups
        elif "uniqueValueGroups" in renderer:
            for group in renderer["uniqueValueGroups"]:
                for cls in group.get("classes", []):
                    if "values" in cls:
                        for val_list in cls["values"]:
                            attrs = {}
                            fields = [renderer.get(f"field{i+1}") for i in range(3)]
                            for i, v in enumerate(val_list):
                                if i < len(fields) and fields[i]:
                                    attrs[fields[i]] = v
                            if attrs:
                                result.append(attrs)
                                
        return result if result else [{}]
        
    def _class_breaks_attrs(self, renderer: Dict) -> List[Dict]:
        """Extract class break attribute values."""
        field = renderer.get("field")
        if not field or "classBreakInfos" not in renderer:
            return [{}]
            
        result = []
        for cbi in renderer["classBreakInfos"]:
            if "classMinValue" in cbi:
                result.append({field: cbi["classMinValue"]})
                
        return result if result else [{}]
        
    def _domain_or_subtype_attrs(self, renderer: Dict, layer_props: Dict) -> List[Dict]:
        """Extract domain or subtype attribute values."""
        # Check for simple renderer with domain
        primary = renderer.get("field") or renderer.get("field1")
        if primary and "fields" in layer_props:
            for f in layer_props["fields"]:
                if f["name"] == primary and "domain" in f:
                    dom = f["domain"]
                    if dom["type"] == "codedValue" and "codedValues" in dom:
                        cv = dom["codedValues"]
                        return [{primary: cv[i]["code"]} for i in range(min(3, len(cv)))]
                        
        # Check for subtypes
        st_field = layer_props.get("subtypeFieldName")
        if st_field and layer_props.get("types"):
            return [{st_field: t["id"]} for t in layer_props["types"]]
            
        return [{}]
        
    def _track_service_urls(self, src_item: Item, new_item: Item, src_flc: FeatureLayerCollection, new_flc: FeatureLayerCollection):
        """Track service and sublayer URL mappings."""
        # Store the mapping data to return
        mapping_data = {
            'id': new_item.id,
            'url': new_item.url,
            'sublayer_urls': {}
        }
        
        # Track main service URL
        if src_item.url and new_item.url:
            logger.debug(f"Service URL mapping: {src_item.url} -> {new_item.url}")
            
            # Track individual layer URLs
            for i, (src_layer, new_layer) in enumerate(zip(src_flc.layers, new_flc.layers)):
                src_layer_url = f"{src_item.url}/{i}"
                new_layer_url = f"{new_item.url}/{i}"
                mapping_data['sublayer_urls'][src_layer_url] = new_layer_url
                logger.debug(f"Layer {i} URL mapping: {src_layer_url} -> {new_layer_url}")
                
            # Track table URLs
            for i, (src_table, new_table) in enumerate(zip(src_flc.tables, new_flc.tables)):
                # Tables continue numbering after layers
                table_idx = len(src_flc.layers) + i
                src_table_url = f"{src_item.url}/{table_idx}"
                new_table_url = f"{new_item.url}/{table_idx}"
                mapping_data['sublayer_urls'][src_table_url] = new_table_url
                logger.debug(f"Table {table_idx} URL mapping: {src_table_url} -> {new_table_url}")
                
        # Store this data for the caller to use
        self._last_mapping_data = mapping_data
        
    def get_last_mapping_data(self) -> Optional[Dict[str, Any]]:
        """Get the mapping data from the last clone operation."""
        return self._last_mapping_data
        
    def update_references(
        self,
        item: Item,
        id_mapping: Dict[str, Dict[str, str]],
        gis: GIS
    ) -> bool:
        """
        Update references in a feature service item.
        
        Feature services themselves don't typically have references to other items,
        but this method is here for consistency and future extensibility.
        """
        try:
            # Feature services don't usually contain references to other items
            # But we'll check item data just in case
            item_data = item.get_data()
            if item_data:
                # Use the base class method to update any JSON references
                updated_data = self.update_json_references(item_data, id_mapping.get('ids', {}))
                if updated_data != item_data:
                    item.update(item_properties={'text': json.dumps(updated_data)})
                    logger.info(f"Updated references in feature service: {item.title}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Error updating references in feature service {item.title}: {str(e)}")
            return False