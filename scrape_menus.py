"""
FoodiEATS Live Scraper - Fetches restaurants + menus directly from API.
No HAR files needed. Usage: python scrape_menus.py
"""

import httpx
import json
import base64
import time
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "restaurant_dashboard", "data.json")
PARQUET_FILE = os.path.join(DATA_DIR, "restaurant_dashboard", "data.parquet")

BASE_URL = "https://api.foodibd.com"

HEADERS_BASE = {
    "accept": "application/json",
    "accept-charset": "UTF-8",
    "accept-encoding": "gzip",
    "content-type": "application/json",
    "host": "api.foodibd.com",
    "origin": "foodi-prod-android 8.0.3 16 1b5a4567bbcb95d4",
    "user-agent": "ktor-client",
    "x-requested-with": "XMLHttpRequest",
}

LOCATIONS = [
    {"name": "Khilgaon", "lat": 23.7480914, "lng": 90.4344348},
    {"name": "Banasree", "lat": 23.763347317340862, "lng": 90.43200127780437},
]

PAGE_LIMIT = 20
REQUEST_DELAY = 0.3
MAX_WORKERS = 5


def double_b64(val):
    s = base64.b64encode(val.encode("utf-8")).decode("utf-8")
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def get_fresh_sxsrf(client, lat, lng):
    headers = {**HEADERS_BASE}
    headers.pop("sxsrf", None)

    r = client.get(
        f"{BASE_URL}/restaurants-go/api/v2/all-branch",
        params={"longitude": str(lng), "latitude": str(lat), "serviceType": "1", "page": "1", "limit": "1", "tags": "-1"},
        headers=headers, timeout=15,
    )
    cf_ray = r.headers.get("cf-ray-status-id-tn", "")
    if not cf_ray:
        return None

    new_sxsrf = double_b64(cf_ray)
    headers["sxsrf"] = new_sxsrf
    r2 = client.get(
        f"{BASE_URL}/restaurants-go/api/v2/all-branch",
        params={"longitude": str(lng), "latitude": str(lat), "serviceType": "1", "page": "1", "limit": "1", "tags": "-1"},
        headers=headers, timeout=15,
    )
    if r2.status_code == 200:
        return new_sxsrf

    cf_ray2 = r2.headers.get("cf-ray-status-id-tn", "")
    if cf_ray2:
        sxsrf2 = double_b64(cf_ray2)
        headers["sxsrf"] = sxsrf2
        r3 = client.get(
            f"{BASE_URL}/restaurants-go/api/v2/all-branch",
            params={"longitude": str(lng), "latitude": str(lat), "serviceType": "1", "page": "1", "limit": "1", "tags": "-1"},
            headers=headers, timeout=15,
        )
        if r3.status_code == 200:
            cf_ray3 = r3.headers.get("cf-ray-status-id-tn", "")
            if cf_ray3:
                return double_b64(cf_ray3)
            return sxsrf2
    return None


def ensure_sxsrf(client, lat, lng, sxsrf, consecutive_fails, req_count):
    if sxsrf is None or consecutive_fails >= 3 or req_count % 25 == 0:
        fresh = get_fresh_sxsrf(client, lat, lng)
        if fresh:
            print(f"  [auth] Fresh sxsrf obtained")
            return fresh, 0
        else:
            print(f"  [auth] FAILED - will retry each request")
            return sxsrf, consecutive_fails
    return sxsrf, consecutive_fails


def fetch_all_branches(client, lat, lng, sxsrf):
    """Fetch all restaurant listings for a location via paginated all-branch API."""
    all_branches = []
    page = 1

    while True:
        params = {
            "longitude": str(lng), "latitude": str(lat),
            "serviceType": "1", "page": str(page),
            "limit": str(PAGE_LIMIT), "tags": "-1",
        }
        headers = {**HEADERS_BASE, "sxsrf": sxsrf}

        r = client.get(
            f"{BASE_URL}/restaurants-go/api/v2/all-branch",
            params=params, headers=headers, timeout=15,
        )

        if r.status_code == 401:
            return None, sxsrf, True

        cf_ray = r.headers.get("cf-ray-status-id-tn", "")
        if cf_ray:
            sxsrf = double_b64(cf_ray)
            headers["sxsrf"] = sxsrf

        if r.status_code != 200:
            print(f"  [list] Page {page}: HTTP {r.status_code}")
            break

        body = r.json()
        if not body.get("status") or not body.get("data"):
            break

        data = body["data"]
        branches = data.get("branches", [])
        total_pages = data.get("totalPage", 1)

        if not branches:
            break

        all_branches.extend(branches)
        print(f"  [list] Page {page}/{total_pages}: +{len(branches)} restaurants (total: {len(all_branches)})")

        if page >= total_pages:
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    return all_branches, sxsrf, False


