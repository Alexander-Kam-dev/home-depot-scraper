"""Tests for PLP and PDP modules with mocked httpx calls."""

import json
import pytest
import httpx
import respx

from hd_scraper.plp import get_skus


class TestPLPGetSKUs:
    """Test PLP SKU extraction with mocked httpx."""

    @respx.mock
    def test_get_skus_returns_unique_skus(self):
        """get_skus should return unique SKUs from API response."""
        category_url = "https://www.homedepot.com/b/Bath-Bathroom-Faucets"
        
        # Mock the API response
        api_response = {
            "products": [
                {"sku": "123456", "name": "Product 1"},
                {"sku": "123457", "name": "Product 2"},
                {"sku": "123458", "name": "Product 3"},
            ]
        }
        
        respx.get("https://www.homedepot.com/api/v1/products", params={"offset": 0, "limit": 24}).mock(
            return_value=httpx.Response(200, json=api_response)
        )
        
        with httpx.Client() as client:
            skus, category_path = get_skus(category_url, client, limit=50)
            
            assert len(skus) == 3
            assert "123456" in skus
            assert "123457" in skus
            assert "123458" in skus

    @respx.mock
    def test_get_skus_returns_sorted_list(self):
        """get_skus should return SKUs as a sorted list."""
        category_url = "https://www.homedepot.com/b/Bath-Bathroom-Faucets"
        
        api_response = {
            "products": [
                {"sku": "999", "name": "Product 1"},
                {"sku": "111", "name": "Product 2"},
                {"sku": "555", "name": "Product 3"},
            ]
        }
        
        respx.get("https://www.homedepot.com/api/v1/products", params={"offset": 0, "limit": 24}).mock(
            return_value=httpx.Response(200, json=api_response)
        )
        
        with httpx.Client() as client:
            skus, category_path = get_skus(category_url, client, limit=50)
            
            # Verify SKUs are sorted
            assert skus == sorted(skus)

    @respx.mock
    def test_get_skus_pagination(self):
        """get_skus should handle pagination and collect SKUs from multiple pages."""
        category_url = "https://www.homedepot.com/b/Bath-Bathroom-Faucets"
        
        # First page response
        page1_response = {
            "products": [
                {"sku": f"SKU00{i}", "name": f"Product {i}"}
                for i in range(24)
            ]
        }
        
        # Second page response
        page2_response = {
            "products": [
                {"sku": f"SKU01{i}", "name": f"Product {i}"}
                for i in range(10)
            ]
        }
        
        # Mock first page
        respx.get(
            "https://www.homedepot.com/api/v1/products",
            params={"offset": 0, "limit": 24}
        ).mock(return_value=httpx.Response(200, json=page1_response))
        
        # Mock second page
        respx.get(
            "https://www.homedepot.com/api/v1/products",
            params={"offset": 24, "limit": 24}
        ).mock(return_value=httpx.Response(200, json=page2_response))
        
        with httpx.Client() as client:
            skus, category_path = get_skus(category_url, client, limit=50)
            
            # Should have SKUs from both pages
            assert len(skus) >= 24  # At least first page

    @respx.mock
    def test_get_skus_handles_empty_response(self):
        """get_skus should handle empty API responses gracefully."""
        category_url = "https://www.homedepot.com/b/Bath-Bathroom-Faucets"
        
        # Empty response
        api_response = {"products": []}
        
        # Mock both API endpoints
        respx.get("https://www.homedepot.com/api/v1/products", params={"offset": 0, "limit": 24}).mock(
            return_value=httpx.Response(200, json=api_response)
        )
        respx.post("https://www.homedepot.com/apiservice/v1/graphql").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        respx.get("https://www.homedepot.com/api/products").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        # Mock the category URL fallback to HTML
        respx.get(category_url).mock(
            return_value=httpx.Response(200, text="<html></html>")
        )
        
        with httpx.Client() as client:
            skus, category_path = get_skus(category_url, client, limit=50)
            
            assert isinstance(skus, list)
            assert len(skus) == 0

    def test_get_skus_extracts_category_path(self):
        """get_skus should extract and format category path from URL."""
        category_url = "https://www.homedepot.com/b/Bath-Bathroom-Faucets/Touchless"
        
        with respx.mock:
            # Mock API endpoints
            respx.get("https://www.homedepot.com/api/v1/products", params={"offset": 0, "limit": 24}).mock(
                return_value=httpx.Response(200, json={"products": []})
            )
            respx.post("https://www.homedepot.com/apiservice/v1/graphql").mock(
                return_value=httpx.Response(200, json={"data": {}})
            )
            respx.get(category_url).mock(
                return_value=httpx.Response(200, text="<html></html>")
            )
            
            with httpx.Client() as client:
                skus, category_path = get_skus(category_url, client, limit=50)
                
                # Verify category path is a string
                assert isinstance(category_path, str)
                assert len(category_path) > 0


