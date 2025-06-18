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
  4. Web Maps (reference layers)
  5. Instant Apps (reference web maps)
  6. Dashboards (reference layers/maps)
  7. Experience Builder Apps (reference various items)

This architecture provides a robust, maintainable, and extensible foundation for cloning complete ArcGIS Online solutions while preserving all the proven functionality from your existing individual scripts.