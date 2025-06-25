# Solution Cloning Utility Architecture Plan

## Overview

Transform the existing individual Python scripts into a comprehensive solution cloning utility that can clone entire ArcGIS Online solutions from one organization to another while maintaining all item relationships and references.

## Recommended Approach: Orchestrator-Centric Design

### 1. **Main Orchestrator** (`solution_cloner.py`)

The central entry point that contains ALL configurable variables and manages the entire cloning process:

- **Central Configuration**: All changeable variables (credentials, folder names, item IDs, etc.) are defined at the top of the orchestrator
- **Folder-Based Collection**: Uses the pattern from `old_clone/get_items_in_folder.py` to collect all items from a specified source folder
- **Solution Analysis**: Analyzes collected items to identify all dependencies and proper cloning order
- **Dependency Management**: Coordinates cloning in proper dependency order (Feature Layers → Views → Join Views → Web Maps → Instant Apps → Dashboards → Experience Builder)
- **ID/URL Mapping**: Maintains a global mapping of old item IDs/service URLs to new ones throughout the process
- **Progress Tracking**: Provides real-time feedback on cloning progress
- **Error Handling**: Comprehensive error handling with rollback capabilities
- **No Hardcoded Values**: Individual cloner modules receive all configuration from orchestrator

### 2. **Item Type Modules** (refactored from existing scripts)

Transform each existing `recreate_*_by_json.py` script into a focused cloner module:

```
cloners/
├── __init__.py
├── feature_layer_cloner.py    # From recreate_FeatureLayer_by_json.py
├── view_layer_cloner.py       # From recreate_Views_by_json.py
├── join_view_cloner.py        # From recreate_JoinView_by_json.py
├── webmap_cloner.py           # From recreate_WebMap_by_json.py
├── instant_app_cloner.py      # From recreate_InstantApp_by_json.py
├── dashboard_cloner.py        # From recreate_Dashboard_by_json.py
└── experience_builder_cloner.py # From recreate_ExB_by_json.py
```

Each module:
- Implements a common `BaseCloner` interface
- Handles its specific item type's complexities
- Accepts ID mapping for reference updates
- Returns new item information for mapping

### 3. **Core Utilities** (`utils/`)

Support modules that provide shared functionality:

#### `auth.py`
- Centralized authentication management
- Handles both source and destination organization connections
- Integrates with existing `old_clone/log_into_gis.py` patterns

#### `json_handler.py` 
- JSON extraction, saving, and manipulation utilities
- Timestamped file saving (building on existing `jdump` pattern)
- JSON comparison and validation tools

#### `id_mapper.py`
- Core ID/URL mapping functionality
- Reference updating across all item types
- Handles service URLs, item IDs, layer references, etc.
- Pattern matching and replacement for various reference formats

#### `item_analyzer.py`
- Item type detection and classification
- Dependency analysis between items
- Validation of item accessibility and permissions

#### `folder_collector.py`
- Integrates existing `old_clone/get_items_in_folder.py` functionality
- Collects all items from specified source folder
- Returns items with metadata for dependency analysis
- Handles both root and named folders

### 4. **Base Classes** (`base/`)

#### `base_cloner.py`
Abstract base class defining the common interface for all cloners:

```python
class BaseCloner:
    def analyze_item(self, item_id: str) -> ItemAnalysis
    def extract_definition(self, item_id: str) -> dict
    def create_item(self, definition: dict, id_mapping: dict) -> CreatedItem
    def update_references(self, item: CreatedItem, id_mapping: dict) -> bool
    def validate_clone(self, original_id: str, new_id: str) -> bool
```

### 5. **Configuration System** (`config/`)

#### `solution_config.py`
- Solution definitions and cloning configurations
- Cloning order rules and dependency mappings
- Default settings and preferences

#### `credentials.py`
- Credential management for source/destination organizations
- Integration with existing YAML-based authentication

## Process Flow

### Phase 1: Discovery & Analysis
1. **Folder Collection**: Use folder name to collect all items from source GIS (similar to `get_items_in_folder.py`)
2. **Item Type Classification**: Identify the type of each collected item
3. **Dependency Analysis**: Build complete dependency graph for proper cloning order
4. **Validation**: Verify access permissions and item integrity
5. **Planning**: Determine optimal cloning order based on dependencies

