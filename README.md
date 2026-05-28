# Home Depot Product Scraper

An MVP Python 3.11 scraper for Home Depot product data with store context support.

**⚠️ MVP Status and Limitations**

This is a minimum viable product (MVP) scraper intended for portfolio demonstration and experimentation. 
Please note:

- **No guarantee of uptime or reliability**: The scraper may break at any time if Home Depot changes their website structure or API endpoints.
- **Best-effort approach**: Product data extraction uses a combination of API endpoints and HTML parsing fallbacks. Not all fields may be available for every product.
- **Rate limiting**: The scraper respects standard HTTP rate limits (429 responses) with exponential backoff, but Home Depot may block aggressive scraping.
- **For development/learning only**: Do not use in production without proper review and load testing.

## Features

- **Store Context Support**: Sets physical store #0205 before scraping via Playwright
- **Dual-Tool Architecture**: 
  - Playwright for session bootstrap and cookie extraction
  - httpx for subsequent requests with automatic retries
- **Data Validation**: Pydantic models for row schema validation
- **Retry Logic**: Tenacity for automatic retries with exponential backoff
- **CSV Export**: Outputs products.csv with exact column ordering and format
- **Debug Mode**: Network endpoint discovery with `--debug` flag to inspect actual API calls

## Installation

```bash
pip install -e .
```

This installs the package and all dependencies:
- playwright >= 1.40.0
- httpx >= 0.25.0
- pydantic >= 2.0.0
- tenacity >= 8.2.0

Install browser drivers:
```bash
python -m playwright install chromium
```

## Configuration

### Proxy Support

To route both Playwright and httpx traffic through a proxy, set the `HD_PROXY_URL` environment variable:

```bash
export HD_PROXY_URL="http://proxy.example.com:8080"
python -m hd_scraper --category-url "https://www.homedepot.com/c/..."
```

If the proxy URL is not set, the scraper runs normally without proxy routing.

### Debug Mode

Run with `--debug` to capture network endpoints and sample API payloads for analysis:

```bash
python -m hd_scraper \
  --category-url "https://www.homedepot.com/b/Bath-Bathroom-Faucets/Touchless" \
  --output products.csv \
  --debug
```

This will create an `artifacts/` directory containing:
- `network.jsonl` - Captured network requests (for endpoint discovery)
- Sample PLP and PDP JSON payloads (for debugging data extraction)

## Usage

### Command Line

```bash
python -m hd_scraper --category-url "https://www.homedepot.com/c/..." --output products.csv
```

### Options

- `--category-url` (required): Home Depot category URL to scrape
- `--output` (optional): Output CSV file path (default: products.csv)
- `--store-id` (optional): Home Depot store ID (default: hd-0205)
- `--no-headless` (optional): Run browser in non-headless mode (default: headless)

### Example

```bash
python -m hd_scraper \
  --category-url "https://www.homedepot.com/c/Tools/Hand-Tools" \
  --output my_products.csv \
  --store-id hd-0205
```

## Output Format

The scraper outputs a CSV file with exactly these columns in this order:

1. `id` - Product identifier
2. `name` - Product name
3. `price` - Price (digits and decimal only, no currency symbol)
4. `category_path` - URL category path
5. `store_id` - Store identifier (hardcoded: hd-0205)
6. `image_url` - Product image URL
7. `description` - Product description
8. `features` - JSON array string of product features
9. `stock` - Available stock count (blank if unavailable)
10. `aisle` - Store aisle location (blank if unavailable)
11. `bay` - Store bay location (blank if unavailable)

## Example CSV Output

```csv
id,name,price,category_path,store_id,image_url,description,features,stock,aisle,bay
001,Drill Set,29.99,tools/power-tools,hd-0205,https://...,A drill set,"[""Titanium coated"",""100 pieces""]",45,B2,5
002,Screwdriver,19.99,tools/hand-tools,hd-0205,https://...,A set of screwdrivers,"[""Ergonomic""]",,, 
```

## Architecture

### Flow

1. **Playwright Bootstrap** (store context setup)
   - Playwright opens a browser and sets the physical store context to #0205
   - Captures cookies and session data
   - Browser is closed after bootstrap completes

2. **httpx Data Fetching** (bulk operations)
   - Cookies from Playwright are exported to httpx client
   - httpx handles all subsequent API calls with browser-like headers
   - Includes automatic retry logic with exponential backoff

3. **Data Extraction**
   - PLP (Product Listing Page): Discovers SKU list via discovered endpoints or HTML parsing
   - PDP (Product Detail Page): Fetches enriched data for each SKU via API or HTML fallback
   - Block Detection: Monitors for rate limits and captchas

4. **Output**
   - Products are validated using Pydantic models
   - Data is written to CSV with exact column ordering
   - Run report (JSON) includes metadata and metrics

### Why Playwright + httpx?

- **Playwright** is resource-intensive but excellent for:
  - Setting up store context (requires JavaScript execution)
  - Capturing actual network endpoints used by Home Depot's JS frontend
  - Extracting session cookies

- **httpx** is lightweight and efficient for:
  - Making subsequent JSON API calls
  - Handling retries, connection pooling, and rate limiting
  - Running concurrent requests with bounded concurrency

After Playwright establishes the session, all heavy lifting is done via httpx, reducing memory usage and improving performance.

## Data Validation

- **Price**: Must contain only digits and decimal point (no $ or other characters)
- **Features**: Stored as JSON array string in CSV
- **Optional Fields**: stock, aisle, bay are left blank if unavailable (not dropped)

## Run Report

The scraper generates a `run_report.json` file containing metadata about the scraping session:

- `category_url` - URL that was scraped
- `requested_limit` - Target number of products requested
- `attempted_skus` - Number of SKUs discovered in the category
- `succeeded_rows` - Number of products successfully enriched and written to CSV
- `blocked_count` - Number of responses detected as blocked (HTTP 403/429 or captcha)
- `store_verified` - Boolean indicating if store context was successfully verified
- `store_verification_note` - Details about how store verification succeeded or failed
- `proxy_enabled` (optional) - Boolean indicating if a proxy was used (only present if true)
- `store_number` (optional) - The numeric store number (e.g., "0205")

## Requirements

- Python >= 3.11
- Playwright (chromium)
- httpx
- pydantic
- tenacity

## License

MIT
