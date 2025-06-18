"""
ID Mapper Utility
=================
Manages the mapping between source and destination item IDs and URLs.
"""

from typing import Dict, Optional, Tuple
import re
import logging
from urllib.parse import urlparse, urlunparse


logger = logging.getLogger(__name__)


class IDMapper:
    """Manages mappings between source and destination IDs/URLs."""
    
    def __init__(self):
        """Initialize the ID mapper."""
        self.id_mapping: Dict[str, str] = {}  # old_id -> new_id
        self.url_mapping: Dict[str, str] = {}  # old_url -> new_url
        self.service_mapping: Dict[str, str] = {}  # old_service_url -> new_service_url
        
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
        # Direct URL mapping
        if old_url in self.url_mapping:
            return self.url_mapping[old_url]
            
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
            'services': self.service_mapping
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