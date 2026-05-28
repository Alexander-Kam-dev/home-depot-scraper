"""Product listing page (PLP) scraper for extracting SKUs and category data."""

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx

logger = logging.getLogger(__name__)

# Constants
API_PAGE_SIZE = 24


def get_skus(
    category_url: str,
    httpx_client: httpx.Client,
    limit: int = 50,
    discovered_endpoints: Optional[list[dict]] = None,
) -> tuple[list[str], str]:
    """
    Extract SKUs from a Home Depot PLP (product listing page).
    
    Collects more SKUs than needed (aiming for 80+) to handle failures during enrichment.
    
    Attempts to use discovered JSON endpoints first, then falls back to HTML parsing.
    
    Args:
        category_url: Full URL of the category page
        httpx_client: Configured httpx client with cookies
        limit: Target number of SKUs (actual returned may be more)
        discovered_endpoints: List of discovered JSON endpoints from network capture
        
    Returns:
        Tuple of (skus: list of unique SKU strings, category_path: formatted path)
        
    Raises:
        RuntimeError: If SKU extraction fails
    """
    skus = set()
    category_path = _extract_category_path(category_url)
    page = 1
    max_pages = 5  # Limit pagination attempts
    target_count = int(limit * 1.6)  # Overfetch to ~80 for 50 target
    
    # Try endpoint-based approach first if endpoints are available
    if discovered_endpoints:
        for endpoint_info in discovered_endpoints:
            endpoint_url = endpoint_info.get("url", "")
            if _fetch_from_endpoint(endpoint_url, httpx_client, skus, max_pages, target_count):
                if len(skus) >= target_count:
                    break
    
    # If we have enough SKUs from endpoints, return early
    if len(skus) >= target_count:
        return sorted(list(skus)), category_path
    
    # Fallback to guessed API endpoints
    while len(skus) < target_count and page <= max_pages:
        try:
            # Attempt to fetch from guessed API first
            api_skus = _fetch_from_api(category_url, httpx_client, page)
            if api_skus:
                skus.update(api_skus)
                if len(skus) >= target_count:
                    break
                page += 1
                continue
            
            # Fallback to HTML parsing
            html = httpx_client.get(category_url, params={"page": page} if page > 1 else None).text
            html_skus = _extract_skus_from_html(html)
            
            if not html_skus:
                break  # No more products
            
            skus.update(html_skus)
            page += 1
            
        except Exception as e:
            # If we have some SKUs, continue; otherwise raise
            if not skus:
                raise RuntimeError(f"Failed to extract SKUs: {e}") from e
            break
    
    return sorted(list(skus)), category_path


def _fetch_from_endpoint(
    endpoint_url: str,
    httpx_client: httpx.Client,
    skus: set,
    max_pages: int,
    target_count: int,
) -> bool:
    """
    Fetch SKUs from a discovered JSON endpoint with pagination.
    
    Args:
        endpoint_url: Base endpoint URL
        httpx_client: Configured httpx client
        skus: Set to add found SKUs to
        max_pages: Maximum number of pages to fetch
        target_count: Target number of SKUs
        
    Returns:
        True if endpoint produced results, False otherwise
    """
    try:
        page = 1
        while len(skus) < target_count and page <= max_pages:
            try:
                # Try with offset pagination
                params = {"offset": (page - 1) * API_PAGE_SIZE, "limit": API_PAGE_SIZE}
                response = httpx_client.get(endpoint_url, params=params, timeout=10.0)
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                found_skus = _extract_skus_from_api_response(data)
                
                if not found_skus:
                    break
                
                skus.update(found_skus)
                page += 1
            
            except Exception as e:
                logger.debug(f"Failed to fetch from endpoint {endpoint_url} page {page}: {e}")
                break
        
        return len(skus) > 0
    
    except Exception as e:
        logger.debug(f"Error fetching from endpoint {endpoint_url}: {e}")
        return False


