"""Home Depot product scraper using httpx with retry logic."""

import json
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Product


class HomeDepotScraper:
    """Scraper for Home Depot products with retry logic."""

    BASE_URL = "https://www.homedepot.com"
    STORE_ID = "hd-0205"
    
    def __init__(self, cookies: Optional[dict[str, str]] = None):
        """
        Initialize scraper with optional cookies from Playwright session.
        
        Args:
            cookies: Dictionary of cookies from Playwright context
        """
        self.cookies = cookies or {}
        self.session = httpx.Client(
            base_url=self.BASE_URL,
            cookies=self.cookies,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            },
            timeout=30.0,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _fetch_page(self, url: str, params: Optional[dict] = None) -> str:
        """
        Fetch a page with retry logic.
        
        Args:
            url: URL to fetch
            params: Query parameters
            
        Returns:
            Response text
            
        Raises:
            httpx.HTTPError: If request fails after retries
        """
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.text

    def extract_products_from_html(self, html: str, category_path: str) -> list[Product]:
        """
        Extract products from Home Depot category page HTML.
        
        Args:
            html: HTML content of category page
            category_path: Category path for the products
            
        Returns:
            List of Product objects
        """
        products = []
        
        # Look for product data in page scripts or API responses
        # Home Depot typically embeds product data in JSON within script tags
        # or provides it via API calls
        
        # Pattern to find product data in script tags
        script_pattern = r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        matches = re.findall(script_pattern, html, re.DOTALL)
        
        if not matches:
            # Try alternative pattern for other data sources
            script_pattern = r'<script[^>]*>(.*?"productId".*?)</script>'
            matches = re.findall(script_pattern, html, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                products.extend(self._parse_product_data(data, category_path))
            except json.JSONDecodeError:
                continue
        
        return products

    def _parse_product_data(self, data: dict, category_path: str) -> list[Product]:
        """
        Parse product data from JSON structure.
        
        Args:
            data: JSON data containing product information
            category_path: Category path for products
            
        Returns:
            List of parsed Product objects
        """
        products = []
        
        # Navigate through Home Depot's data structure
        # This is a simplified extraction - actual structure may vary
        try:
            # Try to find products in common locations in the JSON
            items = self._find_items_in_data(data)
            
            for item in items:
                try:
                    product = self._create_product(item, category_path)
                    if product:
                        products.append(product)
                except (ValueError, KeyError):
                    # Skip invalid products
                    continue
        except Exception:
            pass
        
        return products

    def _find_items_in_data(self, data: dict, _visited_paths: Optional[set] = None) -> list[dict]:
        """
        Recursively find product items in nested JSON structure.
        
        Args:
            data: JSON data to search
            _visited_paths: Internal set to track visited paths and avoid infinite recursion
            
        Returns:
            List of product item dictionaries
        """
        if _visited_paths is None:
            _visited_paths = set()
        
        items = []
        
        if isinstance(data, dict):
            # Check for common product array keys
            for key in ["products", "items", "results", "data"]:
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        # Only add if it's a dict with product-like data
                        if isinstance(item, dict) and any(
                            k in item for k in ["id", "productId", "sku", "name", "title"]
                        ):
                            items.append(item)
            
            # Recursively search nested structures (but skip already-processed keys)
            for key, value in data.items():
                if key not in ["products", "items", "results", "data"]:
                    if isinstance(value, (dict, list)):
                        # Create path identifier to avoid revisiting same structures
                        path_id = f"{id(value)}_{key}"
                        if path_id not in _visited_paths:
                            _visited_paths.add(path_id)
                            items.extend(self._find_items_in_data(value, _visited_paths))
        
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                if isinstance(item, dict) and any(
                    k in item for k in ["id", "productId", "sku"]
                ):
                    items.append(item)
                elif isinstance(item, (dict, list)):
                    path_id = f"{id(item)}_{idx}"
                    if path_id not in _visited_paths:
                        _visited_paths.add(path_id)
                        items.extend(self._find_items_in_data(item, _visited_paths))
        
        return items

    def _create_product(self, item: dict, category_path: str) -> Optional[Product]:
        """
        Create a Product object from item data.
        
        Args:
            item: Product item data
            category_path: Category path
            
        Returns:
            Product object or None if required fields are missing
        """
        # Extract fields with fallbacks
        product_id = item.get("id") or item.get("productId") or item.get("sku")
        name = item.get("name") or item.get("title") or ""
        
        # Handle price - convert to string and clean
        price_value = item.get("price") or item.get("regularPrice")
        if price_value is not None:
            price = str(price_value)
            # Clean price - remove all non-digit/non-decimal characters first
            price = re.sub(r"[^\d.]", "", price)
            # Ensure only one decimal point by keeping only first occurrence
            if "." in price:
                integer_part, _, decimal_part = price.partition(".")
                # Remove decimals from decimal_part
                decimal_part = re.sub(r"\.", "", decimal_part)
                price = integer_part + ("." + decimal_part if decimal_part else "")
            # Clean up: remove leading/trailing decimals
            price = price.strip(".")
        else:
            price = ""
        
        image_url = item.get("image") or item.get("imageUrl") or ""
        description = item.get("description") or ""
        features = item.get("features") or item.get("specs") or []
        
        # Ensure features is a list of strings
        if isinstance(features, dict):
            features = list(features.values())
        features = [str(f) for f in features if f]
        
        stock = str(item.get("stock") or item.get("inventory") or "")
        aisle = str(item.get("aisle") or "")
        bay = str(item.get("bay") or "")
        
        if not product_id or not name:
            return None
        
        return Product(
            id=str(product_id),
            name=name,
            price=price,
            category_path=category_path,
            store_id=self.STORE_ID,
            image_url=image_url,
            description=description,
            features=features,
            stock=stock,
            aisle=aisle,
            bay=bay,
        )

    def scrape_category(self, category_url: str) -> list[Product]:
        """
        Scrape products from a Home Depot category URL.
        
        Args:
            category_url: Full URL of the category page
            
        Returns:
            List of Product objects
        """
        # Extract category path from URL for categorization
        parsed_url = urlparse(category_url)
        category_path = parsed_url.path.strip("/")
        
        # Fetch the category page
        try:
            html = self._fetch_page(category_url)
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch category URL: {e}") from e
        
        # Extract products from HTML
        products = self.extract_products_from_html(html, category_path)
        
        return products

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
