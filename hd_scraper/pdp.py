"""Product detail page (PDP) scraper for extracting enriched product data."""

import json
import logging
import re
from typing import Optional

import httpx

from .block_detector import BlockDetector, BlockedError

logger = logging.getLogger(__name__)
block_detector = BlockDetector()


def fetch_product_details(
    sku: str,
    httpx_client: httpx.Client,
    discovered_endpoints: Optional[list[dict]] = None,
) -> dict:
    """
    Fetch enriched product details for a SKU.
    
    Attempts to use discovered endpoints first, then guesses common endpoints,
    and falls back to HTML scraping.
    
    Args:
        sku: Product SKU
        httpx_client: Configured httpx client with cookies
        discovered_endpoints: List of discovered JSON endpoints from network capture
        
    Returns:
        Dictionary with product details (name, price, description, features, image_url, stock, aisle, bay)
        
    Raises:
        BlockedError: If a block condition is detected
    """
    details = {
        "name": "",
        "price": "",
        "description": "",
        "features": [],
        "image_url": "",
        "stock": "",
        "aisle": "",
        "bay": "",
    }
    
    try:
        # Try discovered endpoints first
        if discovered_endpoints:
            for endpoint_info in discovered_endpoints:
                endpoint_url = endpoint_info.get("url", "")
                try:
                    api_details = _fetch_from_discovered_endpoint(sku, endpoint_url, httpx_client)
                    if api_details.get("name"):
                        details.update(api_details)
                        return details
                except BlockedError:
                    raise
                except Exception:
                    continue
        
        # Try guessed API endpoints
        try:
            api_details = _fetch_from_api(sku, httpx_client)
            if api_details:
                details.update(api_details)
                return details
        except BlockedError:
            # Re-raise block errors
            raise
        
        # Fallback to HTML scraping
        html_details = _fetch_from_html(sku, httpx_client)
        details.update(html_details)
        return details
    
    except BlockedError:
        # Re-raise block errors
        raise
    except Exception as e:
        # Return partial details on other errors
        logger.warning(f"Failed to fetch product details for SKU {sku}: {e}")
        return details


def _fetch_from_discovered_endpoint(
    sku: str,
    endpoint_url: str,
    httpx_client: httpx.Client,
) -> dict:
    """
    Try to fetch product details from a discovered JSON endpoint.
    
    Args:
        sku: Product SKU
        endpoint_url: Base endpoint URL discovered from network capture
        httpx_client: Configured httpx client
        
    Returns:
        Dictionary with product details, or empty dict if unavailable
        
    Raises:
        BlockedError: If a block condition is detected
    """
    try:
        # Try appending SKU to endpoint URL
        url = f"{endpoint_url.rstrip('/')}/{sku}"
        response = httpx_client.get(url, timeout=10.0)
        
        # Check for block conditions
        if block_detector.check_response(response, url):
            raise BlockedError(block_detector.get_block_reason())
        
        if response.status_code == 200:
            data = response.json()
            details = _parse_api_response(data)
            if details.get("name"):
                return details
    
    except BlockedError:
        raise
    except Exception:
        pass
    
    return {}


def _fetch_from_api(sku: str, httpx_client: httpx.Client) -> dict:
    """
    Try to fetch product details from Home Depot API.
    
    Args:
        sku: Product SKU
        httpx_client: Configured httpx client
        
    Returns:
        Dictionary with product details, or empty dict if API unavailable
        
    Raises:
        BlockedError: If a block condition is detected (403, 429, captcha)
    """
    details = {}
    
    try:
        # Try common API endpoints
        api_endpoints = [
            f"/api/products/{sku}",
            f"/api/v1/products/{sku}",
        ]
        
        for endpoint in api_endpoints:
            try:
                url = f"https://www.homedepot.com{endpoint}"
                response = httpx_client.get(url, timeout=10.0)
                
                # Check for block conditions
                if block_detector.check_response(response, endpoint):
                    raise BlockedError(block_detector.get_block_reason())
                
                if response.status_code == 200:
                    data = response.json()
                    details = _parse_api_response(data)
                    if details.get("name"):
                        return details
            
            except BlockedError:
                # Re-raise block errors immediately
                raise
            except Exception:
                # Silently continue to next endpoint (network, parse, timeout errors)
                continue
        
        return {}
    
    except BlockedError:
        raise
    except Exception:
        return {}


