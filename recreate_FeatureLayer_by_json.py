"""
Hosted Feature-Service  •  Schema & Symbology Cloner  (v5)
──────────────────────────────────────────────────────────
 • Copies schema (layers, tables, domains, relationships)
 • Copies BOTH service renderers AND item visualization
 • Creates dummy features for each symbol in visualization
"""

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from arcgis._impl.common._mixins import PropertyMap
import re, uuid, math, json
from datetime import datetime

# ── EDIT THESE ────────────────────────────────────────────────────────────────
USERNAME        = "xxx"  # your ArcGIS Online username
PASSWORD        = "xxx"
ITEM_ID         = "59ad9d29b3c444c888e921db6ea7f092"
SEED_DUMMIES    = False        # create placeholders for each renderer bucket?
DELETE_DUMMIES  = True       # wipe them after pushing symbology?
DEBUG_MODE      = False       # print debug info?
# ──────────────────────────────────────────────────────────────────────────────


# -----------------------------------------------------------------------------#
# Helpers                                                                       #
# -----------------------------------------------------------------------------#
def _pm_to_dict(o):
    if isinstance(o, PropertyMap):
        o = dict(o)
    if isinstance(o, dict):
        return {k: _pm_to_dict(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_pm_to_dict(i) for i in o]
    return o


def _safe_name(title, uid=8, max_len=30):
    core_max = max_len - uid - 1
    core = re.sub(r"[^0-9A-Za-z]", "_", title).strip("_").lower()
    core = re.sub(r"__+", "_", core)[:core_max]
    return f"{core}_{uuid.uuid4().hex[:uid]}"


_EXCLUDE_PROPS = {
    'currentVersion','serviceItemId','capabilities','maxRecordCount',
    'supportsAppend','supportedQueryFormats','isDataVersioned',
    'allowGeometryUpdates','supportsCalculate','supportsValidateSql',
    'advancedQueryCapabilities','supportsCoordinatesQuantization',
    'supportsApplyEditsWithGlobalIds','supportsMultiScaleGeometry',
    'syncEnabled','syncCapabilities','editorTrackingInfo',
    'changeTrackingInfo'
}


def _layer_def(lyr, keep_render=True):
    d = _pm_to_dict(lyr.properties)
    if keep_render:
        ri = lyr.properties.get('drawingInfo')
        if ri:
            d['drawingInfo'] = _pm_to_dict(ri)
    for k in _EXCLUDE_PROPS:
        d.pop(k, None)
    return d


def _blank_geom(gtype, has_z, has_m, sr):
    """Return the smallest valid geometry (with Z/M if required)."""
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
            [0, 0]           + z + m,
            [0.0001, 0]      + z + m,
            [0.0001, 0.0001] + z + m,
            [0, 0.0001]      + z + m,
            [0, 0]           + z + m
        ]
        return {"rings": [ring], "spatialReference": sr}

    return None


def _dummy_attr_sets(renderer, layer_props, debug=False):
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
        print(f"\n[DEBUG] Renderer type: {renderer.get('type')}")

    # ---------- UNIQUE VALUES ----------------------------------------------
    if renderer["type"] == "uniqueValue":
        field1 = renderer.get("field1") or renderer.get("field")
        if debug:
            print(f"[DEBUG] Unique value field: {field1}")

        # First try uniqueValueInfos (primary list used by JS API, REST admin, ArcPy)
        infos = renderer.get("uniqueValueInfos", [])
        
        # If empty, try uniqueValueGroups/classes (Map Viewer format)
        if not infos and renderer.get("uniqueValueGroups"):
            for grp in renderer["uniqueValueGroups"]:
                infos.extend(grp.get("classes", []))
        
        if debug:
            print(f"[DEBUG] Found {len(infos)} unique value infos")

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
                    print(f"[DEBUG] UniqueValue {i}: fields={field1},{field2},{field3}, value={value}, label={info.get('label')}")
                
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
                print(f"[DEBUG] Returning {len(out)} unique value attribute sets")
                if field2:
                    print(f"[DEBUG] Multi-field renderer with fields: {field1}, {field2}" + (f", {field3}" if field3 else ""))
            return out
        
        elif infos:  # Arcade expression (no field)
            if debug:
                print(f"[DEBUG] No field found, returning {len(infos)} empty dicts (Arcade renderer)")
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
                print(f"[DEBUG] Returning {len(result)} class break attribute sets")
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
                    print(f"[DEBUG] Returning {len(result)} coded-value domain attribute sets")
                return result

    # ---------- SUBTYPES ----------------------------------------------------
    st_field = layer_props.get("subtypeFieldName")
    if st_field and layer_props.get("types"):
        result = [{st_field: t["id"]} for t in layer_props["types"]]
        if debug:
            print(f"[DEBUG] Returning {len(result)} subtype attribute sets")
        return result

    # ---------- FALLBACK ----------------------------------------------------
    if debug:
        print(f"[DEBUG] FALLBACK: Returning single empty dict")
    return [{}]


