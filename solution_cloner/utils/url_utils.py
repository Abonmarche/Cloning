"""
URL Utilities
=============
Utilities for handling and normalizing ArcGIS URLs.
"""

from urllib.parse import urlparse, urlunparse
import logging

logger = logging.getLogger(__name__)


def normalize_portal_url(url: str) -> str:
    """
    Normalize a portal URL to ensure consistent formatting.
    Converts the domain portion to lowercase while preserving path case.
    
    Args:
        url: Portal URL to normalize
        
    Returns:
        Normalized URL with lowercase domain
    """
    if not url:
        return url
        
    try:
        parsed = urlparse(url)
        
        # Convert netloc (domain) to lowercase
        normalized_netloc = parsed.netloc.lower()
        
        # Reconstruct URL with normalized domain
        normalized = urlunparse((
            parsed.scheme,
            normalized_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        logger.debug(f"Normalized URL: {url} -> {normalized}")
        return normalized
        
    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {str(e)}")
        return url


def extract_portal_url_from_gis(gis) -> str:
    """
    Extract and normalize the portal URL from a GIS connection.
    
    Args:
        gis: ArcGIS GIS connection object
        
    Returns:
        Normalized portal URL
    """
    if not gis or not hasattr(gis, 'url'):
        return "https://www.arcgis.com"
        
    # Extract base URL from GIS connection
    gis_url = gis.url
    
    # Parse the URL to get just the protocol and domain
    parsed = urlparse(gis_url)
    
    # Reconstruct with just scheme and netloc (domain)
    portal_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Normalize to lowercase
    return normalize_portal_url(portal_url)


def ensure_url_consistency(source_url: str, dest_url: str) -> tuple:
    """
    Ensure both URLs are normalized for consistent comparison.
    
    Args:
        source_url: Source portal URL
        dest_url: Destination portal URL
        
    Returns:
        Tuple of (normalized_source_url, normalized_dest_url)
    """
    return normalize_portal_url(source_url), normalize_portal_url(dest_url)