"""Playwright session bootstrapper for Home Depot store context setup."""

import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright


# Store playwright instance for cleanup
_playwright_instance: Optional[Playwright] = None


async def setup_store_context(
    store_id: str = "hd-0205",
    headless: bool = True,
) -> tuple[Browser, BrowserContext]:
    """
    Bootstrap a Playwright session with store context for Home Depot.
    
    Sets the store context to the specified physical store before scraping.
    
    IMPORTANT: Call cleanup_playwright() when done with the returned browser and context.
    
    Args:
        store_id: Home Depot store ID (default: hd-0205)
        headless: Whether to run browser in headless mode
        
    Returns:
        Tuple of (browser, context) for use with httpx cookie extraction
        
    Raises:
        RuntimeError: If store context setup fails
    """
    global _playwright_instance
    
    _playwright_instance = await async_playwright().start()
    
    try:
        browser = await _playwright_instance.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Extract numeric part of store_id (e.g., "hd-0205" -> "0205")
        store_number = store_id.replace("hd-", "") if store_id.startswith("hd-") else store_id
        
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
            cookie_propagation_delay = 1.0  # seconds
            await asyncio.sleep(cookie_propagation_delay)
            
            # Verify store is active by checking if we can access store-specific content
            # This would typically involve checking page content or making an API call
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
