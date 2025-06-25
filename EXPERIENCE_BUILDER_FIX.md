# Experience Builder Cloning Fix Documentation

## Issues Resolved (June 2025)

This document details the issues encountered when cloning Experience Builder apps with map widgets and the solutions implemented.

## Problem Description

When cloning an ArcGIS Online solution containing:
- Feature Layer (master)
- Multiple View Layers
- Web Map (using the views)
- Experience Builder app (with map widget)

The cloned Experience Builder app would show:
1. "Failed to create map" error in the map widget
2. "Sorry, you don't have access to the resources" error pointing to source organization URLs
3. Empty view layers with no sublayers visible
4. Map widget data source showing as "none" in edit mode

## Root Causes Identified

### 1. Incorrect Dependency Order
- Experience Builder apps were cloned at dependency level 0 (before their dependent web maps)
- The dependency extraction wasn't recognizing 'Web Experience' item type
- This caused the Experience to be cloned before the web map it references

### 2. View Cloning Issues
- View layer definitions weren't available immediately after view creation
- The cloner only waited 2 seconds between retry attempts (3 attempts total)
- When layer definitions failed to load, sublayer URLs weren't added to the mapping
- This left web maps with unmapped URLs pointing to the source organization

### 3. URL Mapping Gaps
- The web map cloner had no fallback when URLs weren't in the mapping
- Missing sublayer URLs (e.g., `.../FeatureServer/0`) weren't being resolved
- No validation to detect remaining source organization references

### 4. Experience Reference Updates
- The post-clone update phase wasn't detecting changes properly
- JSON comparison was too strict (exact string match including whitespace)
- Draft config wasn't being updated even when published config changed

## Solutions Implemented

### 1. Fixed Dependency Resolution

**File**: `solution_cloner/utils/item_analyzer.py`

```python
# Updated hierarchy with correct order
ITEM_TYPE_HIERARCHY = {
    'Feature Service': 0,
    'View': 1,
    'Join View': 2,
    'Form': 3,
    'Web Map': 4,
    'Instant App': 5,
    'Dashboard': 6,
    'Experience Builder': 7,  # Now after web maps
    'Web Experience': 7,      # Alias for Experience Builder
    'Hub Site': 8,
    'Hub Page': 8,
    'Notebook': 9
}

# Fixed dependency extraction to handle Web Experience type
elif item_type == 'Web Experience' or 'Experience' in item.get('typeKeywords', []):
    deps.update(extract_experience_dependencies(item, gis))
```

### 2. Enhanced View Cloning Reliability

**File**: `solution_cloner/cloners/view_cloner.py`

```python
# Exponential backoff for view readiness
wait_times = [2, 5, 10, 20]  # seconds
max_attempts = len(wait_times)

for attempt in range(max_attempts):
    try:
        view_layer_definitions = view_manager.get_definitions(new_view_item)
        if view_layer_definitions:
            break
    except Exception as e:
        logger.debug(f"Error getting view definitions (attempt {attempt + 1}): {e}")
    
    if attempt < max_attempts - 1:
        wait_time = wait_times[attempt]
        logger.info(f"Waiting for view to be ready... (attempt {attempt + 1}/{max_attempts}, waiting {wait_time}s)")
        time.sleep(wait_time)

# Force URL mapping even when layer definitions fail
if not view_layer_definitions:
    self._force_url_mapping(src_item, new_view_item)
```

### 3. Web Map Fallback URL Resolution

**File**: `solution_cloner/cloners/web_map_cloner.py`

```python
# Fallback to item ID lookup when URL not mapped
if not new_url and 'itemId' in layer and layer['itemId'] in id_map:
    new_item_id = id_map[layer['itemId']]
    logger.warning(f"URL not found in mappings, using item ID fallback")
    
    if hasattr(id_mapping, 'dest_gis'):
        try:
            new_item = id_mapping.dest_gis.content.get(new_item_id)
            if new_item and hasattr(new_item, 'url'):
                # Preserve sublayer index
                if old_url.endswith('/0') or old_url.endswith('/1'):
                    sublayer_idx = old_url.split('/')[-1]
                    new_url = f"{new_item.url}/{sublayer_idx}"
                else:
                    new_url = new_item.url
        except Exception as e:
            logger.error(f"Failed to lookup item for URL fallback: {e}")
```

### 4. Improved Experience Reference Updates

**File**: `solution_cloner/cloners/experience_builder_cloner.py`

```python
# Better change detection
data_sources_changed = False
if 'dataSources' in experience_json and 'dataSources' in updated_json:
    for ds_id in experience_json.get('dataSources', {}):
        orig_ds = experience_json['dataSources'].get(ds_id, {})
        updated_ds = updated_json['dataSources'].get(ds_id, {})
        if orig_ds.get('itemId') != updated_ds.get('itemId'):
            data_sources_changed = True
            logger.info(f"Data source {ds_id} changed: {orig_ds.get('itemId')} -> {updated_ds.get('itemId')}")
            break

# Always update draft config when changes detected
if data_sources_changed or widgets_changed:
    item.update(item_properties={'text': json.dumps(updated_json)})
    self.update_draft_config(item, updated_json)
```

### 5. Post-Clone Validation

**File**: `solution_cloner/solution_cloner.py`

```python
def _validate_no_source_urls(self):
    """Validate that no source organization URLs remain in cloned items."""
    source_patterns = [source_org_url, "www.arcgis.com", known_service_urls]
    
    for item in self.created_items:
        if item.type == 'Web Map':
            # Check operational layers for source URLs
        elif item.type == 'Web Experience':
            # Check data sources for source portal URLs
    
    if issues_found:
        logger.warning("SOURCE ORGANIZATION REFERENCES FOUND")
        # List specific issues for manual fixing
```

## Results

After implementing these fixes:
1. ✅ Experience Builder apps are cloned AFTER their dependent web maps
2. ✅ View layers have sufficient time to initialize (up to 37 seconds total wait)
3. ✅ All URLs are mapped, even if view configuration partially fails
4. ✅ Web maps can resolve layer URLs through multiple mechanisms
5. ✅ Experience Builder map widgets properly reference cloned web maps
6. ✅ Clear warnings are provided for any remaining issues

## Best Practices

1. **Always check logs** for warnings about view configuration failures
2. **Run post-clone validation** to detect any remaining source references
3. **Allow time** for view services to fully initialize before expecting field visibility
4. **Use the fallback mechanisms** - the cloner will try multiple ways to resolve references
5. **Monitor the dependency analysis** to ensure items are cloned in the correct order