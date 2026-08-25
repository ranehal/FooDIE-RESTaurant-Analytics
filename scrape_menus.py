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
    """Load historical price records across all previous history snapshot JSONs and data.json."""
    import glob
    existing_dish_hist = {}

    # 1. Load from all history snapshot files
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

    # 2. Also load from current DATA_FILE if available
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
            print(f"  [WARN] Failed to load previous dish history: {e}")

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

                # Remove any existing entry for today and append latest
                hist = [h for h in hist if h.get("date") != today_str and str(h.get("date"))[:10] != today_str]
                if curr_price > 0:
                    hist.append({
                        "date": today_str,
                        "timestamp": now_iso,
                        "price": curr_price,
                        "oldPrice": old_price
                    })
                menu["price_history"] = hist

    return new_locations


def _save(locations, existing_dish_hist=None):
    if not locations:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")
    merged = merge_dish_histories(locations, now_iso, today_str, existing_dish_hist)
    total_r = sum(len(loc["restaurants"]) for loc in merged)
    total_d = sum(len(r.get("menus", {})) for loc in merged for r in loc["restaurants"])
    with _save_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"locations": merged, "totalRestaurants": total_r, "totalDishes": total_d, "scrapedAt": now_iso}, f, ensure_ascii=False, indent=2)


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
                    _save(output_locations, existing_dish_hist)

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

    now_iso = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Merge with loaded historical data
    merged_locations = merge_dish_histories(output_locations, now_iso, today_str, existing_dish_hist)

    output = {
        "locations": merged_locations,
        "totalRestaurants": sum(len(l["restaurants"]) for l in merged_locations),
        "totalDishes": sum(len(r.get("menus", {})) for l in merged_locations for r in l["restaurants"]),
        "scrapedAt": now_iso,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Save daily history snapshot
    hist_dir = os.path.join(DATA_DIR, "history")
    os.makedirs(hist_dir, exist_ok=True)
    snapshot_file = os.path.join(hist_dir, f"foodie_restaurants_{today_str}.json")
    with open(snapshot_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)
    print(f"  Saved snapshot: {snapshot_file}")

    print(f"\n{'=' * 60}")
    print(f"  DONE")
    print(f"  Restaurants:    {output['totalRestaurants']}")
    print(f"  Dishes:         {output['totalDishes']}")
    print(f"  Total Dishes:   {output['totalDishes']}")
    print(f"  Total Products: {output['totalDishes']}")
    print(f"  Scraped {output['totalDishes']} products")
    print(f"  File:           {DATA_FILE}")
    print(f"  Size:           {os.path.getsize(DATA_FILE) / 1024:.0f} KB")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
