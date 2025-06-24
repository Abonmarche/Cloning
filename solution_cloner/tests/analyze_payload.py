#!/usr/bin/env python
"""
Analyze payload JSON files to identify potential issues
"""
import json
import sys
from pathlib import Path
import glob

def analyze_payload(payload_file):
    """Analyze a payload JSON file for potential issues"""
    
    print(f"\nAnalyzing: {payload_file}")
    print("=" * 80)
    
    with open(payload_file, 'r') as f:
        payload = json.load(f)
    
    issues = []
    
    # Basic structure
    print(f"Structure:")
    print(f"  - Layers: {len(payload.get('layers', []))}")
    print(f"  - Tables: {len(payload.get('tables', []))}")
    print(f"  - Relationships: {len(payload.get('relationships', []))}")
    
    # Check layers
    if 'layers' in payload:
        print(f"\nLayer Analysis:")
        for i, layer in enumerate(payload['layers']):
            print(f"\n  Layer {i}: {layer.get('name', 'Unnamed')}")
            
            # Check for required fields
            required = ['name', 'type', 'fields']
            missing = [f for f in required if f not in layer]
            if missing:
                issues.append(f"Layer {i} missing required fields: {missing}")
                print(f"    ⚠️  Missing required fields: {missing}")
            
            # Check geometry type
            geom_type = layer.get('geometryType')
            print(f"    - Geometry Type: {geom_type}")
            if geom_type and geom_type not in ['esriGeometryPoint', 'esriGeometryPolyline', 
                                               'esriGeometryPolygon', 'esriGeometryMultipoint']:
                issues.append(f"Layer {i} has invalid geometry type: {geom_type}")
            
            # Check renderer
            if 'drawingInfo' in layer:
                renderer = layer['drawingInfo'].get('renderer', {})
                renderer_type = renderer.get('type')
                print(f"    - Renderer Type: {renderer_type}")
                
                # Check for problematic renderer properties
                if renderer_type == 'uniqueValue':
                    infos = renderer.get('uniqueValueInfos', [])
                    groups = renderer.get('uniqueValueGroups', [])
                    print(f"    - Unique Value Infos: {len(infos)}")
                    print(f"    - Unique Value Groups: {len(groups)}")
                    
                    # Check for invalid values
                    for j, info in enumerate(infos):
                        value = info.get('value')
                        if isinstance(value, dict) or isinstance(value, list):
                            issues.append(f"Layer {i} uniqueValueInfo {j} has complex value type: {type(value)}")
            
            # Check fields
            fields = layer.get('fields', [])
            print(f"    - Fields: {len(fields)}")
            
            # Look for problematic properties
            problematic_props = []
            for key in layer.keys():
                value = layer[key]
                # Check for objects that might not serialize properly
                if isinstance(value, object) and not isinstance(value, (dict, list, str, int, float, bool, type(None))):
                    problematic_props.append(f"{key}: {type(value)}")
            
            if problematic_props:
                issues.append(f"Layer {i} has problematic properties: {problematic_props}")
                print(f"    ⚠️  Problematic properties: {problematic_props}")
    
    # Check tables
    if 'tables' in payload:
        print(f"\nTable Analysis:")
        for i, table in enumerate(payload['tables']):
            print(f"\n  Table {i}: {table.get('name', 'Unnamed')}")
            
            # Tables should NOT have drawingInfo
            if 'drawingInfo' in table:
                issues.append(f"Table {i} has drawingInfo (not allowed for tables)")
                print(f"    ⚠️  Has drawingInfo (should be removed)")
            
            # Check for required fields
            required = ['name', 'type', 'fields']
            missing = [f for f in required if f not in table]
            if missing:
                issues.append(f"Table {i} missing required fields: {missing}")
                print(f"    ⚠️  Missing required fields: {missing}")
    
    # Summary
    print(f"\n{'Issues Found:' if issues else 'No Issues Found!'}")
    for issue in issues:
        print(f"  ❌ {issue}")
    
    # Check if JSON is serializable
    print(f"\nJSON Serialization Test:")
    try:
        json_str = json.dumps(payload)
        print(f"  ✓ Payload is JSON serializable ({len(json_str)} bytes)")
    except Exception as e:
        print(f"  ❌ JSON serialization failed: {str(e)}")
        issues.append(f"JSON serialization failed: {str(e)}")
    
    return issues

def find_payload_files(pattern="add_to_definition_payload_*.json"):
    """Find all payload files matching pattern"""
    return sorted(glob.glob(f"json_files/{pattern}"))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Analyze specific file
        analyze_payload(sys.argv[1])
    else:
        # Find and analyze all payload files
        files = find_payload_files()
        if files:
            print(f"Found {len(files)} payload files")
            for f in files:
                analyze_payload(f)
        else:
            print("No payload files found in json_files/")