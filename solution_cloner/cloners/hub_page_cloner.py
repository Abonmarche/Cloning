"""
Hub Page Cloner
===============
Clones Hub pages and maintains site-page relationships.
"""

from typing import Dict, Optional, Any, List
from arcgis.gis import GIS, Item
import logging
from datetime import datetime
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from base.base_cloner import BaseCloner
from utils.json_handler import save_json

logger = logging.getLogger(__name__)


class HubPageCloner(BaseCloner):
    """Clones Hub pages and Enterprise pages."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the Hub page cloner."""
        super().__init__()
        self.supported_types = ['Hub Page', 'Site Page']
        self.json_output_dir = json_output_dir or Path("json_files")
        
    def clone(
        self,
        source_item: Dict[str, Any],
        source_gis: GIS,
        dest_gis: GIS,
        dest_folder: str,
        id_mapping: Dict[str, str],
        **kwargs
    ) -> Optional[Item]:
        """
        Clone a Hub page from source to destination.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            
        Returns:
            Created page item or None
        """
        try:
            # Get source page item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item or src_item.type not in self.supported_types:
                logger.error(f"Item {source_item['id']} is not a Hub page")
                return None
                
            logger.info(f"Cloning Hub page: {src_item.title}")
            
            # Extract page definition
            page_def = self.extract_definition(src_item.id, source_gis)
            
            # Log the original site references
            original_sites = page_def.get('data', {}).get('values', {}).get('sites', [])
            logger.debug(f"Original page has {len(original_sites)} site references")
            for site in original_sites:
                logger.debug(f"  - Site: {site.get('id')} ({site.get('title')})")
            
            # Determine if this is Enterprise
            is_enterprise = not dest_gis._portal.is_arcgisonline
            
            # Generate slug from title
            slug = self._generate_slug(src_item.title)
            
            # Create item properties
            item_properties = self._prepare_item_properties(
                src_item,
                slug,
                dest_gis,
                is_enterprise
            )
            
            # Create the page item
            logger.info(f"Creating page item: {item_properties['title']}")
            new_item = dest_gis.content.add(
                item_properties,
                folder=dest_folder
            )
            
            if not new_item:
                logger.error("Failed to create page item")
                return None
                
            # Update page data with new references
            page_data = page_def.get('data', {})
            updated_data = self._update_page_data(
                page_data,
                slug,
                id_mapping,
                dest_gis
            )
            
            # Update item with data
            update_result = new_item.update(
                item_properties={'text': json.dumps(updated_data)}
            )
            
            if update_result:
                logger.info(f"Successfully created Hub page: {new_item.id}")
                
                # Re-establish site linkages
                self._link_to_sites(new_item, updated_data, dest_gis, id_mapping)
                
                return new_item
            else:
                logger.error("Failed to update page with data")
                return None
                
        except Exception as e:
            logger.error(f"Error cloning Hub page: {str(e)}")
            return None
            
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract the complete definition of a Hub page.
        
        Args:
            item_id: ID of the page to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the page definition
        """
        try:
            # Get the page item
            item = gis.content.get(item_id)
            if not item:
                logger.error(f"Page item not found: {item_id}")
                return {}
                
            # Get item properties
            item_dict = dict(item)
            
            # Get page data
            page_data = item.get_data()
            
            # Get linked sites info
            sites = []
            if page_data and 'values' in page_data and 'sites' in page_data['values']:
                for site_ref in page_data['values']['sites']:
                    site_item = gis.content.get(site_ref.get('id'))
                    if site_item:
                        sites.append({
                            'id': site_item.id,
                            'title': site_item.title,
                            'type': site_item.type
                        })
                        
            definition = {
                'item': item_dict,
                'data': page_data,
                'sites': sites
            }
            
            # Save if requested
            if save_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filepath = save_path / f"hub_page_{item_id}_{timestamp}.json"
                save_json(definition, filepath)
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting page definition: {str(e)}")
            return {}
            
    def _generate_slug(self, title: str) -> str:
        """
        Generate a URL-friendly slug from the page title.
        
        Args:
            title: Page title
            
        Returns:
            Slug string
        """
        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower().replace(' ', '-')
        
        # Remove special characters
        import re
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        
        # Remove multiple consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
        
    def _prepare_item_properties(
        self,
        source_item: Item,
        slug: str,
        dest_gis: GIS,
        is_enterprise: bool
    ) -> Dict[str, Any]:
        """
        Prepare item properties for the new page.
        
        Args:
            source_item: Source page item
            slug: Generated slug
            dest_gis: Destination GIS
            is_enterprise: Whether this is Enterprise
            
        Returns:
            Dictionary of item properties
        """
        # Base properties
        properties = {
            'title': source_item.title,
            'snippet': source_item.snippet or '',
            'description': source_item.description or '',
            'tags': source_item.tags or [],
            'culture': source_item.culture or 'en-us'
        }
        
        # Type-specific properties
        if is_enterprise:
            properties['type'] = 'Site Page'
            properties['typeKeywords'] = [
                "Hub", "hubPage", "OpenData", f"slug|{dest_gis.properties['urlKey']}|{slug}"
            ]
        else:
            properties['type'] = 'Hub Page'
            properties['typeKeywords'] = [
                "Hub", "hubPage", "OpenData", f"slug|{dest_gis.properties['urlKey']}|{slug}"
            ]
            
        # Page-specific properties
        properties['properties'] = {
            'slug': f"{dest_gis.properties['urlKey']}|{slug}",
            'schemaVersion': 1,
            'orgUrlKey': dest_gis.properties['urlKey']
        }
        
        # Pages don't have a direct URL
        properties['url'] = ''
        
        return properties
        
    def _update_page_data(
        self,
        page_data: Dict[str, Any],
        slug: str,
        id_mapping: Dict[str, str],
        dest_gis: GIS
    ) -> Dict[str, Any]:
        """
        Update page data with new references.
        
        Args:
            page_data: Original page data
            slug: Page slug
            id_mapping: ID mapping for content references
            dest_gis: Destination GIS
            
        Returns:
            Updated page data
        """
        if not page_data:
            page_data = {'values': {}}
            
        # Ensure values section exists
        if 'values' not in page_data:
            page_data['values'] = {}
            
        values = page_data['values']
        
        # Update slug
        values['slug'] = slug
        
        # Update sites array with mapped IDs
        if 'sites' in values:
            updated_sites = []
            # Handle both dict and IDMapper object
            mapping_dict = id_mapping if isinstance(id_mapping, dict) else getattr(id_mapping, 'id_mapping', {})
            logger.debug(f"ID mapping has {len(mapping_dict)} entries")
            logger.debug(f"Mapping dict: {mapping_dict}")
            
            for site_ref in values['sites']:
                old_site_id = site_ref.get('id')
                logger.debug(f"Looking for site ID {old_site_id} in mapping")
                if old_site_id and old_site_id in mapping_dict:
                    new_site_id = mapping_dict[old_site_id]
                    # Get the new site to update title
                    new_site = dest_gis.content.get(new_site_id)
                    if new_site:
                        updated_sites.append({
                            'id': new_site_id,
                            'title': new_site.title
                        })
                    else:
                        logger.warning(f"Could not find mapped site: {new_site_id}")
                else:
                    logger.warning(f"Site {old_site_id} not found in mapping")
                    
            values['sites'] = updated_sites
            
        # Update any content references in layout
        if 'layout' in values:
            if hasattr(id_mapping, 'update_json_references'):
                values['layout'] = id_mapping.update_json_references(values['layout'])
            else:
                # Basic ID replacement in layout
                layout_str = json.dumps(values['layout'])
                # Handle both dict and IDMapper object
                items_to_map = id_mapping.items() if isinstance(id_mapping, dict) else getattr(id_mapping, 'id_mapping', {}).items()
                for old_id, new_id in items_to_map:
                    if isinstance(old_id, str) and isinstance(new_id, str):
                        layout_str = layout_str.replace(old_id, new_id)
                values['layout'] = json.loads(layout_str)
                
        # Update organization URLs
        if hasattr(id_mapping, 'update_org_urls'):
            page_data = id_mapping.update_org_urls(page_data, dest_gis)
            
        # Update metadata
        values['updatedBy'] = dest_gis.users.me.username
        values['updatedAt'] = datetime.now().isoformat()
        
        page_data['values'] = values
        return page_data
        
    def _link_to_sites(
        self,
        page_item: Item,
        page_data: Dict[str, Any],
        dest_gis: GIS,
        id_mapping: Dict[str, str]
    ):
        """
        Re-establish page-site relationships by updating site data.
        
        Args:
            page_item: The newly created page item
            page_data: Page data with site references
            dest_gis: Destination GIS
            id_mapping: ID mapping
        """
        try:
            # Get linked sites from page data
            sites = page_data.get('values', {}).get('sites', [])
            
            for site_ref in sites:
                site_id = site_ref.get('id')
                if not site_id:
                    continue
                    
                logger.info(f"Linking page to site {site_id}")
                
                # Get the site item fresh (important for getting latest data)
                site_item = dest_gis.content.get(site_id)
                if not site_item:
                    logger.warning(f"Site {site_id} not found for linking")
                    continue
                    
                # Force refresh of site data by accessing properties first
                _ = site_item.properties
                
                # Get site data
                site_data = site_item.get_data()
                if not site_data:
                    logger.warning(f"No data found for site {site_id}")
                    continue
                    
                # Ensure pages array exists
                if 'values' not in site_data:
                    site_data['values'] = {}
                if 'pages' not in site_data['values']:
                    site_data['values']['pages'] = []
                    
                # Check if page already linked
                existing_pages = site_data['values']['pages']
                page_exists = any(p.get('id') == page_item.id for p in existing_pages)
                
                if not page_exists:
                    # Add page reference to site
                    page_slug = page_data.get('values', {}).get('slug', '')
                    page_ref = {
                        'id': page_item.id,
                        'title': page_item.title,
                        'slug': page_slug
                    }
                    site_data['values']['pages'].append(page_ref)
                    
                    logger.debug(f"Adding page reference to site: {page_ref}")
                    
                    # Update site item with modified data
                    update_result = site_item.update(
                        item_properties={'text': json.dumps(site_data)}
                    )
                    
                    if update_result:
                        logger.info(f"Successfully linked page {page_item.id} to site {site_id}")
                        
                        # Share the page with the site's content group for catalog permissions
                        content_group_id = site_item.properties.get('contentGroupId') if hasattr(site_item, 'properties') else None
                        if content_group_id:
                            try:
                                # Share the page with the content group
                                share_result = page_item.share(groups=[content_group_id])
                                if share_result.get('results', [{}])[0].get('success', False):
                                    logger.info(f"Successfully shared page with content group {content_group_id}")
                                else:
                                    logger.warning(f"Failed to share page with content group: {share_result}")
                            except Exception as e:
                                logger.warning(f"Error sharing page with content group: {str(e)}")
                        else:
                            logger.warning("No content group ID found for site, page may not have catalog permissions")
                    else:
                        logger.warning(f"Failed to link page to site {site_id}")
                else:
                    logger.info(f"Page {page_item.id} already linked to site {site_id}")
                        
        except Exception as e:
            logger.error(f"Error linking page to sites: {str(e)}", exc_info=True)
            
    def _update_page_sites(self, page_data: Dict[str, Any], id_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Update linked sites in page data based on ID mapping.
        
        Args:
            page_data: Page data containing site references
            id_mapping: Mapping of old to new IDs
            
        Returns:
            Updated page data
        """
        if 'values' in page_data and 'sites' in page_data['values']:
            updated_sites = []
            
            for site in page_data['values']['sites']:
                old_id = site.get('id')
                if old_id in id_mapping:
                    new_id = id_mapping[old_id]
                    updated_site = site.copy()
                    updated_site['id'] = new_id
                    updated_sites.append(updated_site)
                    logger.info(f"Updated site reference: {old_id} -> {new_id}")
                else:
                    logger.warning(f"Site {old_id} not found in ID mapping, skipping")
                    
            page_data['values']['sites'] = updated_sites
            
        return page_data