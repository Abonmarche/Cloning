"""
Solution Configuration
======================
Configuration structures and constants for the solution cloner.
No hardcoded values - all configuration comes from the orchestrator.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


class ItemType(Enum):
    """Enumeration of ArcGIS Online item types."""
    FEATURE_SERVICE = "Feature Service"
    TABLE = "Table"
    MAP_SERVICE = "Map Service"
    VECTOR_TILE_SERVICE = "Vector Tile Service"
    IMAGE_SERVICE = "Image Service"
    SCENE_SERVICE = "Scene Service"
    VIEW_SERVICE = "View Service"
    JOIN_VIEW = "Join View"
    WEB_MAP = "Web Map"
    WEB_SCENE = "Web Scene"
    DASHBOARD = "Dashboard"
    WEB_APP = "Web Mapping Application"
    INSTANT_APP = "Instant App"
    STORYMAP = "StoryMap"
    EXPERIENCE_BUILDER = "Experience Builder"
    NOTEBOOK = "Notebook"
    HUB_SITE = "Hub Site Application"
    HUB_PAGE = "Hub Page"
    SITE_APP = "Site Application"  # Enterprise sites
    SITE_PAGE = "Site Page"  # Enterprise pages


class CloneOrder:
    """Defines the order in which items should be cloned."""
    ORDER = [
        # Base data layers (no dependencies)
        [ItemType.FEATURE_SERVICE, ItemType.TABLE, ItemType.MAP_SERVICE,
         ItemType.VECTOR_TILE_SERVICE, ItemType.IMAGE_SERVICE, ItemType.SCENE_SERVICE],
        
        # View layers (depend on feature services)
        [ItemType.VIEW_SERVICE],
        
        # Join views (depend on feature services/views)
        [ItemType.JOIN_VIEW],
        
        # Forms (depend on feature services/views for data collection)
        ['Form'],  # Using string since ItemType enum doesn't have FORM yet
        
        # Maps (depend on layers)
        [ItemType.WEB_MAP, ItemType.WEB_SCENE],
        
        # Apps (depend on maps/layers)
        [ItemType.DASHBOARD, ItemType.WEB_APP, ItemType.INSTANT_APP, ItemType.STORYMAP],
        
        # Complex apps (may depend on various items)
        [ItemType.EXPERIENCE_BUILDER],
        
        # Notebooks (may reference any items)
        [ItemType.NOTEBOOK],
        
        # Hub sites and pages (may reference any items, must be cloned last)
        [ItemType.HUB_SITE, ItemType.SITE_APP, ItemType.HUB_PAGE, ItemType.SITE_PAGE]
    ]


@dataclass
class SourceConfig:
    """Configuration for source organization."""
    city: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    url: Optional[str] = None
    folder: str = "root"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for auth module."""
        return {
            'city': self.city,
            'username': self.username,
            'password': self.password,
            'url': self.url
        }


@dataclass
class DestinationConfig:
    """Configuration for destination organization."""
    city: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    url: str = "https://www.arcgis.com"
    folder: str = "Cloned_Solution"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for auth module."""
        return {
            'city': self.city,
            'username': self.username,
            'password': self.password,
            'url': self.url
        }


@dataclass
class CloneOptions:
    """Options for the cloning process."""
    clone_data: bool = True
    create_dummy_features: bool = True
    preserve_item_ids: bool = False
    skip_existing: bool = True
    rollback_on_error: bool = True
    update_references: bool = True
    update_refs_before_create: bool = False  # Update references before creating items (vs after)
    validate_items: bool = True
    max_retries: int = 3
    retry_delay: int = 5  # seconds


@dataclass
class OutputOptions:
    """Options for output and logging."""
    json_output_dir: str = "json_files"
    log_level: str = "INFO"
    log_file: Optional[str] = None
    save_intermediate: bool = True
    verbose: bool = False


class Privileges:
    """Required privileges for different operations."""
    
    # Basic privileges needed for cloning
    BASIC = [
        "portal:user:createItem",
        "portal:user:shareToOrg",
        "portal:user:shareToGroup"
    ]
    
    # Privileges for creating services
    SERVICE_CREATE = [
        "portal:publisher:publishFeatures",
        "portal:publisher:publishTiles",
        "portal:publisher:publishScenes"
    ]
    
    # Admin privileges for advanced operations
    ADMIN = [
        "portal:admin:updateItems",
        "portal:admin:reassignItems",
        "portal:admin:viewItems"
    ]


class ReferencePatterns:
    """Regular expression patterns for finding references."""
    
    # Item ID patterns
    ITEM_ID = r'\b[a-f0-9]{32}\b'
    ITEM_ID_IN_URL = r'/items/([a-f0-9]{32})'
    
    # Service URL patterns
    FEATURE_SERVICE = r'(https?://[^/]+/[^/]+/rest/services/[^/]+/[^/]+/FeatureServer)'
    MAP_SERVICE = r'(https?://[^/]+/[^/]+/rest/services/[^/]+/[^/]+/MapServer)'
    
    # Common parameter patterns
    WEBMAP_PARAM = r'webmap=([a-f0-9]{32})'
    PORTAL_ITEM_PARAM = r'portalItem=([a-f0-9]{32})'
    ITEM_ID_PARAM = r'itemId=([a-f0-9]{32})'


class ErrorMessages:
    """Standard error messages."""
    
    MISSING_CREDENTIALS = "No credentials provided for {org} organization"
    FOLDER_NOT_FOUND = "Folder '{folder}' not found in {org} organization"
    ITEM_NOT_FOUND = "Item '{item_id}' not found"
    CLONE_FAILED = "Failed to clone item '{title}' ({item_id})"
    DEPENDENCY_MISSING = "Missing dependency '{dep_id}' for item '{item_id}'"
    PRIVILEGE_MISSING = "Missing required privilege: {privilege}"
    CONNECTION_FAILED = "Failed to connect to {org} organization"


@dataclass
class CloneResult:
    """Result of cloning an individual item."""
    success: bool
    source_id: str
    new_id: Optional[str] = None
    error: Optional[str] = None
    item_type: Optional[str] = None
    title: Optional[str] = None
    
    
@dataclass
class SolutionCloneResult:
    """Result of cloning an entire solution."""
    total_items: int
    successful_items: int
    failed_items: int
    id_mapping: Dict[str, str]
    errors: List[str]
    warnings: List[str]
    clone_results: List[CloneResult]