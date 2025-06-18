"""
Authentication Utility
======================
Handles authentication for source and destination ArcGIS organizations.
"""

from typing import Optional, Dict, Tuple, Any
from arcgis.gis import GIS
import logging


logger = logging.getLogger(__name__)


def connect_to_gis(
    url: str = None,
    username: str = None,
    password: str = None
) -> GIS:
    """
    Connect to an ArcGIS organization.
    
    Args:
        url: ArcGIS organization URL
        username: Username for authentication
        password: Password for authentication
        
    Returns:
        Authenticated GIS connection
    """
    if username and password:
        # Direct authentication
        try:
            if not url:
                url = "https://www.arcgis.com"
                
            gis = GIS(url, username, password)
            logger.info(f"Connected to {url} as {username}")
            return gis
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            raise
            
    else:
        # Anonymous connection
        logger.warning("Creating anonymous connection")
        return GIS()


def connect_to_source_and_dest(
    source_config: Dict[str, str],
    dest_config: Dict[str, str]
) -> Tuple[GIS, GIS]:
    """
    Connect to both source and destination organizations.
    
    Args:
        source_config: Configuration for source org
            - username: Direct username
            - password: Direct password
            - url: Organization URL
        dest_config: Configuration for destination org
            - username: Direct username
            - password: Direct password
            - url: Organization URL
            
    Returns:
        Tuple of (source_gis, dest_gis)
    """
    logger.info("Connecting to source organization...")
    source_gis = connect_to_gis(
        url=source_config.get('url'),
        username=source_config.get('username'),
        password=source_config.get('password')
    )
    
    logger.info("Connecting to destination organization...")
    dest_gis = connect_to_gis(
        url=dest_config.get('url'),
        username=dest_config.get('username'),
        password=dest_config.get('password')
    )
    
    # Verify connections
    try:
        source_user = source_gis.users.me
        dest_user = dest_gis.users.me
        
        logger.info(f"Source: {source_user.username} ({source_user.fullName})")
        logger.info(f"Destination: {dest_user.username} ({dest_user.fullName})")
        
    except Exception as e:
        logger.error(f"Failed to verify connections: {str(e)}")
        raise
        
    return source_gis, dest_gis


def get_user_content_folders(gis: GIS, username: str = None) -> Dict[str, int]:
    """
    Get all folders and item counts for a user.
    
    Args:
        gis: GIS connection
        username: Username (defaults to logged-in user)
        
    Returns:
        Dictionary mapping folder names to item counts
    """
    user = gis.users.get(username) if username else gis.users.me
    
    folders = {'root': len(user.items())}
    
    for folder in user.folders:
        if isinstance(folder, dict):
            folder_name = folder["title"]
        else:
            folder_name = getattr(folder, 'title', str(folder))
        items = list(user.items(folder=folder_name))
        folders[folder_name] = len(items)
        
    return folders


def validate_folder_access(
    gis: GIS,
    folder_name: str,
    username: str = None
) -> bool:
    """
    Validate that a folder exists and is accessible.
    
    Args:
        gis: GIS connection
        folder_name: Folder name to check
        username: Username (defaults to logged-in user)
        
    Returns:
        True if folder exists and is accessible
    """
    user = gis.users.get(username) if username else gis.users.me
    
    if folder_name.lower() in ['root', '', '/']:
        return True
        
    folder_titles = []
    for f in user.folders:
        if isinstance(f, dict):
            folder_titles.append(f["title"])
        else:
            folder_titles.append(getattr(f, 'title', str(f)))
    
    return folder_name in folder_titles


def ensure_folder_exists(
    gis: GIS,
    folder_name: str,
    username: str = None
) -> bool:
    """
    Ensure a folder exists, creating it if necessary.
    
    Args:
        gis: GIS connection
        folder_name: Folder name
        username: Username (defaults to logged-in user)
        
    Returns:
        True if folder exists or was created
    """
    if folder_name.lower() in ['root', '', '/']:
        return True
        
    user = gis.users.get(username) if username else gis.users.me
    
    # Check if folder exists
    if validate_folder_access(gis, folder_name, username):
        logger.debug(f"Folder already exists: {folder_name}")
        return True
        
    # Create folder
    try:
        # Try newer API (2.3+)
        try:
            gis.content.folders.create(folder_name, owner=user.username)
            logger.info(f"Created folder: {folder_name}")
            return True
        except AttributeError:
            # Fall back to older API (<2.3)
            result = gis.content.create_folder(folder_name, owner=user.username)
            if result:
                logger.info(f"Created folder: {folder_name}")
                return True
            else:
                logger.error(f"Failed to create folder: {folder_name}")
                return False
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return False


def get_org_info(gis: GIS) -> Dict[str, Any]:
    """
    Get organization information.
    
    Args:
        gis: GIS connection
        
    Returns:
        Dictionary with organization details
    """
    try:
        org = gis.properties.get('organization', {})
        user = gis.users.me
        
        return {
            'org_id': org.get('id'),
            'org_name': org.get('name'),
            'org_url': gis.url,
            'username': user.username,
            'user_fullname': user.fullName,
            'user_role': user.role,
            'user_privileges': user.privileges
        }
    except Exception as e:
        logger.error(f"Error getting org info: {str(e)}")
        return {}


def check_privileges(
    gis: GIS,
    required_privileges: list
) -> Tuple[bool, list]:
    """
    Check if user has required privileges.
    
    Args:
        gis: GIS connection
        required_privileges: List of required privilege strings
        
    Returns:
        Tuple of (has_all_privileges, missing_privileges)
    """
    try:
        user = gis.users.me
        user_privileges = set(user.privileges)
        required = set(required_privileges)
        
        missing = list(required - user_privileges)
        
        return len(missing) == 0, missing
        
    except Exception as e:
        logger.error(f"Error checking privileges: {str(e)}")
        return False, required_privileges