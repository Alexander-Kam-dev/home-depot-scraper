"""
Endpoint discovery from network logs.

This module analyzes network capture data to identify and extract
stable API endpoints used by Home Depot for PLP and PDP data.
"""

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


def find_json_endpoints(network_log: list[dict]) -> dict:
    """
    Identify JSON API endpoints from network log.
    
    Args:
        network_log: List of network log entries from bootstrap
        
    Returns:
        Dictionary with 'plp_endpoints' and 'pdp_endpoints' lists
    """
    plp_endpoints = []
    pdp_endpoints = []
    
    for entry in network_log:
        if not isinstance(entry, dict):
            continue
        
        url = entry.get("url", "")
        content_type = entry.get("content_type", "")
        status = entry.get("status", 0)
        method = entry.get("method", "")
        
        # Skip non-successful responses
        if status != 200:
            continue
        
        # Look for JSON endpoints
        if "application/json" not in content_type:
            continue
        
        # Skip internal/tracking endpoints
        if any(skip in url for skip in ["beacon", "analytics", "tracking", "ads", "pixel"]):
            continue
        
        # Extract base URL (remove query parameters)
        base_url = url.split("?")[0] if "?" in url else url
        
        # Classify endpoints by common patterns
        plp_patterns = [
            "/search", "/category", "/browse", "/api/graphql", 
            "/mobileapi/", "/p/product-list", "/products/search",
        ]
        pdp_patterns = [
            "/p/", "/product/", "/pdp", "/api/product", "/mobileapi/product",
        ]
        
        # Avoid duplicates
        existing_urls = [e["url"] for e in plp_endpoints + pdp_endpoints]
        
        if base_url in existing_urls:
            continue
        
        # Check for PLP endpoints
        if any(pattern in base_url.lower() for pattern in plp_patterns):
            plp_endpoints.append({
                "url": base_url,
                "method": method,
                "content_type": content_type,
            })
        
        # Check for PDP endpoints
        elif any(pattern in base_url.lower() for pattern in pdp_patterns):
            pdp_endpoints.append({
                "url": base_url,
                "method": method,
                "content_type": content_type,
            })
    
    return {
        "plp_endpoints": plp_endpoints,
        "pdp_endpoints": pdp_endpoints,
    }


def extract_pagination_params(url: str) -> dict:
    """
    Extract pagination parameters from URL.
    
    Args:
        url: URL to parse
        
    Returns:
        Dictionary with pagination parameters (offset, limit, page, etc.)
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    
    # Convert lists to single values
    params = {k: v[0] if v else None for k, v in params.items()}
    
    pagination_info = {}
    
    # Common pagination parameter names
    for offset_name in ["offset", "from", "start"]:
        if offset_name in params:
            try:
                pagination_info["offset"] = int(params[offset_name])
            except (ValueError, TypeError):
                pass
    
    for limit_name in ["limit", "size", "per_page"]:
        if limit_name in params:
            try:
                pagination_info["limit"] = int(params[limit_name])
            except (ValueError, TypeError):
                pass
    
    # Check for page parameter
    if "page" in params:
        try:
            pagination_info["page"] = int(params["page"])
        except (ValueError, TypeError):
            pass
    
    return pagination_info


def get_stored_endpoints() -> dict:
    """
    Get stored endpoint discovery data from previous session.
    
    Returns:
        Dictionary with endpoint info, or empty dict if not available
    """
    try:
        with open("artifacts/endpoints.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def store_endpoints(endpoints: dict) -> None:
    """
    Store endpoint discovery data for later use.
    
    Args:
        endpoints: Dictionary with endpoint information
    """
    from pathlib import Path
    Path("artifacts").mkdir(parents=True, exist_ok=True)
    
    with open("artifacts/endpoints.json", "w", encoding="utf-8") as f:
        json.dump(endpoints, f, indent=2)


def save_sample_response(response_body: str, name: str = "sample.json") -> None:
    """
    Save a sample API response for analysis.
    
    Args:
        response_body: Response body text (JSON)
        name: Filename to save to (in artifacts/)
    """
    from pathlib import Path
    
    Path("artifacts").mkdir(parents=True, exist_ok=True)
    
    # Try to parse and pretty-print JSON
    try:
        data = json.loads(response_body)
        output = json.dumps(data, indent=2)
    except json.JSONDecodeError:
        output = response_body
    
    with open(f"artifacts/{name}", "w", encoding="utf-8") as f:
        f.write(output)