### Phase 2: Sequential Cloning
1. **Feature Layers First**: Clone all hosted feature services
2. **Views & Join Views**: Clone view layers that depend on feature layers
3. **Web Maps**: Clone maps that reference the layers
4. **Applications**: Clone instant apps, dashboards, and experience builder apps
5. **ID Mapping**: Build comprehensive mapping throughout process

### Phase 3: Reference Updates
1. **Cross-Reference Updates**: Update all item IDs and service URLs in cloned items
2. **Configuration Updates**: Update any hardcoded references in app configurations
3. **Validation**: Verify all references point to correct new items

### Phase 4: Verification
1. **Functionality Testing**: Verify cloned items work correctly
2. **Reference Validation**: Confirm all cross-references are properly updated
3. **Rollback Capability**: Provide option to remove partially completed clones

## Key Benefits of This Architecture

### **Maintainability**
- Clean separation of concerns
- Reuses existing, proven logic from current scripts
- Easy to modify individual item type handling

### **Extensibility**
- Simple to add support for new ArcGIS Online item types
- Modular design allows independent development of components
- Configuration-driven approach for easy customization

### **Reliability**
- Comprehensive error handling and validation at each step
- Rollback capabilities for failed cloning attempts
- Detailed logging and progress tracking

### **Flexibility**
- Supports both individual item cloning and full solution cloning
- Configurable cloning order and dependency handling
- Multiple authentication methods and organization types

## Implementation Strategy

### Phase 1: Core Infrastructure
1. Create base classes and utility modules
2. Implement ID mapping and reference updating system
3. Build solution scanning and analysis capabilities

### Phase 2: Cloner Modules
1. Refactor existing scripts into cloner modules
2. Implement common interface across all cloners
3. Add reference updating to each cloner

### Phase 3: Orchestration
1. Build main solution cloner orchestrator
2. Implement dependency management and cloning order
3. Add progress tracking and error handling

### Phase 4: Testing & Validation
1. Test with simple solutions first
2. Gradually test with more complex, interconnected solutions
3. Add comprehensive validation and rollback features

## File Structure

```
solution_cloner/
├── solution_cloner.py              # Main orchestrator entry point with ALL config variables
├── base/
│   └── base_cloner.py             # Abstract base class
├── cloners/
│   ├── __init__.py
│   ├── feature_layer_cloner.py
│   ├── view_layer_cloner.py
│   ├── join_view_cloner.py
│   ├── form_cloner.py
│   ├── webmap_cloner.py
│   ├── instant_app_cloner.py
│   ├── dashboard_cloner.py
│   └── experience_builder_cloner.py
├── utils/
│   ├── __init__.py
│   ├── auth.py
│   ├── json_handler.py
│   ├── id_mapper.py
│   ├── item_analyzer.py
│   └── folder_collector.py        # Folder-based item collection
├── config/
│   ├── __init__.py
│   └── solution_config.py         # Config structures, no hardcoded values
├── tests/
│   └── test_*.py
└── json_files/                    # Preserve existing JSON storage location
```

## Key Architectural Changes

### Orchestrator-Centric Configuration
- **ALL** configuration variables (credentials, folder names, target locations, etc.) are defined at the top of `solution_cloner.py`
- Individual cloner modules receive configuration via parameters, never hardcode values
- This makes the tool easy to use - users only need to modify one file

### Folder-Based Item Collection
- The orchestrator uses the existing `get_items_in_folder.py` pattern to collect all items from a specified folder
- This eliminates the need to manually specify individual item IDs
- Automatically discovers all items that need to be cloned as part of the solution

### Proper Cloning Order
- Items are cloned in dependency order to ensure references work correctly:
  1. Feature Layers (base data)
  2. Views (depend on feature layers)
  3. Join Views (depend on feature layers/views)
  4. Forms (Survey123 - depend on feature layers/views for data collection)
  5. Web Maps (reference layers)
  6. Instant Apps (reference web maps)
  7. Dashboards (reference layers/maps) - may have circular references with experiences
  8. Experience Builder Apps (Web Experience) (reference various items) - may have circular references with dashboards
  9. Hub Sites and Pages (reference many item types)