def fetch_branch_detail(client, branch_id, lat, lng, sxsrf):
    avail_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    params = {
        "branchId": str(branch_id),
        "userLat": str(lat), "userLong": str(lng),
        "orderType": "1", "availibilityTime": avail_time,
    }
    headers = {**HEADERS_BASE, "sxsrf": sxsrf}

    r = client.get(
        f"{BASE_URL}/restaurants/api/Branch/v2/GetBranchDetail",
        params=params, headers=headers, timeout=20,
    )

    if r.status_code == 401:
        fresh = get_fresh_sxsrf(client, lat, lng)
        if fresh:
            sxsrf = fresh
            headers["sxsrf"] = fresh
            r = client.get(
                f"{BASE_URL}/restaurants/api/Branch/v2/GetBranchDetail",
                params=params, headers=headers, timeout=20,
            )

    cf_ray = r.headers.get("cf-ray-status-id-tn", "")
    new_sxsrf = sxsrf
    if cf_ray:
        new_sxsrf = double_b64(cf_ray)

    if r.status_code != 200:
        return None, new_sxsrf

    body = r.json()
    if not body.get("status") or not body.get("data"):
        return None, new_sxsrf

    return body["data"], new_sxsrf


def parse_branch_listing(branch):
    return {
        "id": branch["id"],
        "name": branch.get("name", ""),
        "image": branch.get("image", ""),
        "coverImage": branch.get("coverImage", ""),
        "primaryCuisine": branch.get("primaryCuisine", ""),
        "openAt": branch.get("openAt"),
        "distance": branch.get("distance"),
        "deliveryTime": branch.get("deliveryTime"),
        "totalDeliveryTime": branch.get("totalDeliveryTime"),
        "isPopular": branch.get("isPopular", False),
        "isTakePreOrder": branch.get("isTakePreOrder", False),
        "deliveryCharge": branch.get("deliveryCharge"),
        "rating": branch.get("rating"),
        "ratingCount": branch.get("ratingCount"),
        "averageReviewCount": branch.get("rating"),
        "totalReviewCount": branch.get("ratingCount"),
        "priceRange": branch.get("priceRange", ""),
        "location": branch.get("location"),
        "cuisineList": branch.get("cuisineList", []),
        "shopType": branch.get("shopType"),
        "branchImages": branch.get("branchImages", {}),
    }


def parse_branch_detail(data):
    categories = []
    for cat in data.get("categories", []):
        categories.append({
            "id": cat["id"],
            "name": cat.get("name", ""),
            "priorityNumber": cat.get("priorityNumber", 0),
            "menuIds": cat.get("menuIds", []),
        })

    menus = {}
    menus_data = data.get("menus", {})
    if isinstance(menus_data, dict):
        for mid, menu in menus_data.items():
            menus[str(mid)] = {
                "id": menu["id"],
                "name": menu.get("name", ""),
                "price": menu.get("price", "0"),
                "oldPrice": menu.get("oldPrice", "0"),
                "hasVariation": menu.get("hasVariation", 0),
                "image": menu.get("image"),
                "bannerImage": menu.get("bannerImage"),
                "isPopular": menu.get("isPopular", False),
                "description": menu.get("description"),
                "variationIds": menu.get("variationIds", []),
                "addOnCategoryIds": menu.get("addOnCategoryIds", []),
                "variationOtherInfo": menu.get("variationOtherInfo", {}),
            }

    variations = {}
    vars_data = data.get("variations", {})
    if isinstance(vars_data, dict):
        for vid, var in vars_data.items():
            variations[str(vid)] = {
                "id": var["id"],
                "name": var.get("name", ""),
                "isAvailable": var.get("isAvailable", True),
            }

    return {
        "categories": categories,
        "menus": menus,
        "variations": variations,
        "averageReviewCount": data.get("averageReviewCount"),
        "totalReviewCount": data.get("totalReviewCount"),
        "minOrderValue": data.get("minOrderValue"),
        "preparationTime": data.get("preparationTime"),
        "deliveryRadius": data.get("deliveryRadius"),
        "pickupTime": data.get("pickupTime"),
        "workingHours": data.get("workingHours"),
    }


