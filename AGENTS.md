# AGENTS.md

## What this is
- ShopGOD scraper project for `sharedealnow.com` (Bangladeshi grocery/deal store): daily price tracker + dashboard.
- Live code exists: `scraper.py` (live API), `extract_har.py` (one-time seed from the HAR), `frontend/` grid dashboard, `run.bat` launcher.
- Reference implementation: sibling project `shopno` at `C:\PROJECTS\ShopGOD\shopno` (same pipeline family, own git repo).

## Git / repo layout gotchas
- Each ShopGOD project is its own git repo. `sharedeal/` has **no `.git` yet**; the parent `C:\PROJECTS` repo is currently tracking it.
- The parent repo `C:\PROJECTS` is a junk drawer of ~60 unrelated projects; its remote is `ranehal/SSC` and recent commits there are unrelated (SSC notes site, gitw). Never `git add -A` / commit from `C:\PROJECTS` — it sweeps in hundreds of unrelated changes.
- Follow `shopno/.gitignore`: ignore `*.har`, `scratch/`, `*.pyc`, `__pycache__/`, `PROMPT.md`.

## The scraper (scraper.py)
- **Fully independent of the HAR** — pure live API. `extract_har.py` is optional and only seeds a baseline snapshot for days before scraping started.
- Data model: `frontend/sharedeal_products.json` is the master — `{categories[], products: {id: {..., history: [{date, price, offer, group, stock}]}}}`. Frontend builds everything from this one file.
- Outputs (regenerated every run): `sharedeal_products.json`, `sharedeal_data.js` (`window.sharedeal_data = ...`), `sharedeal_manifest.js`, plus `frontend/history/sharedeal_products_YYYY-MM-DD.json` daily snapshots.
- Run modes: `python scraper.py` (one pass) or `python scraper.py --watch [minutes]` (re-scrape loop, default 60). Date is Asia/Dhaka (UTC+6).
- API calls have retry-with-backoff; the site throws transient **503s** when hammered — keep `PAGE_DELAY` and don't reduce it.
- The `/products` endpoint is **POST** with JSON body `{"page": "N"}` (or `{"category_id": "N"}` to filter); `/group-buy/products` and `/deal-buy/products` are **GET** with `?page=N`. All send `Authorization: Bearer` (empty) and UA `Dart/3.12 (dart:io)`.

## sharedealnow.com API (verified in HAR + live)
- Base: `https://sharedealnow.com/api/v1/...`
- `GET /home` — `{success, allCategories[], featuredCategories[], products}`; category tree lives here.
- `GET /products` responses are Laravel-style pagination: `{success, products: {current_page, data[], last_page, next_page_url, per_page, total}}`.
- Also `GET /group-buy/products`, `/deal-buy/products`, `/sliders`, `/setting`.
- `GET /profile`, `/addresses`, `/last/order` return **401** (auth required) — not API failures.
- Product prices: `price` (string), `offer_price` when `is_discounted`, `group_prices[]` (tiered group-buy price — min of these is tracked as `group`). Images: `https://sharedealnow.com/storage/<id>/...`.

## Frontend (frontend/)
- Grid of product cards: image, name, category, regular (struck when on sale) + offer/group chips, change-vs-previous-day, and a canvas **sparkline** of price history.
- Click a card → right drawer with Chart.js line chart (regular/offer/group series), low/high stats, and a history table. Chart.js via CDN — offline it degrades to a message.
- `index.html` loads `sharedeal_data.js`; falls back to `fetch('sharedeal_products.json')`. Serve from the **project root** (not `-d frontend`) so `data` paths resolve: `python -m http.server 8765`, dashboard at `/frontend/`.

## Environment
- Windows / PowerShell (pwsh). Tooling is Python + Windows batch (`run.bat` launcher: scrape / watch / serve / HAR-seed / analysis).
- No `requirements.txt` — scripts use the standard library only (`json`, `urllib`, `gzip`, `base64`).