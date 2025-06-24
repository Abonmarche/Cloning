# Solution Cloner Processing Flow

## Command to navigate to wsl directory
```bash
cd /mnt/c/Users/ggarcia/OneDrive\ -\ Abonmarche/Documents/GitHub/Cloning
```

## Command to open workspace
```bash
code-insiders Cloning.code-workspace
```

## Combined command
```bash
code-insiders /mnt/c/Users/ggarcia/OneDrive\ -\ Abonmarche/Documents/GitHub/Cloning/Cloning.code-workspace
```

## Command to Run
```bash
python -m solution_cloner.solution_cloner
```

## File Architecture and Execution Flow

### 1. Entry Point
- **`solution_cloner/solution_cloner.py`** - Main orchestrator script
  - Defines configuration variables loaded from environment/.env
  - Contains the `main()` function and `SolutionCloner` class

### 2. Initial Imports and Dependencies
When the command runs, the main script imports:

#### Core Utilities
- **`utils/auth.py`** - Handles GIS authentication (`connect_to_gis`)
- **`utils/folder_collector.py`** - Collects items from source folder (`collect_items_from_folder`) 
- **`utils/item_analyzer.py`** - Analyzes dependencies and classifies items (`analyze_dependencies`, `classify_items`)
- **`utils/id_mapper.py`** - Maps old IDs to new IDs (`IDMapper` class)
- **`utils/json_handler.py`** - Handles JSON saving operations (`save_json`)

#### Configuration
- **`config/solution_config.py`** - Defines cloning order and priority (`CloneOrder`)

#### Item Type Cloners
- **`cloners/feature_layer_cloner.py`** - Clones feature layers (`FeatureLayerCloner`)
- **`cloners/web_map_cloner.py`** - Clones web maps (`WebMapCloner`) 
- **`cloners/view_cloner.py`** - Clones feature layer views (`ViewCloner`)
- **`cloners/join_view_cloner.py`** - Clones join views (`JoinViewCloner`)

#### Base Classes
- **`base/base_cloner.py`** - Abstract base class that all cloners inherit from (`BaseCloner`)

### 3. Execution Flow Steps

1. **Configuration Loading**
   - Loads `.env` file from parent directory
   - Sets up environment variables for source/destination credentials
   - Validates required configuration parameters

2. **Main Function Execution**
   - Prints configuration summary
   - Creates `SolutionCloner` instance
   - Calls `clone_solution()` method

3. **Solution Cloning Process**
   - **Authentication**: Uses `utils/auth.py` to connect to source and destination GIS
   - **Item Collection**: Uses `utils/folder_collector.py` to gather all items from source folder
   - **Analysis**: Uses `utils/item_analyzer.py` to classify items and analyze dependencies
   - **ID Mapping Setup**: Creates `IDMapper` instance from `utils/id_mapper.py`
   - **Folder Creation**: Ensures destination folder exists using built-in logic
   - **Dependency-Ordered Cloning**: Processes items in dependency order using appropriate cloners

4. **Item-Specific Cloning**
   - Each item type uses its specific cloner from the `cloners/` directory
   - All cloners inherit from `base/base_cloner.py` for common functionality
   - Cloners extract JSON definitions, create new items, and update references
   - JSON configurations are saved using `utils/json_handler.py`

5. **Reference Updates**
   - Uses `utils/id_mapper.py` to update all cross-references between cloned items
   - Ensures all internal links point to new item IDs

### 4. Supporting Files
- **`__init__.py`** files in each directory make them Python packages
- **`tests/`** directory contains test files (not executed during normal operation)
- **`README.md`** provides documentation for the solution_cloner module

## Key Design Patterns
- **Modular Architecture**: Each component has a specific responsibility
- **Abstract Base Classes**: Common cloning interface via `BaseCloner`
- **Dependency Management**: Items cloned in proper order to maintain relationships  
- **Configuration-Driven**: All settings controlled via environment variables
- **Error Handling**: Comprehensive logging and optional rollback functionality