def _extract_category_path(url: str) -> str:
    """
    Extract and format category path from URL.
    
    Attempts to derive from breadcrumbs or URL path.
    Format like: "Bath - Bathroom Faucets - Touchless"
    
    Args:
        url: Category URL
        
    Returns:
        Formatted category path string
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        
        # Home Depot URL structure: /b/category-name/subcategory/...
        # or /c/category/subcategory
        parts = [p for p in path.split("/") if p]
        
        if not parts:
            return "products"
        
        # Format as human-readable path (replace hyphens with spaces, title case)
        category_parts = []
        for part in parts[1:]:  # Skip 'b' or 'c'
            # Handle category codes (like N-5yc1vZbreoZ1z0nv12)
            if part.startswith("N-"):
                break
            
            # Format: replace hyphens, capitalize each word
            formatted = " ".join(word.capitalize() for word in part.split("-"))
            category_parts.append(formatted)
        
        if not category_parts and len(parts) > 1:
            # Try to extract from the first part
            formatted = " ".join(word.capitalize() for word in parts[0].split("-"))
            return formatted
        
        return " - ".join(category_parts) if category_parts else "products"
    
    except Exception:
        return "products"


def _fetch_from_api(
    category_url: str,
    httpx_client: httpx.Client,
    page: int = 1,
) -> list[str]:
    """
    Try to fetch SKUs from Home Depot's internal API.
    
    Args:
        category_url: Category URL
        httpx_client: Configured httpx client
        page: Page number
        
    Returns:
        List of SKU strings, or empty list if API not found
    """
    try:
        # Try common Home Depot API patterns
        parsed = urlparse(category_url)
        
        # Try GraphQL endpoint
        try:
            graphql_url = "https://www.homedepot.com/apiservice/v1/graphql"
            
            # Extract category parameters from original URL
            query_params = parse_qs(parsed.query)
            
            # Build GraphQL query
            graphql_payload = {
                "operationName": "GetSearchProducts",
                "variables": {
                    "searchInput": {
                        "query": "",
                        "offset": (page - 1) * API_PAGE_SIZE,
                        "limit": API_PAGE_SIZE,
                    }
                },
                "query": "query GetSearchProducts($searchInput: SearchInput!) { search(input: $searchInput) { products { productId } } }"
            }
            
            response = httpx_client.post(
                graphql_url,
                json=graphql_payload,
                timeout=10.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                skus = _extract_skus_from_api_response(data)
                if skus:
                    return skus
        
        except Exception:
            pass
        
        # Try REST API endpoint
        try:
            api_url = "https://www.homedepot.com/api/v1/products"
            
            api_params = {
                "offset": (page - 1) * API_PAGE_SIZE,
                "limit": API_PAGE_SIZE,
            }
            
            response = httpx_client.get(api_url, params=api_params, timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                skus = _extract_skus_from_api_response(data)
                if skus:
                    return skus
        
        except Exception:
            pass
        
        return []
    
    except Exception:
        return []


def _extract_skus_from_api_response(data: dict) -> list[str]:
    """
    Extract SKUs from Home Depot API response.
    
    Args:
        data: API response data
        
    Returns:
        List of SKU strings
    """
    skus = []
    
    # Navigate through common API response structures
    for key in ["products", "items", "results", "data"]:
        if key in data and isinstance(data[key], list):
            for item in data[key]:
                if isinstance(item, dict):
                    sku = item.get("sku") or item.get("productId") or item.get("id")
                    if sku:
                        skus.append(str(sku))
    
    return skus


def _extract_skus_from_html(html: str) -> list[str]:
    """
    Extract SKUs from PLP HTML.
    
    Prefers extracting from embedded JSON state, falls back to CSS selectors.
    
    Args:
        html: PLP HTML content
        
    Returns:
        List of SKU strings
    """
    skus = []
    
    # Try to find SKUs in embedded JSON (preferred method)
    # Home Depot often embeds product data in script tags
    
    # Pattern 1: Look for __NEXT_DATA__ or similar state
    state_patterns = [
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        r'<script[^>]*>(.*?"productId".*?)</script>',
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
    ]
    
    for pattern in state_patterns:
        try:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    # Try to parse as JSON
                    data = json.loads(match)
                    found_skus = _find_skus_in_json(data)
                    skus.extend(found_skus)
                except json.JSONDecodeError:
                    # Not JSON, try text extraction
                    pass
        except Exception:
            pass
    
    # Fallback: Extract from common product data attributes
    # Pattern: data-productid="123456"
    sku_pattern = r'(?:data-|data["\']?\s*[=:]\s*["\']?)productid["\']?\s*[=:]\s*["\']?([^\'">\s]+)'
    found = re.findall(sku_pattern, html, re.IGNORECASE)
    skus.extend(found)
    
    # Pattern: "productId":"123456" or "productId": 123456
    sku_pattern = r'["\']productId["\']:\s*["\']?(\d+)["\']?'
    found = re.findall(sku_pattern, html)
    skus.extend(found)
    
    # Pattern: "sku":"123456" or "sku": 123456
    sku_pattern = r'["\']sku["\']:\s*["\']?(\d+)["\']?'
    found = re.findall(sku_pattern, html)
    skus.extend(found)
    
    # Remove duplicates and empty strings
    skus = list(set(s for s in skus if s and s.strip()))
    
    return skus


def _find_skus_in_json(data: dict, _visited: Optional[set] = None) -> list[str]:
    """
    Recursively find SKUs in JSON data structure.
    
    Args:
        data: JSON data to search
        _visited: Internal set to track visited objects
        
    Returns:
        List of SKU strings
    """
    if _visited is None:
        _visited = set()
    
    skus = []
    
    if isinstance(data, dict):
        # Check for SKU fields
        for key in ["sku", "productId", "id", "product_id"]:
            if key in data:
                value = data[key]
                if isinstance(value, str):
                    skus.append(value)
                elif isinstance(value, (int, float)):
                    skus.append(str(value))
        
        # Recurse into nested structures
        for value in data.values():
            if isinstance(value, (dict, list)):
                obj_id = id(value)
                if obj_id not in _visited:
                    _visited.add(obj_id)
                    if isinstance(value, dict):
                        skus.extend(_find_skus_in_json(value, _visited))
                    elif isinstance(value, list):
                        skus.extend(_find_skus_in_list(value, _visited))
    
    return skus


def _find_skus_in_list(data: list, _visited: Optional[set] = None) -> list[str]:
    """
    Recursively find SKUs in JSON list structure.
    
    Args:
        data: JSON list to search
        _visited: Internal set to track visited objects
        
    Returns:
        List of SKU strings
    """
    if _visited is None:
        _visited = set()
    
    skus = []
    
    for item in data:
        if isinstance(item, dict):
            obj_id = id(item)
            if obj_id not in _visited:
                _visited.add(obj_id)
                skus.extend(_find_skus_in_json(item, _visited))
        elif isinstance(item, list):
            obj_id = id(item)
            if obj_id not in _visited:
                _visited.add(obj_id)
                skus.extend(_find_skus_in_list(item, _visited))
    
    return skus
