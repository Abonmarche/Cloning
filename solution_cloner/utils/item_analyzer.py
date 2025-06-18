"""
Item Analyzer Utility
=====================
Analyzes ArcGIS Online items to determine types, dependencies, and cloning order.
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
from arcgis.gis import GIS
import logging
import re


logger = logging.getLogger(__name__)


# Define item type categories and their dependencies
ITEM_TYPE_HIERARCHY = {
    'Feature Service': 0,  # Base data layer
    'Table': 0,           # Base data layer
    'Map Service': 0,     # Base service
    'Vector Tile Service': 0,  # Base service
    'Image Service': 0,   # Base service
    'Scene Service': 0,   # Base service
    'View Service': 1,    # Depends on feature services
    'Join View': 2,       # Depends on feature services/views
    'Web Map': 3,         # Depends on layers
    'Web Scene': 3,       # Depends on layers
    'Dashboard': 4,       # Depends on maps/layers
    'Web Mapping Application': 4,  # Depends on maps
    'Instant App': 4,     # Depends on maps
    'StoryMap': 4,        # Depends on maps/content
    'Experience Builder': 5,  # Depends on various items
    'Notebook': 6,        # May depend on any items
}


def classify_items(items: List[Dict[str, Any]], gis: GIS = None) -> Dict[str, List[Dict]]:
    """
    Classify items by their types and subtypes.
    
    Args:
        items: List of item dictionaries
        gis: Optional GIS connection for additional analysis
        
    Returns:
        Dictionary mapping item types to lists of items
    """
    classified = defaultdict(list)
    
    for item in items:
        item_type = item.get('type', 'Unknown')
        
        # Handle special cases based on typeKeywords
        type_keywords = item.get('typeKeywords', [])
        
        # Identify join views
        if 'Join View' in type_keywords or 'joinedView' in type_keywords:
            classified['Join View'].append(item)
        # Identify view layers
        elif 'View Service' in type_keywords:
            classified['View Service'].append(item)
        # Experience Builder apps
        elif 'Experience' in type_keywords or 'ExB' in type_keywords:
            classified['Experience Builder'].append(item)
        # Instant apps
        elif 'Instant App' in type_keywords:
            classified['Instant App'].append(item)
        # Default classification
        else:
            classified[item_type].append(item)
            
    logger.info(f"Classified {len(items)} items into {len(classified)} types")
    return dict(classified)


def analyze_dependencies(
    classified_items: Dict[str, List[Dict]],
    gis: GIS
) -> List[List[str]]:
    """
    Analyze dependencies between items and determine cloning order.
    
    Args:
        classified_items: Items grouped by type
        gis: GIS connection for detailed analysis
        
    Returns:
        List of item ID lists, ordered by dependency level
    """
    # Build dependency graph
    dependencies = defaultdict(set)  # item_id -> set of items it depends on
    all_items = {}  # item_id -> item dict
    
    # Flatten classified items
    for item_list in classified_items.values():
        for item in item_list:
            all_items[item['id']] = item
            
    # Analyze each item for dependencies
    for item_id, item in all_items.items():
        item_deps = extract_item_dependencies(item, gis, all_items)
        dependencies[item_id] = item_deps
        
    # Perform topological sort
    levels = topological_sort(dependencies, all_items)
    
    logger.info(f"Determined {len(levels)} dependency levels")
    for i, level in enumerate(levels):
        logger.debug(f"Level {i}: {len(level)} items")
        
    return levels


def extract_item_dependencies(item: Dict[str, Any], gis: GIS, all_items: Dict[str, Dict] = None) -> Set[str]:
    """
    Extract dependencies for a specific item.
    
    Args:
        item: Item dictionary
        gis: GIS connection
        
    Returns:
        Set of item IDs this item depends on
    """
    deps = set()
    item_type = item.get('type', '')
    
    # Web Maps depend on layers
    if item_type == 'Web Map':
        deps.update(extract_webmap_dependencies(item, gis))
        
    # Dashboards depend on maps and data sources
    elif item_type == 'Dashboard':
        deps.update(extract_dashboard_dependencies(item, gis))
        
    # Apps depend on web maps
    elif item_type in ['Web Mapping Application', 'Instant App']:
        deps.update(extract_app_dependencies(item, gis))
        
    # Experience Builder can depend on many things
    elif 'Experience' in item.get('typeKeywords', []):
        deps.update(extract_experience_dependencies(item, gis))
        
    # View layers depend on source feature services
    elif 'View Service' in item.get('typeKeywords', []):
        deps.update(extract_view_dependencies(item, gis))
        
    # Join views depend on source layers
    elif 'Join View' in item.get('typeKeywords', []):
        deps.update(extract_join_view_dependencies(item, gis))
        
    # Filter out non-existent dependencies
    if all_items:
        valid_deps = set()
        for dep_id in deps:
            if dep_id in all_items:
                valid_deps.add(dep_id)
        return valid_deps
    else:
        return deps


def extract_webmap_dependencies(item: Dict, gis: GIS) -> Set[str]:
    """Extract layer dependencies from a web map."""
    deps = set()
    
    try:
        # Get the web map item
        webmap_item = gis.content.get(item['id'])
        if not webmap_item:
            return deps
            
        # Get web map JSON
        webmap_json = webmap_item.get_data()
        
        # Extract operational layers
        for layer in webmap_json.get('operationalLayers', []):
            # Layer with itemId
            if 'itemId' in layer:
                deps.add(layer['itemId'])
                
            # Feature service URL
            elif 'url' in layer:
                # Try to find item by URL
                item_id = find_item_by_url(layer['url'], gis)
                if item_id:
                    deps.add(item_id)
                    
        # Extract basemap layers
        basemap = webmap_json.get('baseMap', {})
        for layer in basemap.get('baseMapLayers', []):
            if 'itemId' in layer:
                deps.add(layer['itemId'])
                
    except Exception as e:
        logger.warning(f"Error extracting web map dependencies: {str(e)}")
        
    return deps


def extract_dashboard_dependencies(item: Dict, gis: GIS) -> Set[str]:
    """Extract dependencies from a dashboard."""
    deps = set()
    
    try:
        # Get dashboard configuration
        dashboard_item = gis.content.get(item['id'])
        if not dashboard_item:
            return deps
            
        dashboard_json = dashboard_item.get_data()
        
        # Look for data sources
        if 'widgets' in dashboard_json:
            for widget in dashboard_json['widgets']:
                if 'datasets' in widget:
                    for dataset in widget['datasets']:
                        if 'dataSource' in dataset:
                            data_source = dataset['dataSource']
                            if 'itemId' in data_source:
                                deps.add(data_source['itemId'])
                                
        # Look for web maps
        if 'desktopView' in dashboard_json:
            view = dashboard_json['desktopView']
            if 'widgets' in view:
                for widget_id, widget in view['widgets'].items():
                    if widget.get('type') == 'mapWidget':
                        if 'itemId' in widget:
                            deps.add(widget['itemId'])
                            
    except Exception as e:
        logger.warning(f"Error extracting dashboard dependencies: {str(e)}")
        
    return deps


def extract_app_dependencies(item: Dict, gis: GIS) -> Set[str]:
    """Extract web map dependencies from an app."""
    deps = set()
    
    try:
        app_item = gis.content.get(item['id'])
        if not app_item:
            return deps
            
        # Check for web map in app config
        app_json = app_item.get_data()
        
        # Common patterns for web map references
        if isinstance(app_json, dict):
            # Direct webmap property
            if 'webmap' in app_json:
                deps.add(app_json['webmap'])
                
            # Values.webmap pattern
            elif 'values' in app_json and 'webmap' in app_json['values']:
                deps.add(app_json['values']['webmap'])
                
            # ItemId pattern
            elif 'itemId' in app_json:
                deps.add(app_json['itemId'])
                
    except Exception as e:
        logger.warning(f"Error extracting app dependencies: {str(e)}")
        
    return deps


def extract_experience_dependencies(item: Dict, gis: GIS) -> Set[str]:
    """Extract dependencies from Experience Builder app."""
    deps = set()
    
    try:
        exp_item = gis.content.get(item['id'])
        if not exp_item:
            return deps
            
        # Experience Builder can reference many item types
        # This would need more sophisticated parsing of the experience config
        # For now, we'll do basic extraction
        
        exp_json = exp_item.get_data()
        if isinstance(exp_json, dict):
            # Recursively search for item IDs
            deps.update(find_item_ids_in_dict(exp_json))
            
    except Exception as e:
        logger.warning(f"Error extracting experience dependencies: {str(e)}")
        
    return deps


def extract_view_dependencies(item: Dict, gis: GIS) -> Set[str]:
    """Extract source layer dependencies from a view."""
    deps = set()
    
    # View layers typically reference their source in the URL
    if 'url' in item and item['url']:
        # Try to extract source service from view URL
        source_id = extract_source_from_view_url(item['url'], gis)
        if source_id:
            deps.add(source_id)
            
    return deps


def extract_join_view_dependencies(item: Dict, gis: GIS) -> Set[str]:
    """Extract source layer dependencies from a join view."""
    deps = set()
    
    try:
        # Join views have complex dependencies that may require admin API
        # For basic analysis, check the item relationships
        join_item = gis.content.get(item['id'])
        if join_item:
            # Check item relationships
            related = join_item.related_items('Service2Service', 'forward')
            for rel_item in related:
                deps.add(rel_item.id)
                
    except Exception as e:
        logger.warning(f"Error extracting join view dependencies: {str(e)}")
        
    return deps


def topological_sort(
    dependencies: Dict[str, Set[str]],
    all_items: Dict[str, Dict]
) -> List[List[str]]:
    """
    Perform topological sort to determine dependency levels.
    
    Args:
        dependencies: Dictionary mapping item_id to set of dependencies
        all_items: Dictionary of all items
        
    Returns:
        List of lists, each containing item IDs at that dependency level
    """
    # Create a copy to track remaining dependencies
    remaining_deps = {k: v.copy() for k, v in dependencies.items()}
    levels = []
    processed = set()
    
    while remaining_deps:
        # Find items with no remaining dependencies
        current_level = []
        
        for item_id, deps in remaining_deps.items():
            if item_id not in processed and len(deps - processed) == 0:
                current_level.append(item_id)
                
        if not current_level:
            # Circular dependency or missing items
            logger.warning("Circular dependency detected or missing items")
            # Add remaining items in type-based order
            remaining_items = [id for id in remaining_deps if id not in processed]
            remaining_items.sort(key=lambda x: get_type_priority(all_items.get(x, {})))
            levels.append(remaining_items)
            break
            
        # Process this level
        levels.append(current_level)
        processed.update(current_level)
        
        # Remove processed items from remaining
        for item_id in current_level:
            del remaining_deps[item_id]
            
    return levels


def get_type_priority(item: Dict) -> int:
    """Get priority for an item type (lower = higher priority)."""
    item_type = item.get('type', '')
    type_keywords = item.get('typeKeywords', [])
    
    # Check special types first
    if 'Join View' in type_keywords:
        return ITEM_TYPE_HIERARCHY.get('Join View', 999)
    elif 'View Service' in type_keywords:
        return ITEM_TYPE_HIERARCHY.get('View Service', 999)
    elif 'Experience' in type_keywords:
        return ITEM_TYPE_HIERARCHY.get('Experience Builder', 999)
        
    return ITEM_TYPE_HIERARCHY.get(item_type, 999)


def find_item_ids_in_dict(data: Any) -> Set[str]:
    """Recursively find potential item IDs in a dictionary."""
    ids = set()
    
    if isinstance(data, dict):
        for key, value in data.items():
            # Common ID field names
            if key in ['itemId', 'webmap', 'portalItemId', 'id', 'sourceItemId']:
                if isinstance(value, str) and len(value) == 32:
                    ids.add(value)
            # Recurse
            ids.update(find_item_ids_in_dict(value))
            
    elif isinstance(data, list):
        for item in data:
            ids.update(find_item_ids_in_dict(item))
            
    elif isinstance(data, str):
        # Look for 32-character hex strings
        matches = re.findall(r'\b[a-f0-9]{32}\b', data)
        ids.update(matches)
        
    return ids


def find_item_by_url(url: str, gis: GIS) -> Optional[str]:
    """Try to find an item ID by its service URL."""
    # Extract service path
    service_pattern = r'/rest/services/(.+?)/(Feature|Map|Vector)Server'
    match = re.search(service_pattern, url, re.IGNORECASE)
    
    if match:
        service_name = match.group(1).split('/')[-1]
        
        # Search for items with this service name
        results = gis.content.search(f'title:"{service_name}"', max_items=10)
        
        for item in results:
            if item.url and url in item.url:
                return item.id
                
    return None


def extract_source_from_view_url(view_url: str, gis: GIS) -> Optional[str]:
    """Extract source item ID from a view layer URL."""
    # Views often have URLs like .../FeatureServer/0
    # We need to find the base service
    base_pattern = r'(.+?/Feature(?:Server|Service))(?:/\d+)?'
    match = re.search(base_pattern, view_url, re.IGNORECASE)
    
    if match:
        base_url = match.group(1)
        return find_item_by_url(base_url, gis)
        
    return None