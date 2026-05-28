"""Tests for Product model and validation."""

import json
import pytest

from hd_scraper.models import Product


class TestProductPriceValidation:
    """Test Product.validate_price method."""

    def test_valid_price_integer(self):
        """Valid price with just digits."""
        product = Product(
            id="123",
            name="Test Product",
            price="29",
            category_path="test",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="Test description",
            features=["Feature1"],
        )
        assert product.price == "29"

    def test_valid_price_decimal(self):
        """Valid price with decimal point."""
        product = Product(
            id="123",
            name="Test Product",
            price="29.99",
            category_path="test",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="Test description",
            features=["Feature1"],
        )
        assert product.price == "29.99"

    def test_valid_price_multiple_decimals_in_format(self):
        """Valid price format with trailing decimals."""
        product = Product(
            id="123",
            name="Test Product",
            price="1000.50",
            category_path="test",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="Test description",
            features=["Feature1"],
        )
        assert product.price == "1000.50"

    def test_valid_empty_price(self):
        """Empty price string is allowed."""
        product = Product(
            id="123",
            name="Test Product",
            price="",
            category_path="test",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="Test description",
            features=["Feature1"],
        )
        assert product.price == ""

    def test_invalid_price_currency_symbol(self):
        """Price with currency symbol should be rejected."""
        with pytest.raises(ValueError, match="price must contain only digits and decimal point"):
            Product(
                id="123",
                name="Test Product",
                price="$29.99",
                category_path="test",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="Test description",
                features=["Feature1"],
            )

    def test_invalid_price_multiple_decimal_points(self):
        """Price with multiple decimal points should be rejected."""
        with pytest.raises(ValueError, match="price cannot have multiple decimal points"):
            Product(
                id="123",
                name="Test Product",
                price="29.99.99",
                category_path="test",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="Test description",
                features=["Feature1"],
            )

    def test_invalid_price_only_decimal(self):
        """Price with only decimal point should be rejected."""
        with pytest.raises(ValueError, match="price must contain at least one digit"):
            Product(
                id="123",
                name="Test Product",
                price=".",
                category_path="test",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="Test description",
                features=["Feature1"],
            )

    def test_invalid_price_letters(self):
        """Price with letters should be rejected."""
        with pytest.raises(ValueError, match="price must contain only digits and decimal point"):
            Product(
                id="123",
                name="Test Product",
                price="29.99abc",
                category_path="test",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="Test description",
                features=["Feature1"],
            )

    def test_invalid_price_special_chars(self):
        """Price with special characters should be rejected."""
        with pytest.raises(ValueError, match="price must contain only digits and decimal point"):
            Product(
                id="123",
                name="Test Product",
                price="29,99",  # comma instead of period
                category_path="test",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="Test description",
                features=["Feature1"],
            )


class TestProductCSVSerialization:
    """Test Product.to_csv_row method and features JSON serialization."""

    def test_csv_row_features_as_json_array(self):
        """Features should be serialized as JSON array string."""
        product = Product(
            id="123",
            name="Drill Set",
            price="29.99",
            category_path="tools/power-tools",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="A drill set",
            features=["Titanium coated", "100 pieces"],
        )
        row = product.to_csv_row()
        
        # Check that features is a JSON string
        assert isinstance(row["features"], str)
        
        # Parse the JSON to verify it's valid
        parsed_features = json.loads(row["features"])
        assert parsed_features == ["Titanium coated", "100 pieces"]

    def test_csv_row_empty_features(self):
        """Empty features list should serialize as empty JSON array."""
        product = Product(
            id="123",
            name="Screwdriver",
            price="19.99",
            category_path="tools/hand-tools",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="A screwdriver",
            features=[],
        )
        row = product.to_csv_row()
        
        parsed_features = json.loads(row["features"])
        assert parsed_features == []

    def test_csv_row_single_feature(self):
        """Single feature should be in JSON array."""
        product = Product(
            id="123",
            name="Hammer",
            price="12.99",
            category_path="tools/hand-tools",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="A hammer",
            features=["Ergonomic"],
        )
        row = product.to_csv_row()
        
        parsed_features = json.loads(row["features"])
        assert parsed_features == ["Ergonomic"]

    def test_csv_row_optional_fields_empty(self):
        """Optional fields (stock, aisle, bay) should be empty strings when not set."""
        product = Product(
            id="123",
            name="Test Product",
            price="29.99",
            category_path="test",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="Test description",
            features=["Feature1"],
        )
        row = product.to_csv_row()
        
        assert row["stock"] == ""
        assert row["aisle"] == ""
        assert row["bay"] == ""

    def test_csv_row_optional_fields_set(self):
        """Optional fields should be included when set."""
        product = Product(
            id="123",
            name="Test Product",
            price="29.99",
            category_path="test",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="Test description",
            features=["Feature1"],
            stock="45",
            aisle="B2",
            bay="5",
        )
        row = product.to_csv_row()
        
        assert row["stock"] == "45"
        assert row["aisle"] == "B2"
        assert row["bay"] == "5"

    def test_csv_row_all_fields(self):
        """CSV row should contain all expected fields."""
        product = Product(
            id="001",
            name="Drill Set",
            price="29.99",
            category_path="tools/power-tools",
            store_id="hd-0205",
            image_url="https://example.com/image.jpg",
            description="A drill set",
            features=["Titanium coated", "100 pieces"],
            stock="45",
            aisle="B2",
            bay="5",
        )
        row = product.to_csv_row()
        
        expected_keys = [
            "id",
            "name",
            "price",
            "category_path",
            "store_id",
            "image_url",
            "description",
            "features",
            "stock",
            "aisle",
            "bay",
        ]
        
        assert set(row.keys()) == set(expected_keys)
        assert row["id"] == "001"
        assert row["name"] == "Drill Set"
        assert row["price"] == "29.99"
        assert row["store_id"] == "hd-0205"
