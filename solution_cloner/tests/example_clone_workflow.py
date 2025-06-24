#!/usr/bin/env python3
"""
Example Cloning Workflow
========================
This script demonstrates how to clone a feature layer and a web map that references it,
with proper ID and URL mapping so the cloned web map references the cloned feature layer.

This example shows:
1. Cloning a feature layer
2. Tracking its new ID and URLs
3. Cloning a web map
4. Updating the web map to reference the cloned feature layer
"""

import logging
from pathlib import Path
from arcgis.gis import GIS

# Import our cloning modules
from solution_cloner.utils.auth import connect_to_gis
from solution_cloner.utils.id_mapper import IDMapper
from solution_cloner.utils.json_handler import save_json
from solution_cloner.cloners.feature_layer_cloner import FeatureLayerCloner
from solution_cloner.cloners.web_map_cloner import WebMapCloner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====
# Source items to clone
SOURCE_FEATURE_LAYER_ID = "xxx"  # Replace with your feature layer ID
SOURCE_WEB_MAP_ID = "xxx"  # Replace with your web map ID that references the feature layer

# Source organization
SOURCE_URL = "https://www.arcgis.com"
SOURCE_USERNAME = "xxx"  # Replace with your username
SOURCE_PASSWORD = "xxx"  # Replace with your password

# Destination organization
DEST_URL = "https://www.arcgis.com"
DEST_USERNAME = "xxx"  # Replace with your username
DEST_PASSWORD = "xxx"  # Replace with your password
DEST_FOLDER = "Clone_Example"  # Folder to create/use in destination

# Output directory for JSON files
JSON_OUTPUT_DIR = Path("json_files") / "example_workflow"
JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# =========================


