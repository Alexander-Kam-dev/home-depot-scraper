"""Command-line interface for Home Depot scraper."""

import argparse
import asyncio
import sys
from pathlib import Path

from .bootstrap import setup_store_context, get_cookies_dict
from .scraper import HomeDepotScraper
from .csv_writer import write_products_csv


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Home Depot product scraper",
        prog="hd-scraper",
    )
    parser.add_argument(
        "--category-url",
        required=True,
        help="Home Depot category URL to scrape",
    )
    parser.add_argument(
        "--output",
        default="products.csv",
        help="Output CSV file path (default: products.csv)",
    )
    parser.add_argument(
        "--store-id",
        default="hd-0205",
        help="Home Depot store ID (default: hd-0205)",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        default=True,
        help="Run browser in non-headless mode (default: headless mode)",
    )
    
    args = parser.parse_args()
    
    # Run async main function
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\nScraping interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


async def _async_main(args):
    """Async main function for scraping."""
    print(f"Setting up Playwright session for store {args.store_id}...")
    
    browser = None
    context = None
    
    try:
        # Setup browser context with store information
        browser, context = await setup_store_context(
            store_id=args.store_id,
            headless=args.headless,
        )
        print("✓ Store context established")
        
        # Extract cookies for httpx
        cookies = await get_cookies_dict(context)
        print("✓ Cookies extracted")
        
        # Close Playwright (we now have cookies for httpx)
        await context.close()
        await browser.close()
        context = None
        browser = None
        
        # Create scraper with cookies
        print(f"Starting scraper for: {args.category_url}")
        scraper = HomeDepotScraper(cookies=cookies)
        
        try:
            # Scrape products
            products = scraper.scrape_category(args.category_url)
            print(f"✓ Found {len(products)} products")
            
            # Write to CSV
            output_path = write_products_csv(products, args.output)
            print(f"✓ Wrote {len(products)} products to {output_path}")
            
        finally:
            scraper.close()
    
    finally:
        # Cleanup Playwright resources
        if context:
            await context.close()
        if browser:
            await browser.close()


if __name__ == "__main__":
    main()
