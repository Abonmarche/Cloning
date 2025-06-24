"""
ID Mapper Utility
=================
Manages the mapping between source and destination item IDs and URLs.
"""

from typing import Dict, Optional, Tuple, Any, List
import re
import logging
import json
from urllib.parse import urlparse, urlunparse


logger = logging.getLogger(__name__)


class IDMapper:
    """Manages mappings between source and destination IDs/URLs."""
    
    def __init__(self):
        """Initialize the ID mapper."""
        self.id_mapping: Dict[str, str] = {}  # old_id -> new_id
        self.url_mapping: Dict[str, str] = {}  # old_url -> new_url
        self.service_mapping: Dict[str, str] = {}  # old_service_url -> new_service_url
        self.sublayer_mapping: Dict[str, str] = {}  # old_sublayer_url -> new_sublayer_url
        self.portal_mapping: Dict[str, str] = {}  # old_portal_url -> new_portal_url
        self.pending_updates: Dict[str, Dict] = {}  # item_id -> update_info for phase 2
        self.group_mapping: Dict[str, str] = {}  # old_group_id -> new_group_id
        self.domain_mapping: Dict[str, str] = {}  # old_domain -> new_domain
        
    def add_mapping(self, old_id: str, new_id: str, old_url: str = None, new_url: str = None):
        """
        Add a mapping between old and new IDs/URLs.
        
        Args:
            old_id: Source item ID
            new_id: Destination item ID
            old_url: Optional source URL
            new_url: Optional destination URL
        """
        self.id_mapping[old_id] = new_id
        logger.debug(f"Added ID mapping: {old_id} -> {new_id}")
        
        if old_url and new_url:
            self.url_mapping[old_url] = new_url
            
            # Extract and map service URLs
            old_service = self._extract_service_url(old_url)
            new_service = self._extract_service_url(new_url)
            if old_service and new_service:
                self.service_mapping[old_service] = new_service
                logger.debug(f"Added service mapping: {old_service} -> {new_service}")
                
            # Check if this is a sublayer URL (ends with /0, /1, etc.)
            if re.search(r'/\d+$', old_url):
                self.sublayer_mapping[old_url] = new_url
                logger.debug(f"Added sublayer mapping: {old_url} -> {new_url}")
                
    def add_mappings(self, mappings: Dict[str, str]):
        """
        Add multiple ID mappings at once.
        
        Args:
            mappings: Dictionary of old_id -> new_id mappings
        """
        self.id_mapping.update(mappings)
        logger.info(f"Added {len(mappings)} ID mappings")
        
    def get_new_id(self, old_id: str) -> Optional[str]:
        """Get the new ID for an old ID."""
        return self.id_mapping.get(old_id)
        
    def get_new_url(self, old_url: str) -> Optional[str]:
        """Get the new URL for an old URL."""
        # Direct URL mapping (includes sublayer URLs)
        if old_url in self.url_mapping:
            return self.url_mapping[old_url]
            
        # Check sublayer mapping specifically
        if old_url in self.sublayer_mapping:
            return self.sublayer_mapping[old_url]
            
        # Try service URL mapping
        old_service = self._extract_service_url(old_url)
        if old_service and old_service in self.service_mapping:
            new_service = self.service_mapping[old_service]
            return old_url.replace(old_service, new_service)
            
        return None
        
    def update_text_references(self, text: str) -> str:
        """
        Update all ID and URL references in a text string.
        
        Args:
            text: Text containing references to update
            
        Returns:
            Updated text
        """
        updated = text
        
        # Update IDs
        for old_id, new_id in self.id_mapping.items():
            # Match IDs in various contexts
            patterns = [
                rf'\b{old_id}\b',  # Word boundary
                rf'"{old_id}"',     # Quoted
                rf"'{old_id}'",     # Single quoted
                rf'/{old_id}/',     # In URL path
                rf'={old_id}',      # As parameter value
                rf':{old_id}',      # After colon
            ]
            
            for pattern in patterns:
                if re.search(pattern, updated):
                    # Use the same pattern to replace, maintaining context
                    updated = re.sub(
                        pattern,
                        lambda m: m.group(0).replace(old_id, new_id),
                        updated
                    )
                    logger.debug(f"Updated ID reference: {old_id} -> {new_id}")
                    
        # Update URLs
        for old_url, new_url in self.url_mapping.items():
            if old_url in updated:
                updated = updated.replace(old_url, new_url)
                logger.debug(f"Updated URL reference: {old_url} -> {new_url}")
                
        # Update service URLs
        for old_service, new_service in self.service_mapping.items():
            if old_service in updated:
                updated = updated.replace(old_service, new_service)
                logger.debug(f"Updated service reference: {old_service} -> {new_service}")
                
        # Update sublayer URLs
        for old_sublayer, new_sublayer in self.sublayer_mapping.items():
            if old_sublayer in updated:
                updated = updated.replace(old_sublayer, new_sublayer)
                logger.debug(f"Updated sublayer reference: {old_sublayer} -> {new_sublayer}")
                
        return updated
        
    def update_url_with_id(self, url: str) -> str:
        """
        Update item IDs within URLs.
        
        Args:
            url: URL potentially containing item IDs
            
        Returns:
            Updated URL
        """
        updated_url = url
        
        # Common patterns for IDs in URLs
        patterns = [
            r'/items/([a-f0-9]{32})',  # Item ID in path
            r'id=([a-f0-9]{32})',       # ID parameter
            r'itemId=([a-f0-9]{32})',   # ItemId parameter
            r'webmap=([a-f0-9]{32})',   # Webmap parameter
            r'portalItem=([a-f0-9]{32})', # Portal item
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, updated_url)
            for match in matches:
                old_id = match.group(1)
                if old_id in self.id_mapping:
                    new_id = self.id_mapping[old_id]
                    updated_url = updated_url.replace(old_id, new_id)
                    logger.debug(f"Updated ID in URL: {old_id} -> {new_id}")
                    
        return updated_url
        
    def get_mapping(self) -> Dict[str, Dict[str, str]]:
        """
        Get the complete mapping dictionary.
        
        Returns:
            Dictionary containing all mappings
        """
        return {
            'ids': self.id_mapping,
            'urls': self.url_mapping,
            'services': self.service_mapping,
            'sublayers': self.sublayer_mapping
        }
        
    def _extract_service_url(self, url: str) -> Optional[str]:
        """
        Extract the base service URL from a full URL.
        
        Args:
            url: Full URL
            
        Returns:
            Base service URL or None
        """
        # Pattern for ArcGIS service URLs
        patterns = [
            r'(https?://[^/]+/[^/]+/rest/services/[^/]+/[^/]+/(?:Feature|Map|Vector)Server)',
            r'(https?://[^/]+/server/rest/services/[^/]+/[^/]+/(?:Feature|Map|Vector)Server)',
            r'(https?://services[0-9]*\.arcgis\.com/[^/]+/[^/]+/(?:Feature|Map|Vector)Server)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
                
        return None
        
    def find_references_in_dict(self, data: Dict) -> Dict[str, list]:
        """
        Find all ID and URL references in a dictionary.
        
        Args:
            data: Dictionary to search
            
        Returns:
            Dictionary of found references by type
        """
        references = {
            'ids': [],
            'urls': [],
            'potential_ids': []
        }
        
        def search_value(value):
            if isinstance(value, str):
                # Check for IDs (32 character hex strings)
                id_matches = re.findall(r'\b[a-f0-9]{32}\b', value)
                for match in id_matches:
                    if match in self.id_mapping:
                        references['ids'].append(match)
                    else:
                        references['potential_ids'].append(match)
                        
                # Check for URLs
                url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                url_matches = re.findall(url_pattern, value)
                references['urls'].extend(url_matches)
                
            elif isinstance(value, dict):
                for v in value.values():
                    search_value(v)
            elif isinstance(value, list):
                for item in value:
                    search_value(item)
                    
        search_value(data)
        
        # Remove duplicates
        references['ids'] = list(set(references['ids']))
        references['urls'] = list(set(references['urls']))
        references['potential_ids'] = list(set(references['potential_ids']))
        
        return references
        
    def update_json_urls(self, json_data: Any) -> Any:
        """
        Update all URL references in JSON data, including sublayer URLs.
        
        Args:
            json_data: JSON data (dict, list, or primitive)
            
        Returns:
            Updated JSON data
        """
        if isinstance(json_data, dict):
            updated = {}
            for key, value in json_data.items():
                # Common URL fields
                if key in ['url', 'serviceUrl', 'layerUrl', 'featureLayerUrl', 
                          'mapServiceUrl', 'dataUrl', 'sourceUrl']:
                    if isinstance(value, str):
                        new_url = self.get_new_url(value)
                        if new_url:
                            updated[key] = new_url
                            logger.debug(f"Updated {key}: {value} -> {new_url}")
                        else:
                            updated[key] = value
                    else:
                        updated[key] = value
                else:
                    updated[key] = self.update_json_urls(value)
            return updated
            
        elif isinstance(json_data, list):
            return [self.update_json_urls(item) for item in json_data]
            
        elif isinstance(json_data, str):
            # Check if this string contains URLs that need updating
            new_value = json_data
            
            # Update full URLs
            for old_url, new_url in self.url_mapping.items():
                if old_url in new_value:
                    new_value = new_value.replace(old_url, new_url)
                    
            # Update sublayer URLs
            for old_url, new_url in self.sublayer_mapping.items():
                if old_url in new_value:
                    new_value = new_value.replace(old_url, new_url)
                    
            # Update service URLs
            for old_service, new_service in self.service_mapping.items():
                if old_service in new_value:
                    new_value = new_value.replace(old_service, new_service)
                    
            return new_value
            
        else:
            return json_data
            
    def add_portal_mapping(self, source_portal_url: str, dest_portal_url: str):
        """
        Add a portal URL mapping.
        
        Args:
            source_portal_url: Source organization portal URL
            dest_portal_url: Destination organization portal URL
        """
        # Normalize URLs (remove trailing slashes)
        source_url = source_portal_url.rstrip('/')
        dest_url = dest_portal_url.rstrip('/')
        
        self.portal_mapping[source_url] = dest_url
        logger.debug(f"Added portal mapping: {source_url} -> {dest_url}")
        
    def add_pending_update(self, item_id: str, update_type: str, update_data: Dict):
        """
        Add a pending update for phase 2 resolution.
        
        Args:
            item_id: Item that needs updating
            update_type: Type of update needed ('embed_url', 'data_expression', etc.)
            update_data: Additional data needed for the update
        """
        if item_id not in self.pending_updates:
            self.pending_updates[item_id] = []
            
        self.pending_updates[item_id].append({
            'type': update_type,
            'data': update_data
        })
        logger.debug(f"Added pending update for {item_id}: {update_type}")
        
    def get_pending_updates(self) -> Dict[str, List[Dict]]:
        """Get all pending updates for phase 2 resolution."""
        return self.pending_updates
        
    def clear_pending_updates(self):
        """Clear all pending updates after resolution."""
        self.pending_updates.clear()
        
    def parse_arcade_portal_items(self, expression: str) -> List[Dict]:
        """
        Extract portal item references from an Arcade expression.
        
        Args:
            expression: Arcade expression code
            
        Returns:
            List of dictionaries with item_id and layer_index
        """
        pattern = r"FeatureSetByPortalItem\s*\(\s*\w+\s*,\s*['\"]([a-f0-9]{32})['\"]\s*(?:,\s*(\d+))?\s*\)"
        matches = re.findall(pattern, expression, re.IGNORECASE)
        
        results = []
        for match in matches:
            item_id = match[0]
            layer_index = int(match[1]) if match[1] else 0
            results.append({
                'item_id': item_id,
                'layer_index': layer_index
            })
            
        return results
        
    def update_arcade_expressions(self, expression: str, source_org_url: str = None, dest_org_url: str = None) -> str:
        """
        Update portal URLs and item IDs in Arcade expressions.
        
        Args:
            expression: Arcade expression to update
            source_org_url: Optional source organization URL
            dest_org_url: Optional destination organization URL
            
        Returns:
            Updated expression
        """
        updated = expression
        
        # Update portal URLs if provided
        if source_org_url and dest_org_url:
            updated = self.update_arcade_portal_url(updated, source_org_url, dest_org_url)
            
        # Update Portal('https://www.arcgis.com/') to destination org if dest_org_url provided
        if dest_org_url:
            generic_patterns = [
                (r"Portal\s*\(\s*['\"]https://www\.arcgis\.com/?['\"]\s*\)", f"Portal('{dest_org_url}')"),
                (r"Portal\s*\(\s*['\"]https://arcgis\.com/?['\"]\s*\)", f"Portal('{dest_org_url}')")
            ]
            for pattern, replacement in generic_patterns:
                updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
        
        # Update portal item references
        portal_items = self.parse_arcade_portal_items(updated)
        for item_ref in portal_items:
            old_id = item_ref['item_id']
            if old_id in self.id_mapping:
                new_id = self.id_mapping[old_id]
                # Replace the item ID in the expression, preserving the layer index
                old_pattern = rf"(FeatureSetByPortalItem\s*\(\s*\w+\s*,\s*['\"]){old_id}(['\"]\s*(?:,\s*{item_ref['layer_index']})?\s*\))"
                new_replacement = rf"\g<1>{new_id}\g<2>"
                updated = re.sub(old_pattern, new_replacement, updated, flags=re.IGNORECASE)
                logger.debug(f"Updated Arcade item reference: {old_id} -> {new_id}")
                
        return updated
        
    def update_arcade_portal_url(self, expression: str, old_url: str, new_url: str) -> str:
        """
        Update portal URLs in Arcade expressions.
        
        Args:
            expression: Arcade expression
            old_url: Source portal URL
            new_url: Destination portal URL
            
        Returns:
            Updated expression
        """
        # Normalize URLs
        old_url = old_url.rstrip('/')
        new_url = new_url.rstrip('/')
        
        # Handle various quote styles and formats
        patterns = [
            (f"Portal\\s*\\(\\s*['\"]\\s*{re.escape(old_url)}/?\\s*['\"]\\s*\\)", f"Portal('{new_url}')"),
            (f"Portal\\(['\"]\\s*{re.escape(old_url)}/?\\s*['\"]\\)", f"Portal('{new_url}')"),
        ]
        
        updated = expression
        for pattern, replacement in patterns:
            updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
            
        # Also update any portal mapping we know about
        for old_portal, new_portal in self.portal_mapping.items():
            if old_portal in updated:
                updated = updated.replace(old_portal, new_portal)
                
        return updated
        
    def update_embed_urls(self, url: str) -> Tuple[str, bool]:
        """
        Update embed URLs with known item mappings.
        
        Args:
            url: Embed URL to update
            
        Returns:
            Tuple of (updated_url, was_updated)
        """
        updated_url = url
        was_updated = False
        
        # Common embed URL patterns
        embed_patterns = [
            r'/apps/dashboards/#/([a-f0-9]{32})',
            r'/apps/experiencebuilder/experience/\?id=([a-f0-9]{32})',
            r'/apps/instant/app\.html\?appid=([a-f0-9]{32})',
            r'/apps/webappviewer/index\.html\?id=([a-f0-9]{32})',
            r'/home/item\.html\?id=([a-f0-9]{32})'
        ]
        
        for pattern in embed_patterns:
            match = re.search(pattern, updated_url, re.IGNORECASE)
            if match:
                old_id = match.group(1)
                if old_id in self.id_mapping:
                    new_id = self.id_mapping[old_id]
                    updated_url = updated_url.replace(old_id, new_id)
                    was_updated = True
                    logger.debug(f"Updated embed URL ID: {old_id} -> {new_id}")
                    
        # Update portal URLs in embed URLs
        for old_portal, new_portal in self.portal_mapping.items():
            if old_portal in updated_url:
                updated_url = updated_url.replace(old_portal, new_portal)
                was_updated = True
                
        return updated_url, was_updated
        
    def add_group_mapping(self, old_group_id: str, new_group_id: str):
        """
        Add a group ID mapping.
        
        Args:
            old_group_id: Source group ID
            new_group_id: Destination group ID
        """
        self.group_mapping[old_group_id] = new_group_id
        logger.debug(f"Added group mapping: {old_group_id} -> {new_group_id}")
        
    def add_domain_mapping(self, old_domain: str, new_domain: str):
        """
        Add a domain mapping for Hub sites.
        
        Args:
            old_domain: Source domain/subdomain
            new_domain: Destination domain/subdomain
        """
        self.domain_mapping[old_domain] = new_domain
        logger.debug(f"Added domain mapping: {old_domain} -> {new_domain}")
        
    def update_hub_references(self, json_data: Any) -> Any:
        """
        Update Hub-specific references including groups, domains, and organization URLs.
        
        Args:
            json_data: JSON data containing Hub references
            
        Returns:
            Updated JSON data
        """
        if isinstance(json_data, dict):
            updated = {}
            for key, value in json_data.items():
                # Group ID fields
                if key in ['contentGroupId', 'collaborationGroupId', 'followersGroupId', 
                          'groupId', 'catalogGroupId'] and isinstance(value, str):
                    if value in self.group_mapping:
                        updated[key] = self.group_mapping[value]
                        logger.debug(f"Updated group reference {key}: {value} -> {self.group_mapping[value]}")
                    else:
                        updated[key] = value
                # Catalog groups array
                elif key == 'groups' and isinstance(value, list):
                    updated_groups = []
                    for group_id in value:
                        if isinstance(group_id, str) and group_id in self.group_mapping:
                            updated_groups.append(self.group_mapping[group_id])
                            logger.debug(f"Updated catalog group: {group_id} -> {self.group_mapping[group_id]}")
                        else:
                            updated_groups.append(group_id)
                    updated[key] = updated_groups
                # Domain/hostname fields
                elif key in ['hostname', 'defaultHostname', 'internalUrl', 'subdomain'] and isinstance(value, str):
                    # Check domain mappings
                    updated_value = value
                    for old_domain, new_domain in self.domain_mapping.items():
                        if old_domain in value:
                            updated_value = value.replace(old_domain, new_domain)
                            logger.debug(f"Updated domain in {key}: {old_domain} -> {new_domain}")
                    updated[key] = updated_value
                else:
                    # Recursively update nested structures
                    updated[key] = self.update_hub_references(value)
            return updated
            
        elif isinstance(json_data, list):
            return [self.update_hub_references(item) for item in json_data]
            
        elif isinstance(json_data, str):
            # Update group IDs in strings
            updated_value = json_data
            for old_group, new_group in self.group_mapping.items():
                if old_group in updated_value:
                    updated_value = updated_value.replace(old_group, new_group)
                    
            # Update domains in strings
            for old_domain, new_domain in self.domain_mapping.items():
                if old_domain in updated_value:
                    updated_value = updated_value.replace(old_domain, new_domain)
                    
            return updated_value
            
        else:
            return json_data
            
    def update_org_urls(self, json_data: Any, dest_gis: Any) -> Any:
        """
        Update organization-specific URLs in JSON data.
        
        Args:
            json_data: JSON data containing org URLs
            dest_gis: Destination GIS connection
            
        Returns:
            Updated JSON data
        """
        if not hasattr(dest_gis, 'url'):
            return json_data
            
        # Convert to string for easier replacement
        json_str = json.dumps(json_data) if not isinstance(json_data, str) else json_data
        
        # Common org URL patterns to replace
        org_patterns = [
            r'https?://[^/]+\.maps\.arcgis\.com',  # Organization URLs
            r'https?://www\.arcgis\.com/sharing/rest',  # Sharing API
            r'https?://[^/]+\.arcgis\.com',  # General ArcGIS URLs
        ]
        
        # Get destination org URL
        dest_url = dest_gis.url.rstrip('/')
        
        # Update portal mappings
        for old_portal, new_portal in self.portal_mapping.items():
            json_str = json_str.replace(old_portal, new_portal)
            
        # Parse back to original type
        if isinstance(json_data, str):
            return json_str
        else:
            return json.loads(json_str)
            
    def update_json_references(self, json_data: Any) -> Any:
        """
        Update all references in JSON data including IDs, URLs, groups, and domains.
        
        Args:
            json_data: JSON data to update
            
        Returns:
            Updated JSON data
        """
        # First update regular IDs and URLs
        updated = self.update_json_urls(json_data)
        
        # Then update Hub-specific references
        updated = self.update_hub_references(updated)
        
        # Update ID references
        if isinstance(updated, dict):
            result = {}
            for key, value in updated.items():
                # Check for ID fields
                if key in ['itemId', 'webmap', 'portalItemId', 'sourceItemId', 
                          'targetItemId', 'id', 'layerId', 'serviceItemId', 'parentId'] and isinstance(value, str):
                    if value in self.id_mapping:
                        result[key] = self.id_mapping[value]
                        logger.debug(f"Updated {key}: {value} -> {self.id_mapping[value]}")
                    else:
                        result[key] = value
                else:
                    result[key] = self.update_json_references(value)
            return result
        elif isinstance(updated, list):
            return [self.update_json_references(item) for item in updated]
        elif isinstance(updated, str):
            # Update IDs in strings
            for old_id, new_id in self.id_mapping.items():
                if old_id in updated:
                    updated = updated.replace(old_id, new_id)
            return updated
        else:
            return updated