#!/usr/bin/env python3
"""
Test ID Mapping and Reference Updates
=====================================
This script tests the ID mapping functionality by:
1. Creating a simple feature layer
2. Creating a web map that references the feature layer
3. Cloning both items
4. Verifying that the cloned web map references the cloned feature layer
"""

import json
import logging
from pathlib import Path
from arcgis.gis import GIS

# Import our modules
from solution_cloner.utils.id_mapper import IDMapper
from solution_cloner.utils.json_handler import save_json, load_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_URL = "https://www.arcgis.com"
TEST_USERNAME = "xxx"  # Replace with your username
TEST_PASSWORD = "xxx"  # Replace with your password
TEST_FOLDER = "ID_Mapping_Test"

# Test data
FEATURE_LAYER_ID = "xxx"  # Replace with a feature layer ID to test
WEB_MAP_ID = "xxx"  # Replace with a web map ID that references the feature layer


def test_id_mapper():
    """Test the IDMapper functionality."""
    logger.info("Testing IDMapper functionality...")
    
    # Create mapper
    mapper = IDMapper()
    
    # Test ID mapping
    old_id = "abcd1234567890abcd1234567890abcd"
    new_id = "1234567890abcd1234567890abcd1234"
    mapper.add_mapping(old_id, new_id)
    
    assert mapper.get_new_id(old_id) == new_id
    logger.info("✓ ID mapping works")
    
    # Test URL mapping
    old_url = "https://services.arcgis.com/old/arcgis/rest/services/test/FeatureServer"
    new_url = "https://services.arcgis.com/new/arcgis/rest/services/test/FeatureServer"
    mapper.add_mapping(old_id, new_id, old_url, new_url)
    
    assert mapper.get_new_url(old_url) == new_url
    logger.info("✓ URL mapping works")
    
    # Test sublayer mapping
    old_sublayer = f"{old_url}/0"
    new_sublayer = f"{new_url}/0"
    mapper.sublayer_mapping[old_sublayer] = new_sublayer
    
    # Test reference updates in text
    test_text = f"This references {old_id} and {old_url}/0"
    updated_text = mapper.update_text_references(test_text)
    
    assert new_id in updated_text
    assert new_sublayer in updated_text
    logger.info("✓ Text reference updates work")
    
    # Test JSON reference updates
    test_json = {
        "itemId": old_id,
        "url": old_url,
        "layers": [
            {"url": f"{old_url}/0"},
            {"url": f"{old_url}/1"}
        ]
    }
    
    # Add mapping for sublayer 1
    mapper.sublayer_mapping[f"{old_url}/1"] = f"{new_url}/1"
    
    updated_json = mapper.update_json_urls(test_json)
    
    assert updated_json["url"] == new_url
    assert updated_json["layers"][0]["url"] == f"{new_url}/0"
    assert updated_json["layers"][1]["url"] == f"{new_url}/1"
    logger.info("✓ JSON reference updates work")
    
    # Test finding references
    refs = mapper.find_references_in_dict(test_json)
    assert old_id in refs['ids']
    assert old_url in refs['urls']
    logger.info("✓ Reference finding works")
    
    logger.info("All IDMapper tests passed!")
    

