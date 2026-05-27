"""Configuration management for Home Depot scraper."""

import os
from typing import Optional


def get_proxy_url() -> Optional[str]:
    """
    Get proxy URL from environment variable HD_PROXY_URL.
    
    Returns:
        Proxy URL string (e.g., "http://proxy.example.com:8080") or None if not set.
    """
    proxy = os.getenv("HD_PROXY_URL")
    if proxy and proxy.strip():
        return proxy.strip()
    return None
