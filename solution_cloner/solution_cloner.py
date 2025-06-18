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
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from arcgis.gis import GIS

# Import our modules
from utils.auth import connect_to_gis
from utils.folder_collector import collect_items_from_folder
from utils.item_analyzer import analyze_dependencies, classify_items
from utils.id_mapper import IDMapper
from utils.json_handler import save_json
from config.solution_config import CloneOrder

# Import cloners (will be created from existing scripts)
from cloners.feature_layer_cloner import FeatureLayerCloner
# from cloners.view_layer_cloner import ViewLayerCloner
# from cloners.join_view_cloner import JoinViewCloner
# from cloners.webmap_cloner import WebMapCloner
# from cloners.instant_app_cloner import InstantAppCloner
# from cloners.dashboard_cloner import DashboardCloner
# from cloners.experience_builder_cloner import ExperienceBuilderCloner


# ================================================================================================
# CONFIGURATION VARIABLES - MODIFY THESE FOR YOUR SOLUTION
# ================================================================================================

# Source Organization Configuration
SOURCE_URL = "https://www.arcgis.com"  # Source ArcGIS Online URL
SOURCE_USERNAME = "gargarcia"  # Source username
SOURCE_PASSWORD = "xxx"  # Source password
SOURCE_FOLDER = "json clone content"  # Folder containing items to clone (use "root" for root folder)

# Destination Organization Configuration  
DEST_URL = "https://www.arcgis.com"  # Destination ArcGIS Online URL
DEST_USERNAME = "gogarcia"  # Destination username
DEST_PASSWORD = "xxx"  # Destination password
DEST_FOLDER = "test json clone content"  # Folder to create/use in destination

# Cloning Options
CLONE_DATA = True  # Whether to copy data for feature layers
CREATE_DUMMY_FEATURES = True  # Create dummy features for symbology (feature layers)
PRESERVE_ITEM_IDS = False  # Try to preserve original item IDs (requires admin)
SKIP_EXISTING = True  # Skip items that already exist in destination
ROLLBACK_ON_ERROR = True  # Delete all created items if any error occurs

# Output Options
JSON_OUTPUT_DIR = Path(__file__).parent.parent / "json_files"  # Where to save JSON extracts
LOG_LEVEL = logging.INFO  # Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_FILE = f"solution_clone_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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
            # 'View Service': ViewLayerCloner(),
            # 'Join View': JoinViewCloner(),
            # 'Web Map': WebMapCloner(),
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
        
        if DEST_FOLDER not in folder_names:
            self.logger.info(f"Creating destination folder: {DEST_FOLDER}")
            try:
                # Try newer API (2.3+)
                self.dest_gis.content.folders.create(DEST_FOLDER, owner=user.username)
            except AttributeError:
                # Fall back to older API (<2.3)
                self.dest_gis.content.create_folder(DEST_FOLDER, owner=user.username)
            
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
                cloner = self.get_cloner_for_type(item_type)
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
                    self.logger.info(f"Successfully cloned: {title} -> {new_item.id}")
                else:
                    self.logger.error(f"Failed to clone: {title}")
                    
            except Exception as e:
                self.logger.error(f"Error cloning item {item.get('title', 'Unknown')}: {str(e)}")
                if ROLLBACK_ON_ERROR:
                    self.rollback()
                    raise
                    
        return level_mapping
        
    def get_cloner_for_type(self, item_type: str):
        """Get the appropriate cloner for an item type."""
        # Direct match
        if item_type in self.cloners:
            return self.cloners[item_type]
            
        # Pattern matching for complex types
        if 'Dashboard' in item_type:
            return self.cloners['Dashboard']
        elif 'Experience' in item_type or 'ExB' in item_type:
            return self.cloners['Experience Builder']
        elif 'Instant App' in item_type:
            return self.cloners['Instant App']
            
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
    print("ArcGIS Online Solution Cloner")
    print("=" * 50)
    print(f"Source: {SOURCE_USERNAME} / Folder: {SOURCE_FOLDER}")
    print(f"Destination: {DEST_USERNAME} / Folder: {DEST_FOLDER}")
    print("=" * 50)
    
    cloner = SolutionCloner()
    cloner.clone_solution()


if __name__ == "__main__":
    main()