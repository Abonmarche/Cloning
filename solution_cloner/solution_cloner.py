#!/usr/bin/env python3
"""
Solution Cloner Orchestrator
============================
Main entry point for cloning ArcGIS Online solutions from one organization to another.
All configuration variables are defined here.

Usage:
    1. Update the configuration variables below
    2. Run: python solution_cloner.py
"""

import sys
import logging
import datetime
import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

from arcgis.gis import GIS

# Import our modules
from .utils.auth import connect_to_gis
from .utils.folder_collector import collect_items_from_folder
from .utils.item_analyzer import analyze_dependencies, classify_items
from .utils.id_mapper import IDMapper
from .utils.json_handler import save_json
from .config.solution_config import CloneOrder

# Import cloners (will be created from existing scripts)
from .cloners.feature_layer_cloner import FeatureLayerCloner
from .cloners.web_map_cloner import WebMapCloner
from .cloners.view_cloner import ViewCloner
from .cloners.join_view_cloner import JoinViewCloner
# from cloners.instant_app_cloner import InstantAppCloner
# from cloners.dashboard_cloner import DashboardCloner
# from cloners.experience_builder_cloner import ExperienceBuilderCloner


# ================================================================================================
# CONFIGURATION - LOADED FROM ENVIRONMENT VARIABLES
# ================================================================================================

# Load environment variables from .env file
# override=True ensures .env file values take precedence over shell environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    print(f"Warning: No .env file found at {env_path}")
    print("Please create a .env file based on .env.template")

# Source Organization Configuration
SOURCE_URL = os.getenv('SOURCE_URL', 'https://www.arcgis.com')
SOURCE_USERNAME = os.getenv('SOURCE_USERNAME')
SOURCE_PASSWORD = os.getenv('SOURCE_PASSWORD')
SOURCE_FOLDER = os.getenv('SOURCE_FOLDER', 'root')

# Destination Organization Configuration  
DEST_URL = os.getenv('DEST_URL', 'https://www.arcgis.com')
DEST_USERNAME = os.getenv('DEST_USERNAME')
DEST_PASSWORD = os.getenv('DEST_PASSWORD')
DEST_FOLDER = os.getenv('DEST_FOLDER', f"cloned_content_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")

# Cloning Options (with defaults)
CLONE_DATA = os.getenv('CLONE_DATA', 'False').lower() == 'true'
CREATE_DUMMY_FEATURES = os.getenv('CREATE_DUMMY_FEATURES', 'False').lower() == 'true'
PRESERVE_ITEM_IDS = os.getenv('PRESERVE_ITEM_IDS', 'False').lower() == 'true'
SKIP_EXISTING = os.getenv('SKIP_EXISTING', 'False').lower() == 'true'
ROLLBACK_ON_ERROR = os.getenv('ROLLBACK_ON_ERROR', 'False').lower() == 'true'

# Output Options
JSON_OUTPUT_DIR = Path(__file__).parent.parent / "json_files"
LOG_LEVEL = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO)
LOG_FILE = f"solution_clone_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Validate required configuration
def validate_configuration():
    """Validate that all required configuration is present."""
    errors = []
    if not SOURCE_USERNAME:
        errors.append("SOURCE_USERNAME is required in .env file")
    if not SOURCE_PASSWORD:
        errors.append("SOURCE_PASSWORD is required in .env file")
    if not DEST_USERNAME:
        errors.append("DEST_USERNAME is required in .env file")
    if not DEST_PASSWORD:
        errors.append("DEST_PASSWORD is required in .env file")
    
    if errors:
        print("\nConfiguration errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease update your .env file with the required values.")
        sys.exit(1)

# ================================================================================================
# END CONFIGURATION
# ================================================================================================