def main():
    """Run the example cloning workflow."""
    logger.info("Starting Example Cloning Workflow")
    logger.info("=" * 50)
    
    # Connect to source and destination
    logger.info("Connecting to source organization...")
    source_gis = GIS(SOURCE_URL, SOURCE_USERNAME, SOURCE_PASSWORD)
    logger.info(f"Connected as: {source_gis.users.me.username}")
    
    logger.info("Connecting to destination organization...")
    dest_gis = GIS(DEST_URL, DEST_USERNAME, DEST_PASSWORD)
    logger.info(f"Connected as: {dest_gis.users.me.username}")
    
    # Create/get destination folder
    logger.info(f"Setting up destination folder: {DEST_FOLDER}")
    dest_user = dest_gis.users.me
    existing_folders = [f['title'] for f in dest_user.folders]
    if DEST_FOLDER not in existing_folders:
        folder_result = dest_gis.content.create_folder(DEST_FOLDER)
        if folder_result['success']:
            logger.info(f"Created folder: {DEST_FOLDER}")
        else:
            logger.error(f"Failed to create folder: {DEST_FOLDER}")
            return
    
    # Initialize ID mapper and cloners
    id_mapper = IDMapper()
    feature_cloner = FeatureLayerCloner()
    webmap_cloner = WebMapCloner(JSON_OUTPUT_DIR, update_refs_before_create=False)
    
    # Step 1: Clone the feature layer
    logger.info("\n" + "="*50)
    logger.info("STEP 1: Clone Feature Layer")
    logger.info("="*50)
    
    # Get source feature layer
    src_feature_layer = source_gis.content.get(SOURCE_FEATURE_LAYER_ID)
    if not src_feature_layer:
        logger.error(f"Feature layer {SOURCE_FEATURE_LAYER_ID} not found")
        return
        
    logger.info(f"Source feature layer: {src_feature_layer.title}")
    
    # Clone it
    feature_item_dict = {
        'id': src_feature_layer.id,
        'title': src_feature_layer.title,
        'type': src_feature_layer.type,
        'url': src_feature_layer.url
    }
    
    new_feature_layer = feature_cloner.clone(
        source_item=feature_item_dict,
        source_gis=source_gis,
        dest_gis=dest_gis,
        dest_folder=DEST_FOLDER,
        id_mapping={},  # Empty for first item
        clone_data=True,
        create_dummy_features=True
    )
    
    if not new_feature_layer:
        logger.error("Failed to clone feature layer")
        return
        
    logger.info(f"Cloned feature layer: {new_feature_layer.title} ({new_feature_layer.id})")
    
    # Track the ID mapping
    id_mapper.add_mapping(
        src_feature_layer.id, 
        new_feature_layer.id,
        src_feature_layer.url,
        new_feature_layer.url
    )
    
    # Get detailed URL mappings from the cloner
    if hasattr(feature_cloner, 'get_last_mapping_data'):
        mapping_data = feature_cloner.get_last_mapping_data()
        if mapping_data and 'sublayer_urls' in mapping_data:
            for old_url, new_url in mapping_data['sublayer_urls'].items():
                id_mapper.sublayer_mapping[old_url] = new_url
                logger.info(f"Tracked sublayer: {old_url} -> {new_url}")
    
    # Save mapping so far
    save_json(
        id_mapper.get_mapping(),
        JSON_OUTPUT_DIR / "id_mapping_after_feature_layer.json"
    )
    
    # Step 2: Clone the web map
    logger.info("\n" + "="*50)
    logger.info("STEP 2: Clone Web Map")
    logger.info("="*50)
    
    # Get source web map
    src_web_map = source_gis.content.get(SOURCE_WEB_MAP_ID)
    if not src_web_map:
        logger.error(f"Web map {SOURCE_WEB_MAP_ID} not found")
        return
        
    logger.info(f"Source web map: {src_web_map.title}")
    
    # Clone it with current mappings
    webmap_item_dict = {
        'id': src_web_map.id,
        'title': src_web_map.title,
        'type': src_web_map.type
    }
    
    new_web_map = webmap_cloner.clone(
        source_item=webmap_item_dict,
        source_gis=source_gis,
        dest_gis=dest_gis,
        dest_folder=DEST_FOLDER,
        id_mapping=id_mapper.get_mapping()  # Pass current mappings
    )
    
    if not new_web_map:
        logger.error("Failed to clone web map")
        return
        
    logger.info(f"Cloned web map: {new_web_map.title} ({new_web_map.id})")
    
    # Track the web map ID mapping
    id_mapper.add_mapping(src_web_map.id, new_web_map.id)
    
    # Step 3: Update references in the web map
    logger.info("\n" + "="*50)
    logger.info("STEP 3: Update Web Map References")
    logger.info("="*50)
    
    # Since we set update_refs_before_create=False, we need to update after creation
    success = webmap_cloner.update_references(
        new_web_map,
        id_mapper.get_mapping(),
        dest_gis
    )
    
    if success:
        logger.info("Successfully updated web map references")
    else:
        logger.error("Failed to update web map references")
    
    # Save final mapping
    final_mapping = id_mapper.get_mapping()
    save_json(
        final_mapping,
        JSON_OUTPUT_DIR / "id_mapping_final.json"
    )
    
    # Generate summary report
    logger.info("\n" + "="*50)
    logger.info("CLONING SUMMARY")
    logger.info("="*50)
    
    logger.info("\nCloned Items:")
    logger.info(f"1. Feature Layer: {src_feature_layer.title}")
    logger.info(f"   Old ID: {src_feature_layer.id}")
    logger.info(f"   New ID: {new_feature_layer.id}")
    logger.info(f"   Old URL: {src_feature_layer.url}")
    logger.info(f"   New URL: {new_feature_layer.url}")
    
    logger.info(f"\n2. Web Map: {src_web_map.title}")
    logger.info(f"   Old ID: {src_web_map.id}")
    logger.info(f"   New ID: {new_web_map.id}")
    
    logger.info("\nID Mappings:")
    for old_id, new_id in final_mapping['ids'].items():
        logger.info(f"   {old_id} -> {new_id}")
        
    logger.info("\nURL Mappings:")
    for old_url, new_url in final_mapping['urls'].items():
        logger.info(f"   {old_url} -> {new_url}")
        
    logger.info("\nSublayer Mappings:")
    for old_url, new_url in final_mapping['sublayers'].items():
        logger.info(f"   {old_url} -> {new_url}")
    
    logger.info(f"\nAll JSON outputs saved to: {JSON_OUTPUT_DIR}")
    logger.info("\nWorkflow completed successfully!")


if __name__ == "__main__":
    # Check if configuration is set
    if SOURCE_FEATURE_LAYER_ID == "xxx" or SOURCE_WEB_MAP_ID == "xxx":
        logger.error("Please configure the source item IDs before running")
        logger.error("Edit SOURCE_FEATURE_LAYER_ID and SOURCE_WEB_MAP_ID in this script")
    elif SOURCE_USERNAME == "xxx" or DEST_USERNAME == "xxx":
        logger.error("Please configure the credentials before running")
        logger.error("Edit the username and password variables in this script")
    else:
        main()