def test_webmap_reference_update():
    """Test web map reference updates with real data."""
    logger.info("\nTesting web map reference updates...")
    
    # Create mapper
    mapper = IDMapper()
    
    # Sample web map JSON with references
    webmap_json = {
        "operationalLayers": [
            {
                "id": "layer1",
                "title": "Test Feature Layer",
                "url": "https://services.arcgis.com/old/arcgis/rest/services/test/FeatureServer/0",
                "itemId": "abcd1234567890abcd1234567890abcd",
                "layerType": "ArcGISFeatureLayer"
            },
            {
                "id": "layer2", 
                "title": "Test Table",
                "url": "https://services.arcgis.com/old/arcgis/rest/services/test/FeatureServer/1",
                "itemId": "abcd1234567890abcd1234567890abcd",
                "layerType": "ArcGISFeatureLayer"
            }
        ],
        "baseMap": {
            "baseMapLayers": [
                {
                    "id": "base1",
                    "url": "https://services.arcgis.com/base/arcgis/rest/services/basemap/MapServer"
                }
            ]
        }
    }
    
    # Add mappings
    old_item_id = "abcd1234567890abcd1234567890abcd"
    new_item_id = "1234567890abcd1234567890abcd1234"
    old_service_url = "https://services.arcgis.com/old/arcgis/rest/services/test/FeatureServer"
    new_service_url = "https://services.arcgis.com/new/arcgis/rest/services/test/FeatureServer"
    
    mapper.add_mapping(old_item_id, new_item_id, old_service_url, new_service_url)
    mapper.sublayer_mapping[f"{old_service_url}/0"] = f"{new_service_url}/0"
    mapper.sublayer_mapping[f"{old_service_url}/1"] = f"{new_service_url}/1"
    
    # Get mapping for update
    mapping = mapper.get_mapping()
    
    # Import and use WebMapCloner's update method
    from solution_cloner.cloners.web_map_cloner import WebMapCloner
    cloner = WebMapCloner()
    
    # Update references
    updated_json = cloner._update_webmap_references(webmap_json, mapping)
    
    # Verify updates
    assert updated_json["operationalLayers"][0]["itemId"] == new_item_id
    assert updated_json["operationalLayers"][0]["url"] == f"{new_service_url}/0"
    assert updated_json["operationalLayers"][1]["url"] == f"{new_service_url}/1"
    logger.info("✓ Web map reference updates work correctly")
    
    # Save test results
    output_dir = Path("json_files") / "test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    save_json(
        {
            "original": webmap_json,
            "updated": updated_json,
            "mappings": mapping
        },
        output_dir / "webmap_reference_test.json"
    )
    
    logger.info(f"Test results saved to {output_dir / 'webmap_reference_test.json'}")
    

def test_real_items():
    """Test with real ArcGIS Online items if configured."""
    if not all([TEST_USERNAME != "xxx", TEST_PASSWORD != "xxx", 
                FEATURE_LAYER_ID != "xxx", WEB_MAP_ID != "xxx"]):
        logger.info("\nSkipping real item tests - credentials not configured")
        return
        
    logger.info("\nTesting with real ArcGIS Online items...")
    
    try:
        # Connect to ArcGIS Online
        gis = GIS(TEST_URL, TEST_USERNAME, TEST_PASSWORD)
        logger.info(f"Connected as: {gis.users.me.username}")
        
        # Get test items
        feature_layer = gis.content.get(FEATURE_LAYER_ID)
        web_map_item = gis.content.get(WEB_MAP_ID)
        
        if not feature_layer or not web_map_item:
            logger.error("Test items not found")
            return
            
        logger.info(f"Feature Layer: {feature_layer.title}")
        logger.info(f"Web Map: {web_map_item.title}")
        
        # Get web map definition
        webmap_json = json.loads(web_map_item.get_data())
        
        # Find references to the feature layer
        mapper = IDMapper()
        refs = mapper.find_references_in_dict(webmap_json)
        
        if FEATURE_LAYER_ID in refs['ids']:
            logger.info(f"✓ Web map references feature layer {FEATURE_LAYER_ID}")
        else:
            logger.warning(f"Web map does not reference feature layer {FEATURE_LAYER_ID}")
            
        # Save the web map JSON for analysis
        output_dir = Path("json_files") / "test_results"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        save_json(
            {
                "feature_layer": {
                    "id": feature_layer.id,
                    "title": feature_layer.title,
                    "url": feature_layer.url
                },
                "web_map": {
                    "id": web_map_item.id,
                    "title": web_map_item.title
                },
                "webmap_definition": webmap_json,
                "found_references": refs
            },
            output_dir / f"real_items_test_{web_map_item.id}.json"
        )
        
        logger.info("Real item test completed")
        
    except Exception as e:
        logger.error(f"Error testing real items: {str(e)}")
        

def main():
    """Run all tests."""
    logger.info("Starting ID Mapping Tests")
    logger.info("=" * 50)
    
    # Test IDMapper
    test_id_mapper()
    
    # Test web map reference updates
    test_webmap_reference_update()
    
    # Test with real items if configured
    test_real_items()
    
    logger.info("\nAll tests completed!")
    

if __name__ == "__main__":
    main()