class TestPDPFetchProductDetails:
    """Test PDP product detail fetching with mocked httpx."""

    @respx.mock
    def test_fetch_product_details_parses_api_response(self):
        """fetch_product_details should parse JSON API response correctly."""
        from hd_scraper.pdp import fetch_product_details
        
        sku = "123456"
        api_response = {
            "title": "Test Drill",
            "price": "29.99",
            "description": "A powerful drill",
            "features": ["1/2 inch chuck", "Titanium bits"],
            "images": [{"url": "https://example.com/drill.jpg"}],
            "storeInfo": {
                "inventory": "45",
                "aisle": "B2",
                "bay": "5"
            }
        }
        
        respx.get(f"https://www.homedepot.com/api/v1/products/{sku}").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        
        with httpx.Client() as client:
            details = fetch_product_details(sku, client)
            
            assert details["name"] == "Test Drill"
            assert details["price"] == "29.99"
            assert details["description"] == "A powerful drill"
            assert "1/2 inch chuck" in details["features"]
            assert details["image_url"] == "https://example.com/drill.jpg"
            assert details["stock"] == "45"
            assert details["aisle"] == "B2"
            assert details["bay"] == "5"

    @respx.mock
    def test_fetch_product_details_handles_missing_fields(self):
        """fetch_product_details should handle missing optional fields."""
        from hd_scraper.pdp import fetch_product_details
        
        sku = "123456"
        api_response = {
            "title": "Test Product",
            "price": "19.99",
            # Missing description, features, images, storeInfo
        }
        
        respx.get(f"https://www.homedepot.com/api/v1/products/{sku}").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        
        with httpx.Client() as client:
            details = fetch_product_details(sku, client)
            
            assert details["name"] == "Test Product"
            assert details["price"] == "19.99"
            assert details["description"] == ""
            assert details["features"] == []
            assert details["image_url"] == ""
            assert details["stock"] == ""

    @respx.mock
    def test_fetch_product_details_returns_default_on_404(self):
        """fetch_product_details should return empty details on 404."""
        from hd_scraper.pdp import fetch_product_details
        
        sku = "999999"
        
        respx.get(f"https://www.homedepot.com/api/v1/products/{sku}").mock(
            return_value=httpx.Response(404, json={})
        )
        respx.get(f"https://www.homedepot.com/api/products/{sku}").mock(
            return_value=httpx.Response(404, json={})
        )
        respx.get(f"https://www.homedepot.com/p/{sku}").mock(
            return_value=httpx.Response(404, text="Not found")
        )
        
        with httpx.Client() as client:
            details = fetch_product_details(sku, client)
            
            # Should return default empty details
            assert isinstance(details, dict)
            assert details.get("name", "") == ""

    @respx.mock
    def test_fetch_product_details_with_discovered_endpoints(self):
        """fetch_product_details should use discovered endpoints if provided."""
        from hd_scraper.pdp import fetch_product_details
        
        sku = "123456"
        api_response = {
            "title": "Faucet",
            "price": "99.99",
            "description": "Chrome faucet",
            "features": ["Touchless"],
            "images": [{"url": "https://example.com/faucet.jpg"}],
        }
        
        discovered_endpoint = "https://api.homedepot.com/v2/products"
        respx.get(f"{discovered_endpoint}/{sku}").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        
        with httpx.Client() as client:
            endpoints = [{"url": discovered_endpoint}]
            details = fetch_product_details(sku, client, discovered_endpoints=endpoints)
            
            assert details["name"] == "Faucet"
            assert details["price"] == "99.99"
