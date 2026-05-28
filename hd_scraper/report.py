"""Report generation for scraping results."""

import json
from pathlib import Path
from typing import Optional


def generate_report(
    category_url: str,
    requested_limit: int,
    attempted_skus: int,
    succeeded_rows: int,
    blocked_count: int = 0,
    store_verified: bool = False,
    store_verification_note: str = "",
    proxy_enabled: bool = False,
    store_number: Optional[str] = None,
    output_path: str | Path = "run_report.json",
) -> Path:
    """
    Generate a run report for the scraping session.
    
    Args:
        category_url: URL that was scraped
        requested_limit: Target number of products
        attempted_skus: Number of SKUs discovered
        succeeded_rows: Number of successfully enriched rows
        blocked_count: Number of responses detected as blocked/captcha
        store_verified: Whether store context was successfully verified
        store_verification_note: Details about store verification
        proxy_enabled: Whether proxy was used
        store_number: The numeric store number (e.g., "0205")
        output_path: Path to save the report
        
    Returns:
        Path object of created report file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        "category_url": category_url,
        "requested_limit": requested_limit,
        "attempted_skus": attempted_skus,
        "succeeded_rows": succeeded_rows,
        "blocked_count": blocked_count,
        "store_verified": store_verified,
        "store_verification_note": store_verification_note,
    }
    
    # Add optional fields (only when they have meaningful non-default values)
    # proxy_enabled only added if True (otherwise defaults to False/absent)
    if proxy_enabled:
        report["proxy_enabled"] = proxy_enabled
    
    # store_number only added if provided (otherwise absent from report)
    if store_number:
        report["store_number"] = store_number
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    
    return output_path
