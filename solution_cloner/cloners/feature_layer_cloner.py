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


class ArcGISEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle ArcGIS objects."""
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            try:
                return dict(obj)
            except:
                return str(obj)
        return super().default(obj)


class FeatureLayerCloner(BaseCloner):
    """Clones feature layers and feature services."""
    
    def __init__(self):
        """Initialize the feature layer cloner."""
        super().__init__()
        self._last_mapping_data = None
    
    # Properties to exclude when copying layer definitions
    # These are server-managed properties that should not be included in add_to_definition
    # This list matches exactly what's in the working recreate_FeatureLayer_by_json.py script
    EXCLUDE_PROPS = {
        'currentVersion','serviceItemId','capabilities','maxRecordCount',
        'supportsAppend','supportedQueryFormats','isDataVersioned',
        'allowGeometryUpdates','supportsCalculate','supportsValidateSql',
        'advancedQueryCapabilities','supportsCoordinatesQuantization',
        'supportsApplyEditsWithGlobalIds','supportsMultiScaleGeometry',
        'syncEnabled','syncCapabilities','editorTrackingInfo',
        'changeTrackingInfo', 'id', 'hasViews', 'sourceSchemaChangesAllowed',
        'relationships', 'editingInfo', 'hasContingentValuesDefinition',
        'supportsASyncCalculate', 'supportsTruncate', 'supportsAttachmentsByUploadId',
        'supportsAttachmentsResizing', 'supportsRollbackOnFailureParameter',
        'supportsStatistics', 'supportsExceedsLimitStatistics', 'supportsAdvancedQueries',
        'supportsLayerOverrides', 'supportsTilesAndBasicQueriesMode',
        'supportsFieldDescriptionProperty', 'supportsQuantizationEditMode',
        'supportsColumnStoreIndex', 'supportsReturningQueryGeometry',
        'enableNullGeometry', 'parentLayer', 'subLayers', 'timeInfo',
        'hasGeometryProperties', 'advancedEditingCapabilities', 'lastEditDate'
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
            
            # Get source FLC first
            src_flc = FeatureLayerCollection.fromitem(src_item)
            
            # Extract definition
            definition = self.extract_definition(source_item['id'], source_gis)
            
            # Save definition for debugging
            try:
                save_json(
                    definition,
                    Path("json_files") / f"feature_service_definition_{source_item['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
            except:
                pass
            
            # Create new service
            new_item = self._create_empty_service(
                src_item, src_flc, definition, dest_gis, dest_folder
            )
            
            if not new_item:
                return None
                
            new_flc = FeatureLayerCollection.fromitem(new_item)
            
            # Apply schema using the same pattern as the working script
            try:
                # Build layer definitions directly (matching working script line 249)
                layer_defs = []
                for l in src_flc.layers:
                    d = self._pm_to_dict(l.properties)
                    # Keep renderer
                    ri = l.properties.get('drawingInfo')
                    if ri:
                        d['drawingInfo'] = self._pm_to_dict(ri)
                    # Remove excluded props
                    for k in self.EXCLUDE_PROPS:
                        d.pop(k, None)
                    layer_defs.append(d)
                    
                # Build table definitions
                table_defs = []
                for t in src_flc.tables:
                    d = self._pm_to_dict(t.properties)
                    # CRITICAL: Remove drawingInfo from tables - tables cannot have renderers
                    d.pop('drawingInfo', None)
                    # Remove other excluded properties
                    for k in self.EXCLUDE_PROPS:
                        d.pop(k, None)
                    table_defs.append(d)
                    
                # Get relationships
                relationships = self._pm_to_dict(src_flc.properties).get("relationships", [])
                
                # Build payload
                payload = {"layers": layer_defs, "tables": table_defs}
                if relationships:
                    payload["relationships"] = relationships
                    
                # Log and save payload for debugging
                logger.info(f"Payload structure: layers={len(layer_defs)}, tables={len(table_defs)}, relationships={len(relationships)}")
                
                # Save payload to JSON for inspection
                try:
                    payload_path = Path("json_files") / f"add_to_definition_payload_{source_item['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    save_json(payload, payload_path, add_timestamp=False)
                    logger.info(f"Saved payload to: {payload_path}")
                    
                    # Test JSON serialization to ensure no issues
                    json_test = json.dumps(payload, cls=ArcGISEncoder)
                    logger.debug(f"Payload JSON serialization test passed, size: {len(json_test)} bytes")
                except Exception as e:
                    logger.warning(f"Could not save/serialize payload: {str(e)}")
                    # This might indicate a problem with the payload structure
                    logger.error("Payload serialization failed - this may cause add_to_definition to fail")
                
                # Log first layer definition for debugging
                if layer_defs:
                    logger.debug(f"First layer definition keys: {list(layer_defs[0].keys())}")
                    if 'drawingInfo' in layer_defs[0]:
                        logger.debug(f"First layer has drawingInfo with renderer type: {layer_defs[0]['drawingInfo'].get('renderer', {}).get('type', 'unknown')}")
                
                # Apply
                logger.info("Applying schema definition with add_to_definition()...")
                try:
                    new_flc.manager.add_to_definition(payload)
                    logger.info("Applied schema definition")
                except Exception as add_def_error:
                    logger.warning(f"Failed to add complete definition: {str(add_def_error)}")
                    # Try without relationships first
                    if relationships:
                        logger.info("Retrying without relationships...")
                        payload_no_rel = {"layers": layer_defs, "tables": table_defs}
                        new_flc.manager.add_to_definition(payload_no_rel)
                        logger.info("Schema posted without relationships")
                        # Add relationships separately
                        logger.info("Adding relationships separately...")
                        new_flc.manager.add_to_definition({"relationships": relationships})
                        logger.info("Relationships added")
                    else:
                        raise
            except Exception as e:
                logger.error(f"Error applying schema: {str(e)}")
                # Try to get more details about the error
                if hasattr(e, 'args') and len(e.args) > 0:
                    logger.error(f"Error details: {e.args}")
                # Log the problematic definitions
                if layer_defs:
                    logger.error(f"Number of layer definitions that failed: {len(layer_defs)}")
                    for i, layer_def in enumerate(layer_defs):
                        if 'name' in layer_def:
                            logger.error(f"  Layer {i}: {layer_def['name']}")
                raise
            
            # Handle data and symbology
            if create_dummy_features:
                self._create_dummy_features(src_flc, new_flc, definition)
                
            if clone_data:
                self._copy_data(src_flc, new_flc)
            elif create_dummy_features and kwargs.get('delete_dummies', True):
                # Delete dummy features if requested (default behavior from working script)
                logger.info("Removing dummy features...")
                for lyr in new_flc.layers:
                    lyr.delete_features(where="1=1")
                logger.info("Dummy features removed - clone stays empty")
            
            # Apply symbology - first update service definitions (matching working script lines 362-369)
            logger.info("Pushing symbology to service...")
            for src_lyr in src_flc.layers:
                # Find matching target layer by name
                tgt_lyr = next((l for l in new_flc.layers 
                               if l.properties.name == src_lyr.properties.name), None)
                if tgt_lyr:
                    tgt_lyr.manager.update_definition(
                        {"drawingInfo": self._pm_to_dict(src_lyr.properties.drawingInfo)}
                    )
            logger.info("Service symbology pushed")
            
            # Apply item visualization
            self._apply_item_visualization(src_item, new_item, definition)
            
            # Update the title to match the source item
            # The service URL will remain unique with the safe name
            new_item.update(item_properties={"title": src_item.title})
            
            logger.info(f"Successfully cloned: {src_item.title} -> {new_item.id}")
            
            # Track URL mappings
            if hasattr(src_item, 'url') and hasattr(new_item, 'url'):
                self._track_service_urls(src_item, new_item, src_flc, new_flc)
            
            # Store layer ID mappings for views to reference
            self._last_layer_mappings = self._create_layer_id_mappings(src_flc, new_flc)
            
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
            new_item.update(data=definition['item_data'])
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
        
        # Log original keys for debugging
        original_keys = set(d.keys())
        logger.debug(f"Layer '{d.get('name', 'unknown')}' original properties: {original_keys}")
        
        if keep_render:
            ri = layer.properties.get('drawingInfo')
            if ri:
                d['drawingInfo'] = self._pm_to_dict(ri)
                # Log renderer details
                if 'drawingInfo' in d and 'renderer' in d['drawingInfo']:
                    renderer_type = d['drawingInfo']['renderer'].get('type', 'unknown')
                    logger.debug(f"Layer '{d.get('name', 'unknown')}' has renderer type: {renderer_type}")
                
        # Remove excluded properties
        removed_keys = []
        for k in self.EXCLUDE_PROPS:
            if k in d:
                d.pop(k)
                removed_keys.append(k)
                
        logger.debug(f"Layer '{d.get('name', 'unknown')}' removed properties: {removed_keys}")
        logger.debug(f"Layer '{d.get('name', 'unknown')}' remaining properties: {set(d.keys())}")
        
        # Check for potential issues
        if 'fields' in d and isinstance(d['fields'], list):
            logger.debug(f"Layer '{d.get('name', 'unknown')}' has {len(d['fields'])} fields")
        
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
        
    def _dummy_attr_sets(self, renderer: Dict, layer_props: Dict, debug: bool = False) -> List[Dict]:
        """
        Return a list of {field:value} dicts that cover every symbology bucket.
        Works with:
          • unique values   (uniqueValueInfos OR uniqueValueGroups/classes)
          • class breaks
          • coded-value domains
          • subtypes
          • Arcade / field-less renderers  → empty dicts but one per bucket
        """
        
        if debug:
            logger.debug(f"Renderer type: {renderer.get('type')}")

        # ---------- UNIQUE VALUES ----------------------------------------------
        if renderer["type"] == "uniqueValue":
            field1 = renderer.get("field1") or renderer.get("field")
            if debug:
                logger.debug(f"Unique value field: {field1}")

            # First try uniqueValueInfos (primary list used by JS API, REST admin, ArcPy)
            infos = renderer.get("uniqueValueInfos", [])
            
            # If empty, try uniqueValueGroups/classes (Map Viewer format)
            if not infos and renderer.get("uniqueValueGroups"):
                for grp in renderer["uniqueValueGroups"]:
                    infos.extend(grp.get("classes", []))
            
            if debug:
                logger.debug(f"Found {len(infos)} unique value infos")

            if infos and field1:
                out = []
                # Check if we have a multi-field renderer
                field2 = renderer.get("field2")
                field3 = renderer.get("field3")
                fieldDelimiter = renderer.get("fieldDelimiter", ",")
                
                for i, info in enumerate(infos):
                    # Try different value formats
                    value = None
                    
                    # Format 1: Simple value field (could be comma-separated for multi-field)
                    if "value" in info:
                        value = info["value"]
                    # Format 2: Values array (from uniqueValueGroups)
                    elif "values" in info and info["values"]:
                        # For multi-field from uniqueValueGroups, values are like [["0", "1"]]
                        if isinstance(info["values"][0], list):
                            # Join with fieldDelimiter to match the "value" format
                            value = fieldDelimiter.join(str(v) for v in info["values"][0])
                        else:
                            value = info["values"][0]
                    
                    if debug and i < 3:  # Show first 3 for debugging
                        logger.debug(f"UniqueValue {i}: fields={field1},{field2},{field3}, value={value}, label={info.get('label')}")
                    
                    if value is not None:
                        # Handle multi-field renderer
                        if field2 and isinstance(value, str) and fieldDelimiter in value:
                            values = value.split(fieldDelimiter)
                            attrs = {field1: values[0]}
                            if len(values) > 1 and field2:
                                attrs[field2] = values[1]
                            if len(values) > 2 and field3:
                                attrs[field3] = values[2]
                            out.append(attrs)
                        else:
                            # Single field renderer
                            out.append({field1: value})
                
                if debug:
                    logger.debug(f"Returning {len(out)} unique value attribute sets")
                    if field2:
                        logger.debug(f"Multi-field renderer with fields: {field1}, {field2}" + (f", {field3}" if field3 else ""))
                return out
            
            elif infos:  # Arcade expression (no field)
                if debug:
                    logger.debug(f"No field found, returning {len(infos)} empty dicts (Arcade renderer)")
                return [{}] * len(infos)

        # ---------- CLASS BREAKS -----------------------------------------------
        if renderer["type"] == "classBreaks":
            fld   = renderer.get("field")
            infos = renderer.get("classBreakInfos") or []
            if infos and fld:
                def mid(cb):
                    lo = cb.get("classMinValue", cb.get("minValue", 0))
                    hi = cb.get("classMaxValue", cb.get("maxValue", lo))
                    return (lo + hi) / 2.0 if hi != lo else lo
                result = [{fld: mid(cb)} for cb in infos]
                if debug:
                    logger.debug(f"Returning {len(result)} class break attribute sets")
                return result
            if infos:
                return [{}] * len(infos)

        # ---------- CODED-VALUE DOMAIN -----------------------------------------
        primary = renderer.get("field1") or renderer.get("field")
        if primary:
            for fld_def in layer_props["fields"]:
                dom = fld_def.get("domain")
                if fld_def["name"] == primary and dom and dom.get("type") == "codedValue":
                    cv = dom["codedValues"]
                    result = [{primary: cv[i]["code"]} for i in range(min(3, len(cv)))]
                    if debug:
                        logger.debug(f"Returning {len(result)} coded-value domain attribute sets")
                    return result

        # ---------- SUBTYPES ----------------------------------------------------
        st_field = layer_props.get("subtypeFieldName")
        if st_field and layer_props.get("types"):
            result = [{st_field: t["id"]} for t in layer_props["types"]]
            if debug:
                logger.debug(f"Returning {len(result)} subtype attribute sets")
            return result

        # ---------- FALLBACK ----------------------------------------------------
        if debug:
            logger.debug("FALLBACK: Returning single empty dict")
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
        
    def _create_layer_id_mappings(self, src_flc: FeatureLayerCollection, new_flc: FeatureLayerCollection) -> Dict[str, str]:
        """Create mappings between source and destination layer IDs."""
        layer_mappings = {}
        
        # Map layers by matching names
        for src_layer in src_flc.layers:
            src_layer_id = src_layer.properties.get('id')
            src_layer_name = src_layer.properties.get('name')
            
            # Find matching layer in new service by name
            for new_layer in new_flc.layers:
                if new_layer.properties.get('name') == src_layer_name:
                    new_layer_id = new_layer.properties.get('id')
                    if src_layer_id and new_layer_id:
                        layer_mappings[src_layer_id] = new_layer_id
                        logger.debug(f"Layer ID mapping: {src_layer_id} -> {new_layer_id} ({src_layer_name})")
                    break
                    
        # Map tables similarly
        for src_table in src_flc.tables:
            src_table_id = src_table.properties.get('id')
            src_table_name = src_table.properties.get('name')
            
            for new_table in new_flc.tables:
                if new_table.properties.get('name') == src_table_name:
                    new_table_id = new_table.properties.get('id')
                    if src_table_id and new_table_id:
                        layer_mappings[src_table_id] = new_table_id
                        logger.debug(f"Table ID mapping: {src_table_id} -> {new_table_id} ({src_table_name})")
                    break
                    
        return layer_mappings
        
    def get_layer_id_mappings(self) -> Dict[str, str]:
        """Get the last created layer ID mappings."""
        return getattr(self, '_last_layer_mappings', {})
        
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
            if item_data and isinstance(item_data, dict):
                # Use the base class method to update any JSON references
                updated_data = self.update_json_references(item_data, id_mapping.get('ids', {}))
                if updated_data != item_data:
                    item.update(data=updated_data)
                    logger.info(f"Updated references in feature service: {item.title}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Error updating references in feature service {item.title}: {str(e)}")
            return False