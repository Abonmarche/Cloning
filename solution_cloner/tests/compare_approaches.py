#!/usr/bin/env python
"""
Compare the working script approach with the module approach
"""
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from arcgis._impl.common._mixins import PropertyMap
import json
import sys

# From working script
def working_pm_to_dict(o):
    if isinstance(o, PropertyMap):
        o = dict(o)
    if isinstance(o, dict):
        return {k: working_pm_to_dict(v) for k, v in o.items()}
    if isinstance(o, list):
        return [working_pm_to_dict(i) for i in o]
    return o

# From module (before fix)
def module_pm_to_dict_old(o):
    if isinstance(o, PropertyMap):
        o = dict(o)
    if isinstance(o, dict):
        return {k: module_pm_to_dict_old(v) for k, v in o.items()}
    if isinstance(o, list):
        return [module_pm_to_dict_old(i) for i in o]
    # This is the problematic part
    if hasattr(o, '__dict__') and not isinstance(o, (str, int, float, bool, type(None))):
        try:
            return dict(o)
        except:
            return str(o)
    return o

# Exclude props from working script
EXCLUDE_PROPS = {
    'currentVersion','serviceItemId','capabilities','maxRecordCount',
    'supportsAppend','supportedQueryFormats','isDataVersioned',
    'allowGeometryUpdates','supportsCalculate','supportsValidateSql',
    'advancedQueryCapabilities','supportsCoordinatesQuantization',
    'supportsApplyEditsWithGlobalIds','supportsMultiScaleGeometry',
    'syncEnabled','syncCapabilities','editorTrackingInfo',
    'changeTrackingInfo'
}

def compare_definitions(item_id, username, password):
    """Compare how both approaches build definitions"""
    
    print(f"Comparing approaches for item: {item_id}")
    print("=" * 80)
    
    # Connect
    gis = GIS("https://www.arcgis.com", username, password)
    item = gis.content.get(item_id)
    if not item:
        print(f"Item not found: {item_id}")
        return
        
    print(f"Item: {item.title} ({item.type})")
    
    # Get FLC
    flc = FeatureLayerCollection.fromitem(item)
    
    # Test with first layer
    if flc.layers:
        layer = flc.layers[0]
        print(f"\nTesting with layer: {layer.properties.name}")
        
        # Working approach
        print("\n1. Working Script Approach:")
        working_def = working_pm_to_dict(layer.properties)
        ri = layer.properties.get('drawingInfo')
        if ri:
            working_def['drawingInfo'] = working_pm_to_dict(ri)
        for k in EXCLUDE_PROPS:
            working_def.pop(k, None)
            
        # Module approach (old)
        print("\n2. Module Approach (old with __dict__ handling):")
        module_def_old = module_pm_to_dict_old(layer.properties)
        ri = layer.properties.get('drawingInfo')
        if ri:
            module_def_old['drawingInfo'] = module_pm_to_dict_old(ri)
        for k in EXCLUDE_PROPS:
            module_def_old.pop(k, None)
        
        # Compare
        print("\n3. Comparison:")
        
        # Check keys
        working_keys = set(working_def.keys())
        module_keys = set(module_def_old.keys())
        
        if working_keys == module_keys:
            print("   ✓ Same keys in both definitions")
        else:
            print("   ✗ Different keys:")
            only_working = working_keys - module_keys
            only_module = module_keys - working_keys
            if only_working:
                print(f"     Only in working: {only_working}")
            if only_module:
                print(f"     Only in module: {only_module}")
        
        # Check for differences in values
        differences = []
        for key in working_keys & module_keys:
            w_val = working_def[key]
            m_val = module_def_old[key]
            
            # Compare types
            if type(w_val) != type(m_val):
                differences.append(f"{key}: type mismatch - working={type(w_val).__name__}, module={type(m_val).__name__}")
            elif isinstance(w_val, dict) and isinstance(m_val, dict):
                # Recursively check dicts
                if json.dumps(w_val, sort_keys=True) != json.dumps(m_val, sort_keys=True):
                    differences.append(f"{key}: dict contents differ")
            elif isinstance(w_val, list) and isinstance(m_val, list):
                # Check lists
                if len(w_val) != len(m_val):
                    differences.append(f"{key}: list length differs - working={len(w_val)}, module={len(m_val)}")
            elif w_val != m_val:
                # Check if one is a string representation of an object
                if isinstance(m_val, str) and not isinstance(w_val, str):
                    differences.append(f"{key}: module converted to string - '{m_val[:50]}...'")
                else:
                    differences.append(f"{key}: values differ")
        
        if differences:
            print("   ✗ Value differences found:")
            for diff in differences[:10]:  # Show first 10
                print(f"     - {diff}")
            if len(differences) > 10:
                print(f"     ... and {len(differences) - 10} more differences")
        else:
            print("   ✓ All values match")
        
        # Save both for detailed inspection
        with open('working_layer_def.json', 'w') as f:
            json.dump(working_def, f, indent=2)
        print("\n   Saved working definition to: working_layer_def.json")
        
        try:
            with open('module_layer_def_old.json', 'w') as f:
                json.dump(module_def_old, f, indent=2)
            print("   Saved module definition to: module_layer_def_old.json")
        except Exception as e:
            print(f"   Could not save module definition: {str(e)}")
            print("   This suggests the module approach created non-serializable objects!")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python compare_approaches.py <item_id> <username> <password>")
    else:
        compare_definitions(sys.argv[1], sys.argv[2], sys.argv[3])