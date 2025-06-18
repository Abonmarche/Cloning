# Solution Cloner

A refactored utility for cloning ArcGIS Online solutions from one organization to another.

## Architecture

The solution cloner follows an orchestrator-centric design where:

1. **All configuration** is centralized in `solution_cloner.py` at the top of the file
2. **Folder-based collection** automatically discovers items to clone
3. **Dependency analysis** ensures items are cloned in the correct order
4. **Modular cloners** handle each item type's specific requirements

## Usage

1. Edit the configuration variables at the top of `solution_cloner.py`:

```python
# Source Organization Configuration
SOURCE_CITY = "Abonmarche"  # Or use SOURCE_USERNAME/PASSWORD
SOURCE_FOLDER = "Testing"   # Folder containing items to clone

# Destination Organization Configuration  
DEST_USERNAME = "your_username"
DEST_PASSWORD = "your_password"
DEST_FOLDER = "Cloned_Solution"

# Cloning Options
CLONE_DATA = True  # Copy actual data
CREATE_DUMMY_FEATURES = True  # For symbology
```

2. Run the cloner:

```bash
cd solution_cloner
python solution_cloner.py
```

## Directory Structure

```
solution_cloner/
├── solution_cloner.py      # Main entry point with ALL configuration
├── base/
│   └── base_cloner.py     # Abstract base for all cloners
├── cloners/
│   ├── feature_layer_cloner.py
│   ├── view_layer_cloner.py (to be implemented)
│   └── ...
├── utils/
│   ├── auth.py            # Authentication handling
│   ├── folder_collector.py # Collects items from folders
│   ├── item_analyzer.py   # Dependency analysis
│   ├── id_mapper.py       # ID/URL mapping
│   └── json_handler.py    # JSON utilities
└── config/
    └── solution_config.py # Configuration structures
```

## Cloning Order

Items are cloned in dependency order:

1. Feature Services / Tables (base data)
2. View Services (depend on feature services)
3. Join Views (depend on multiple sources)
4. Web Maps (reference layers)
5. Apps/Dashboards (reference maps/layers)
6. Experience Builder (complex dependencies)

## Current Status

- ✅ Core architecture implemented
- ✅ Orchestrator with centralized config
- ✅ Base cloner abstract class
- ✅ Utility modules
- ✅ Feature layer cloner refactored
- ⏳ Other cloners to be refactored from existing scripts

## Next Steps

Continue refactoring the remaining cloner modules from the existing `recreate_*.py` scripts.