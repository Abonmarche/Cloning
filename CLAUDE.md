# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Python-based ArcGIS Online content cloning toolkit that has evolved from individual recreation scripts to a comprehensive solution cloning framework. The toolkit can:

1. **Individual Item Recreation**: Use standalone scripts to recreate specific ArcGIS Online items by extracting their JSON definitions
2. **Solution Cloning**: Use the modular `solution_cloner/` framework to clone entire ArcGIS Online solutions with automatic dependency resolution and reference updating

The toolkit handles complex scenarios including feature layers with symbology and relationships, views with field visibility, join views with proper geometry, web maps with updated references, instant apps, dashboards, and experience builder apps.

## Architecture

The repository contains two approaches to cloning:

### 1. Legacy Individual Scripts (Original Approach)
- **Recreation Scripts**: Standalone scripts prefixed with `recreate_` that handle specific ArcGIS item types
- **Utility Scripts**: Helper scripts for item analysis, payload checking, and version checking
- **Authentication Module**: `old_clone/log_into_gis.py` provides YAML-based authentication
- **JSON Storage**: `json_files/` directory stores extracted configurations for debugging

### 2. Solution Cloner Framework (Recommended Approach)
A comprehensive orchestrator-centric design located in `solution_cloner/`:

#### Core Components
- **Main Orchestrator** (`solution_cloner.py`): Central entry point with all configuration variables at the top
- **Base Classes** (`base/`): Abstract base cloner defining common interface
- **Item Cloners** (`cloners/`): Modular implementations for each ArcGIS item type
- **Utilities** (`utils/`): Shared functionality for auth, JSON handling, ID mapping, etc.

#### Key Features
- **Folder-Based Collection**: Automatically discovers all items in a source folder
- **Dependency Analysis**: Determines correct cloning order based on item relationships  
- **ID/URL Mapping**: Maintains mappings throughout the process for reference updates
- **No Hardcoded Values**: All configuration in one place (orchestrator)

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

## Virtual Environment Setup

This project uses [uv](https://github.com/astral-sh/uv) for fast Python package and virtual environment management. The virtual environment is located at `.venv/` and uses Python 3.12.3.

### Using uv (Recommended)
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate the virtual environment
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate  # On Windows

# Install dependencies
uv pip install -r requirements.txt
```

### Traditional Setup (Alternative)
```bash
# Create virtual environment
python -m venv .venv

# Activate and install dependencies
source .venv/bin/activate
pip install -r requirements.txt
```

## Development Commands

### Installation
With uv:
```bash
uv pip install -r requirements.txt
```

With pip:
```bash
pip install -r requirements.txt
```

### Running the Solution Cloner (Recommended)
```bash
# Edit solution_cloner/solution_cloner.py to set:
# - SOURCE_FOLDER_NAME: Name of folder containing items to clone
# - DEST_FOLDER_NAME: Name of destination folder (created if needed)
# - Credentials (or use .env file)

# Run the solution cloner
python solution_cloner/solution_cloner.py
```

### Running Individual Scripts (Legacy Approach)
Each recreation script requires modifying the top-level constants:
- `USERNAME` and `PASSWORD` for ArcGIS Online credentials
- Item ID constants specific to each script (e.g., `SRC_VIEWID`, `ITEM_ID`)

```bash
python recreate_FeatureLayer_by_json.py
python recreate_JoinView_by_json.py
python recreate_WebMap_by_json.py
python recreate_InstantApp_by_json.py
# etc.
```

### Utility Scripts
```bash
# Analyze a JSON payload for potential issues
python analyze_payload.py

# Check titles of cloned items
python check_cloned_titles.py

# Print item information
python print_itemInfo.py

# Compare different cloning approaches
python compare_approaches.py
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

## Project Terminology

### ArcGIS Online Concepts
- **Item**: Any content in ArcGIS Online (feature layer, web map, app, etc.) with a unique ID
- **Feature Layer**: Hosted data service containing geographic features with attributes
- **View**: A filtered or subset view of a feature layer with specific field visibility
- **Join View**: A view that combines data from multiple feature layers based on relationships
- **Service URL**: The REST endpoint for accessing feature data (e.g., `https://services.arcgis.com/.../FeatureServer`)
- **Sublayer URL**: Specific layer within a service (e.g., `/0` for first layer)
- **Operational Layers**: The data layers displayed in a web map
- **Solution**: A collection of related ArcGIS Online items that work together

### Cloning Concepts
- **Source Organization**: The ArcGIS Online organization containing items to be cloned
- **Destination Organization**: The target organization where cloned items will be created
- **Recreation**: Creating a new item based on extracted JSON definitions
- **ID Mapping**: Tracking relationships between source item IDs and newly created item IDs
- **Reference Updates**: Replacing old IDs/URLs with new ones in dependent items
- **Dependency Order**: The sequence for cloning items based on their relationships (e.g., layers before maps)
- **Orchestrator**: The main controller that manages the entire cloning process

### Technical Terms
- **JSON Definition**: The complete configuration of an ArcGIS item in JSON format
- **Admin REST API**: Special endpoints requiring admin privileges for complete item details
- **Service Definition**: The schema and configuration of a feature service
- **Renderer**: The symbology rules that define how features are displayed
- **View Manager API**: Special API for managing view layer field visibility
- **Portal URL**: The base URL of an ArcGIS organization (e.g., `https://org.maps.arcgis.com`)

## Solution Cloner Implementation Status

### ✅ Fully Implemented and Tested
- **Feature Layers**: Complete schema, symbology, relationships, and dummy feature seeding
- **Views**: Field visibility, filters, and parent layer references  
- **Join Views**: Proper geometry handling, join definitions, and cardinality
- **Web Maps**: Operational layer updates, organization URL replacement, Linux/WSL compatibility
- **Instant Apps**: Web map reference updates, cross-organization support

### 🚧 In Development
- **Dashboards**: Need widget reference update implementation
- **Experience Builder Apps**: Need to refactor from existing scripts

### Key Capabilities
- **Automatic Dependency Resolution**: Clones items in correct order based on relationships
- **Cross-Organization Support**: Handles cloning between different ArcGIS organizations
- **ID/URL Mapping**: Automatically updates all references in dependent items
- **Folder-Based Discovery**: Clones entire folders without manually specifying item IDs