def merge_into_restaurant(rest, detail):
    for key in ("categories", "menus", "variations", "minOrderValue",
                "preparationTime", "deliveryRadius", "pickupTime", "workingHours"):
        val = detail.get(key)
        if val is not None and val != "" and val != [] and val != {}:
            rest[key] = val
    if detail.get("averageReviewCount"):
        rest["averageReviewCount"] = detail["averageReviewCount"]
    if detail.get("totalReviewCount"):
        rest["totalReviewCount"] = detail["totalReviewCount"]


_thread_local = threading.local()
_worker_clients = []
_worker_clients_lock = threading.Lock()
_save_lock = threading.Lock()


def _worker_client():
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = httpx.Client(http2=True, follow_redirects=True)
        _thread_local.client = client
        with _worker_clients_lock:
            _worker_clients.append(client)
    return client


def scrape_restaurant_menu(rest, lat, lng, seed_sxsrf, idx, total_to_scrape):
    client = _worker_client()
    sxsrf = getattr(_thread_local, "sxsrf", seed_sxsrf)
    consecutive_fails = getattr(_thread_local, "consecutive_fails", 0)
    req_count = getattr(_thread_local, "req_count", 0)

    rid = rest["id"]
    rname = rest.get("name", str(rid))

    ok = False
    try:
        sxsrf, consecutive_fails = ensure_sxsrf(client, lat, lng, sxsrf, consecutive_fails, req_count)

        detail, sxsrf = fetch_branch_detail(client, rid, lat, lng, sxsrf)

        if detail:
            parsed = parse_branch_detail(detail)
            merge_into_restaurant(rest, parsed)
            dish_count = len(parsed.get("menus", {}))
            if dish_count > 0:
                print(f"  [{idx+1}/{total_to_scrape}] {rname}: {dish_count} dishes")
            else:
                print(f"  [{idx+1}/{total_to_scrape}] {rname}: empty menu")
            ok = True
        else:
            print(f"  [{idx+1}/{total_to_scrape}] {rname}: FAIL")
    except Exception as exc:
        print(f"  [{idx+1}/{total_to_scrape}] {rname}: EXC {exc!r}")
    finally:
        _thread_local.sxsrf = sxsrf
        _thread_local.consecutive_fails = 0 if ok else consecutive_fails + 1
        _thread_local.req_count = req_count + 1
        time.sleep(REQUEST_DELAY)
    return ok


