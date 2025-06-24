# ID Mapping Implementation

## Overview

The ID mapping system tracks relationships between source and cloned ArcGIS Online items, enabling proper reference updates when cloning complex solutions with interdependencies.

## Architecture

### Core Components

1. **IDMapper** (`solution_cloner/utils/id_mapper.py`)
   - Tracks four types of mappings:
     - Item IDs (old → new)
     - Full URLs (service URLs)
     - Service base URLs
     - Sublayer URLs (e.g., `/0`, `/1`)
   - Provides methods to update references in text and JSON

2. **FeatureLayerCloner** 
   - Enhanced with `_track_service_urls()` method
   - Records service and sublayer URLs during cloning
   - Provides mapping data via `get_last_mapping_data()`

3. **WebMapCloner** (new)
   - Implements reference updates for web maps
   - Updates operational layers, basemaps, and tables
   - Supports both pre-creation and post-creation updates

4. **FormCloner** (new)
   - Handles Survey123 forms that reference feature services/views
   - Downloads and updates form ZIP packages
   - Updates service references in .webform JSON files
   - Maintains Survey2Service relationships

## How It Works

### 1. During Feature Layer Cloning

```python
# FeatureLayerCloner tracks URLs
mapping_data = {
    'id': 'new_item_id',
    'url': 'https://services.arcgis.com/new/rest/services/Service/FeatureServer',
    'sublayer_urls': {
        '.../old/FeatureServer/0': '.../new/FeatureServer/0',
        '.../old/FeatureServer/1': '.../new/FeatureServer/1'
    }
}
```

### 2. ID Mapper Storage

The solution cloner adds these mappings:

```python
# Item ID mapping
id_mapper.add_mapping(old_id, new_id, old_url, new_url)

# Sublayer URL mappings
for old_url, new_url in sublayer_urls.items():
    id_mapper.sublayer_mapping[old_url] = new_url
```

### 3. Reference Updates in Web Maps

The WebMapCloner updates:
- `operationalLayers[].itemId` - Feature layer item IDs
- `operationalLayers[].url` - Feature service sublayer URLs
- `tables[].itemId` and `tables[].url` - Table references
- `baseMap.baseMapLayers[]` - Basemap references (if cloned)

### 4. Reference Updates in Forms

The FormCloner updates:
- Service URLs in .webform JSON files within the ZIP package
- Item relationship (Survey2Service) to point to cloned feature service
- `submissionUrl` and `serviceUrl` in item properties

## Update Strategies

### Option 1: Post-Creation Updates (Default)
1. Clone all items first
2. Update references after all items exist
3. Advantage: All items available for reference

### Option 2: Pre-Creation Updates
1. Clone items in dependency order
2. Update references before creating dependent items
3. Advantage: Items created with correct references
4. Enable with: `UPDATE_REFS_BEFORE_CREATE = True`

## Mapping Data Structure

```json
{
  "ids": {
    "old_item_id": "new_item_id"
  },
  "urls": {
    "https://old/FeatureServer": "https://new/FeatureServer"
  },
  "services": {
    "https://old/FeatureServer": "https://new/FeatureServer"
  },
  "sublayers": {
    "https://old/FeatureServer/0": "https://new/FeatureServer/0",
    "https://old/FeatureServer/1": "https://new/FeatureServer/1"
  }
}
```

## Usage Example

```python
# Initialize components
id_mapper = IDMapper()
feature_cloner = FeatureLayerCloner()
webmap_cloner = WebMapCloner()

# Clone feature layer
new_feature = feature_cloner.clone(...)

# Track mappings
id_mapper.add_mapping(old_id, new_id, old_url, new_url)

# Clone web map with mappings
new_webmap = webmap_cloner.clone(
    ...,
    id_mapping=id_mapper.get_mapping()
)

# Update references (if post-creation)
webmap_cloner.update_references(
    new_webmap,
    id_mapper.get_mapping(),
    gis
)
```

## Testing

Run `test_id_mapping.py` to verify:
- ID mapping functionality
- URL mapping and updates
- Web map reference updates
- Reference finding in JSON structures

## Cloning Order Hierarchy

Items are cloned in the following dependency order:

1. **Level 0 - Base Data Layers** (no dependencies)
   - Feature Service
   - Table
   - Map Service
   - Vector Tile Service
   - Image Service
   - Scene Service

2. **Level 1 - View Layers** (depend on feature services)
   - View Service / View

3. **Level 2 - Join Views** (depend on feature services/views)
   - Join View

4. **Level 3 - Forms & Maps** (depend on layers)
   - Form (Survey123)
   - Web Map
   - Web Scene

5. **Level 4 - Applications** (depend on maps/layers)
   - Dashboard
   - Web Mapping Application
   - Instant App
   - StoryMap

6. **Level 5 - Complex Applications** (may depend on various items)
   - Experience Builder

7. **Level 6 - Notebooks** (may reference any items)
   - Notebook

## Next Steps

1. **Dashboard Cloner**: Implement reference updates for dashboard widgets
2. **Experience Builder Cloner**: Handle data source configurations
3. **Join View Cloner**: Update source layer references
4. **Validation**: Add methods to verify all references are mapped
5. **Reporting**: Generate detailed mapping reports