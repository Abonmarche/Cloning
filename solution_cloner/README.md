# Solution Cloner

A comprehensive framework for cloning ArcGIS Online solutions from one organization to another.

## Architecture

The solution cloner follows an orchestrator-centric design where:

1. **Environment-based configuration** using `.env` file for credentials
2. **Folder-based collection** automatically discovers items to clone
3. **Dependency analysis** ensures items are cloned in the correct order
4. **Modular cloners** handle each item type's specific requirements
5. **ID/URL mapping** maintains references between cloned items

## Setup

1. Create a `.env` file in the project root:

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

# Optional Settings
CLONE_DATA=True
CREATE_DUMMY_FEATURES=True
LOG_LEVEL=INFO
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the cloner:

```bash
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

## Supported Item Types

### Fully Implemented
- ✅ **Feature Layers** - Complete schema, symbology, relationships, dummy features
- ✅ **Views** - Field visibility, filters, parent references
- ✅ **Join Views** - Join definitions, geometry handling
- ✅ **Web Maps** - Layer references, popups, bookmarks
- ✅ **Instant Apps** - Web map references, configuration
- ✅ **Hub Sites** - Groups, domain registration, catalog
- ✅ **Hub Pages** - Slugs, site relationships
- ✅ **Survey123 Forms** - Form JSON, feature service references

### In Development
- 🚧 **Dashboards** - Widget configuration, data expressions
- 🚧 **Experience Builder** - Complex dependencies, data sources

## Key Features

### ID Mapping
The `IDMapper` utility tracks relationships between source and destination items:
- Item IDs
- Service URLs
- Layer URLs
- Group IDs
- Domain mappings

### Dependency Resolution
Items are automatically cloned in the correct order:
1. Feature Services (base data)
2. Views (depend on features)
3. Join Views (multiple dependencies)
4. Web Maps (reference layers)
5. Applications (reference maps/data)

### Error Handling
- Rollback on critical errors
- Detailed logging to file and console
- JSON exports for debugging

## Known Limitations

1. **Hub Catalog Migration** - Pages may require manual catalog configuration
2. **Protected Items** - Cannot be automatically deleted on failure
3. **Premium Content** - May require additional licenses
4. **Large Datasets** - Data cloning can be slow for large feature services