# -----------------------------------------------------------------------------#
# Main                                                                          #
# -----------------------------------------------------------------------------#
def clone_schema(username, password, item_id,
                 seed_dummies=True, delete_dummies=False, debug=False):

    gis = GIS("https://www.arcgis.com", username, password)
    print(f"✓ Signed in as {gis.users.me.username}")

    src_item = gis.content.get(item_id)
    if not src_item or src_item.type.lower() != "feature service":
        raise ValueError("Source item must be a hosted Feature Service")

    src_flc = FeatureLayerCollection.fromitem(src_item)
    print(f"Cloning schema from: {src_item.title}")
    
    # GET ITEM VISUALIZATION DATA
    print("\n• Getting item visualization data...")
    item_data = None
    try:
        item_data = src_item.get_data()
        if debug and item_data:
            print("[DEBUG] Item has visualization data")
            if "layers" in item_data:
                print(f"[DEBUG] Visualization has {len(item_data['layers'])} layer overrides")
    except:
        print("  No item visualization data found")

    # Build definitions
    layer_defs = [_layer_def(l, keep_render=True) for l in src_flc.layers]
    table_defs = [_layer_def(t, keep_render=False) for t in src_flc.tables]
    relationships = _pm_to_dict(src_flc.properties).get("relationships", [])

    # Create empty service
    new_name = _safe_name(src_item.title)
    params = {
        "name": new_name,
        "serviceDescription": "",
        "spatialReference": _pm_to_dict(src_flc.properties.spatialReference),
        "capabilities": "Query",
        "hasStaticData": False
    }
    new_item = gis.content.create_service(
        name=new_name, service_type="featureService",
        create_params=params,
        tags=src_item.tags or ["schema copy"],
        snippet=f"Schema copy of {src_item.title}"
    )
    new_flc = FeatureLayerCollection.fromitem(new_item)
    print("✓ Empty service created")

    # Push schema
    payload = {"layers": layer_defs, "tables": table_defs}
    if relationships:
        payload["relationships"] = relationships
    new_flc.manager.add_to_definition(payload)
    print("✓ Schema posted")

    # ------------------------------------------------------------------#
    # Seed dummy features so renderer will stick                         #
    # ------------------------------------------------------------------#
    if seed_dummies:
        print("\n• Seeding dummy features so renderer can stick…")
        
        # Create lookup for visualization data by layer index
        viz_layers = {}
        if item_data and "layers" in item_data:
            for viz_layer in item_data["layers"]:
                if "id" in viz_layer:
                    viz_layers[viz_layer["id"]] = viz_layer
        
        for idx, (src_lyr, tgt_lyr) in enumerate(zip(src_flc.layers, new_flc.layers)):
            gtype = tgt_lyr.properties.get("geometryType")
            if not gtype:
                continue                                  # table / annotation

            if debug:
                print(f"\n[DEBUG] Processing layer {idx}: {src_lyr.properties.name}")

            sr     = _pm_to_dict(tgt_lyr.properties.spatialReference) or {"wkid": 4326}
            has_z  = bool(getattr(tgt_lyr.properties, "hasZ", False))
            has_m  = bool(getattr(tgt_lyr.properties, "hasM", False))

            # Check for visualization override first
            renderer_dict = None
            if idx in viz_layers and "layerDefinition" in viz_layers[idx]:
                viz_def = viz_layers[idx]["layerDefinition"]
                if "drawingInfo" in viz_def and "renderer" in viz_def["drawingInfo"]:
                    renderer_dict = viz_def["drawingInfo"]["renderer"]
                    if debug:
                        print(f"[DEBUG] Using ITEM VISUALIZATION renderer")
            
            # Fall back to service renderer if no visualization
            if renderer_dict is None:
                renderer_dict = _pm_to_dict(src_lyr.properties.drawingInfo.renderer)
                if debug:
                    print(f"[DEBUG] Using SERVICE renderer")
            
            if debug:
                print(f"[DEBUG] Renderer structure preview:")
                print(json.dumps(renderer_dict, indent=2)[:500] + "...")
            
            layer_props = _pm_to_dict(src_lyr.properties)
            attr_sets = _dummy_attr_sets(renderer_dict, layer_props, debug=debug)

            if debug:
                print(f"[DEBUG] Generated {len(attr_sets)} attribute sets:")
                for i, attrs in enumerate(attr_sets):
                    print(f"  [{i}] {attrs}")

            # Create dummy features
            dummy_feats = []
            for attrs in attr_sets:
                dummy_feat = {
                    "geometry": _blank_geom(gtype, has_z, has_m, sr),
                    "attributes": attrs
                }
                dummy_feats.append(dummy_feat)
            
            if debug:
                print(f"[DEBUG] Attempting to add {len(dummy_feats)} features...")

            # Add features
            res = tgt_lyr.edit_features(adds=dummy_feats)
            
            # Check results
            if res and "addResults" in res:
                success_count = sum(1 for r in res["addResults"] if r.get("success", False))
                if success_count != len(dummy_feats):
                    print(f"  ⚠️  Only {success_count}/{len(dummy_feats)} features added successfully")
                else:
                    print(f"  ✓ Seeded {success_count} feature(s) in '{tgt_lyr.properties.name}'")
            else:
                raise RuntimeError(f"Failed to seed '{tgt_lyr.properties.name}'")

        print("\n✓ All dummy features added")

    # ------------------------------------------------------------------#
    # Push drawingInfo to service AND item visualization                 #
    # ------------------------------------------------------------------#
    print("\n• Pushing symbology...")
    
    # First update service definitions
    for src_lyr in src_flc.layers:
        tgt_lyr = next(l for l in new_flc.layers
                       if l.properties.name == src_lyr.properties.name)
        tgt_lyr.manager.update_definition(
            {"drawingInfo": _pm_to_dict(src_lyr.properties.drawingInfo)}
        )
    print("✓ Service symbology pushed")
    
    # Then update item visualization if it exists
    if item_data:
        try:
            new_item.update(data=item_data)
            print("✓ Item visualization pushed")
        except Exception as e:
            print(f"  ⚠️  Could not update item visualization: {e}")

    # ------------------------------------------------------------------#
    # Delete dummy features if requested                                 #
    # ------------------------------------------------------------------#
    if seed_dummies and delete_dummies:
        print("\n• Removing dummy features …")
        for lyr in new_flc.layers:
            lyr.delete_features(where="1=1")
        print("✓ Dummy features removed – clone stays empty")

    # Rename item
    title = f"{src_item.title}_schemaCopy_{datetime.now():%Y%m%d_%H%M%S}"
    new_item.update(item_properties={"title": title})
    print(f"\nClone ready → {new_item.homepage}")
    return new_item


# -----------------------------------------------------------------------------#
if __name__ == "__main__":
    try:
        clone_schema(USERNAME, PASSWORD, ITEM_ID,
                     seed_dummies=SEED_DUMMIES,
                     delete_dummies=DELETE_DUMMIES,
                     debug=DEBUG_MODE)
    except Exception as e:
        print(f"Error: {e}")