def load_all_existing_history():
    """Load historical price records across data.parquet, previous history snapshot JSONs, and data.json."""
    import glob
    existing_dish_hist = {}

    # 1. First priority: load directly and fast from PARQUET_FILE if it exists
    if os.path.exists(PARQUET_FILE):
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(PARQUET_FILE, columns=['r_id', 'd_id', 'd_history'])
            r_ids = table['r_id'].to_pylist()
            d_ids = table['d_id'].to_pylist()
            d_hists = table['d_history'].to_pylist()
            for rid, did, h_json in zip(r_ids, d_ids, d_hists):
                if rid and did and h_json:
                    key = f"{str(rid).strip()}:{str(did).strip()}"
                    try:
                        p_hist = json.loads(h_json) if isinstance(h_json, str) else h_json
                        if isinstance(p_hist, list) and p_hist:
                            existing_dish_hist[key] = p_hist
                    except Exception:
                        pass
            if existing_dish_hist:
                print(f"  [history] Loaded {len(existing_dish_hist)} continuous dish histories instantly from {os.path.basename(PARQUET_FILE)}")
                return existing_dish_hist
        except Exception as e:
            print(f"  [WARN] Failed to load history from parquet: {e}")

    # 2. Second priority: current DATA_FILE if available
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            for loc in old_data.get("locations", []):
                for rest in loc.get("restaurants", []):
                    rid = str(rest.get("id"))
                    for did, menu in rest.get("menus", {}).items():
                        key = f"{rid}:{did}"
                        p_hist = menu.get("price_history") or menu.get("priceHistory") or menu.get("history") or []
                        if isinstance(p_hist, list):
                            for entry in p_hist:
                                if isinstance(entry, dict) and entry.get("date"):
                                    if key not in existing_dish_hist:
                                        existing_dish_hist[key] = []
                                    if not any(h.get("date") == entry.get("date") for h in existing_dish_hist[key]):
                                        existing_dish_hist[key].append(entry)
        except Exception as e:
            print(f"  [WARN] Failed to load previous dish history from data.json: {e}")

    # 3. Third priority: history snapshots
    hist_dir = os.path.join(DATA_DIR, "history")
    if os.path.exists(hist_dir):
        for f in sorted(glob.glob(os.path.join(hist_dir, "*.json"))):
            try:
                fname = os.path.basename(f)
                date_part = fname.replace(".json", "").split("_")[-1]
                with open(f, "r", encoding="utf-8") as fh:
                    h_data = json.load(fh)
                for loc in h_data.get("locations", []):
                    for rest in loc.get("restaurants", []):
                        rid = str(rest.get("id"))
                        for did, menu in rest.get("menus", {}).items():
                            key = f"{rid}:{did}"
                            p_hist = menu.get("price_history") or menu.get("priceHistory") or menu.get("history") or []
                            if isinstance(p_hist, list) and p_hist:
                                for entry in p_hist:
                                    if isinstance(entry, dict) and entry.get("date"):
                                        if key not in existing_dish_hist:
                                            existing_dish_hist[key] = []
                                        if not any(h.get("date") == entry.get("date") for h in existing_dish_hist[key]):
                                            existing_dish_hist[key].append(entry)
                            else:
                                try: p = float(menu.get("price", 0))
                                except: p = 0
                                if p > 0:
                                    if key not in existing_dish_hist:
                                        existing_dish_hist[key] = []
                                    if not any(h.get("date") == date_part for h in existing_dish_hist[key]):
                                        existing_dish_hist[key].append({
                                            "date": date_part,
                                            "price": p,
                                            "oldPrice": float(menu.get("oldPrice", p) or p)
                                        })
            except Exception:
                pass

    for key in existing_dish_hist:
        existing_dish_hist[key].sort(key=lambda x: str(x.get("date", "")))

    return existing_dish_hist


def merge_dish_histories(new_locations, now_iso, today_str, existing_dish_hist=None):
    if existing_dish_hist is None:
        existing_dish_hist = load_all_existing_history()

    for loc in new_locations:
        for rest in loc.get("restaurants", []):
            rid = str(rest.get("id"))
            for did, menu in rest.get("menus", {}).items():
                key = f"{rid}:{did}"
                hist = list(existing_dish_hist.get(key, []))
                try:
                    curr_price = float(menu.get("price", 0))
                except (ValueError, TypeError):
                    curr_price = 0
                try:
                    old_price = float(menu.get("oldPrice", curr_price) or curr_price)
                except (ValueError, TypeError):
                    old_price = curr_price

                # Remove any existing entry for today
                hist = [h for h in hist if str(h.get("date"))[:10] != today_str]
                if curr_price > 0:
                    entry = {
                        "date": today_str,
                        "price": curr_price,
                    }
                    if old_price > 0 and old_price != curr_price:
                        entry["oldPrice"] = old_price
                    hist.append(entry)

                # Deduplicate consecutive identical prices to keep payload ultra-lean!
                if len(hist) > 1:
                    deduped = [hist[0]]
                    for pt in hist[1:]:
                        p_val = float(pt.get("price") or 0)
                        if p_val > 0 and p_val != float(deduped[-1].get("price") or 0):
                            d_entry = {"date": str(pt.get("date"))[:10], "price": p_val}
                            if pt.get("oldPrice") and float(pt.get("oldPrice")) != p_val:
                                d_entry["oldPrice"] = float(pt.get("oldPrice"))
                            deduped.append(d_entry)
                    # Always preserve latest observation date
                    last_pt = hist[-1]
                    last_p = float(last_pt.get("price") or 0)
                    last_d = str(last_pt.get("date"))[:10]
                    if last_p > 0 and last_d and last_d != str(deduped[-1].get("date"))[:10]:
                        d_entry = {"date": last_d, "price": last_p}
                        if last_pt.get("oldPrice") and float(last_pt.get("oldPrice")) != last_p:
                            d_entry["oldPrice"] = float(last_pt.get("oldPrice"))
                        deduped.append(d_entry)
                    hist = deduped

                menu["price_history"] = hist
                menu.pop("priceHistory", None)

    return new_locations


