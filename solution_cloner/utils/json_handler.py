"""
JSON Handler Utility
====================
Handles JSON extraction, saving, and manipulation for the solution cloner.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Union, Tuple
import logging
import os


logger = logging.getLogger(__name__)

# Check if JSON output is enabled
JSON_OUTPUT_ENABLED = os.getenv('JSON_OUTPUT_ENABLED', 'True').lower() == 'true'


def save_json(
    data: Any,
    filepath: Union[str, Path],
    add_timestamp: bool = True,
    indent: int = 2,
    ensure_ascii: bool = False
) -> Path:
    """
    Save data to JSON file with optional timestamp.
    
    Args:
        data: Data to save
        filepath: Path to save file
        add_timestamp: Whether to add timestamp to filename
        indent: JSON indentation level
        ensure_ascii: Whether to escape non-ASCII characters
        
    Returns:
        Path to saved file
    """
    # If JSON output is disabled, return a dummy path without saving
    if not JSON_OUTPUT_ENABLED:
        filepath = Path(filepath)
        if add_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if filepath.suffix == '.json':
                return filepath.parent / f"{filepath.stem}_{timestamp}{filepath.suffix}"
            else:
                return filepath.parent / f"{filepath.name}_{timestamp}.json"
        return filepath
    
    filepath = Path(filepath)
    
    # Add timestamp if requested
    if add_timestamp:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if filepath.suffix == '.json':
            final_path = filepath.parent / f"{filepath.stem}_{timestamp}{filepath.suffix}"
        else:
            final_path = filepath.parent / f"{filepath.name}_{timestamp}.json"
    else:
        final_path = filepath
        
    # Ensure directory exists
    final_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save JSON
    with open(final_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        
    logger.info(f"Saved JSON to: {final_path}")
    return final_path


def load_json(filepath: Union[str, Path]) -> Any:
    """
    Load data from JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Loaded data
    """
    filepath = Path(filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    logger.debug(f"Loaded JSON from: {filepath}")
    return data


def jdump(obj: Any, description: str = "", save_to_file: bool = True) -> str:
    """
    Pretty print and optionally save JSON data (compatible with existing code).
    
    Args:
        obj: Object to dump
        description: Description for logging
        save_to_file: Whether to save to file
        
    Returns:
        JSON string
    """
    json_str = json.dumps(obj, indent=2, ensure_ascii=False)
    
    if description:
        logger.info(f"{description}:\n{json_str[:500]}...")  # Log first 500 chars
        
    if save_to_file and description and JSON_OUTPUT_ENABLED:
        # Save to json_files directory with description as filename
        json_dir = Path(__file__).parent.parent.parent / "json_files"
        safe_filename = description.replace(' ', '_').replace('/', '_')
        save_json(obj, json_dir / f"{safe_filename}.json")
        
    return json_str


def merge_json(base: Dict, updates: Dict, deep: bool = True) -> Dict:
    """
    Merge two JSON objects.
    
    Args:
        base: Base dictionary
        updates: Updates to apply
        deep: Whether to do deep merge
        
    Returns:
        Merged dictionary
    """
    if not deep:
        result = base.copy()
        result.update(updates)
        return result
        
    # Deep merge
    result = base.copy()
    
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_json(result[key], value, deep=True)
        else:
            result[key] = value
            
    return result


def extract_json_subset(data: Dict, keys: list) -> Dict:
    """
    Extract a subset of keys from a dictionary.
    
    Args:
        data: Source dictionary
        keys: List of keys to extract (supports dot notation)
        
    Returns:
        Dictionary with extracted keys
    """
    result = {}
    
    for key in keys:
        if '.' in key:
            # Handle nested keys
            parts = key.split('.')
            value = data
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            if value is not None:
                # Reconstruct nested structure
                current = result
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
        else:
            # Simple key
            if key in data:
                result[key] = data[key]
                
    return result


def clean_json_for_create(item_json: Dict) -> Dict:
    """
    Clean item JSON for creating a new item.
    
    Args:
        item_json: Raw item JSON
        
    Returns:
        Cleaned JSON suitable for item creation
    """
    # Fields to remove (these are set by the system)
    remove_fields = [
        'id', 'owner', 'created', 'modified', 'guid', 'name',
        'isOrgItem', 'lastModified', 'uploaded', 'username',
        'storageUsed', 'storageQuota', 'orgId', 'ownerFolder',
        'protected', 'size', 'numViews', 'numComments', 'numRatings',
        'avgRating', 'culture', 'properties', 'appCategories',
        'listed', 'commentsEnabled', 'itemControl', 'scoreCompleteness',
        'groupDesignations', 'contentOrigin'
    ]
    
    cleaned = {k: v for k, v in item_json.items() if k not in remove_fields}
    
    # Clean specific fields
    if 'extent' in cleaned and cleaned['extent'] == []:
        cleaned['extent'] = None
        
    # Ensure required fields
    if 'type' not in cleaned:
        logger.warning("Missing 'type' field in item JSON")
        
    if 'title' not in cleaned:
        logger.warning("Missing 'title' field in item JSON")
        
    return cleaned


def compare_json(obj1: Any, obj2: Any, path: str = "") -> list:
    """
    Compare two JSON objects and return differences.
    
    Args:
        obj1: First object
        obj2: Second object
        path: Current path in object hierarchy
        
    Returns:
        List of differences
    """
    differences = []
    
    if type(obj1) != type(obj2):
        differences.append(f"{path}: Type mismatch - {type(obj1).__name__} vs {type(obj2).__name__}")
        return differences
        
    if isinstance(obj1, dict):
        all_keys = set(obj1.keys()) | set(obj2.keys())
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            if key not in obj1:
                differences.append(f"{new_path}: Missing in first object")
            elif key not in obj2:
                differences.append(f"{new_path}: Missing in second object")
            else:
                differences.extend(compare_json(obj1[key], obj2[key], new_path))
                
    elif isinstance(obj1, list):
        if len(obj1) != len(obj2):
            differences.append(f"{path}: List length mismatch - {len(obj1)} vs {len(obj2)}")
        else:
            for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                differences.extend(compare_json(item1, item2, f"{path}[{i}]"))
                
    elif obj1 != obj2:
        differences.append(f"{path}: Value mismatch - {obj1} vs {obj2}")
        
    return differences


def validate_json_structure(data: Dict, required_fields: list) -> Tuple[bool, list]:
    """
    Validate that a JSON object has required fields.
    
    Args:
        data: JSON object to validate
        required_fields: List of required field paths (supports dot notation)
        
    Returns:
        Tuple of (is_valid, missing_fields)
    """
    missing = []
    
    for field in required_fields:
        if '.' in field:
            # Check nested field
            parts = field.split('.')
            current = data
            found = True
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    found = False
                    break
            if not found:
                missing.append(field)
        else:
            # Check top-level field
            if field not in data:
                missing.append(field)
                
    return len(missing) == 0, missing