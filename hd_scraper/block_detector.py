"""Block detection helper for identifying rate limits, captchas, and other blocks."""

import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Keywords that indicate captcha or bot checks
BLOCK_KEYWORDS = {
    "captcha",
    "recaptcha",
    "bot",
    "verify",
    "challenge",
    "blocked",
    "suspended",
    "forbidden",
}

# Threshold for detecting captcha patterns (number of keywords that must match)
CAPTCHA_PATTERN_THRESHOLD = 2


class BlockedError(Exception):
    """Exception raised when a block condition is detected."""
    
    def __init__(self, reason: str):
        """Initialize BlockedError.
        
        Args:
            reason: Description of the block condition
        """
        self.reason = reason
        super().__init__(reason)


class BlockDetector:
    """Detect likely block conditions in HTTP responses."""

    def __init__(self):
        """Initialize the block detector."""
        self.block_detected = False
        self.block_reason = ""

    def check_response(
        self,
        response: httpx.Response,
        endpoint: str = "",
    ) -> bool:
        """
        Check if a response indicates a block condition.

        Args:
            response: httpx Response object
            endpoint: The endpoint URL or path being called (for logging)

        Returns:
            True if a block condition is detected, False otherwise
        """
        self.block_detected = False
        self.block_reason = ""

        # Check HTTP status codes for explicit blocks
        if response.status_code == 403:
            self.block_detected = True
            self.block_reason = f"HTTP 403 Forbidden at {endpoint}"
            logger.warning(f"Block detected: {self.block_reason}")
            return True

        if response.status_code == 429:
            self.block_detected = True
            self.block_reason = f"HTTP 429 Too Many Requests at {endpoint}"
            logger.warning(f"Block detected: {self.block_reason}")
            return True

        # Check content-type mismatch for JSON-expected endpoints
        content_type = response.headers.get("content-type", "").lower()
        expected_json_endpoints = [
            "/api/",
            "/graphql",
        ]

        # Extract path from endpoint (handle both full URLs and paths)
        endpoint_path = endpoint
        try:
            parsed = urlparse(endpoint)
            if parsed.scheme:  # It's a full URL
                endpoint_path = parsed.path
        except Exception:
            pass

        is_json_endpoint = any(
            endpoint_path.lower().startswith(ep) for ep in expected_json_endpoints
        )

        if is_json_endpoint and response.text:
            if "application/json" not in content_type:
                # Only flag if response looks like HTML (common for captcha redirects)
                if response.text.strip().startswith("<"):
                    self.block_detected = True
                    self.block_reason = (
                        f"Unexpected content-type '{content_type}' at {endpoint} "
                        f"(expected JSON)"
                    )
                    logger.warning(f"Block detected: {self.block_reason}")
                    return True

        # Check response body for captcha/bot keywords
        try:
            response_text = response.text.lower()
            for keyword in BLOCK_KEYWORDS:
                if keyword in response_text:
                    # Do more specific checking to avoid false positives
                    if self._contains_captcha_pattern(response_text):
                        self.block_detected = True
                        self.block_reason = f"Captcha/bot block detected at {endpoint}"
                        logger.warning(f"Block detected: {self.block_reason}")
                        return True
        except Exception:
            # If we can't check the response text, don't assume it's blocked
            pass

        return False

    def _contains_captcha_pattern(self, response_text: str) -> bool:
        """
        Check if response text contains patterns indicative of captcha/bot checks.

        Args:
            response_text: Response body as lowercase string

        Returns:
            True if captcha patterns detected, False otherwise
        """
        # Check for common captcha markers
        captcha_patterns = [
            "challenge",
            "bot",
            "recaptcha",
            "captcha",
            "verify",
        ]

        # Must have multiple indicators or specific patterns
        pattern_count = sum(1 for p in captcha_patterns if p in response_text)

        if pattern_count >= CAPTCHA_PATTERN_THRESHOLD:
            return True

        # Also check for specific patterns like <title>Just a moment</title>
        if "just a moment" in response_text:
            return True

        return False

    def get_block_reason(self) -> str:
        """
        Get the reason for the last block detection.

        Returns:
            Reason string, or empty string if no block was detected
        """
        return self.block_reason
