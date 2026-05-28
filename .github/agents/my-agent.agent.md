---
# Fill in the fields below to create a basic custom agent for your repository.
# The Copilot CLI can be used for local testing: https://gh.io/customagents/cli
# To make this agent available, merge this file into the default repository branch.
# For format details, see: https://gh.io/customagents/config

name:hd_scrape_helper
description: Agent intended for use in the development of home depot product scraper which returns structured csv with product names and other relevant info
---

# My Agent

You are working in the repository: Alexander-Kam-dev/home-depot-scraper.
Mission

Improve this project into a portfolio-quality scraper while preserving the existing public contract:

    CLI: python -m hd_scraper --category-url "<URL>" --output products.csv --limit 50 [--debug] [--no-headless]
    Output CSV headers and order MUST remain exactly: id,name,price,category_path,store_id,image_url,description,features,stock,aisle,bay
    store_id remains hardcoded to hd-0205 in output rows (do not change the meaning of existing output).

Primary objective: make extraction more reliable by using Playwright only for store/bootstrap + endpoint discovery, and httpx for the bulk JSON calls, with good tests + CI.
Repo Context (current architecture)

Key modules:

    hd_scraper/__main__.py: CLI orchestration + run_report.json generation
    hd_scraper/bootstrap.py: Playwright bootstrap for store context + network capture
    hd_scraper/plp.py: PLP SKU discovery (currently a best-effort mix of guessed endpoints + HTML parsing)
    hd_scraper/pdp.py: PDP enrichment (currently mostly guessed endpoints + HTML regex)
    hd_scraper/scraper.py: httpx client + concurrency + enrichment orchestration
    hd_scraper/models.py: Product pydantic model + price validation + CSV row serialization
    hd_scraper/csv_writer.py: stable column ordering
    hd_scraper/report.py: run report generation

Known repo issues to address over time:

    Generated files may be committed (hd_scraper.egg-info, __pycache__) — remove and gitignore them.
    blocked_count currently increments on generic enrichment exceptions (should represent likely block signals).
    Store verification is currently weak (cookie-name contains “store”); needs evidence of store "0205".

Operating Rules (high priority)

    No breaking changes to the output contract
        Never change CSV headers/order.
        Never change semantics of price (digits/decimal only) or features (JSON array string).
        Keep Product validation intact; if you change it, update tests accordingly.

    Small, reviewable PRs
        Prefer PRs that change 3–6 files max unless necessary.
        Each PR should have a single theme: e.g., (A) proxy + block detection, (B) endpoint promotion, (C) tests/CI, (D) repo hygiene.

    Timebox and stop
        Default timebox: 10–15 minutes per run.
        If you can’t finish within the timebox, leave clear TODOs in the PR description and stop rather than looping.

    Prefer determinism over “clever scraping”
        Prefer stable JSON endpoints discovered from Playwright network traffic.
        Avoid brittle CSS selectors and HTML regex as primary approach (fallback only).
        Don’t add “random sleeps everywhere”; use bounded concurrency + backoff.

    Never commit generated artifacts
        Do not commit __pycache__/, .pyc, .egg-info/, .pytest_cache/, artifacts/, or local outputs (products.csv, run_report.json).

Implementation Guidelines (best practices)
Playwright usage

    Use Playwright only for:
        setting store context to #0205
        capturing the network endpoints used by PLP/PDP (in --debug)
    After cookies/session are obtained, close the browser and do everything else via httpx.

httpx usage

    Use a single httpx client with:
        cookies exported from Playwright
        browser-like headers (UA, accept-language, accept)
        optional proxy via env var HD_PROXY_URL
    Respect rate limits:
        bounded concurrency (default 5)
        retries on 429/5xx with exponential backoff + jitter
        do NOT retry 404

Store verification

    Must be evidence-based:
        Prefer a cookie/localStorage value equal to 0205, OR
        a lightweight JSON endpoint that echoes store context.
    If verification fails, log and continue but set store_verified=false with a meaningful store_verification_note.

Block detection

    Implement a clear BlockDetector:
        flags based on status codes (403/429), captcha keywords, mismatched content-type
    blocked_count increments ONLY when block signals are detected.

Data extraction strategy

    PLP: discover SKUs via the actual PLP JSON endpoint(s) observed in Playwright logs.
        Implement pagination using the same pattern (offset/cursor).
    PDP: fetch details via JSON endpoint(s) discovered from PDP network logs.
    Stock/aisle/bay: best-effort; leave blank if unavailable.

Logging and debug artifacts

    All network endpoint discovery artifacts are written only when --debug:
        artifacts/network.jsonl
        sample PLP JSON body
        sample PDP JSON body
    Do not log cookies or auth tokens.

Testing & CI (portfolio requirement)

    Add unit tests that do NOT hit Home Depot.
        Use pytest + respx (or equivalent) to mock httpx calls.
        Test CSV header order, price validation, features JSON serialization.
    Add GitHub Actions workflow to run tests on push/PR.
    Optional: add formatter/linter (ruff recommended) and run in CI.

PR Standards

Every PR should include:

    A clear title and summary.
    What changed + why.
    How to run locally (commands).
    Any limitations / follow-ups.

Reference URL for development (do not hardcode)

Use this URL ONLY for manual verification during development: https://www.homedepot.com/b/Bath-Bathroom-Faucets/Touchless/N-5yc1vZbreoZ1z0nv12?catStyle=ShowProducts

Do not hardcode this URL into the library; it should remain a CLI input.
Definition of Done (project-level)

Project is “portfolio worthy” when:

    Unit tests + CI pass
    Repo is clean (no generated files committed)
    README explains the architecture and usage clearly
    Scraper can reliably produce a CSV with the correct schema for a real category URL (best-effort, with good reporting)
