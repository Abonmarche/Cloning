# Feature Layer Clone Module Fix

## Problem Description

The feature layer cloner module was failing with the following error when attempting to clone feature services:

```
Error applying schema: Unable to add feature service definition.
Invalid definition for System.Collections.Generic.List`1[ESRI.ArcGIS.SDS.Metadata.LayerCoreInfo]
Exception has been thrown by the target of an invocation.
(Error Code: 400)
```

This error occurred during the `add_to_definition()` API call, even though the standalone test script (`recreate_FeatureLayer_by_json.py`) was able to successfully clone the same feature service.

## Root Cause Analysis

### 1. Initial Investigation
The error message suggested an issue with the structure of the layer/table definitions being passed to the `add_to_definition()` method. Analysis of the JSON payloads revealed that the module was including many more properties than necessary.

### 2. Property Comparison
Comparing the working test script with the failing module revealed the key difference:
- **Working Script**: Only includes essential properties needed to define layers and tables
- **Failing Module**: Includes ALL properties from the source service, including server-managed and read-only properties

### 3. Problematic Properties Identified
The payload included server-managed properties that should not be sent when creating new services:
```json
{
  "hasViews": true,
  "sourceSchemaChangesAllowed": false,
  "supportsLayerOverrides": true,
  "enableNullGeometry": false,
  "editingInfo": {...},
  "supportsASyncCalculate": true,
  "supportsTruncate": false,
  // ... many more supports* properties
}
```

These properties are:
- Set by the server when a service is created
- Read-only and cannot be specified during service creation
- Cause the API to reject the definition as invalid

## The Fix

### Original EXCLUDE_PROPS (16 properties)
```python
EXCLUDE_PROPS = {
    'currentVersion','serviceItemId','capabilities','maxRecordCount',
    'supportsAppend','supportedQueryFormats','isDataVersioned',
    'allowGeometryUpdates','supportsCalculate','supportsValidateSql',
    'advancedQueryCapabilities','supportsCoordinatesQuantization',
    'supportsApplyEditsWithGlobalIds','supportsMultiScaleGeometry',
    'syncEnabled','syncCapabilities','editorTrackingInfo',
    'changeTrackingInfo'
}
```

### Expanded EXCLUDE_PROPS (45+ properties)
```python
EXCLUDE_PROPS = {
    # Original exclusions from working script
    'currentVersion','serviceItemId','capabilities','maxRecordCount',
    'supportsAppend','supportedQueryFormats','isDataVersioned',
    'allowGeometryUpdates','supportsCalculate','supportsValidateSql',
    'advancedQueryCapabilities','supportsCoordinatesQuantization',
    'supportsApplyEditsWithGlobalIds','supportsMultiScaleGeometry',
    'syncEnabled','syncCapabilities','editorTrackingInfo',
    'changeTrackingInfo',
    # Additional server-managed properties that cause errors
    'advancedEditingCapabilities', 'advancedQueryAnalyticCapabilities',
    'collation', 'dateFieldsTimeReference', 'editingInfo',
    'enableNullGeometry', 'hasContingentValuesDefinition', 
    'hasStaticData', 'hasViews', 'infoInEstimates',
    'maxRecordCountFactor', 'preferredTimeReference',
    'queryBinsCapabilities', 'sourceSchemaChangesAllowed',
    'standardMaxRecordCount', 'standardMaxRecordCountNoGeometry',
    'supportedAppendFormats', 'supportedAppendSourceFilterFormats',
    'supportedContingentValuesFormats', 'supportedConvertContentFormats',
    'supportedConvertFileFormats', 'supportedExportFormats',
    'supportedSpatialRelationships', 'supportedSyncDataOptions',
    'supportsASyncCalculate', 'supportsAdvancedQueries',
    'supportsAttachmentsByUploadId', 'supportsAttachmentsResizing',
    'supportsColumnStoreIndex', 'supportsExceedsLimitStatistics',
    'supportsFieldDescriptionProperty', 'supportsLayerOverrides',
    'supportsQuantizationEditMode', 'supportsReturningQueryGeometry',
    'supportsRollbackOnFailureParameter', 'supportsStatistics',
    'supportsTilesAndBasicQueriesMode', 'supportsTruncate',
    'tileMaxRecordCount', 'uniqueIdField', 'useStandardizedQueries'
}
```

## Technical Details

### Why the Working Script Succeeded
The working script (`recreate_FeatureLayer_by_json.py`) uses a `_layer_def()` function that:
1. Converts PropertyMap objects to dictionaries
2. Preserves drawing info if requested
3. **Removes only the explicitly excluded properties**
4. Returns a clean definition

However, since it starts with a fresh service and builds definitions from scratch, it naturally doesn't include server-managed properties.

### Why the Module Failed
The module's approach:
1. Extracts the complete definition from the source service
2. Includes ALL properties, including server-managed ones
3. Only removes the original 16 excluded properties
4. Sends a definition with invalid server-managed properties

### The Solution
By expanding the EXCLUDE_PROPS set to include all server-managed properties, the module now:
1. Removes all properties that cannot be set during service creation
2. Only includes properties that define the schema, fields, relationships, and symbology
3. Produces a clean definition that the API accepts

## Verification

To verify the fix works correctly:

```python
# Test with the problematic item
ITEM_ID = "fe7f19431cbc495ba71871a07b25db19"  # Test Relationship item

# Run the test script
python test_fixed_cloner.py
```

The fixed module should now successfully clone feature services without the "Invalid definition" error.

## Lessons Learned

1. **ArcGIS REST API Strictness**: The `add_to_definition()` endpoint is strict about which properties can be included. Server-managed properties must be excluded.

2. **Property Categories**: 
   - **User-definable**: name, fields, indexes, types, relationships, drawingInfo, etc.
   - **Server-managed**: supports*, has*, capabilities, editing info, etc.

3. **Debugging Approach**: Saving the payload JSON before sending to the API was crucial for identifying the problematic properties.

4. **API Error Messages**: While the error mentioned "LayerCoreInfo", the actual issue was with the properties included in the definition, not the structure itself.