def _parse_api_response(data: dict) -> dict:
    """
    Parse product details from API response.
    
    Args:
        data: API response data
        
    Returns:
        Dictionary with extracted details
    """
    details = {}
    
    # Extract basic info
    details["name"] = data.get("title") or data.get("name") or data.get("productName") or ""
    
    # Extract price
    price = data.get("price") or data.get("regularPrice") or data.get("salePrice")
    if price is not None:
        details["price"] = _clean_price(str(price))
    else:
        details["price"] = ""
    
    # Extract description
    details["description"] = data.get("description") or data.get("overview") or ""
    
    # Extract features
    features = data.get("features") or data.get("specs") or data.get("specifications") or []
    if isinstance(features, dict):
        details["features"] = list(features.values())
    elif isinstance(features, list):
        details["features"] = [str(f) for f in features if f]
    else:
        details["features"] = []
    
    # Extract image
    images = data.get("images") or []
    if isinstance(images, list) and images:
        # Get highest resolution image
        image_url = images[0]
        if isinstance(image_url, dict):
            image_url = image_url.get("url") or image_url.get("src") or ""
        details["image_url"] = str(image_url)
    else:
        image = data.get("image") or data.get("imageUrl") or ""
        details["image_url"] = str(image) if image else ""
    
    # Extract store-specific data
    # Stock information
    store_data = data.get("storeInfo") or data.get("store") or {}
    if isinstance(store_data, dict):
        details["stock"] = str(store_data.get("inventory") or store_data.get("stock") or "")
        details["aisle"] = str(store_data.get("aisle") or "")
        details["bay"] = str(store_data.get("bay") or "")
    else:
        details["stock"] = ""
        details["aisle"] = ""
        details["bay"] = ""
    
    return details


def _fetch_from_html(sku: str, httpx_client: httpx.Client) -> dict:
    """
    Fetch product details from HTML (fallback method).
    
    Args:
        sku: Product SKU
        httpx_client: Configured httpx client
        
    Returns:
        Dictionary with extracted details
        
    Raises:
        BlockedError: If a block condition is detected
    """
    details = {
        "name": "",
        "price": "",
        "description": "",
        "features": [],
        "image_url": "",
        "stock": "",
        "aisle": "",
        "bay": "",
    }
    
    try:
        # Try to construct product URL
        url = f"https://www.homedepot.com/p/{sku}"
        response = httpx_client.get(url, timeout=10.0)
        
        # Check for block conditions
        if block_detector.check_response(response, url):
            raise BlockedError(block_detector.get_block_reason())
        
        if response.status_code != 200:
            return details
        
        html = response.text
        
        # Extract product name from title tag or h1
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if name_match:
            details["name"] = name_match.group(1).strip()
        else:
            title_match = re.search(r'<title>([^-]+)', html)
            if title_match:
                details["name"] = title_match.group(1).strip()
        
        # Extract price
        price_match = re.search(r'\$\s*([0-9]+(?:\.[0-9]{2})?)', html)
        if price_match:
            details["price"] = price_match.group(1)
        
        # Extract description from common div/section patterns
        desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)</div>', html)
        if desc_match:
            details["description"] = desc_match.group(1).strip()
        
        # Extract image URL
        img_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*alt="Product image"', html)
        if img_match:
            details["image_url"] = img_match.group(1)
        
        # Extract features from list
        features_match = re.findall(
            r'<li[^>]*class="[^"]*spec[^"]*"[^>]*>([^<]+)</li>',
            html,
            re.IGNORECASE
        )
        if features_match:
            details["features"] = [f.strip() for f in features_match]
        
        # Try to extract inventory/location info from JSON embedded in page
        json_match = re.search(r'<script[^>]*>.*?"inventory":\s*(\d+).*?</script>', html, re.DOTALL)
        if json_match:
            details["stock"] = json_match.group(1)
        
        return details
    
    except BlockedError:
        # Re-raise block errors
        raise
    except Exception:
        return details


def _clean_price(price_str: str) -> str:
    """
    Clean price string to only contain digits and decimal point.
    
    Args:
        price_str: Raw price string
        
    Returns:
        Cleaned price string
    """
    # Remove all non-digit and non-decimal characters
    cleaned = re.sub(r"[^\d.]", "", price_str)
    
    # Ensure only one decimal point
    if "." in cleaned:
        parts = cleaned.split(".")
        cleaned = parts[0] + "." + "".join(parts[1:])
    
    # Remove leading/trailing decimals
    cleaned = cleaned.strip(".")
    
    return cleaned
