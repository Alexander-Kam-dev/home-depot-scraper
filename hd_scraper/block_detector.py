"""Block detection helper for identifying blocked/captcha responses."""

import re
from typing import Optional

import httpx


class BlockDetector:
    """Detects likely block conditions from HTTP responses."""
    
    # Keywords that indicate captcha or bot detection
    CAPTCHA_KEYWORDS = [
        "captcha",
        "recaptcha",
        "bot",
        "robot",
        "challenge",
        "verify",
        "click here if you",
        "security check",
    ]
    
    # Expected content types for API endpoints
    JSON_ENDPOINTS = {
        "/api",
        "/apiservice",
        "/graphql",
    }
    
    @staticmethod
    def is_blocked(
        response: httpx.Response,
        endpoint: str = "",
    ) -> tuple[bool, str]:
        """
        Determine if a response indicates a blocked/captcha condition.
        
        Args:
            response: httpx Response object
            endpoint: Optional endpoint path for context-aware checks
            
        Returns:
            Tuple of (is_blocked: bool, reason: str)
        """
        # Check status codes
        if response.status_code == 403:
            return True, f"HTTP 403 Forbidden (endpoint: {endpoint})"
        
        if response.status_code == 429:
            return True, f"HTTP 429 Too Many Requests (endpoint: {endpoint})"
        
        # Check for captcha keywords in response body
        try:
            body = response.text.lower()
            for keyword in BlockDetector.CAPTCHA_KEYWORDS:
                if keyword in body:
                    return True, f"Captcha detected: '{keyword}' found in response (endpoint: {endpoint})"
        except Exception:
            pass
        
        # Check content-type mismatch for API endpoints
        if any(endpoint.startswith(api) for api in BlockDetector.JSON_ENDPOINTS):
            content_type = response.headers.get("content-type", "").lower()
            
            # API endpoints should return JSON, not HTML
            if "text/html" in content_type:
                return True, f"Unexpected HTML response from API endpoint: {endpoint}"
            
            if not content_type and response.status_code == 200:
                # Some blocks return 200 but with no content-type header
                if response.text and response.text.strip().startswith("<"):
                    return True, f"HTML response without content-type from API endpoint: {endpoint}"
        
        return False, ""
    
    @staticmethod
    def check_response(response: httpx.Response, endpoint: str = "") -> bool:
        """
        Quick check if response is blocked.
        
        Args:
            response: httpx Response object
            endpoint: Optional endpoint path
            
        Returns:
            True if blocked, False otherwise
        """
        is_blocked, _ = BlockDetector.is_blocked(response, endpoint)
        return is_blocked
    
    @staticmethod
    def get_block_reason(response: httpx.Response, endpoint: str = "") -> str:
        """
        Get detailed reason for block if present.
        
        Args:
            response: httpx Response object
            endpoint: Optional endpoint path
            
        Returns:
            Block reason string, or empty string if not blocked
        """
        _, reason = BlockDetector.is_blocked(response, endpoint)
        return reason
