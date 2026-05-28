# Home Depot Product Scraper

An MVP Python 3.11 scraper for Home Depot product data with store context support.

## Features

- **Store Context Support**: Sets physical store #0205 before scraping via Playwright
- **Dual-Tool Architecture**: 
  - Playwright for session bootstrap and cookie extraction
  - httpx for subsequent requests with automatic retries
- **Data Validation**: Pydantic models for row schema validation
- **Retry Logic**: Tenacity for automatic retries with exponential backoff
- **CSV Export**: Outputs products.csv with exact column ordering and format

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

### Modules

- **models.py**: Pydantic Product model with CSV serialization and validation
- **config.py**: Environment variable configuration (proxy support)
- **block_detector.py**: Block detection helper for identifying rate limits and captchas
- **bootstrap.py**: Playwright session setup for store context establishment
- **scraper.py**: httpx-based scraper with Tenacity retry logic and block detection
- **csv_writer.py**: CSV output writer with exact column ordering
- **report.py**: Run report generation with session metadata
- **__main__.py**: CLI entry point and orchestration

### Flow

1. Playwright bootstraps a browser session and sets store context to #0205
2. Cookies are extracted from the Playwright session
3. Playwright browser is closed
4. httpx client uses extracted cookies for subsequent requests
5. Products are validated with Pydantic models
6. Results are written to CSV with exact column ordering

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
