"""
Export SQLite database to static JSON files for GitHub Pages hosting.
"""
import os, sqlite3, json, sys, io

# Fix Windows console encoding
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

DB_FILE = 'pickaboo_prices.db'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def export():
    if not os.path.exists(DB_FILE):
        print(f"Warning: Database file {DB_FILE} not found. Skipping static export.")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = dict_factory
    cursor = conn.cursor()

    os.makedirs("data", exist_ok=True)
    os.makedirs("data/products", exist_ok=True)

    # 1. Stats
    total_products = cursor.execute("SELECT COUNT(*) AS c FROM products").fetchone()['c']
    total_cats     = cursor.execute("SELECT COUNT(*) AS c FROM categories").fetchone()['c']
    last_scraped   = cursor.execute("SELECT MAX(scraped_at) AS t FROM price_history").fetchone()['t']
    stats = {
        "total_products": total_products,
        "total_cats": total_cats,
        "last_scraped": last_scraped
    }
    with open("data/stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # 2. Categories
    categories = cursor.execute("""
        SELECT c.id, c.name, c.slug, c.parent_id,
               COALESCE(p.cnt, 0) as prod_count
        FROM categories c
        LEFT JOIN (
            SELECT category_id, COUNT(*) as cnt
            FROM products
            GROUP BY category_id
        ) p ON c.id = p.category_id
        ORDER BY c.name
    """).fetchall()
    with open("data/categories.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=2)

    # 3. Products
    products = cursor.execute("""
        SELECT p.*, h.price, h.special_price, h.discount, h.stock_available,
        (COALESCE(NULLIF(h.special_price,0), h.price) <= (
            SELECT MIN(COALESCE(NULLIF(special_price,0), price))
            FROM price_history
            WHERE product_id = p.id
        )) as is_atl
        FROM products p
        JOIN (
            SELECT product_id, price, special_price, discount, stock_available
            FROM price_history
            WHERE id IN (SELECT MAX(id) FROM price_history GROUP BY product_id)
        ) h ON p.id = h.product_id
        ORDER BY p.rowid DESC
    """).fetchall()

    with open("data/products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2)

    # 4. Product Details / History
    for p in products:
        pid = p['id']
        history = cursor.execute("""
            SELECT price, special_price, discount, stock_available, scraped_at
            FROM price_history WHERE product_id=? ORDER BY scraped_at
        """, (pid,)).fetchall()
        
        detail = {
            "product": p,
            "history": history
        }
        with open(f"data/products/{pid}.json", "w", encoding="utf-8") as f:
            json.dump(detail, f, indent=2)

    conn.close()
    print("Static export completed successfully for GitHub Pages!")

if __name__ == "__main__":
    export()
