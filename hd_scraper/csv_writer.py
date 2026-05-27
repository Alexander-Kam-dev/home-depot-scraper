"""CSV writer for product data with correct column ordering."""

import csv
from pathlib import Path
from typing import Iterator

from .models import Product


# Exact column ordering as specified in requirements
PRODUCT_CSV_COLUMNS = [
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


def write_products_csv(
    products: Iterator[Product] | list[Product],
    output_path: str | Path = "products.csv",
) -> Path:
    """
    Write products to CSV file with correct column ordering.
    
    Args:
        products: Iterator or list of Product objects
        output_path: Path to write CSV file to
        
    Returns:
        Path object of created CSV file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRODUCT_CSV_COLUMNS)
        writer.writeheader()
        
        for product in products:
            row = product.to_csv_row()
            writer.writerow(row)
    
    return output_path
