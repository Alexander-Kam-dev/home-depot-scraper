"""Configuration management for Home Depot scraper."""

import os
from typing import Optional


def get_proxy_url() -> Optional[str]:
    """
    Get proxy URL from HD_PROXY_URL environment variable.
    
    Returns:
        Proxy URL string if set, None otherwise
    """
    proxy_url = os.getenv("HD_PROXY_URL", "").strip()
    return proxy_url if proxy_url else None


def is_proxy_enabled() -> bool:
    """
    Check if proxy is configured.
    
    Returns:
        True if HD_PROXY_URL is set, False otherwise
    """
    return get_proxy_url() is not None
