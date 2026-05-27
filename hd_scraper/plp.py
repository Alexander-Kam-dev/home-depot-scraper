"""Product listing page (PLP) scraper for extracting SKUs and category data."""

import json
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx


def get_skus(
    category_url: str,
    httpx_client: httpx.Client,
    limit: int = 50,
) -> tuple[list[str], str]:
    """
    Extract SKUs from a Home Depot PLP (product listing page).
    
    Collects more SKUs than needed (aiming for 80+) to handle failures during enrichment.
    
    Args:
        category_url: Full URL of the category page
        httpx_client: Configured httpx client with cookies
        limit: Target number of SKUs (actual returned may be more)
        
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
    
    while len(skus) < target_count and page <= max_pages:
        try:
            # Attempt to fetch from API first
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
            
            # Format: capitalize and replace hyphens
            formatted = part.replace("-", " ").title()
            category_parts.append(formatted)
        
        if not category_parts:
            # Try to extract from the first part
            formatted = parts[0].replace("-", " ").title()
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
        
        # Extract category ID from URL parameters
        params = parse_qs(parsed.query)
        
        # Common API endpoint patterns
        api_endpoints = [
            "/api/products/search",
            "/api/v1/products",
            "/api/graphql",
        ]
        
        for endpoint in api_endpoints:
            try:
                # Build API call with pagination
                api_url = f"https://www.homedepot.com{endpoint}"
                
                # Try with common parameters
                api_params = {
                    "offset": (page - 1) * 24,
                    "limit": 24,
                    "searchTerm": "",
                }
                
                response = httpx_client.get(api_url, params=api_params, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    skus = _extract_skus_from_api_response(data)
                    if skus:
                        return skus
            
            except Exception:
                continue
        
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
                    pass
        except Exception:
            pass
    
    # Fallback: Extract from common product data attributes
    # Pattern: data-productid="123456"
    sku_pattern = r'data-productid=["\']([^\'"]+)["\']'
    found = re.findall(sku_pattern, html, re.IGNORECASE)
    skus.extend(found)
    
    # Pattern: class="productid-123456"
    sku_pattern = r'class="[^"]*productid-([^"\s]+)[^"]*"'
    found = re.findall(sku_pattern, html, re.IGNORECASE)
    skus.extend(found)
    
    return list(set(skus))  # Remove duplicates


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
