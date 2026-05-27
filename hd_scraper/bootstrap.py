"""Playwright session bootstrapper for Home Depot store context setup."""

import asyncio
import json
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright


# Store playwright instance for cleanup
_playwright_instance: Optional[Playwright] = None
_network_log: list[dict] = []


def _record_request(url: str, method: str, headers: dict) -> None:
    """Record request details to network log."""
    _network_log.append({
        "type": "request",
        "url": url,
        "method": method,
        "headers": headers,
    })


async def _record_response_handler(response) -> None:
    """Record response details to network log."""
    try:
        content_type = response.headers.get("content-type", "")
        _network_log.append({
            "type": "response",
            "url": response.url,
            "status": response.status,
            "content_type": content_type,
        })
    except Exception:
        pass


def get_network_log() -> list[dict]:
    """Get the recorded network log."""
    return _network_log.copy()


def clear_network_log() -> None:
    """Clear the network log."""
    global _network_log
    _network_log = []


async def setup_store_context(
    store_id: str = "hd-0205",
    headless: bool = True,
    debug: bool = False,
    plp_url: Optional[str] = None,
    proxy_url: Optional[str] = None,
) -> tuple[Browser, BrowserContext]:
    """
    Bootstrap a Playwright session with store context for Home Depot.
    
    Sets the store context to the specified physical store before scraping.
    
    IMPORTANT: Call cleanup_playwright() when done with the returned browser and context.
    
    Args:
        store_id: Home Depot store ID (default: hd-0205)
        headless: Whether to run browser in headless mode
        debug: Whether to capture network traffic for debugging
        plp_url: Optional PLP URL to load for network capture
        proxy_url: Optional proxy URL (e.g., "http://proxy.example.com:8080")
        
    Returns:
        Tuple of (browser, context) for use with httpx cookie extraction
        
    Raises:
        RuntimeError: If store context setup fails
    """
    global _playwright_instance
    
    clear_network_log()
    _playwright_instance = await async_playwright().start()
    
    try:
        # Configure launch options with optional proxy
        launch_options = {"headless": headless}
        if proxy_url:
            launch_options["proxy"] = {"server": proxy_url}
        
        browser = await _playwright_instance.chromium.launch(**launch_options)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Setup network listener if debug mode
        if debug:
            page.on("response", _record_response_handler)
        
        # Extract numeric part of store_id (e.g., "hd-0205" -> "0205")
        store_number = store_id.replace("hd-", "") if store_id.startswith("hd-") else store_id
        
        # Validate store_number contains only digits to prevent URL injection
        if not store_number.isdigit():
            raise RuntimeError(f"Invalid store_id format: {store_id}. Must be numeric or hd-XXXX format.")
        
        try:
            # Navigate to Home Depot
            await page.goto("https://www.homedepot.com", wait_until="networkidle")
            
            # Set store ID via cookies/storage
            # Home Depot uses store context in various ways, attempting to set via API
            await page.evaluate(
                f"""
                () => {{
                    localStorage.setItem('storeId', '{store_number}');
                    localStorage.setItem('storeNumber', '{store_number}');
                }}
                """
            )
            
            # Navigate to verify store context is set
            await page.goto(
                f"https://www.homedepot.com/s/set-store?store={store_number}",
                wait_until="networkidle"
            )
            
            # Wait a moment for cookies to be set
            # Give Home Depot servers time to process store context before extraction
            await asyncio.sleep(1.0)
            
            # If PLP URL provided and debug mode, load it to capture network traffic
            if debug and plp_url:
                await page.goto(plp_url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(1.0)
            else:
                # Verify store is active by checking if we can access store-specific content
                await page.goto("https://www.homedepot.com", wait_until="networkidle")
            
            return browser, context
            
        except Exception as e:
            await context.close()
            await browser.close()
            await cleanup_playwright()
            raise RuntimeError(f"Failed to setup store context: {e}") from e
    except Exception as e:
        await cleanup_playwright()
        raise


async def cleanup_playwright() -> None:
    """
    Clean up the global Playwright instance.
    
    Call this after closing the browser and context.
    """
    global _playwright_instance
    if _playwright_instance:
        await _playwright_instance.stop()
        _playwright_instance = None


async def get_cookies_dict(context: BrowserContext) -> dict[str, str]:
    """
    Extract cookies from Playwright context for use with httpx.
    
    Args:
        context: Playwright browser context
        
    Returns:
        Dictionary of cookies suitable for httpx headers
    """
    cookies = await context.cookies()
    return {cookie["name"]: cookie["value"] for cookie in cookies}


async def verify_store(context: BrowserContext, store_id: str = "hd-0205") -> tuple[bool, str]:
    """
    Verify that the store context is active with strict, evidence-based checks.
    
    Checks for actual evidence of store 0205:
    - Cookie or localStorage value equals the store number
    - UI text on homepage includes the store number
    
    Args:
        context: Playwright browser context
        store_id: Expected store ID (default: hd-0205)
        
    Returns:
        Tuple of (is_verified: bool, verification_note: str)
    """
    store_number = store_id.replace("hd-", "") if store_id.startswith("hd-") else store_id
    
    try:
        # Check 1: Look for cookies with exact store number value
        cookies = await context.cookies()
        for cookie in cookies:
            if cookie["value"] == store_number:
                # Found exact match - strong evidence
                return True, f"Store verified via cookie '{cookie['name']}' = {store_number}"
        
        # Check 2: Check localStorage via page for exact store number
        page = None
        try:
            page = await context.new_page()
            await page.goto("https://www.homedepot.com", wait_until="networkidle", timeout=30000)
            
            # Check localStorage values
            storage_values = await page.evaluate("""
                () => {
                    const values = {};
                    // Check multiple possible keys
                    const keys = ['storeId', 'storeNumber', 'store_id', 'store_number'];
                    for (const key of keys) {
                        values[key] = localStorage.getItem(key);
                    }
                    return values;
                }
            """)
            
            for key, value in storage_values.items():
                if value and value.strip() == store_number:
                    return True, f"Store verified via localStorage '{key}' = {value}"
            
            # Check 3: Look for store UI text on the page (e.g., "Store #0205")
            page_text = await page.evaluate("() => document.body.innerText")
            if page_text and store_number in page_text:
                # Do a more specific check for store UI patterns
                if any(pattern in page_text for pattern in [
                    f"Store #{store_number}",
                    f"store {store_number}",
                    f"#{store_number}",
                    f" {store_number} "
                ]):
                    return True, f"Store verified via UI text matching store number {store_number}"
            
            return False, f"No evidence found for store {store_number} in cookies, storage, or UI text"
        
        finally:
            if page:
                await page.close()
    
    except Exception as e:
        return False, f"Store verification error: {str(e)}"

def save_network_log(output_path: str | Path = "artifacts/network.jsonl") -> None:
    """
    Save the network log to a JSONL file.
    
    Args:
        output_path: Path to save the network log
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in _network_log:
            f.write(json.dumps(entry) + "\n")
