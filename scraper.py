"""
Pickaboo Deep Price Scraper
Discovers all categories dynamically via API, paginates every category,
stores products + daily price snapshots in SQLite.
Run: python scraper.py [--categories 171,64] [--max-pages 50] [--delay 0.5]
"""
import sqlite3, requests, re, time, argparse, sys, io
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
# Fix Windows console encoding
try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except: pass

DB_FILE = 'pickaboo_prices.db'
BASE_URL = 'https://www.pickaboo.com'
HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-encoding': 'gzip',
    'cookie': 'PHPSESSID=7m74vc2uc822l67m5kalahlvgs',
    'user-agent': 'okhttp/4.12.0'
}

# ─── DB ────────────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS products (
            id          TEXT PRIMARY KEY,
            sku         TEXT,
            name        TEXT,
            slug        TEXT,
            category_id TEXT,
            category_name TEXT,
            product_img TEXT,
            unit        TEXT,
            unit_value  REAL
        );
        CREATE TABLE IF NOT EXISTS price_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id     TEXT,
            price          REAL,
            special_price  REAL,
            discount       REAL,
            stock_available INTEGER,
            scraped_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS categories (
            id        TEXT PRIMARY KEY,
            name      TEXT,
            slug      TEXT,
            parent_id TEXT,
            icon      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ph_product ON price_history(product_id);
    ''')
    conn.commit()
    conn.close()

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ─── HTTP ──────────────────────────────────────────────────────────────────────

def get(url, delay=0.5, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(delay)
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            wait = 2 ** attempt
            print(f"  ⚠  Attempt {attempt+1}/{retries} failed: {e}  (retry in {wait}s)")
            time.sleep(wait)
    return None

# ─── UNIT DETECTION ────────────────────────────────────────────────────────────

UNIT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(kg|g(?!b)|ltr?|litre?|ml|l(?!\w)|pcs|pieces?|pack)', re.I)
UNIT_MAP = {'ltr': 'L', 'litre': 'L', 'litr': 'L', 'l': 'L',
            'piece': 'pcs', 'pieces': 'pcs', 'pack': 'pack'}

def extract_unit(name):
    m = UNIT_RE.search(name)
    if not m: return None, None
    val  = float(m.group(1))
    unit = UNIT_MAP.get(m.group(2).lower(), m.group(2).lower())
    return unit, val

# ─── CATEGORIES ────────────────────────────────────────────────────────────────

def fetch_and_save_categories(delay):
    print("[*] Fetching all categories...")
    data = get(f"{BASE_URL}/rest/V1/all-categories", delay)
    if not data:
        print("  [!] Could not fetch categories.")
        return []

    rows = []
    def walk(cat, parent_id=''):
        cid = str(cat.get('id', ''))
        if not cid: return
        rows.append((cid, cat.get('name',''), cat.get('slug',''), parent_id, cat.get('icon','')))
        for child in cat.get('childs', []):
            walk(child, cid)

    for c in data:
        walk(c)

    conn = db()
    conn.executemany(
        'INSERT OR REPLACE INTO categories (id,name,slug,parent_id,icon) VALUES (?,?,?,?,?)', rows)
    conn.commit()
    conn.close()
    print(f"  [OK] {len(rows)} categories saved.")
    return [{'id': r[0], 'name': r[1], 'slug': r[2], 'parent_id': r[3]} for r in rows]

# ─── PRODUCTS ──────────────────────────────────────────────────────────────────

def already_scraped_today(conn, product_id):
    """Return True if we already have a price record for today."""
    r = conn.execute(
        "SELECT 1 FROM price_history WHERE product_id=? AND date(scraped_at)=date('now') LIMIT 1",
        (product_id,)).fetchone()
    return r is not None

def scrape_category(cat_id, cat_name, max_pages, delay):
    print(f"  [>] {cat_name}  (id={cat_id})")
    conn = db()
    added = skipped = 0

    for page in range(1, max_pages + 1):
        url = (f"{BASE_URL}/rest/V1/categorypageapi/{cat_id}"
               f"?prodLimit=20&currentPage={page}&featProdLimit=6&web=1")
        data = get(url, delay)
        if not data:
            break

        # API returns cat_prods (list) at top level
        prods = data.get('cat_prods') or data.get('products') or []
        if not prods:
            break  # no more pages

        for p in prods:
            pid = str(p.get('id', ''))
            if not pid:
                continue

            name = p.get('product_name', '')
            unit, unit_val = extract_unit(name)

            conn.execute('''
                INSERT OR IGNORE INTO products
                    (id, sku, name, slug, category_id, category_name, product_img, unit, unit_value)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (pid, p.get('sku',''), name, p.get('slug',''),
                 cat_id, cat_name, p.get('product_img',''), unit, unit_val))

            if already_scraped_today(conn, pid):
                skipped += 1
                continue

            conn.execute('''
                INSERT INTO price_history
                    (product_id, price, special_price, discount, stock_available)
                VALUES (?,?,?,?,?)''',
                (pid,
                 p.get('product_price', 0),
                 p.get('product_specialPrice', 0),
                 p.get('product_discount', 0),
                 1 if p.get('stock_available') else 0))
            added += 1

        conn.commit()
        total = data.get('total_cat_prods', 0)
        print(f"    page {page}  +{added} new  (total in cat: {total})")
        if total and page * 20 >= int(total):
            break  # fetched everything

    conn.close()
    return added, skipped

# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Pickaboo price scraper')
    ap.add_argument('--categories', help='Comma-separated category IDs (default: all)')
    ap.add_argument('--max-pages', type=int, default=1000, help='Max pages to scrape per category')
    ap.add_argument('--delay',     type=float, default=0.6)
    args = ap.parse_args()

    print(f"\n[START] Pickaboo scraper started  {datetime.now():%Y-%m-%d %H:%M:%S}\n")
    init_db()

    cats = fetch_and_save_categories(args.delay)
    wanted = set(args.categories.split(',')) if args.categories else None

    total_new = total_skip = 0
    jobs = [(cat['id'], cat['name']) for cat in cats
            if (not wanted or cat['id'] in wanted) and cat['id']]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(scrape_category, cid, cname, args.max_pages, args.delay): (cid, cname)
                   for cid, cname in jobs}
        for fut in as_completed(futures):
            cid, cname = futures[fut]
            try:
                new, skip = fut.result()
                total_new  += new
                total_skip += skip
            except Exception as e:
                print(f"  ⚠  Category failed ({cname}, id={cid}): {e}")

    print(f"\n[DONE] {total_new} new price records, {total_skip} already recorded today.\n")

if __name__ == '__main__':
    main()