## Implementation Progress

### ✅ Completed

1. **Core Infrastructure**
   - Created orchestrator-centric design with all configuration at the top of `solution_cloner.py`
   - Built complete directory structure for modular design
   - Created base cloner abstract class defining common interface
   - Made solution completely self-contained (no dependencies on old_clone folder)

2. **Utility Modules**
   - `auth.py` - Direct authentication to ArcGIS organizations
   - `folder_collector.py` - Collects items from folders (handles different API versions)
   - `json_handler.py` - JSON save/load with timestamps
   - `id_mapper.py` - Comprehensive ID/URL mapping with reference updates
   - `item_analyzer.py` - Analyzes dependencies and determines cloning order
   - `solution_config.py` - Configuration structures (no hardcoded values)

3. **Cloner Implementations**
   - **Feature Layer Cloner** - Successfully refactored from `recreate_FeatureLayer_by_json.py`
     - Preserves all original functionality (schema, renderers, symbology)
     - Tracks service and sublayer URLs for mapping
     - Creates dummy features for symbology
     - **Updated (2025-06-20)**: Fixed layer definition issues by expanding EXCLUDE_PROPS list
       - Added properties: 'id', 'hasViews', 'sourceSchemaChangesAllowed', 'relationships'
       - Added retry logic for add_to_definition to handle relationship errors
     - **Tested and working**
   
   - **Web Map Cloner** - Successfully implemented and tested
     - Updates references to feature layers in operational layers
     - Handles item IDs, service URLs, and sublayer URLs
     - Always updates references before creation (no configurable parameter)
     - Fixed _is_geoenabled error with monkey patch for Linux/WSL compatibility
     - Preserves original titles without UUID suffixes
     - **Tested and working**
   
   - **View Cloner** - Refactored from `recreate_Views_by_json.py`
     - Handles field visibility using ViewManager API
     - Preserves layer/table filtering
     - Updates references to parent layers if cloned
     - **Tested and working**
   
   - **Join View Cloner** - Refactored from `recreate_JoinView_by_json.py`
     - Uses admin REST API to extract join definitions
     - Preserves join types and cardinality
     - Updates references to source layers if cloned
     - **Tested and working**
   
   - **Instant App Cloner** - Successfully implemented from `recreate_InstantApp_by_json.py`
     - Extracts instant app JSON configuration
     - Updates web map references in mapItemCollection
     - Handles organization URL replacement for cross-org cloning
     - Properly detects source org URL pattern from JSON
     - Uses destination org's urlKey for proper portal URLs
     - Sets app URL for View button functionality
     - Fixed ID mapping timing issue for same-level dependencies
     - **Tested and working**
   
   - **Form Cloner** - Successfully implemented (2025-06-24)
     - Handles Survey123 forms that reference feature services/views
     - Downloads and processes form ZIP packages
     - Updates service references in .webform JSON files
     - Maintains Survey2Service relationships
     - Supports forms based on both feature layers and views
     - **Tested and working**

4. **ID Mapping & Reference Updates**
   - Comprehensive IDMapper tracks:
     - Item IDs (old → new)
     - Service URLs
     - Sublayer URLs (e.g., /0, /1)
   - Automatic reference updates in dependent items
   - Support for both pre-creation and post-creation updates

5. **Type Detection**
   - Solution cloner automatically detects:
     - Regular feature layers vs views vs join views
     - Uses `isView` property and admin endpoint checks
     - Routes to appropriate cloner automatically

6. **API Compatibility**
   - Handled folder object differences between ArcGIS API versions
   - Implemented proper folder creation for both old (<2.3) and new (2.3+) APIs
   - Fixed sharing deprecation warnings

### ✅ Recently Completed (2025-06-23)

1. **Dashboard Cloner** - Successfully implemented from `recreate_Dashboard_by_json.py`
   - Handles arcade data expressions with Portal() and FeatureSetByPortalItem()
   - Updates embed widgets (instant apps, experiences, etc.)
   - Supports both old ('dataExpressions') and new ('arcadeDataSourceItems') formats
   - Implements phase 2 updates for circular references
   - **Tested and working**

