# Hub Site Cloning Implementation Plan

## Overview

This document outlines the strategy for adding ArcGIS Hub site cloning capabilities to the existing solution cloner framework. Hub sites are complex items that involve multiple components including the site itself, associated pages, groups, and domain registrations.

## Feasibility Assessment

The existing solution cloner framework is well-suited for hub site cloning because it already handles:
- Modular cloner classes with a common interface
- Dependency resolution and ordered cloning
- ID and URL mapping throughout the process
- Complex item relationships

## Key Challenges & Solutions

1. **Domain Registration**: Hub sites require domain registration via the Hub API
2. **Associated Groups**: Sites have content and collaboration groups that need to be created
3. **Site-Page Relationships**: Pages can belong to multiple sites (many-to-many)
4. **Complex Data Structures**: Layout, theme, catalog groups need careful handling
5. **Cross-Organization URLs**: Need to update organization-specific URLs in site data

## Implementation Plan

### 1. Add New Item Types to Configuration

Update `solution_cloner/config/solution_config.py`:

```python
class ItemType(Enum):
    # ... existing types ...
    HUB_SITE = "Hub Site Application"  # AGO Hub sites
    HUB_PAGE = "Hub Page"              # AGO Hub pages
    SITE_APP = "Site Application"      # Enterprise sites
    SITE_PAGE = "Site Page"            # Enterprise pages
```

Update `CloneOrder` to include hub items in the correct dependency order:
- Hub sites should be cloned after feature layers but before web maps
- Hub pages should be cloned after hub sites but before apps that might reference them

### 2. Create HubSiteCloner Class

Location: `solution_cloner/cloners/hub_site_cloner.py`

**Key Methods:**

```python
class HubSiteCloner(BaseCloner):
    def clone(self, source_item, source_gis, dest_gis, dest_folder, id_mapping, **kwargs):
        """Main cloning logic for hub sites"""
        # 1. Create content and collaboration groups
        # 2. Create site item
        # 3. Register domain (AGO) or set typeKeywords (Enterprise)
        # 4. Update site data with new IDs/URLs
        # 5. Update item with final data
        
    def _create_groups(self, site_title, dest_gis, is_enterprise=False):
        """Create content and collaboration groups for the site"""
        # Content group: public for AGO, org for Enterprise
        # Collab group: org access with updateitemcontrol capability
        # Set protected=True on both groups
        
    def _register_domain(self, site_item, subdomain, dest_gis):
        """Register domain with Hub API for AGO sites"""
        # POST to hub.arcgis.com/api/v3/domains
        # Handle domain availability checks
        # Return domain info (siteId, clientKey)
        
    def _update_site_data(self, site_data, new_groups, domain_info, id_mapping):
        """Update site data with new IDs and URLs"""
        # Update catalog groups
        # Update collaboration group ID
        # Update domain/hostname info
        # Update organization URLs
        # Update any item ID references
        
    def extract_definition(self, item_id, gis, save_path=None):
        """Extract complete site definition"""
        # Get item properties
        # Get item data (site configuration)
        # Get linked pages info
        # Save to JSON if requested
```

### 3. Create HubPageCloner Class

Location: `solution_cloner/cloners/hub_page_cloner.py`

**Key Methods:**

```python
class HubPageCloner(BaseCloner):
    def clone(self, source_item, source_gis, dest_gis, dest_folder, id_mapping, **kwargs):
        """Clone a hub page"""
        # 1. Create page item
        # 2. Update page data with new references
        # 3. Re-establish site linkages
        
    def _update_page_sites(self, page_data, id_mapping):
        """Update linked sites in page data"""
        # Map old site IDs to new site IDs
        # Update the sites array in page data
        
    def _link_to_sites(self, page_item, page_data, dest_gis, id_mapping):
        """Re-establish page-site relationships"""
        # For each linked site in page data
        # Update the site's pages array to include this page
        # Handle missing sites gracefully
```

### 4. Update IDMapper

