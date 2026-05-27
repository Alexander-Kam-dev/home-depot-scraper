"""Pydantic models for product data validation."""

import json
from typing import Any, Optional

from pydantic import BaseModel, field_validator, ConfigDict


class Product(BaseModel):
    """Product data model with validation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    price: str
    category_path: str
    store_id: str
    image_url: str
    description: str
    features: list[str]
    stock: Optional[str] = ""
    aisle: Optional[str] = ""
    bay: Optional[str] = ""

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: str) -> str:
        """Ensure price contains only digits and decimal point."""
        if v and not all(c.isdigit() or c == "." for c in v):
            raise ValueError("price must contain only digits and decimal point")
        return v

    def to_csv_row(self) -> dict[str, Any]:
        """Convert product to CSV row with features as JSON array string."""
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "category_path": self.category_path,
            "store_id": self.store_id,
            "image_url": self.image_url,
            "description": self.description,
            "features": json.dumps(self.features),
            "stock": self.stock or "",
            "aisle": self.aisle or "",
            "bay": self.bay or "",
        }
