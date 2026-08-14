import json, os, gzip, base64
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
HAR_FILE = os.path.join(ROOT, 'sharedealnow.com_2026_07_30_04_00_04.har')
FRONTEND = os.path.join(ROOT, 'frontend')
HISTORY = os.path.join(FRONTEND, 'history')
DHAKA = timezone(timedelta(hours=6))

API_BASE = 'https://sharedealnow.com/api/v1'

def decode_entry(entry):
    content = entry.get('response', {}).get('content', {})
    text = content.get('text', '')
    mime = content.get('mimeType', '')
    if not text or 'json' not in mime:
        return None
    raw = text.encode('utf-8', errors='replace')
    for attempt in [
        lambda: json.loads(raw.decode('utf-8')),
        lambda: json.loads(gzip.decompress(raw).decode('utf-8')),
        lambda: json.loads(gzip.decompress(base64.b64decode(text)).decode('utf-8')),
    ]:
        try:
            return attempt()
        except Exception:
            pass
    return None

def capture_date(entries):
    ts = max(e['startedDateTime'] for e in entries)
    utc = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    return (utc.astimezone(DHAKA)).date().isoformat()

def to_float(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(',', '').strip())
    except Exception:
        return None

def group_price(product):
    gp = product.get('group_prices') or []
    vals = [to_float(p.get('price')) for p in gp]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else None

def product_history_entry(product, date):
    return {
        'date': date,
        'price': to_float(product.get('price')),
        'offer': to_float(product.get('offer_price')) if product.get('is_discounted') else None,
        'group': group_price(product),
        'stock': to_float(product.get('stock')),
    }

def product_meta(product):
    cat = product.get('category') or {}
    return {
        'id': product.get('id'),
        'name': product.get('name'),
        'slug': product.get('slug'),
        'sku': product.get('sku'),
        'category_id': product.get('category_id'),
        'category': cat.get('name') if isinstance(cat, dict) else None,
        'unit': product.get('unit'),
        'volume': product.get('volume'),
        'image': product.get('image'),
        'best_selling': product.get('best_selling_product'),
    }

def main():
    with open(HAR_FILE, 'r', encoding='utf-8') as f:
        har = json.load(f)
    entries = har['log']['entries']
    date = capture_date(entries)
    print(f'Capture date (Dhaka): {date}')

    categories = []
    products = {}
    for ent in entries:
        req = ent['request']
        url = req['url']
        if 'sharedealnow.com/api' not in url:
            continue
        data = decode_entry(ent)
        if not isinstance(data, dict):
            continue
        if '/api/v1/home' in url:
            for c in data.get('allCategories', []):
                categories.append({
                    'id': c.get('id'),
                    'name': c.get('name'),
                    'slug': c.get('slug'),
                    'featured': c.get('featured'),
                    'image': c.get('image'),
                })
        plist = data.get('products')
        items = plist.get('data') if isinstance(plist, dict) else (plist if isinstance(plist, list) else [])
        for p in items:
            if not isinstance(p, dict) or p.get('id') is None:
                continue
            pid = int(p['id'])
            if pid not in products:
                products[pid] = {**product_meta(p), 'history': [product_history_entry(p, date)]}

    categories = sorted({c['id']: c for c in categories}.values(), key=lambda c: c['id'])

    os.makedirs(HISTORY, exist_ok=True)
    snapshot_path = os.path.join(HISTORY, f'sharedeal_products_{date}.json')
    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f'Daily snapshot: {snapshot_path} ({len(products)} products)')

    master = {
        'store': 'ShareDeal',
        'api_base': API_BASE,
        'captured_at': date,
        'categories': categories,
        'products': products,
    }

    json_path = os.path.join(FRONTEND, 'sharedeal_products.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(master, f, indent=2, ensure_ascii=False)

    js_path = os.path.join(FRONTEND, 'sharedeal_data.js')
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write('window.sharedeal_data = ')
        json.dump(master, f, ensure_ascii=False)
        f.write(';\n')

    manifest = {
        'store': 'ShareDeal',
        'api_base': API_BASE,
        'headers': {
            'User-Agent': 'Dart/3.12 (dart:io)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer',
        },
        'catalog_pages': 'POST /products  {"page": "{n}"}',
        'category_filter': 'POST /products  {"category_id": "{id}"}',
        'pagination': 'Laravel: {current_page, last_page, per_page, total, next_page_url}',
    }
    js_manifest = 'window.sharedeal_manifest = ' + json.dumps(manifest, indent=2, ensure_ascii=False) + ';\n'
    with open(os.path.join(FRONTEND, 'sharedeal_manifest.js'), 'w', encoding='utf-8') as f:
        f.write(js_manifest)

    print(f'Master: {json_path}')
    print(f'JS data: {js_path}')
    print(f'Manifest: {os.path.join(FRONTEND, "sharedeal_manifest.js")}')
    print(f'Categories: {len(categories)} | Products: {len(products)}')

if __name__ == '__main__':
    main()