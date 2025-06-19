#!/usr/bin/env python3
"""
Test View and Join View Cloning
================================
This script tests the detection and cloning of view layers and join view layers.
"""

import sys
from pathlib import Path
# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

import logging
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection

# Import our modules
from solution_cloner.utils.id_mapper import IDMapper
from solution_cloner.cloners.view_cloner import ViewCloner
from solution_cloner.cloners.join_view_cloner import JoinViewCloner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration - using credentials from recreate_Views_by_json.py
TEST_URL = "https://www.arcgis.com"
TEST_USERNAME = "gargarcia"
TEST_PASSWORD = "GOGpas5252***"  # From the script
TEST_FOLDER = "View_Clone_Test"

# Test IDs
VIEW_ID = "f2cc9a9d588446309eafb81698621ed5"  # From recreate_Views_by_json.py
JOIN_VIEW_ID = "0aef75cb383448c5a94efa802bfe6954"  # From recreate_JoinView_by_json.py

# Output directory
OUTPUT_DIR = Path("json_files") / "view_test_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_view_detection():
    """Test detection of views vs regular feature layers."""
    logger.info("Testing view detection...")
    
    try:
        # Connect to ArcGIS Online
        gis = GIS(TEST_URL, TEST_USERNAME, TEST_PASSWORD)
        logger.info(f"Connected as: {gis.users.me.username}")
        
        # Test items
        test_items = [
            {"name": "View Layer", "id": VIEW_ID},
            {"name": "Join View", "id": JOIN_VIEW_ID}
        ]
        
        for test_item in test_items:
            item = gis.content.get(test_item['id'])
            if not item:
                logger.error(f"{test_item['name']} not found: {test_item['id']}")
                continue
                
            logger.info(f"\nAnalyzing: {item.title}")
            logger.info(f"  Type: {item.type}")
            logger.info(f"  TypeKeywords: {item.typeKeywords[:5]}...")  # First 5 keywords
            
            # Check if it's a view
            flc = FeatureLayerCollection.fromitem(item)
            is_view = getattr(flc.properties, "isView", False)
            logger.info(f"  isView property: {is_view}")
            
            # Test if it's a join view
            if is_view and test_item['name'] == 'Join View':
                join_cloner = JoinViewCloner(OUTPUT_DIR)
                is_join = join_cloner.is_join_view(item, gis)
                logger.info(f"  Is join view: {is_join}")
                
        logger.info("\nView detection test completed!")
        
    except Exception as e:
        logger.error(f"Error in view detection test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def test_view_cloning():
    """Test cloning a view layer."""
    logger.info("\nTesting view layer cloning...")
    
    try:
        # Connect
        gis = GIS(TEST_URL, TEST_USERNAME, TEST_PASSWORD)
        logger.info(f"Connected as: {gis.users.me.username}")
        
        # Get the view
        view_item = gis.content.get(VIEW_ID)
        if not view_item:
            logger.error(f"View not found: {VIEW_ID}")
            return
            
        logger.info(f"Source view: {view_item.title}")
        
        # Initialize components
        id_mapper = IDMapper()
        view_cloner = ViewCloner(OUTPUT_DIR)
        
        # Create test folder
        user = gis.users.me
        existing_folders = [f.get('title', f) for f in user.folders if isinstance(f, dict)] or [str(f) for f in user.folders]
        if TEST_FOLDER not in existing_folders:
            gis.content.create_folder(TEST_FOLDER)
            logger.info(f"Created folder: {TEST_FOLDER}")
            
        # Clone the view
        view_dict = {
            'id': view_item.id,
            'title': view_item.title,
            'type': view_item.type
        }
        
        new_view = view_cloner.clone(
            source_item=view_dict,
            source_gis=gis,
            dest_gis=gis,
            dest_folder=TEST_FOLDER,
            id_mapping={}
        )
        
        if new_view:
            logger.info(f"Successfully cloned view: {new_view.title} ({new_view.id})")
            
            # Track mapping
            id_mapper.add_mapping(view_item.id, new_view.id, view_item.url, new_view.url)
            
            # Get URL mappings
            if hasattr(view_cloner, 'get_last_mapping_data'):
                mapping_data = view_cloner.get_last_mapping_data()
                if mapping_data and 'sublayer_urls' in mapping_data:
                    for old_url, new_url in mapping_data['sublayer_urls'].items():
                        id_mapper.sublayer_mapping[old_url] = new_url
                        logger.info(f"  Mapped: {old_url} -> {new_url}")
                        
            # Verify it's a view
            new_flc = FeatureLayerCollection.fromitem(new_view)
            is_view = getattr(new_flc.properties, "isView", False)
            logger.info(f"  New item isView: {is_view}")
            
            # Check field visibility was applied
            if new_flc.layers:
                layer = new_flc.layers[0]
                if hasattr(layer.properties, 'fields'):
                    field_count = len(layer.properties.fields)
                    logger.info(f"  Fields in cloned view: {field_count}")
                    
        else:
            logger.error("Failed to clone view")
            
    except Exception as e:
        logger.error(f"Error cloning view: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def test_join_view_cloning():
    """Test cloning a join view layer."""
    logger.info("\nTesting join view cloning...")
    
    try:
        # Connect
        gis = GIS(TEST_URL, TEST_USERNAME, TEST_PASSWORD)
        logger.info(f"Connected as: {gis.users.me.username}")
        
        # Get the join view
        join_view_item = gis.content.get(JOIN_VIEW_ID)
        if not join_view_item:
            logger.error(f"Join view not found: {JOIN_VIEW_ID}")
            return
            
        logger.info(f"Source join view: {join_view_item.title}")
        
        # Initialize components
        id_mapper = IDMapper()
        join_cloner = JoinViewCloner(OUTPUT_DIR)
        
        # Clone the join view
        join_dict = {
            'id': join_view_item.id,
            'title': join_view_item.title,
            'type': join_view_item.type
        }
        
        new_join_view = join_cloner.clone(
            source_item=join_dict,
            source_gis=gis,
            dest_gis=gis,
            dest_folder=TEST_FOLDER,
            id_mapping={}  # Empty since we're not mapping the source layers
        )
        
        if new_join_view:
            logger.info(f"Successfully cloned join view: {new_join_view.title} ({new_join_view.id})")
            
            # Track mapping
            id_mapper.add_mapping(join_view_item.id, new_join_view.id, join_view_item.url, new_join_view.url)
            
            # Verify it's a view
            new_flc = FeatureLayerCollection.fromitem(new_join_view)
            is_view = getattr(new_flc.properties, "isView", False)
            logger.info(f"  New item isView: {is_view}")
            
            # Check if it's detected as join view
            is_join = join_cloner.is_join_view(new_join_view, gis)
            logger.info(f"  Detected as join view: {is_join}")
            
        else:
            logger.error("Failed to clone join view")
            
    except Exception as e:
        logger.error(f"Error cloning join view: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def test_type_detection_simple():
    """Simple test for type detection logic."""
    logger.info("\nTesting type detection logic...")
    
    try:
        # Connect
        gis = GIS(TEST_URL, TEST_USERNAME, TEST_PASSWORD)
        
        # Test with actual items
        test_ids = [VIEW_ID, JOIN_VIEW_ID]
        
        for item_id in test_ids:
            item = gis.content.get(item_id)
            if not item:
                continue
                
            # Check if it's a view
            from arcgis.features import FeatureLayerCollection
            flc = FeatureLayerCollection.fromitem(item)
            
            is_view = getattr(flc.properties, "isView", False)
            detected_type = "Feature Service"
            
            if is_view:
                detected_type = "View"
                # Check if it's a join view
                join_cloner = JoinViewCloner(OUTPUT_DIR)
                if join_cloner.is_join_view(item, gis):
                    detected_type = "Join View"
                    
            logger.info(f"{item.title}: Type={item.type}, Detected={detected_type}")
            
        logger.info("\nType detection test completed!")
        
    except Exception as e:
        logger.error(f"Error in type detection test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())


def cleanup_test_items(gis, folder_name):
    """Clean up test items created during testing."""
    logger.info("\nCleaning up test items...")
    
    try:
        # Get items in test folder
        user = gis.users.me
        folders = [f for f in user.folders if f['title'] == folder_name]
        
        if folders:
            folder_id = folders[0]['id']
            items = user.items(folder=folder_id)
            
            for item in items:
                if 'clone' in item.title.lower():
                    logger.info(f"Deleting: {item.title}")
                    item.delete()
                    
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


def main():
    """Run all tests."""
    logger.info("Starting View and Join View Cloning Tests")
    logger.info("=" * 60)
    
    # Run tests
    test_view_detection()
    test_view_cloning()
    test_join_view_cloning()
    test_type_detection_simple()
    
    # Optional cleanup
    try:
        gis = GIS(TEST_URL, TEST_USERNAME, TEST_PASSWORD)
        # cleanup_test_items(gis, TEST_FOLDER)
        logger.info("\nNote: Test items were not deleted. Clean up manually if needed.")
    except:
        pass
    
    logger.info("\nAll tests completed!")
    

if __name__ == "__main__":
    main()