def save_parquet(locations, total_r, total_d, scraped_at):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        print("  [parquet] pyarrow not installed — skipping parquet export")
        return False

    rows = []
    for loc in locations:
        loc_name = loc.get("name", "")
        loc_lat = float(loc.get("lat") or 0)
        loc_lng = float(loc.get("lng") or 0)
        for rest in loc.get("restaurants", []):
            base = {
                "meta_scraped_at": scraped_at,
                "loc_name": loc_name,
                "loc_lat": loc_lat,
                "loc_lng": loc_lng,
                "r_id": int(rest.get("id") or 0),
                "r_name": rest.get("name", ""),
                "r_image": rest.get("image", ""),
                "r_primary": rest.get("primaryCuisine", ""),
                "r_rating": float(rest.get("rating") or 0),
                "r_rating_count": int(rest.get("ratingCount") or 0),
                "r_delivery_time": str(rest.get("deliveryTime") or ""),
                "r_delivery_charge": float(rest.get("deliveryCharge") or 0),
            }
            menus = rest.get("menus", {})
            if not menus:
                rows.append({**base, "d_id": 0, "d_name": "", "d_price": 0.0, "d_old_price": 0.0, "d_desc": "", "d_image": "", "d_popular": False, "d_history": None})
            else:
                for mid, m in menus.items():
                    p_hist = m.get("price_history") or []
                    rows.append({
                        **base,
                        "d_id": int(m.get("id") or mid or 0),
                        "d_name": str(m.get("name") or ""),
                        "d_price": float(m.get("price") or 0),
                        "d_old_price": float(m.get("oldPrice") or 0),
                        "d_desc": str(m.get("description") or ""),
                        "d_image": str(m.get("image") or ""),
                        "d_popular": bool(m.get("isPopular") or False),
                        "d_history": json.dumps(p_hist, separators=(',', ':'), ensure_ascii=False) if p_hist else None,
                    })

    if not rows:
        return False

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, PARQUET_FILE, compression="zstd", compression_level=12)
    if os.path.exists(PARQUET_FILE):
        pq_mb = os.path.getsize(PARQUET_FILE) / (1024 * 1024)
        print(f"  [parquet] Stored continuous history in {os.path.basename(PARQUET_FILE)} ({pq_mb:.2f} MB)")
        return True
    return False


def save_output(locations, is_final=False, existing_dish_hist=None):
    if not locations or sum(len(l["restaurants"]) for l in locations) == 0:
        return 0, 0
    now_iso = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")
    merged = merge_dish_histories(locations, now_iso, today_str, existing_dish_hist)
    total_r = sum(len(loc["restaurants"]) for loc in merged)
    total_d = sum(len(r.get("menus", {})) for loc in merged for r in loc["restaurants"])

    output = {
        "locations": merged,
        "totalRestaurants": total_r,
        "totalDishes": total_d,
        "scrapedAt": now_iso
    }

    with _save_lock:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

        if is_final:
            save_parquet(merged, total_r, total_d, now_iso)
            if total_d > 0:
                # Save daily history snapshot: compact without nested bloated history array
                compact_locations = []
                for loc in merged:
                    c_loc = {k: v for k, v in loc.items() if k != "restaurants"}
                    c_rests = []
                    for r in loc.get("restaurants", []):
                        cr = {k: v for k, v in r.items() if k != "menus"}
                        cm = {}
                        for did, m in r.get("menus", {}).items():
                            cm[did] = {k: v for k, v in m.items() if k not in ("price_history", "priceHistory", "history")}
                        cr["menus"] = cm
                        c_rests.append(cr)
                    c_loc["restaurants"] = c_rests
                    compact_locations.append(c_loc)

                snap_output = {
                    "locations": compact_locations,
                    "totalRestaurants": total_r,
                    "totalDishes": total_d,
                    "scrapedAt": now_iso
                }
                hist_dir = os.path.join(DATA_DIR, "history")
                os.makedirs(hist_dir, exist_ok=True)
                snapshot_file = os.path.join(hist_dir, f"foodie_restaurants_{today_str}.json")
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    json.dump(snap_output, f, ensure_ascii=False, separators=(',', ':'))
                snap_mb = os.path.getsize(snapshot_file) / (1024 * 1024)
                print(f"  [snapshot] Saved daily history: {snapshot_file} ({snap_mb:.2f} MB)")

    return total_r, total_d


