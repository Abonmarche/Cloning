"""
Hub Site Cloner
===============
Clones Hub sites and Enterprise sites with groups, domain registration, and full functionality.
"""

from typing import Dict, Optional, Any, List, Tuple
from arcgis.gis import GIS, Item, Group
import logging
import requests
from datetime import datetime
from pathlib import Path
import re
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from base.base_cloner import BaseCloner
from utils.json_handler import save_json

logger = logging.getLogger(__name__)


class HubSiteCloner(BaseCloner):
    """Clones Hub sites and Enterprise sites."""
    
    def __init__(self, json_output_dir=None):
        """Initialize the Hub site cloner."""
        super().__init__()
        self.supported_types = ['Hub Site Application', 'Site Application']
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
        Clone a Hub site from source to destination.
        
        Args:
            source_item: Source item dictionary
            source_gis: Source GIS connection
            dest_gis: Destination GIS connection
            dest_folder: Destination folder
            id_mapping: ID mapping dictionary
            
        Returns:
            Created site item or None
        """
        try:
            # Get source site item
            src_item = source_gis.content.get(source_item['id'])
            if not src_item or src_item.type not in self.supported_types:
                logger.error(f"Item {source_item['id']} is not a Hub site")
                return None
                
            logger.info(f"Cloning Hub site: {src_item.title}")
            
            # Extract site definition
            site_data = self.extract_definition(src_item.id, source_gis)
            
            # Generate subdomain from title
            subdomain = self._generate_subdomain(src_item.title, dest_gis)
            
            # Determine if this is Enterprise or AGO
            is_enterprise = not dest_gis._portal.is_arcgisonline
            
            # Create groups first
            content_group, collab_group = self._create_groups(
                src_item.title,
                dest_gis,
                is_enterprise
            )
            
            # Update site data with new references BEFORE creating the item
            updated_data = self._update_site_data(
                site_data['data'],
                content_group.id,
                collab_group.id if collab_group else None,
                subdomain,
                None,  # domain_info will be added after domain registration
                id_mapping,
                dest_gis,
                is_enterprise
            )
            
            # Create site item properties
            item_properties = self._prepare_item_properties(
                src_item,
                subdomain,
                content_group.id,
                collab_group.id if collab_group else None,
                dest_gis,
                is_enterprise
            )
            
            # Add the site data as text property BEFORE creation
            item_properties['text'] = json.dumps(updated_data)
            
            # Create the site item with data
            logger.info(f"Creating site item: {item_properties['title']}")
            new_item = dest_gis.content.add(
                item_properties,
                folder=dest_folder
            )
            
            if not new_item:
                logger.error("Failed to create site item")
                # Clean up groups
                self._cleanup_groups(content_group, collab_group)
                return None
                
            # Share with collaboration group if exists
            if collab_group:
                new_item.share(groups=[collab_group])
                
            # Protect site from accidental deletion
            new_item.protect(enable=True)
            
            # Register domain and update site data
            domain_info = None
            if not is_enterprise:
                domain_info = self._register_domain(new_item, subdomain, dest_gis)
                if not domain_info:
                    logger.error("Failed to register domain")
                    # Clean up
                    new_item.delete()
                    self._cleanup_groups(content_group, collab_group)
                    return None
                    
            # If we have domain info, we need to update the site data with it
            if domain_info:
                # Use the actual registered subdomain from domain_info
                actual_subdomain = domain_info.get('subdomain', subdomain)
                actual_hostname = domain_info.get('hostname')
                
                # Generate URL with actual registered subdomain
                url = f"https://{actual_hostname}" if actual_hostname else f"https://{actual_subdomain}-{dest_gis.properties['urlKey']}.hub.arcgis.com"
                
                # Re-update site data with domain info and actual subdomain
                updated_data = self._update_site_data(
                    site_data['data'],
                    content_group.id,
                    collab_group.id if collab_group else None,
                    actual_subdomain,  # Use actual subdomain
                    domain_info,
                    id_mapping,
                    dest_gis,
                    is_enterprise
                )
                
                # Update item with domain info and correct URL
                update_result = new_item.update(
                    item_properties={'text': json.dumps(updated_data), 'url': url}
                )
            else:
                # Generate URL for Enterprise
                url = f"https://{dest_gis.url[8:-6]}/apps/sites/#/{subdomain}"
                
                # Just update the URL for Enterprise sites
                update_result = new_item.update(
                    item_properties={'url': url}
                )
            
            if update_result:
                logger.info(f"Successfully created Hub site: {new_item.id} at {url}")
                
                # Add group mappings to id_mapping
                if hasattr(id_mapping, 'add_group_mapping'):
                    # Get source groups
                    src_content_group_id = site_data['item'].get('properties', {}).get('contentGroupId')
                    src_collab_group_id = site_data['item'].get('properties', {}).get('collaborationGroupId')
                    
                    if src_content_group_id:
                        id_mapping.add_group_mapping(src_content_group_id, content_group.id)
                    if src_collab_group_id and collab_group:
                        id_mapping.add_group_mapping(src_collab_group_id, collab_group.id)
                        
                return new_item
            else:
                logger.error("Failed to update site with data")
                return None
                
        except Exception as e:
            logger.error(f"Error cloning Hub site: {str(e)}")
            return None
            
    def extract_definition(
        self,
        item_id: str,
        gis: GIS,
        save_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Extract the complete definition of a Hub site.
        
        Args:
            item_id: ID of the site to extract
            gis: GIS connection
            save_path: Optional path to save extracted JSON
            
        Returns:
            Dictionary containing the site definition
        """
        try:
            # Get the site item
            item = gis.content.get(item_id)
            if not item:
                logger.error(f"Site item not found: {item_id}")
                return {}
                
            # Get item properties
            item_dict = dict(item)
            
            # Get site data
            site_data = item.get_data()
            
            # Get linked pages info
            pages = []
            if site_data and 'values' in site_data and 'pages' in site_data['values']:
                for page_ref in site_data['values']['pages']:
                    page_item = gis.content.get(page_ref.get('id'))
                    if page_item:
                        pages.append({
                            'id': page_item.id,
                            'title': page_item.title,
                            'type': page_item.type
                        })
                        
            definition = {
                'item': item_dict,
                'data': site_data,
                'pages': pages,
                'groups': {
                    'content': item.properties.get('contentGroupId'),
                    'collaboration': item.properties.get('collaborationGroupId')
                }
            }
            
            # Save if requested
            if save_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filepath = save_path / f"hub_site_{item_id}_{timestamp}.json"
                save_json(definition, filepath)
                
            return definition
            
        except Exception as e:
            logger.error(f"Error extracting site definition: {str(e)}")
            return {}
            
    def _create_groups(
        self,
        site_title: str,
        dest_gis: GIS,
        is_enterprise: bool = False
    ) -> Tuple[Group, Optional[Group]]:
        """
        Create content and collaboration groups for the site.
        
        Args:
            site_title: Title of the site
            dest_gis: Destination GIS connection
            is_enterprise: Whether this is an Enterprise deployment
            
        Returns:
            Tuple of (content_group, collab_group or None)
        """
        # Prepare group titles
        content_title = f"{site_title} Content"
        collab_title = f"{site_title} Core Team"
        
        # Content group configuration
        if is_enterprise:
            content_group_dict = {
                "title": content_title,
                "tags": ["Sites Group", "Sites Content Group"],
                "access": "org",
                "snippet": f"Applications, maps, data, etc. shared with this group generates the {site_title} content catalog."
            }
        else:
            content_group_dict = {
                "title": content_title,
                "tags": ["Hub Group", "Hub Content Group", "Hub Site Group"],
                "access": "public"
            }
            
        # Create content group
        logger.info(f"Creating content group: {content_title}")
        content_group = dest_gis.groups.create_from_dict(content_group_dict)
        content_group.protected = True
        
        # Create collaboration group only if user has admin privileges
        collab_group = None
        if dest_gis.users.me.role == 'org_admin':
            if is_enterprise:
                collab_group_dict = {
                    "title": collab_title,
                    "tags": ["Sites Group", "Sites Core Team Group"],
                    "access": "org",
                    "capabilities": "updateitemcontrol",
                    "membershipAccess": "org",
                    "snippet": f"Members of this group can create, edit, and manage the site, pages, and other content related to {site_title}."
                }
            else:
                collab_group_dict = {
                    "title": collab_title,
                    "tags": ["Hub Group", "Hub Site Group", "Hub Core Team Group", "Hub Team Group"],
                    "access": "org",
                    "capabilities": "updateitemcontrol",
                    "membershipAccess": "collaboration",
                    "snippet": f"Members of this group can create, edit, and manage the site, pages, and other content related to {site_title}."
                }
                
            logger.info(f"Creating collaboration group: {collab_title}")
            collab_group = dest_gis.groups.create_from_dict(collab_group_dict)
            collab_group.protected = True
        else:
            logger.warning("User is not admin, skipping collaboration group creation")
            
        return content_group, collab_group
        
    def _generate_subdomain(self, title: str, dest_gis: GIS) -> str:
        """
        Generate a valid subdomain from the site title.
        
        Args:
            title: Site title
            dest_gis: Destination GIS connection
            
        Returns:
            Valid subdomain string
        """
        # Convert to lowercase and replace spaces with hyphens
        subdomain = title.lower().replace(' ', '-')
        
        # Remove special characters except hyphens
        subdomain = re.sub(r'[^a-z0-9-]', '', subdomain)
        
        # Remove multiple consecutive hyphens
        subdomain = re.sub(r'-+', '-', subdomain)
        
        # Remove leading/trailing hyphens
        subdomain = subdomain.strip('-')
        
        # Ensure it starts with a letter
        if subdomain and not subdomain[0].isalpha():
            subdomain = 'site-' + subdomain
            
        # Truncate if needed (63 chars max for domain)
        if not dest_gis._portal.is_arcgisonline:
            # Enterprise: just subdomain
            if len(subdomain) > 63:
                subdomain = subdomain[:63]
        else:
            # AGO: subdomain + urlKey must be < 63
            max_length = 63 - len(dest_gis.properties['urlKey']) - 1  # -1 for hyphen
            if len(subdomain) > max_length:
                subdomain = subdomain[:max_length]
                
        return subdomain
        
    def _register_domain(
        self,
        site_item: Item,
        subdomain: str,
        dest_gis: GIS
    ) -> Optional[Dict[str, str]]:
        """
        Register domain with Hub API for ArcGIS Online sites.
        
        Args:
            site_item: The created site item
            subdomain: Subdomain to register
            dest_gis: Destination GIS connection
            
        Returns:
            Domain info dict with siteId and clientKey, or None if failed
        """
        try:
            # Determine Hub environment
            if 'qaext' in dest_gis.url:
                hub_env = "hub.arcgis.com"  # Update if there's a QA hub
            elif 'devext' in dest_gis.url:
                hub_env = "hubdev.arcgis.com"
            else:
                hub_env = "hub.arcgis.com"
                
            # Check if subdomain is available
            check_counter = 10  # Start at 10 to avoid conflicts with previous tests
            original_subdomain = subdomain
            
            while check_counter < 100:  # Max attempts increased
                # For first iteration with counter=10, use subdomain10
                if check_counter > 0:
                    subdomain = f"{original_subdomain}{check_counter}"
                hostname = f"{subdomain}-{dest_gis.properties['urlKey']}.{hub_env}"
                
                # Check availability
                session = dest_gis._con._session
                headers = {k: v for k, v in session.headers.items()}
                headers["Content-Type"] = "application/json"
                headers["Authorization"] = "X-Esri-Authorization"
                
                check_url = f"https://{hub_env}/api/v3/domains/{hostname}"
                response = session.get(url=check_url, headers=headers)
                
                if response.status_code == 404:
                    # Domain is available
                    break
                else:
                    # Domain exists, try with counter
                    check_counter += 1
                    subdomain = f"{original_subdomain}{check_counter}"
                    
            if check_counter >= 100:
                logger.error("Could not find available subdomain after many attempts")
                return None
                
            # Register the domain
            logger.info(f"Registering domain: {hostname}")
            
            body = {
                "hostname": hostname,
                "siteId": site_item.id,
                "siteTitle": site_item.title,
                "orgId": dest_gis.properties.id,
                "orgKey": dest_gis.properties["urlKey"],
                "orgTitle": dest_gis.properties["name"],
                "sslOnly": True
            }
            
            register_url = f"https://{hub_env}/api/v3/domains"
            response = session.post(
                url=register_url,
                data=json.dumps(body),
                headers=headers
            )
            
            if response.status_code == 200:
                domain_data = response.json()
                logger.info(f"Successfully registered domain: {hostname}")
                return {
                    'siteId': domain_data.get('id'),
                    'clientKey': domain_data.get('clientKey'),
                    'hostname': hostname,
                    'subdomain': subdomain
                }
            else:
                logger.error(f"Failed to register domain: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error registering domain: {str(e)}")
            return None
            
    def _prepare_item_properties(
        self,
        source_item: Item,
        subdomain: str,
        content_group_id: str,
        collab_group_id: Optional[str],
        dest_gis: GIS,
        is_enterprise: bool
    ) -> Dict[str, Any]:
        """
        Prepare item properties for the new site.
        
        Args:
            source_item: Source site item
            subdomain: Generated subdomain
            content_group_id: ID of content group
            collab_group_id: ID of collaboration group (if exists)
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
            'extent': source_item.extent,
            'culture': source_item.culture or 'en-us'
        }
        
        # Type-specific properties
        if is_enterprise:
            properties['type'] = 'Site Application'
            properties['typeKeywords'] = [
                "Hub", "hubSite", "hubSolution", f"hubsubdomain|{subdomain}",
                "JavaScript", "Map", "Mapping Site", "Online Map", "OpenData",
                "Ready To Use", "selfConfigured", "Web Map"
            ]
            url = f"https://{dest_gis.url[8:-6]}/apps/sites/#/{subdomain}"
        else:
            properties['type'] = 'Hub Site Application'
            properties['typeKeywords'] = [
                "Hub", "hubSite", "hubSolution", "JavaScript", "Map",
                "Mapping Site", "Online Map", "OpenData", "Ready To Use",
                "selfConfigured", "Web Map", "Registered App"
            ]
            url = f"https://{subdomain}-{dest_gis.properties['urlKey']}.hub.arcgis.com"
            
        properties['url'] = url
        
        # Item properties
        properties['properties'] = {
            'hasSeenGlobalNav': True,
            'schemaVersion': 1.9,
            'contentGroupId': content_group_id,
            'children': []
        }
        
        if collab_group_id:
            properties['properties']['collaborationGroupId'] = collab_group_id
            
        return properties
        
    def _update_site_data(
        self,
        site_data: Dict[str, Any],
        content_group_id: str,
        collab_group_id: Optional[str],
        subdomain: str,
        domain_info: Optional[Dict[str, str]],
        id_mapping: Dict[str, str],
        dest_gis: GIS,
        is_enterprise: bool
    ) -> Dict[str, Any]:
        """
        Update site data with new IDs and references.
        
        Args:
            site_data: Original site data
            content_group_id: New content group ID
            collab_group_id: New collaboration group ID
            subdomain: Site subdomain
            domain_info: Domain registration info (AGO only)
            id_mapping: ID mapping for content references
            dest_gis: Destination GIS
            is_enterprise: Whether this is Enterprise
            
        Returns:
            Updated site data
        """
        if not site_data:
            # Create minimal valid site structure if missing
            site_data = {
                'values': {
                    'title': '',
                    'public': True,
                    'capabilities': [],
                    'layout': {'sections': []},
                    'theme': {},
                    'map': {},
                    'pages': []
                },
                'catalog': {
                    'groups': []
                }
            }
            
        # Ensure values section exists
        if 'values' not in site_data:
            site_data['values'] = {}
            
        # Update catalog groups
        if 'catalog' in site_data:
            if 'groups' not in site_data['catalog']:
                site_data['catalog']['groups'] = []
            # Replace with new content group
            site_data['catalog']['groups'] = [content_group_id]
        else:
            # Create catalog section if missing
            site_data['catalog'] = {'groups': [content_group_id]}
            
        # Update catalogV2 if it exists (new Hub catalog system)
        if 'catalogV2' in site_data:
            # Update group references in catalogV2 scopes
            if 'scopes' in site_data['catalogV2']:
                for scope_name, scope_data in site_data['catalogV2']['scopes'].items():
                    if 'filters' in scope_data and isinstance(scope_data['filters'], list):
                        for filter_item in scope_data['filters']:
                            # Look for group filters
                            if isinstance(filter_item, dict) and 'predicates' in filter_item:
                                for predicate in filter_item['predicates']:
                                    if isinstance(predicate, dict) and predicate.get('group'):
                                        # Check if this is a group reference
                                        if 'any' in predicate['group'] and isinstance(predicate['group']['any'], list):
                                            # Replace old group IDs with new content group ID
                                            predicate['group']['any'] = [content_group_id]
                                        elif isinstance(predicate['group'], str):
                                            # Direct group reference
                                            predicate['group'] = content_group_id
            
        # Update values
        values = site_data.get('values', {})
        
        # Update collaboration group
        if collab_group_id:
            values['collaborationGroupId'] = collab_group_id
            
        # Update subdomain and URLs
        values['subdomain'] = subdomain
        values['updatedBy'] = dest_gis.users.me.username
        values['updatedAt'] = datetime.now().isoformat()
        
        if is_enterprise:
            hostname = f"{dest_gis.url[8:-6]}/apps/sites/#/{subdomain}"
            values['defaultHostname'] = hostname
            values['internalUrl'] = hostname
            values['clientId'] = 'arcgisonline'
        else:
            # For AGO, use the actual registered hostname from domain_info if available
            if domain_info and 'hostname' in domain_info:
                hostname = domain_info['hostname']
            else:
                hostname = f"{subdomain}-{dest_gis.properties['urlKey']}.hub.arcgis.com"
                
            values['defaultHostname'] = hostname
            values['internalUrl'] = hostname
            
            if domain_info:
                values['siteId'] = domain_info['siteId']
                values['clientId'] = domain_info['clientKey']
                
        # Update organization-specific URLs
        if hasattr(id_mapping, 'update_org_urls'):
            site_data = id_mapping.update_org_urls(site_data, dest_gis)
        else:
            # Basic URL replacement
            source_org_url = site_data.get('values', {}).get('orgUrl', '')
            if source_org_url:
                dest_org_url = dest_gis.url
                site_data_str = json.dumps(site_data)
                site_data_str = site_data_str.replace(source_org_url, dest_org_url)
                site_data = json.loads(site_data_str)
                
        # Update any item ID references
        if hasattr(id_mapping, 'update_json_references'):
            site_data = id_mapping.update_json_references(site_data)
        else:
            # Basic ID mapping
            for old_id, new_id in id_mapping.items():
                if isinstance(old_id, str) and isinstance(new_id, str):
                    site_data_str = json.dumps(site_data)
                    site_data_str = site_data_str.replace(old_id, new_id)
                    site_data = json.loads(site_data_str)
                    
        # Clear pages array (will be updated when pages are cloned)
        if 'pages' in values:
            values['pages'] = []
            
        site_data['values'] = values
        return site_data
        
    def _cleanup_groups(self, content_group: Group, collab_group: Optional[Group]):
        """
        Clean up groups if site creation fails.
        
        Args:
            content_group: Content group to delete
            collab_group: Collaboration group to delete (if exists)
        """
        try:
            if content_group:
                content_group.protected = False
                content_group.delete()
                logger.info(f"Cleaned up content group: {content_group.title}")
        except Exception as e:
            logger.warning(f"Failed to clean up content group: {str(e)}")
            
        try:
            if collab_group:
                collab_group.protected = False
                collab_group.delete()
                logger.info(f"Cleaned up collaboration group: {collab_group.title}")
        except Exception as e:
            logger.warning(f"Failed to clean up collaboration group: {str(e)}")