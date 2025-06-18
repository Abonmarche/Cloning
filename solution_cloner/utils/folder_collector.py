"""
Folder Collector Utility
========================
Collects items from ArcGIS Online folders.
"""

from typing import List, Dict, Any, Union
from arcgis.gis import GIS
import logging


logger = logging.getLogger(__name__)


def _get_items_in_folder(gis: GIS, folder: str) -> List[str]:
    """
    Get item IDs from a specific folder.
    
    Args:
        gis: Authenticated GIS connection
        folder: Folder name (use "root", "", or "/" for root folder)
        
    Returns:
        List of item IDs
    """
    user = gis.users.me
    
    if folder.lower() in {"", "/", "root"} or folder is None:
        items = list(user.items())  # wrap in list() to force evaluation
    else:
        try:
            # Try passing folder name directly
            items = list(user.items(folder=folder))
        except TypeError:
            # If that fails, try getting folder ID
            folders = {}
            for f in user.folders:
                if isinstance(f, dict):
                    folders[f["title"]] = f["id"]
                else:
                    # Handle different folder object types
                    try:
                        folders[f.title] = f.id
                    except AttributeError:
                        # Try alternative attributes
                        folders[getattr(f, 'title', str(f))] = getattr(f, 'id', str(f))
            
            if folder not in folders:
                raise ValueError(f"Folder '{folder}' not found for user {user.username}")
            
            # Try with folder ID
            items = list(user.items(folder=folders[folder]))
    
    return [item.itemid for item in items]


def collect_items_from_folder(
    folder: str,
    gis: GIS,
    include_metadata: bool = True
) -> List[Dict[str, Any]]:
    """
    Collect all items from a specified folder with full metadata.
    
    Args:
        folder: Folder name (use "root" or "" for root folder)
        gis: GIS connection
        include_metadata: Whether to fetch full item metadata
        
    Returns:
        List of dictionaries containing item information
    """
    # Get item IDs from folder
    item_ids = _get_items_in_folder(gis, folder)
    
    if not item_ids:
        logger.warning(f"No items found in folder: {folder}")
        return []
        
    logger.info(f"Found {len(item_ids)} items in folder: {folder}")
    
    # Collect full item information
    items = []
    for item_id in item_ids:
        try:
            item = gis.content.get(item_id)
            if not item:
                logger.warning(f"Could not retrieve item: {item_id}")
                continue
                
            item_info = {
                'id': item.id,
                'title': item.title,
                'type': item.type,
                'owner': item.owner,
                'created': item.created,
                'modified': item.modified,
                'tags': item.tags,
                'snippet': item.snippet,
                'description': item.description,
                'url': item.url if hasattr(item, 'url') else None,
                'typeKeywords': item.typeKeywords,
                'extent': item.extent,
                'spatialReference': item.spatialReference,
                'accessInformation': item.accessInformation,
                'licenseInfo': item.licenseInfo
            }
            
            # Add additional metadata if requested
            if include_metadata:
                item_info['metadata'] = {
                    'size': item.size,
                    'numViews': item.numViews
                }
                
                # Add type-specific information
                if item.type in ['Feature Service', 'Map Service', 'Vector Tile Service']:
                    try:
                        # Convert layers to list of layer info dictionaries
                        if hasattr(item, 'layers') and item.layers:
                            item_info['layers'] = []
                            for layer in item.layers:
                                layer_info = {
                                    'id': layer.properties.get('id'),
                                    'name': layer.properties.get('name'),
                                    'geometryType': layer.properties.get('geometryType'),
                                    'fields': len(layer.properties.get('fields', [])) if hasattr(layer.properties, 'get') else 0
                                }
                                item_info['layers'].append(layer_info)
                        
                        # Convert tables to list of table info dictionaries
                        if hasattr(item, 'tables') and item.tables:
                            item_info['tables'] = []
                            for table in item.tables:
                                table_info = {
                                    'id': table.properties.get('id'),
                                    'name': table.properties.get('name'),
                                    'fields': len(table.properties.get('fields', [])) if hasattr(table.properties, 'get') else 0
                                }
                                item_info['tables'].append(table_info)
                    except:
                        pass
                        
            items.append(item_info)
            
        except Exception as e:
            logger.error(f"Error processing item {item_id}: {str(e)}")
            continue
            
    logger.info(f"Successfully collected {len(items)} items with metadata")
    return items


def get_folder_structure(gis: GIS, username: str = None) -> Dict[str, List[str]]:
    """
    Get the complete folder structure for a user.
    
    Args:
        gis: GIS connection
        username: Username (defaults to logged-in user)
        
    Returns:
        Dictionary mapping folder names to lists of item IDs
    """
    user = gis.users.get(username) if username else gis.users.me
    
    structure = {}
    
    # Get root folder items
    root_items = user.items()
    structure['root'] = [item.id for item in root_items]
    
    # Get items from each folder
    for folder in user.folders:
        if isinstance(folder, dict):
            folder_name = folder["title"]
        else:
            folder_name = getattr(folder, 'title', str(folder))
        
        folder_items = list(user.items(folder=folder_name))
        structure[folder_name] = [item.id for item in folder_items]
        
    return structure


def find_items_by_type(
    items: List[Dict[str, Any]],
    item_types: Union[str, List[str]]
) -> List[Dict[str, Any]]:
    """
    Filter items by type.
    
    Args:
        items: List of item dictionaries
        item_types: Single type or list of types to filter by
        
    Returns:
        Filtered list of items
    """
    if isinstance(item_types, str):
        item_types = [item_types]
        
    return [
        item for item in items 
        if item.get('type') in item_types
    ]


def find_items_by_keyword(
    items: List[Dict[str, Any]],
    keywords: Union[str, List[str]]
) -> List[Dict[str, Any]]:
    """
    Filter items by type keywords.
    
    Args:
        items: List of item dictionaries
        keywords: Single keyword or list of keywords to filter by
        
    Returns:
        Filtered list of items
    """
    if isinstance(keywords, str):
        keywords = [keywords]
        
    filtered = []
    for item in items:
        item_keywords = item.get('typeKeywords', [])
        if any(kw in item_keywords for kw in keywords):
            filtered.append(item)
            
    return filtered