2. **Experience Builder Cloner** - Successfully implemented from `recreate_ExB_by_json.py`
   - Updates data sources, map widgets, and embed widgets
   - Handles dashboard embeds with circular reference support
   - Updates both published and draft configurations
   - Fixed "Resource already present" error for draft updates
   - **Tested and working**

3. **Two-Phase Update System**
   - Phase 1: Initial cloning with immediate reference updates
   - Phase 2: Resolve circular references (dashboards ↔ experiences)
   - Pending updates tracked by IDMapper for phase 2 resolution

### ⏳ Remaining Work

1. **Enhanced Features**
   - Actual data copying for feature layers (currently copies schema + optional dummy features)
   - Validation and reporting methods for IDMapper
   - Progress tracking UI/reporting
   - Enhanced rollback functionality

2. **Testing**
   - Performance testing with large solutions
   - Edge case testing for complex circular dependencies

### 🐛 Known Minor Issues (Non-Critical)

1. **Folder Handling**
   - Test script has issues with folder enumeration in some API versions
   - Main solution cloner handles folders correctly
   - Only affects test scripts, not core functionality

2. **Thumbnail Copying**
   - Occasional failures when copying thumbnails
   - Items clone successfully without thumbnails
   - Can be manually updated later

3. **Join View Detection**
   - Newly cloned join views may have slightly different admin endpoint responses
   - Does not affect functionality, only re-detection
   - Original join views detect correctly

4. **Import Paths**
   - When using solution_cloner as a module vs script, import paths need adjustment
   - Works correctly when run as designed (python solution_cloner.py)

## Current State

The solution cloner now supports ALL major ArcGIS Online item types:
- **Feature Layers** - Base hosted data with schema, symbology, and relationships
- **Views** - Filtered/subset views of feature layers with field visibility
- **Join Views** - Views that join multiple feature layers with proper geometry
- **Forms** - Survey123 forms with updated feature service references
- **Web Maps** - Maps with updated layer references and organization URLs
- **Instant Apps** - Web mapping applications with updated web map references
- **Dashboards** - With arcade data expressions and embed widgets
- **Experience Builder** - With data sources, widgets, and circular references

The ID mapping and reference update system is fully functional, including two-phase updates for circular references between dashboards and experiences. The system properly detects item types, handles cross-organization cloning with proper URL updates, and manages complex dependencies.

### Ready for Production Use
- Cloning complete ArcGIS Online solutions containing all supported item types
- Full dependency resolution with automatic reference updates
- Cross-organization cloning (personal to work, ArcGIS Online to Enterprise)
- Circular reference handling (dashboards ↔ experiences)

This architecture provides a robust, maintainable, and extensible foundation for cloning complete ArcGIS Online solutions while preserving all the proven functionality from your existing individual scripts.

## Recent Updates

### 2025-06-20: Feature Layer Cloner Fixes

