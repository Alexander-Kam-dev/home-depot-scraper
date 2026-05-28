"""Home Depot product scraper using httpx with retry logic."""

import asyncio
import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import Product
from .block_detector import BlockDetector
from . import config

# Setup logging
logger = logging.getLogger(__name__)


class HomeDepotScraper:
    """Scraper for Home Depot products with retry logic and concurrency control."""

    BASE_URL = "https://www.homedepot.com"
    STORE_ID = "hd-0205"
    
    def __init__(self, cookies: Optional[dict[str, str]] = None, max_workers: int = 5):
        """
        Initialize scraper with optional cookies from Playwright session.
        
        Args:
            cookies: Dictionary of cookies from Playwright context
            max_workers: Maximum concurrent requests for enrichment
        """
        self.cookies = cookies or {}
        self.max_workers = max_workers
        
        # Get proxy configuration
        proxy_url = config.get_proxy_url()
        client_kwargs = {
            "base_url": self.BASE_URL,
            "cookies": self.cookies,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            },
            "timeout": 30.0,
        }
        
        if proxy_url:
            client_kwargs["proxies"] = proxy_url
            logger.info(f"Using proxy: {proxy_url}")
        
        self.session = httpx.Client(**client_kwargs)
        self.blocked_count = 0
        self.block_detector = BlockDetector()

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
        
        Note: This is a sync wrapper. Use enrich_skus() for async enrichment.
        
        Args:
            category_url: Full URL of the category page
            
        Returns:
            List of Product objects
        """
        from . import plp
        
        try:
            # Extract SKUs from PLP
            skus, category_path = plp.get_skus(category_url, self.session, limit=50)
            logger.info(f"Found {len(skus)} SKUs")
            
            # Note: Enrichment is async and must be called with asyncio.run()
            # For now, return partial products from basic parsing
            html = self._fetch_page(category_url)
            products = self.extract_products_from_html(html, category_path)
            
            return products
        
        except Exception as e:
            logger.error(f"Failed to scrape category: {e}")
            raise RuntimeError(f"Failed to scrape category URL: {e}") from e

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    async def enrich_skus(
        self,
        skus: list[str],
        category_path: str,
        limit: int = 50,
        debug: bool = False,
    ) -> list[Product]:
        """
        Enrich SKUs with full product details using bounded concurrency.
        
        Args:
            skus: List of SKUs to enrich
            category_path: Category path for all products
            limit: Maximum number of products to return
            debug: Whether to save debug artifacts
            
        Returns:
            List of enriched Product objects (up to limit)
        """
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_workers)
        
        # Create enrichment tasks
        tasks = [
            self._enrich_sku(sku, category_path, semaphore, debug)
            for sku in skus[:int(limit * 1.5)]  # Try more than needed
        ]
        
        # Run enrichment with timeout
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and None values
        products = [p for p in results if isinstance(p, Product) and p]
        
        # Sort by ID and return up to limit
        return sorted(products, key=lambda p: p.id)[:limit]
    
    async def _enrich_sku(
        self,
        sku: str,
        category_path: str,
        semaphore: asyncio.Semaphore,
        debug: bool = False,
    ) -> Optional[Product]:
        """
        Enrich a single SKU with product details.
        
        Args:
            sku: SKU to enrich
            category_path: Category path
            semaphore: Concurrency semaphore
            debug: Whether to save debug artifacts
            
        Returns:
            Product object or None if enrichment fails
        """
        async with semaphore:
            try:
                # Import pdp here to avoid circular imports
                from . import pdp
                from .block_detector import BlockedError
                
                # Fetch product details (sync function)
                try:
                    details = pdp.fetch_product_details(sku, self.session)
                except BlockedError as e:
                    # Increment blocked_count only for actual block conditions
                    self.blocked_count += 1
                    logger.error(f"SKU {sku} blocked: {e.reason}")
                    return None
                
                if not details.get("name"):
                    logger.warning(f"No name found for SKU {sku}")
                    return None
                
                # Create product
                product = Product(
                    id=sku,
                    name=details.get("name", ""),
                    price=details.get("price", ""),
                    category_path=category_path,
                    store_id=self.STORE_ID,
                    image_url=details.get("image_url", ""),
                    description=details.get("description", ""),
                    features=details.get("features", []),
                    stock=details.get("stock", ""),
                    aisle=details.get("aisle", ""),
                    bay=details.get("bay", ""),
                )
                
                logger.info(f"Enriched SKU {sku}: {product.name}")
                return product
            
            except Exception as e:
                logger.error(f"Failed to enrich SKU {sku}: {e}")
                return None
