"""Command-line interface for Home Depot scraper."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .bootstrap import setup_store_context, get_cookies_dict, cleanup_playwright, verify_store, save_network_log
from .scraper import HomeDepotScraper
from .csv_writer import write_products_csv
from . import plp, report

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug mode (save network captures and artifacts)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Target number of products to scrape (default: 50)",
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
    print(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    
    browser = None
    context = None
    store_verified = False
    store_verification_note = ""
    attempted_skus = 0
    blocked_count = 0
    
    try:
        # Setup browser context with store information
        browser, context = await setup_store_context(
            store_id=args.store_id,
            headless=args.headless,
            debug=args.debug,
            plp_url=args.category_url if args.debug else None,
        )
        print("✓ Store context established")
        
        # Verify store
        store_verified, store_verification_note = await verify_store(context, args.store_id)
        if store_verified:
            print(f"✓ Store verified: {store_verification_note}")
        else:
            print(f"⚠ Store verification failed: {store_verification_note}")
        
        # Save network log if debug mode
        if args.debug:
            save_network_log("artifacts/network.jsonl")
            print("✓ Network capture saved to artifacts/network.jsonl")
        
        # Extract cookies for httpx
        cookies = await get_cookies_dict(context)
        print("✓ Cookies extracted")
        
        # Close Playwright (we now have cookies for httpx)
        await context.close()
        await browser.close()
        await cleanup_playwright()
        context = None
        browser = None
        
        # Create scraper with cookies
        print(f"Starting scraper for: {args.category_url}")
        scraper = HomeDepotScraper(cookies=cookies, max_workers=5)
        
        try:
            # Extract SKUs from PLP
            skus, category_path = plp.get_skus(args.category_url, scraper.session, limit=args.limit)
            attempted_skus = len(skus)
            print(f"✓ Found {attempted_skus} SKUs")
            
            # Save first PLP response if debug
            if args.debug:
                try:
                    html = scraper.session.get(args.category_url).text
                    Path("artifacts").mkdir(exist_ok=True)
                    with open("artifacts/first_plp.html", "w", encoding="utf-8") as f:
                        f.write(html[:5000])  # Save first 5000 chars
                    print("✓ First PLP HTML saved to artifacts/first_plp.html")
                except Exception:
                    pass
            
            # Enrich SKUs with product details
            print(f"Enriching products (max workers: {scraper.max_workers})...")
            products = await scraper.enrich_skus(
                skus,
                category_path,
                limit=args.limit,
                debug=args.debug,
            )
            blocked_count = scraper.blocked_count
            
            print(f"✓ Enriched {len(products)} products")
            
            # Write to CSV
            output_path = write_products_csv(products, args.output)
            print(f"✓ Wrote {len(products)} products to {output_path}")
            
            # Generate run report
            report_path = report.generate_report(
                category_url=args.category_url,
                requested_limit=args.limit,
                attempted_skus=attempted_skus,
                succeeded_rows=len(products),
                blocked_count=blocked_count,
                store_verified=store_verified,
                store_verification_note=store_verification_note,
                output_path="run_report.json",
            )
            print(f"✓ Generated report: {report_path}")
        
        finally:
            scraper.close()
    
    finally:
        # Cleanup Playwright resources
        if context:
            await context.close()
        if browser:
            await browser.close()
        await cleanup_playwright()


if __name__ == "__main__":
    main()