**Issue Discovered**: The `recreate_FeatureLayer_by_json.py` script was failing with error:
```
Error: Unable to add feature service definition.
Invalid definition for System.Collections.Generic.List`1[ESRI.ArcGIS.SDS.Metadata.LayerCoreInfo]
```

**Root Cause**: The layer definitions being passed to `add_to_definition()` included server-managed properties that ArcGIS Online doesn't accept when creating new layers.

**Fixes Applied**:
1. **Expanded EXCLUDE_PROPS list** in both scripts to remove problematic properties:
   - Added: `'id'`, `'hasViews'`, `'sourceSchemaChangesAllowed'`, `'relationships'`
   - These properties are automatically generated by the server and cannot be set during creation

2. **Added JSON dump functionality** to `recreate_FeatureLayer_by_json.py`:
   - Saves all definitions to `json_files/` with timestamps
   - Helps with debugging and comparing source vs. cloned items
   - Matches pattern used in other recreation scripts

3. **Improved error handling** for `add_to_definition()`:
   - Added retry logic that attempts to add layers/tables first, then relationships separately
   - This handles cases where relationships might cause the entire definition to fail

**Result**: Both the standalone script and the solution cloner module now successfully clone feature services with proper schema, symbology, and relationships.

### 2025-06-20: View and Join View Cloner Fixes

**Major Achievement**: Successfully implemented complete cloning support for Feature Layers, Views, and Join Views with proper geometry and reference handling.

**Issues Fixed**:

1. **Folder Creation Error**:
   - Solution cloner was failing when destination folder already existed
   - Fixed by catching "folder not available" errors and proceeding anyway
   - Added `override=True` to `load_dotenv()` to ensure .env file values take precedence

2. **View Parent Layer References**:
   - Views couldn't find parent layers due to layer ID vs item ID mismatch
   - Added `_get_parent_item_id()` method with multiple detection strategies
   - Fixed ID mapping structure (changed from nested to flat dictionary)

3. **View Title Preservation**:
   - Views were getting suffixed titles like "Test_Relationship_view_b2802"
   - Added code to update title back to original after creation
   - Service URLs retain safe names while item titles match source

4. **Join View Geometry Issues**:
   - Join views were appearing as tables without geometry in map viewer
   - Fixed by:
     - Adding Shape field to sourceLayerFields when missing
     - Setting layer type explicitly as "Feature Layer" not "Table"
     - Using qualified geometry field name (ServiceName.Shape)
     - Adding `"materialized": false` to table definition

5. **Service Name Conflicts**:
   - Join view creation was failing with "Service name already exists"
   - Added safe service name generation with unique suffixes
   - Extracted actual service names from URLs instead of using titles

**Technical Improvements**:
- Enhanced folder detection to handle both old and new ArcGIS API versions
- Improved error handling and logging throughout
- Added comprehensive ID mapping for items, services, and sublayers
- Fixed cross-reference updates for all cloned items

**Result**: The solution cloner now successfully clones:
- ✅ **Feature Layers** - With full schema, symbology, and relationships
- ✅ **Views** - With field visibility, filters, and parent references
- ✅ **Join Views** - With proper geometry, join definitions, and cardinality
- ✅ **Proper folder placement** - All items placed in destination folder
- ✅ **Title preservation** - Original titles maintained without suffixes
- ✅ **Reference updates** - All cross-references automatically updated

### 2025-06-23: Web Map and Instant App Cloners

**Major Achievement**: Successfully implemented web map and instant app cloning with full reference updates and cross-organization support.

**Web Map Cloner Implementation**:

1. **Reference Update Strategy**:
   - Removed UPDATE_REFS_BEFORE_CREATE parameter per user requirement
   - Web maps always update references before creation
   - Handles operational layers, basemap layers, and tables

2. **Linux/WSL Compatibility Fix**:
   - Encountered `module 'arcgis.features.geo' has no attribute '_is_geoenabled'` error
   - Implemented monkey patch to provide dummy _is_geoenabled function
   - Allows web map creation in Linux/WSL environments without Windows dependencies

3. **Title Preservation**:
   - Removed UUID suffix generation for cloned items
   - Web maps retain original titles as requested

**Instant App Cloner Implementation**:

1. **Reference Updates**:
   - Updates web map IDs in mapItemCollection array
   - Handles both string and object references
   - Replaces organization URLs for cross-org cloning

2. **Organization URL Handling**:
   - Properly detects source organization URL from JSON content
   - Uses destination organization's urlKey for correct portal URLs
   - Supports both ArcGIS Online and Enterprise deployments

3. **Dependency Resolution Fix**:
   - Fixed issue where instant apps couldn't reference web maps cloned in same level
   - Added immediate ID mapping updates after each item clone
   - Ensures items can reference others cloned in the same dependency level

**Result**: Complete solution cloning now works for data layers (feature layers, views, join views), web maps, and instant apps with proper cross-organization support.

### 2025-06-23: Dashboard and Experience Builder Cloners

**Major Achievement**: Successfully implemented the final two cloner types, completing support for all major ArcGIS Online item types.

**Dashboard Cloner Implementation**:

1. **Arcade Data Expression Support**:
   - Handles both old format ('dataExpressions') and new format ('arcadeDataSourceItems')
   - Updates Portal() URLs and FeatureSetByPortalItem() references
   - Expression fields can be in 'script', 'expression', or nested locations

2. **Embed Widget Updates**:
   - Updates instant app URLs with pattern `/apps/instant/manager/index.html?appid=`
   - Handles circular references to experiences via pending updates
   - Supports various embed URL field names (url, src, embedUrl, iframeSrc)

3. **Data Source Updates**:
   - Updates item IDs in data sources
   - Handles both dict and list formats for widgets
   - Updates references across desktop and mobile views

**Experience Builder Cloner Implementation**:

1. **Comprehensive Reference Updates**:
   - Updates data sources including map services and feature layers
   - Updates childDataSourceJsons for web map data sources
   - Handles embed widgets with dashboard references

2. **Draft Configuration Fix**:
   - Fixed "Resource already present" error when updating draft config
   - Implemented robust update strategy with multiple fallback approaches
   - Both published and draft versions now have properly remapped content

3. **Widget Type Detection**:
   - Fixed widget type detection using 'uri' field instead of manifest.name
   - Properly identifies embed, map, and data widgets for targeted updates

**Two-Phase Update System**:

1. **Phase 1 - Initial Cloning**:
   - Items are cloned in dependency order
   - Immediate reference updates for known dependencies
   - Pending updates tracked for circular references

2. **Phase 2 - Circular Reference Resolution**:
   - Resolves dashboard → experience references
   - Updates embed URLs that couldn't be resolved during initial cloning
   - Clears pending updates after processing

**Technical Improvements**:
- IDMapper enhanced with Arcade expression parsing
- Fixed feature layer update_references to handle IDMapper objects
- All JSON files properly saved to json_files directory
- Improved error handling for pending updates

**Result**: The solution cloner is now feature-complete with support for all major ArcGIS Online item types and complex circular dependencies.

### 2025-06-24: Form (Survey123) Cloner

**Major Achievement**: Successfully implemented Survey123 form cloning to complete the solution cloner's coverage of data collection workflows.

**Form Cloner Implementation**:

1. **Form Package Handling**:
   - Downloads form ZIP files containing XLSForm and web form definitions
   - Extracts and updates .webform JSON files within the package
   - Repackages updated content for upload to destination

2. **Service Reference Updates**:
   - Detects form-to-service relationships via Survey2Service item relationships
   - Falls back to extracting service references from item properties
   - Updates submission URLs to point to cloned feature services/views

3. **Dependency Management**:
   - Forms are cloned after feature layers, views, and join views
   - Properly positioned in hierarchy before web maps (level 3)
   - Supports forms based on both feature layers and view layers

**Technical Details**:
- Uses Python's zipfile module for package manipulation
- Preserves all form configuration while updating only service references
- Maintains proper Survey2Service relationships in destination
- Handles both direct service URLs and item ID references

**Result**: Complete end-to-end solution cloning now includes data collection forms, enabling full workflow migration from source to destination organizations.

### 2025-06-25: Experience Builder Fix and Enhanced Reliability

**Major Achievement**: Fixed critical issues with Experience Builder cloning and improved overall reliability of view cloning.

**Experience Builder Fixes**:

1. **Corrected Dependency Hierarchy**:
   - Fixed item type detection for 'Web Experience' items
   - Updated hierarchy to place Experience Builder at level 7 (after web maps)
   - Ensured proper dependency extraction in item_analyzer.py

2. **View Cloning Enhancements**:
   - Implemented exponential backoff (2s, 5s, 10s, 20s) for view readiness
   - Added forced URL mapping when layer definitions fail to load
   - Ensures sublayer URLs are mapped even in failure scenarios

3. **Web Map Fallback Resolution**:
   - Added item ID-based URL lookup when direct mapping fails
   - Automatically reconstructs sublayer URLs (e.g., /0, /1)
   - Enhanced logging for unmapped references

4. **Experience Reference Update Improvements**:
   - Fixed JSON comparison to properly detect data source changes
   - Enhanced update logic for both published and draft configs
   - Added detailed logging of what's being updated

5. **Post-Clone Validation**:
   - Added validation method to detect remaining source organization URLs
   - Provides clear warnings for any manual fixes needed
   - Validates across web maps and experiences

**Technical Improvements**:
- IDMapper now stores reference to destination GIS for item lookups
- Better error messages throughout the cloning process
- Enhanced logging for troubleshooting view configuration issues

**Result**: Experience Builder apps now clone reliably with all map widgets properly referencing cloned content. The system handles timing issues gracefully and provides clear feedback when manual intervention may be needed.