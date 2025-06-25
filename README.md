# ArcGIS Online Solution Cloner

A comprehensive Python toolkit for cloning ArcGIS Online content including feature layers, web maps, applications, and Hub sites.

## Overview

This repository contains two approaches to cloning ArcGIS Online content:

1. **Legacy Individual Scripts** - Standalone scripts for cloning specific item types
2. **Solution Cloner Framework** (Recommended) - A modular, orchestrated approach for cloning entire solutions

## Solution Cloner Framework

The recommended approach for cloning ArcGIS Online content. Located in the `solution_cloner/` directory.

### Features

- **Automatic Dependency Resolution**: Clones items in the correct order based on dependencies
- **Cross-Organization Support**: Clone content between different ArcGIS organizations
- **ID/URL Mapping**: Automatically updates all references in dependent items
- **Folder-Based Discovery**: Clone entire folders without specifying individual items
- **Modular Architecture**: Easy to extend with new item type cloners

### Supported Item Types

- ✅ **Feature Layers**: Complete schema, symbology, relationships, and dummy feature seeding
- ✅ **Views**: Field visibility, filters, parent layer references, enhanced reliability
- ✅ **Join Views**: Proper geometry handling, join definitions, and cardinality
- ✅ **Web Maps**: Operational layer updates, URL replacement with fallback resolution
- ✅ **Instant Apps**: Web map reference updates, cross-organization support
- ✅ **Experience Builder**: Complete app cloning with data source and widget updates
- ✅ **Hub Sites**: Group creation, domain registration, cross-organization support
- ✅ **Hub Pages**: Slug generation, bidirectional site-page relationships
- ✅ **Survey123 Forms**: Complete form cloning with feature service references
- 🚧 **Dashboards**: In development

### Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Create a `.env` file based on `.env.template`:
   ```env
   # Source Organization
   SOURCE_URL=https://www.arcgis.com
   SOURCE_USERNAME=your_source_username
   SOURCE_PASSWORD=your_source_password
   SOURCE_FOLDER=Source Folder Name

   # Destination Organization
   DEST_URL=https://www.arcgis.com
   DEST_USERNAME=your_dest_username
   DEST_PASSWORD=your_dest_password
   DEST_FOLDER=Destination Folder Name
   ```

3. **Run the Cloner**:
   ```bash
   python solution_cloner/solution_cloner.py
   ```

### Architecture

- **Orchestrator**: `solution_cloner.py` - Main entry point that coordinates the cloning process
- **Base Classes**: `base/` - Abstract base cloner defining the common interface
- **Item Cloners**: `cloners/` - Specific implementations for each ArcGIS item type
- **Utilities**: `utils/` - Shared functionality for auth, JSON handling, ID mapping, etc.

## Legacy Scripts

Individual scripts for cloning specific item types. These are located in the root directory and prefixed with `recreate_`.

### Available Scripts

- `recreate_FeatureLayer_by_json.py` - Clone feature layers with symbology
- `recreate_View_by_json.py` - Clone views with field visibility
- `recreate_JoinView_by_json.py` - Clone join views with relationships
- `recreate_WebMap_by_json.py` - Clone web maps with layer references
- `recreate_InstantApp_by_json.py` - Clone instant apps
- `recreate_Dashboard_by_json.py` - Clone dashboards
- `recreate_ExperienceBuilder_by_json.py` - Clone Experience Builder apps
- `recreate_hub_site_and_pages.py` - Clone Hub sites and pages

### Usage

Each script requires modifying constants at the top of the file:
```python
USERNAME = "your_username"
PASSWORD = "your_password"
SOURCE_ITEM_ID = "source_item_id_here"
```

## Documentation

- [Solution Cloner Plan](solution_cloner_plan.md) - Overall architecture and design
- [Hub Cloning Plan](hub_cloning_plan.md) - Hub site cloning implementation details
- [ID Mapping Implementation](ID_MAPPING_IMPLEMENTATION.md) - How references are updated
- [View Cloning Implementation](VIEW_CLONING_IMPLEMENTATION.md) - View cloning specifics
- [Web Map Cloning Issues](WEB_MAP_CLONING_ISSUES.md) - Known issues and solutions
- [Processing Flow](PROCESSING_FLOW.md) - Detailed cloning workflow

## Recent Improvements (June 2025)

- **Enhanced View Reliability**: Implemented exponential backoff for view layer definitions with forced URL mapping fallback
- **Experience Builder Support**: Full cloning with automatic data source updates and draft config synchronization
- **Improved URL Resolution**: Web maps now use item ID lookups when direct URL mapping fails
- **Better Error Handling**: Clear warnings when views fail to configure properly
- **Post-Clone Validation**: Automatic detection of remaining source organization references

## Known Issues

### Hub Catalog Migration
Hub sites clone successfully but pages may appear in the "Migration" tab due to new catalogV2 permissions. Manual catalog configuration may be required in the Hub UI.

### Deprecated APIs
Some sharing APIs are deprecated in newer versions of the ArcGIS Python API. The cloner continues to work but may show deprecation warnings.

### View Configuration Timing
Views may occasionally appear empty if the view service takes longer to initialize. The cloner will still map URLs correctly, but field visibility may need manual configuration.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.
