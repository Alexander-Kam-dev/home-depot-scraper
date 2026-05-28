"""Tests for CSV writer and column ordering."""

import csv
import tempfile
from pathlib import Path

import pytest

from hd_scraper.csv_writer import PRODUCT_CSV_COLUMNS, write_products_csv
from hd_scraper.models import Product


class TestCSVColumns:
    """Test CSV column ordering and format."""

    def test_product_csv_columns_order(self):
        """Verify CSV columns are in the exact required order."""
        expected_columns = [
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
        assert PRODUCT_CSV_COLUMNS == expected_columns

    def test_product_csv_columns_length(self):
        """Verify exactly 11 columns are defined."""
        assert len(PRODUCT_CSV_COLUMNS) == 11


class TestWriteProductsCSV:
    """Test CSV file writing functionality."""

    def test_write_csv_headers(self):
        """CSV headers should match PRODUCT_CSV_COLUMNS in order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            
            products = [
                Product(
                    id="001",
                    name="Drill Set",
                    price="29.99",
                    category_path="tools",
                    store_id="hd-0205",
                    image_url="https://example.com/image.jpg",
                    description="A drill",
                    features=["Titanium"],
                )
            ]
            
            write_products_csv(products, output_path)
            
            # Read the CSV and verify headers
            with open(output_path, "r") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                assert headers == PRODUCT_CSV_COLUMNS

    def test_write_csv_single_product(self):
        """Single product should be written to CSV correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            
            product = Product(
                id="001",
                name="Drill Set",
                price="29.99",
                category_path="tools/power-tools",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="A drill set",
                features=["Titanium coated"],
            )
            
            write_products_csv([product], output_path)
            
            # Verify file exists and has 2 rows (header + 1 product)
            assert output_path.exists()
            with open(output_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 2  # header + 1 product

    def test_write_csv_multiple_products(self):
        """Multiple products should be written to CSV correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            
            products = [
                Product(
                    id="001",
                    name="Drill Set",
                    price="29.99",
                    category_path="tools",
                    store_id="hd-0205",
                    image_url="https://example.com/image1.jpg",
                    description="Drill",
                    features=["Feature1"],
                ),
                Product(
                    id="002",
                    name="Hammer",
                    price="19.99",
                    category_path="tools",
                    store_id="hd-0205",
                    image_url="https://example.com/image2.jpg",
                    description="Hammer",
                    features=["Feature2"],
                ),
            ]
            
            write_products_csv(products, output_path)
            
            # Verify file has 3 rows (header + 2 products)
            with open(output_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 3

    def test_write_csv_features_as_json(self):
        """Features in CSV should be valid JSON array strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            
            product = Product(
                id="001",
                name="Drill Set",
                price="29.99",
                category_path="tools",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="A drill",
                features=["Titanium coated", "100 pieces"],
            )
            
            write_products_csv([product], output_path)
            
            # Read CSV and verify features field is valid JSON
            with open(output_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                import json
                features_json = json.loads(rows[0]["features"])
                assert features_json == ["Titanium coated", "100 pieces"]

    def test_write_csv_creates_parent_directory(self):
        """CSV writer should create parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "test.csv"
            
            product = Product(
                id="001",
                name="Test",
                price="29.99",
                category_path="tools",
                store_id="hd-0205",
                image_url="https://example.com/image.jpg",
                description="Test",
                features=["Test"],
            )
            
            result = write_products_csv([product], output_path)
            
            assert result.exists()
            assert result.parent.exists()

    def test_write_csv_with_iterator(self):
        """CSV writer should accept an iterator of products."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            
            def product_generator():
                for i in range(3):
                    yield Product(
                        id=f"{i:03d}",
                        name=f"Product {i}",
                        price="29.99",
                        category_path="tools",
                        store_id="hd-0205",
                        image_url=f"https://example.com/image{i}.jpg",
                        description=f"Product {i}",
                        features=["Feature"],
                    )
            
            write_products_csv(product_generator(), output_path)
            
            # Verify file has 4 rows (header + 3 products)
            with open(output_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 4
