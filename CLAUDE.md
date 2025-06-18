# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Python-based ArcGIS Online content cloning toolkit that provides scripts to recreate various ArcGIS Online items by extracting their JSON definitions and reconstructing them programmatically. The toolkit handles complex scenarios including join views, feature layers with symbology, web maps, dashboards, and experience builder apps.

## Architecture

### Core Components

- **Recreation Scripts**: Main scripts prefixed with `recreate_` that handle different ArcGIS item types
- **Utility Scripts**: Helper scripts for printing information and version checking
- **Authentication Module**: `old_clone/log_into_gis.py` provides centralized GIS authentication using YAML config
- **JSON Storage**: `json_files/` directory stores extracted configurations and metadata for reference

### Key Patterns

**JSON Extraction & Recreation**: All recreation scripts follow a common pattern:
1. Connect to ArcGIS Online using credentials
2. Extract source item's JSON definition via REST API
3. Save extracted data to `json_files/` with timestamped filenames
4. Create new item using extracted configuration
5. Apply symbology, metadata, and other properties

**Authentication**: Uses `old_clone/log_into_gis.py` which expects a `CityLogins.yaml` config file one directory up containing city-specific credentials.

**Complex Item Handling**: 
- Join views require admin REST API access to extract complete join definitions
- Feature layers handle both service-level and item-level symbology
- Views manage field visibility and source layer relationships

## Development Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running Scripts
Each recreation script requires modifying the top-level constants:
- `USERNAME` and `PASSWORD` for ArcGIS Online credentials
- Item ID constants specific to each script (e.g., `SRC_VIEWID`, `ITEM_ID`)

### Testing Individual Scripts
```bash
python recreate_FeatureLayer_by_json.py
python recreate_JoinView_by_json.py
python recreate_WebMap_by_json.py
# etc.
```

## Important Implementation Details

### Credential Management
- Scripts use placeholder credentials (`"xxx"`) that must be replaced before execution
- The `log_into_gis.py` module provides centralized authentication via YAML config
- Never commit actual credentials to the repository

### JSON File Organization
- All extracted JSON configurations are saved to `json_files/` with descriptive, timestamped names
- Files include source item metadata, service definitions, layer properties, and admin API responses
- These files serve as both debugging aids and reference documentation

### Complex Feature Handling
- **Join Views**: Require admin REST API access to extract complete join definitions including parent/child key relationships
- **Feature Layer Symbology**: Handles both service-level renderers and item-level visualization overrides
- **Dummy Feature Seeding**: Feature layer cloning optionally creates temporary features to ensure symbology applies correctly

### Error Handling
- Scripts use comprehensive logging to track progress and debug issues
- JSON dumps are created at each major step for troubleshooting
- Scripts validate item types and API responses before proceeding