class SolutionCloner:
    """Orchestrates the cloning of an entire ArcGIS Online solution."""
    
    def __init__(self):
        """Initialize the solution cloner with configuration."""
        self.setup_logging()
        self.source_gis = None
        self.dest_gis = None
        self.id_mapper = IDMapper()
        self.created_items = []  # Track for rollback
        
        # Initialize cloners
        self.cloners = {
            'Feature Service': FeatureLayerCloner(),
            'Feature Layer': FeatureLayerCloner(),
            'Table': FeatureLayerCloner(),
            'View': ViewCloner(JSON_OUTPUT_DIR),
            'Join View': JoinViewCloner(JSON_OUTPUT_DIR),
            'Web Map': WebMapCloner(JSON_OUTPUT_DIR),
            # 'Instant App': InstantAppCloner(),
            # 'Dashboard': DashboardCloner(),
            # 'Experience Builder': ExperienceBuilderCloner()
        }
        
    def setup_logging(self):
        """Configure logging for the cloning process."""
        logging.basicConfig(
            level=LOG_LEVEL,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def connect_to_organizations(self):
        """Connect to source and destination ArcGIS organizations."""
        self.logger.info("Connecting to source organization...")
        
        # Connect to source
        self.source_gis = connect_to_gis(
            url=SOURCE_URL,
            username=SOURCE_USERNAME,
            password=SOURCE_PASSWORD
        )
            
        self.logger.info(f"Connected to source as: {self.source_gis.users.me.username}")
        
        # Connect to destination
        self.logger.info("Connecting to destination organization...")
        self.dest_gis = connect_to_gis(
            url=DEST_URL,
            username=DEST_USERNAME,
            password=DEST_PASSWORD
        )
            
        self.logger.info(f"Connected to destination as: {self.dest_gis.users.me.username}")
        
    def collect_solution_items(self) -> List[Dict]:
        """Collect all items from the specified source folder."""
        self.logger.info(f"Collecting items from folder: {SOURCE_FOLDER}")
        
        items = collect_items_from_folder(
            SOURCE_FOLDER, 
            self.source_gis,
            include_metadata=True
        )
        
        self.logger.info(f"Found {len(items)} items in folder")
        
        # Save inventory for reference
        save_json(
            {"folder": SOURCE_FOLDER, "items": items},
            JSON_OUTPUT_DIR / f"solution_inventory_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        return items
        
    def analyze_solution(self, items: List[Dict]) -> Tuple[Dict, List[List[str]]]:
        """Analyze items to determine types and dependencies."""
        self.logger.info("Analyzing solution structure...")
        
        # Classify items by type
        classified = classify_items(items, self.source_gis)
        
        # Analyze dependencies
        dependency_order = analyze_dependencies(classified, self.source_gis)
        
        self.logger.info(f"Analysis complete. Found {len(dependency_order)} dependency levels")
        
        return classified, dependency_order
        
    def ensure_destination_folder(self):
        """Create destination folder if it doesn't exist."""
        user = self.dest_gis.users.me
        
        # Handle different folder object types
        folder_names = []
        for f in user.folders:
            if isinstance(f, dict):
                folder_names.append(f["title"])
            else:
                folder_names.append(getattr(f, 'title', str(f)))
        
        self.logger.debug(f"Existing folders: {folder_names}")
        self.logger.debug(f"Looking for folder: {DEST_FOLDER}")
        
        if DEST_FOLDER not in folder_names:
            self.logger.info(f"Creating destination folder: {DEST_FOLDER}")
            try:
                # Try newer API (2.3+)
                self.dest_gis.content.folders.create(DEST_FOLDER, owner=user.username)
                self.logger.info(f"Successfully created folder: {DEST_FOLDER}")
            except Exception as e:
                # Check if it's a duplicate folder error (from newer API)
                error_msg = str(e).lower()
                if 'not available' in error_msg or 'already exists' in error_msg:
                    self.logger.warning(f"Folder '{DEST_FOLDER}' appears to already exist despite not being in folder list")
                    self.logger.debug(f"This may be due to a sync issue. Proceeding anyway.")
                elif isinstance(e, AttributeError):
                    # Fall back to older API (<2.3)
                    try:
                        result = self.dest_gis.content.create_folder(DEST_FOLDER, owner=user.username)
                        if result.get('success'):
                            self.logger.info(f"Successfully created folder: {DEST_FOLDER}")
                        else:
                            self.logger.error(f"Failed to create folder: {result}")
                    except Exception as e2:
                        # Check if it's a duplicate folder error (from older API)
                        error_msg2 = str(e2).lower()
                        if 'not available' in error_msg2 or 'already exists' in error_msg2:
                            self.logger.warning(f"Folder '{DEST_FOLDER}' appears to already exist despite not being in folder list")
                            self.logger.debug(f"This may be due to a sync issue. Proceeding anyway.")
                        else:
                            raise
                else:
                    raise
        else:
            self.logger.info(f"Using existing folder: {DEST_FOLDER}")
            
    def clone_items_by_level(self, items: List[Dict], level: int) -> Dict[str, str]:
        """Clone all items at a specific dependency level."""
        self.logger.info(f"Cloning dependency level {level} ({len(items)} items)")
        
        level_mapping = {}
        
        for item in items:
            try:
                item_type = item.get('type', 'Unknown')
                item_id = item['id']
                title = item.get('title', 'Untitled')
                
                self.logger.info(f"Cloning {item_type}: {title} ({item_id})")
                
                # Skip if already exists and SKIP_EXISTING is True
                if SKIP_EXISTING:
                    existing = self.dest_gis.content.search(
                        f'title:"{title}" AND owner:{DEST_USERNAME}',
                        item_type=item_type
                    )
                    if existing:
                        self.logger.info(f"Item already exists, skipping: {title}")
                        level_mapping[item_id] = existing[0].id
                        continue
                
                # Get appropriate cloner
                cloner = self.get_cloner_for_item(item, self.source_gis)
                if not cloner:
                    self.logger.warning(f"No cloner available for type: {item_type}")
                    continue
                    
                # Clone the item
                new_item = cloner.clone(
                    source_item=item,
                    source_gis=self.source_gis,
                    dest_gis=self.dest_gis,
                    dest_folder=DEST_FOLDER,
                    id_mapping=self.id_mapper.get_mapping(),
                    clone_data=CLONE_DATA,
                    create_dummy_features=CREATE_DUMMY_FEATURES
                )
                
                if new_item:
                    level_mapping[item_id] = new_item.id
                    self.created_items.append(new_item)
                    
                    # Add detailed URL mappings if available
                    if hasattr(cloner, 'get_last_mapping_data'):
                        mapping_data = cloner.get_last_mapping_data()
                        if mapping_data:
                            # Add main URL mapping
                            if 'url' in mapping_data and item.get('url'):
                                self.id_mapper.add_mapping(
                                    item_id, new_item.id,
                                    item.get('url'), mapping_data['url']
                                )
                            # Add sublayer URL mappings
                            if 'sublayer_urls' in mapping_data:
                                for old_url, new_url in mapping_data['sublayer_urls'].items():
                                    self.id_mapper.url_mapping[old_url] = new_url
                                    # Also add to sublayer mapping
                                    self.id_mapper.sublayer_mapping[old_url] = new_url
                    
                    # Add layer ID mappings for feature services
                    if hasattr(cloner, 'get_layer_id_mappings'):
                        layer_mappings = cloner.get_layer_id_mappings()
                        if layer_mappings:
                            # Add layer ID mappings to the main ID mapping
                            for old_layer_id, new_layer_id in layer_mappings.items():
                                self.id_mapper.id_mapping[old_layer_id] = new_layer_id
                                self.logger.debug(f"Added layer ID mapping: {old_layer_id} -> {new_layer_id}")
                    
                    self.logger.info(f"Successfully cloned: {title} -> {new_item.id}")
                else:
                    self.logger.error(f"Failed to clone: {title}")
                    
            except Exception as e:
                self.logger.error(f"Error cloning item {item.get('title', 'Unknown')}: {str(e)}")
                if ROLLBACK_ON_ERROR:
                    self.rollback()
                    raise
                    
        return level_mapping
        
    def _detect_feature_service_subtype(self, item_dict: Dict, gis: GIS) -> str:
        """
        Detect if a feature service is actually a view or join view.
        
        Args:
            item_dict: Item dictionary
            gis: GIS connection
            
        Returns:
            'View', 'Join View', or 'Feature Service'
        """
        try:
            # Get the actual item object
            item = gis.content.get(item_dict['id'])
            if not item:
                return 'Feature Service'
                
            # Check if it's a view
            from arcgis.features import FeatureLayerCollection
            flc = FeatureLayerCollection.fromitem(item)
            
            if not getattr(flc.properties, "isView", False):
                # Not a view, so it's a regular feature service
                return 'Feature Service'
                
            # It's a view - now check if it's a join view
            # Check using admin endpoint approach from recreate_JoinView_by_json.py
            import requests
            
            # Try to get admin endpoint to check for join definition
            if "/rest/services/" in item.url:
                admin_url = item.url.replace("/rest/services/", "/rest/admin/services/") + "/0"
                params = {"f": "json"}
                if hasattr(gis._con, 'token') and gis._con.token:
                    params["token"] = gis._con.token
                
                try:
                    r = requests.get(admin_url, params=params)
                    if r.ok:
                        admin_data = r.json()
                        
                        # Save admin response for debugging
                        try:
                            save_json(
                                admin_data,
                                JSON_OUTPUT_DIR / f"admin_endpoint_{item.id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                            )
                        except:
                            pass
                        
                        if "adminLayerInfo" in admin_data:
                            admin_info = admin_data["adminLayerInfo"]
                            if "viewLayerDefinition" in admin_info:
                                view_def = admin_info["viewLayerDefinition"]
                                if "table" in view_def and "relatedTables" in view_def["table"]:
                                    # Has related tables = join view
                                    self.logger.info(f"Detected join view: {item.title}")
                                    return 'Join View'
                except:
                    # If admin endpoint fails, fall back to other detection methods
                    pass
                    
            # It's a regular view
            self.logger.info(f"Detected view layer: {item.title}")
            return 'View'
            
        except Exception as e:
            self.logger.debug(f"Error detecting feature service subtype: {e}")
            return 'Feature Service'
        
    def get_cloner_for_item(self, item_dict: Dict, gis: GIS):
        """
        Get the appropriate cloner for an item, with special handling for feature services.
        
        Args:
            item_dict: Item dictionary with at least 'id' and 'type'
            gis: GIS connection to use for detection
            
        Returns:
            Appropriate cloner instance or None
        """
        item_type = item_dict.get('type', '')
        
        # Special handling for feature services - they might be views or join views
        if item_type in ['Feature Service', 'Feature Layer']:
            actual_type = self._detect_feature_service_subtype(item_dict, gis)
            return self.cloners.get(actual_type)
            
        # For other types, use the standard method
        return self.get_cloner_for_type(item_type)
        
    def get_cloner_for_type(self, item_type: str):
        """Get the appropriate cloner for an item type."""
        # Direct match
        if item_type in self.cloners:
            return self.cloners[item_type]
            
        # Pattern matching for complex types
        if 'Dashboard' in item_type:
            return self.cloners.get('Dashboard')
        elif 'Experience' in item_type or 'ExB' in item_type:
            return self.cloners.get('Experience Builder')
        elif 'Instant App' in item_type:
            return self.cloners.get('Instant App')
            
        return None
        
    def update_all_references(self):
        """Update all references in cloned items to point to new IDs."""
        self.logger.info("Updating all cross-references in cloned items...")
        
        mapping = self.id_mapper.get_mapping()
        
        for item in self.created_items:
            try:
                item_type = item.type
                cloner = self.get_cloner_for_type(item_type)
                
                if cloner and hasattr(cloner, 'update_references'):
                    self.logger.info(f"Updating references in: {item.title}")
                    cloner.update_references(item, mapping, self.dest_gis)
                    
            except Exception as e:
                self.logger.error(f"Error updating references in {item.title}: {str(e)}")
                
    def rollback(self):
        """Delete all created items in case of error."""
        if not self.created_items:
            return
            
        self.logger.warning(f"Rolling back - deleting {len(self.created_items)} created items")
        
        for item in reversed(self.created_items):
            try:
                self.logger.info(f"Deleting: {item.title}")
                item.delete()
            except Exception as e:
                self.logger.error(f"Error deleting {item.title}: {str(e)}")
                
    def clone_solution(self):
        """Main method to clone an entire solution."""
        try:
            # Connect to organizations
            self.connect_to_organizations()
            
            # Collect items from source folder
            items = self.collect_solution_items()
            if not items:
                self.logger.warning("No items found in source folder")
                return
                
            # Analyze solution structure
            classified_items, dependency_order = self.analyze_solution(items)
            
            # Ensure destination folder exists
            self.ensure_destination_folder()
            
            # Clone items in dependency order
            for level, level_items in enumerate(dependency_order):
                if level_items:
                    level_mapping = self.clone_items_by_level(
                        [item for item in items if item['id'] in level_items],
                        level
                    )
                    self.id_mapper.add_mappings(level_mapping)
                    
            # Update all cross-references
            self.update_all_references()
            
            # Save final mapping
            save_json(
                self.id_mapper.get_mapping(),
                JSON_OUTPUT_DIR / f"id_mapping_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            self.logger.info(f"Solution cloning complete! Cloned {len(self.created_items)} items")
            
        except Exception as e:
            self.logger.error(f"Fatal error during solution cloning: {str(e)}")
            if ROLLBACK_ON_ERROR:
                self.rollback()
            raise


def main():
    """Main entry point."""
    # Validate configuration before proceeding
    validate_configuration()
    
    print("\nArcGIS Online Solution Cloner")
    print("=" * 50)
    print(f"Source: {SOURCE_USERNAME} / Folder: {SOURCE_FOLDER}")
    print(f"Destination: {DEST_USERNAME} / Folder: {DEST_FOLDER}")
    print("=" * 50)
    
    cloner = SolutionCloner()
    cloner.clone_solution()


if __name__ == "__main__":
    main()