Enhance `solution_cloner/utils/id_mapper.py`:

```python
class IDMapper:
    def __init__(self):
        # ... existing mappings ...
        self.group_mapping = {}      # source group ID -> dest group ID
        self.domain_mapping = {}     # source domain -> dest domain
        
    def add_group_mapping(self, source_id, dest_id):
        """Add a group ID mapping"""
        
    def add_domain_mapping(self, source_domain, dest_domain):
        """Add a domain mapping"""
        
    def update_hub_references(self, json_data):
        """Update hub-specific references"""
        # Update group IDs
        # Update domain URLs
        # Update organization-specific URLs
```

### 5. Handle Special Cases

#### Group Creation
- Create groups before creating the site item
- Set appropriate access levels (public/org)
- Enable delete protection
- Store group IDs in mapping for reference updates

#### Domain Registration
- **ArcGIS Online**: Use Hub API v3 for domain management
- **Enterprise**: Use typeKeywords with hubsubdomain prefix
- Handle domain conflicts with counter suffix

#### Cross-Organization URL Updates
- Replace source organization URLs with destination URLs
- Update portal URLs in site data
- Update any hardcoded organization references

#### Protected Items
- Set `protected=True` on sites and groups
- Handle protection removal during deletion if needed

#### Page Relationships
- Maintain many-to-many relationships between sites and pages
- Update both site and page data to reflect linkages
- Handle orphaned pages appropriately

### 6. Integration Steps

1. **Update Module Imports**
   - Add hub cloners to `solution_cloner/cloners/__init__.py`
   - Import in `solution_cloner.py`

2. **Update Main Orchestrator**
   ```python
   # In solution_cloner.py
   from .cloners.hub_site_cloner import HubSiteCloner
   from .cloners.hub_page_cloner import HubPageCloner
   
   # In get_cloner_for_type()
   'Hub Site Application': HubSiteCloner(),
   'Hub Page': HubPageCloner(),
   'Site Application': HubSiteCloner(),  # Enterprise sites
   'Site Page': HubPageCloner()          # Enterprise pages
   ```

3. **Add Configuration Options**
   ```
   # In .env.template
   # Hub-specific options
   CLONE_HUB_GROUPS=True       # Clone associated groups
   UPDATE_HUB_DOMAINS=True     # Update domain registrations
   PRESERVE_SUBDOMAINS=False   # Keep original subdomains if available
   ```

4. **Update Documentation**
   - Add hub cloning examples to README
   - Document hub-specific configuration
   - Note any limitations or prerequisites

### 7. Testing Strategy

#### Test Cases

1. **Basic Hub Site Clone**
   - Clone a simple hub site with default configuration
   - Verify groups are created correctly
   - Verify domain registration works

2. **Site with Pages**
   - Clone a site with multiple pages
   - Verify page-site linkages are maintained
   - Test page slug handling

3. **Cross-Organization Clone**
   - Clone from one org to another
   - Verify all org-specific URLs are updated
   - Test with different org URL formats

4. **Enterprise Sites**
   - Clone Enterprise sites with typeKeywords
   - Verify subdomain handling
   - Test without Hub API access

5. **Complex Scenarios**
   - Sites with custom themes
   - Sites with multiple catalog groups
   - Pages linked to multiple sites
   - Sites with restricted access

#### Validation Points

- Groups created with correct permissions
- Domain registered successfully (AGO)
- Site data contains updated references
- Pages maintain proper linkages
- Cross-org URLs properly updated
- Protected flags set appropriately

## Implementation Priority

1. **Phase 1**: Basic site cloning without pages
2. **Phase 2**: Add page support with linkages
3. **Phase 3**: Handle complex scenarios and edge cases
4. **Phase 4**: Add enterprise-specific optimizations

## Notes and Considerations

- Hub Premium features may require additional handling
- Initiative-based sites have different group structures
- Some Hub API endpoints require specific authentication
- Enterprise sites don't use the Hub API domain system
- Consider rate limiting for Hub API calls