def main():
    print("=" * 60)
    print("  FoodiEATS Live Scraper")
    print("=" * 60)

    # Load multi-day history upfront so it is never overwritten during scraping
    existing_dish_hist = load_all_existing_history()
    print(f"  [history] Loaded historical price trends for {len(existing_dish_hist)} dishes")

    client = httpx.Client(http2=True, follow_redirects=True)
    output_locations = []
    total_restaurants = 0
    total_dishes = 0

    for loc in LOCATIONS:
        lat, lng = loc["lat"], loc["lng"]
        name = loc["name"]
        print(f"\n--- {name} (lat={lat}, lng={lng}) ---")

        sxsrf = get_fresh_sxsrf(client, lat, lng)
        if not sxsrf:
            print(f"  [FATAL] Could not bootstrap sxsrf for {name}, skipping")
            continue
        print(f"  [auth] sxsrf obtained")

        branches, sxsrf, need_reauth = fetch_all_branches(client, lat, lng, sxsrf)
        if branches is None:
            print(f"  [FATAL] Failed to list branches for {name}")
            continue

        restaurants = [parse_branch_listing(b) for b in branches]
        print(f"\n  [detail] Fetching menus for {len(restaurants)} restaurants...")

        scraped = 0
        failed = 0
        total_to_scrape = len(restaurants)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(scrape_restaurant_menu, rest, lat, lng, sxsrf, i, total_to_scrape)
                for i, rest in enumerate(restaurants)
            ]

            for completed, future in enumerate(as_completed(futures), 1):
                try:
                    ok = future.result()
                except Exception as exc:
                    print(f"  [worker] task raised: {exc!r}")
                    ok = False
                if ok:
                    scraped += 1
                else:
                    failed += 1

                if completed % 20 == 0:
                    save_output(output_locations, is_final=False, existing_dish_hist=existing_dish_hist)

        loc_dishes = sum(len(r.get("menus", {})) for r in restaurants)
        total_restaurants += len(restaurants)
        total_dishes += loc_dishes

        restaurants.sort(key=lambda r: r.get("distance") or 9999)
        output_locations.append({
            "name": name,
            "lat": lat,
            "lng": lng,
            "restaurants": restaurants,
        })

        print(f"\n  Location summary: {len(restaurants)} restaurants, {loc_dishes} dishes ({scraped} ok, {failed} failed)")

    client.close()
    for wc in _worker_clients:
        wc.close()

    if total_restaurants == 0:
        print("\n[WARN] 0 restaurants scraped. Keeping existing dataset to avoid data loss.")
        return

    total_r, total_d = save_output(output_locations, is_final=True, existing_dish_hist=existing_dish_hist)

    print(f"\n{'=' * 60}")
    print(f"  DONE")
    print(f"  Restaurants:    {total_r}")
    print(f"  Dishes:         {total_d}")
    print(f"  Total Dishes:   {total_d}")
    print(f"  Total Products: {total_d}")
    print(f"  Scraped {total_d} products")
    print(f"  JSON:           {DATA_FILE} ({os.path.getsize(DATA_FILE) / 1024:.0f} KB)")
    if os.path.exists(PARQUET_FILE):
        print(f"  Parquet:        {PARQUET_FILE} ({os.path.getsize(PARQUET_FILE) / 1024:.0f} KB)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
