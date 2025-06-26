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
- ✅ **Dashboards**: Complete dashboard cloning with widget reference updates
- ✅ **Experience Builder**: Complete app cloning with data source and widget updates
- ✅ **Hub Sites**: Group creation, domain registration, cross-organization support
- ✅ **Hub Pages**: Slug generation, bidirectional site-page relationships
- ✅ **Survey123 Forms**: Complete form cloning with feature service references
- ✅ **Notebooks**: Jupyter notebook cloning with reference updates in code and markdown cells

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

The repository provides two main interfaces for cloning operations: a command-line solution cloner and a web-based interface, both built on the same core cloning framework.

```
Cloning/
├── solution_cloner/              # Core cloning framework
│   ├── solution_cloner.py       # CLI orchestrator entry point
│   ├── base/                    # Base classes
│   │   └── base_cloner.py      # Abstract base cloner interface
│   ├── cloners/                 # Item-specific cloners
│   │   ├── dashboard_cloner.py
│   │   ├── experience_builder_cloner.py
│   │   ├── feature_layer_cloner.py
│   │   ├── form_cloner.py      # Survey123 forms
│   │   ├── hub_page_cloner.py
│   │   ├── hub_site_cloner.py
│   │   ├── instant_app_cloner.py
│   │   ├── join_view_cloner.py
│   │   ├── notebook_cloner.py  # Jupyter notebooks
│   │   ├── view_cloner.py
│   │   └── web_map_cloner.py
│   ├── config/                  # Configuration
│   │   └── solution_config.py
│   ├── utils/                   # Shared utilities
│   │   ├── arcgis_utils.py
│   │   ├── auth_utils.py
│   │   ├── id_mapper.py
│   │   └── json_utils.py
│   └── tests/                   # Test scripts and examples
│       ├── recreate_*.py        # Individual item recreation scripts
│       └── test_*.py            # Unit and integration tests
├── web_interface/               # Flask web application
│   ├── app.py                  # Flask server (uses solution_cloner modules)
│   ├── static/
│   │   └── style.css           # UI styling
│   └── templates/
│       └── index.html          # Web interface template
├── old_clone/                   # Legacy utilities
│   ├── log_into_gis.py         # YAML-based authentication
│   └── *.py                    # Helper scripts
├── Hub examples/                # Hub cloning examples and test data
│   ├── hub.py, pages.py, sites.py
│   └── *_data.json, *_item.json
├── SurveyExamples/             # Survey123 form examples
│   ├── formdata.json
│   └── formitem.json
├── json_files/                  # Extracted JSON configurations (gitignored)
├── .env.template               # Environment variable template
├── requirements.txt            # Python dependencies
└── *.md                        # Documentation files
```

**Usage Options:**
- **Command Line**: `python solution_cloner/solution_cloner.py`
- **Web Interface**: `python web_interface/app.py` (runs on http://localhost:5000)

## Legacy Scripts

Individual scripts for cloning specific item types. These are located in `solution_cloner/tests/` directory.

### Available Scripts

- `recreate_FeatureLayer_by_json.py` - Clone feature layers with symbology
- `recreate_Views_by_json.py` - Clone views with field visibility
- `recreate_JoinView_by_json.py` - Clone join views with relationships
- `recreate_WebMap_by_json.py` - Clone web maps with layer references
- `recreate_InstantApp_by_json.py` - Clone instant apps
- `recreate_Dashboard_by_json.py` - Clone dashboards
- `recreate_ExB_by_json.py` - Clone Experience Builder apps
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
- [Experience Builder Fix](EXPERIENCE_BUILDER_FIX.md) - Experience Builder cloning fixes

## Output and Logging

The solution cloner provides comprehensive logging:
- **Console Output**: Real-time progress updates with color-coded status messages
- **Log Files**: Detailed logs saved as `solution_clone_YYYYMMDD_HHMMSS.log`
- **JSON Dumps**: Extracted configurations saved to `json_files/` directory for debugging
- **ID Mappings**: Source-to-destination ID mappings saved for reference

## Recent Improvements (June 2025)

- **Notebook Support**: Added Jupyter notebook cloning with comprehensive reference updates
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

## License

This project is licensed under the MIT License.
