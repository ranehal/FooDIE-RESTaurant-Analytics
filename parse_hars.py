import json
import base64
import os
import re
from urllib.parse import urlparse, parse_qs
from collections import OrderedDict

HAR_DIR = os.path.dirname(os.path.abspath(__file__))
HAR_FILES = [
    os.path.join(HAR_DIR, "cdn.foodibd.com_2026_07_24_05_53_49 restaurants and dishes.har"),
    os.path.join(HAR_DIR, "imrs.foodibd.com_2026_07_24_06_00_31 another delivery location.har"),
]
OUTPUT_FILE = os.path.join(HAR_DIR, "data.json")


def decode_response(entry):
    ct = entry["response"]["content"]
    text = ct.get("text", "")
    if not text:
        return None
    if ct.get("encoding") == "base64":
        text = base64.b64decode(text).decode("utf-8")
    return json.loads(text)


def get_entries_by_url_pattern(har, pattern, exclude=None):
    results = []
    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        base = url.split("?")[0]
        if pattern in base and (exclude is None or exclude not in base):
            results.append(entry)
    return results


def extract_location_from_url(url):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return float(qs["latitude"][0]), float(qs["longitude"][0])


def get_restaurant_summary(branch):
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
        "isFavourite": branch.get("isFavourite", False),
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
        "branchImages": branch.get("branchImages", []),
    }


def parse_branch_detail(data):
    detail = {
        "id": data["id"],
        "name": data.get("name", ""),
        "email": data.get("email", ""),
        "image": data.get("image", ""),
        "coverImage": data.get("coverImage", ""),
        "primaryCuisine": data.get("primaryCuisine", ""),
        "location": data.get("location"),
        "address": data.get("address", ""),
        "description": data.get("description", ""),
        "priceRange": data.get("priceRange", ""),
        "minOrderValue": data.get("minOrderValue"),
        "deliveryCharge": data.get("deliveryCharge"),
        "preparationTime": data.get("preparationTime"),
        "deliveryTime": data.get("deliveryTime"),
        "totalDeliveryTime": data.get("avarageDeliveryTime"),
        "rating": data.get("rating"),
        "averageReviewCount": data.get("averageReviewCount") or data.get("rating"),
        "totalReviewCount": data.get("totalReviewCount") or data.get("ratingCount"),
        "ratingCount": data.get("averageReviewCount") or data.get("totalReviewCount"),
        "isPopular": data.get("isPopular", False),
        "isTakePreOrder": data.get("isTakePreOrder", False),
        "openAt": data.get("openAt"),
        "isTemporary": data.get("isTemporary", False),
        "cuisineList": data.get("cuisineList", []),
        "shopType": data.get("shopTypeName"),
        "slug": data.get("slug", ""),
        "deliveryRadius": data.get("deliveryRadius"),
        "pickupTime": data.get("pickupTime"),
        "isDelivery": data.get("isDelivery"),
        "isPickup": data.get("isPickup"),
        "isDine": data.get("isDine"),
        "serviceChargePercentage": data.get("serviceChargePercentage"),
        "packagingAmount": data.get("packagingAmount"),
        "isVatInclusive": data.get("isVatInclusive"),
        "vat": data.get("vat"),
        "workingHours": data.get("workingHours"),
        "promoBannerList": data.get("promoBannerList", []),
    }

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

    add_on_categories = {}
    aoc_data = data.get("addOnCategory", {})
    if isinstance(aoc_data, dict):
        for acid, aoc in aoc_data.items():
            add_on_categories[str(acid)] = aoc

    add_ons = {}
    ao_data = data.get("addOns", {})
    if isinstance(ao_data, dict):
        for aoid, ao in ao_data.items():
            add_ons[str(aoid)] = ao

    return {
        **detail,
        "categories": categories,
        "menus": menus,
        "variations": variations,
        "addOnCategory": add_on_categories,
        "addOns": add_ons,
    }


def merge_restaurant(listing, detail):
    merged = {**listing}
    for key, val in detail.items():
        if key in ("id",):
            continue
        if val is not None and val != "" and val != [] and val != {}:
            if key == "menus" and isinstance(val, dict) and len(val) > 0:
                merged[key] = val
            elif key == "variations" and isinstance(val, dict) and len(val) > 0:
                merged[key] = val
            elif key == "categories" and isinstance(val, list) and len(val) > 0:
                merged[key] = val
            elif key == "addOnCategory" and isinstance(val, dict) and len(val) > 0:
                merged[key] = val
            elif key == "addOns" and isinstance(val, dict) and len(val) > 0:
                merged[key] = val
            elif key == "promoBannerList" and isinstance(val, list) and len(val) > 0:
                merged[key] = val
            elif key == "workingHours" and isinstance(val, dict) and len(val) > 0:
                merged[key] = val
            else:
                merged[key] = val
    return merged


def main():
    restaurants_by_location = {}
    all_details = {}
    all_cuisines = []
    all_popular_brands = []
    total_dishes = 0

    for har_path in HAR_FILES:
        print(f"\n--- Parsing: {os.path.basename(har_path)} ---")
        with open(har_path, "r", encoding="utf-8") as f:
            har = json.load(f)

        all_branch_entries = get_entries_by_url_pattern(har, "all-branch", exclude="campaign")
        detail_entries = get_entries_by_url_pattern(har, "GetBranchDetail")
        cuisines_entries = get_entries_by_url_pattern(har, "cuisines")
        popular_brands_entries = get_entries_by_url_pattern(har, "popular-brands")

        print(f"  all-branch pages: {len(all_branch_entries)}")
        print(f"  GetBranchDetail calls: {len(detail_entries)}")

        for entry in all_branch_entries:
            body = decode_response(entry)
            if not body:
                continue
            data = body.get("data", {})
            branches = data.get("branches", [])
            lat, lng = extract_location_from_url(entry["request"]["url"])

            loc_key = f"{lat},{lng}"
            if loc_key not in restaurants_by_location:
                restaurants_by_location[loc_key] = {"lat": lat, "lng": lng, "name": "", "restaurants": {}}

            for branch in branches:
                rid = str(branch["id"])
                summary = get_restaurant_summary(branch)
                if rid not in restaurants_by_location[loc_key]["restaurants"]:
                    restaurants_by_location[loc_key]["restaurants"][rid] = summary

        for entry in detail_entries:
            body = decode_response(entry)
            if not body or body.get("data") is None:
                continue
            data = body["data"]
            rid = str(data["id"])
            detail = parse_branch_detail(data)
            all_details[rid] = detail
            menu_count = len(detail.get("menus", {}))
            total_dishes += menu_count
            print(f"  Detail: id={rid} name={data.get('name','')} menus={menu_count}")

        for entry in cuisines_entries:
            body = decode_response(entry)
            if not body:
                continue
            cuisines = body.get("data", {}).get("cuisines", [])
            if cuisines:
                all_cuisines = cuisines
                print(f"  Cuisines: {len(cuisines)}")

        for entry in popular_brands_entries:
            body = decode_response(entry)
            if not body:
                continue
            pb = body.get("data", {}).get("popularBrands", [])
            if pb:
                all_popular_brands = pb
                print(f"  Popular brands: {len(pb)}")

    locations = []
    total_restaurants = 0
    for loc_key, loc_data in restaurants_by_location.items():
        restaurant_list = []
        for rid, restaurant in loc_data["restaurants"].items():
            if rid in all_details:
                merged = merge_restaurant(restaurant, all_details[rid])
            else:
                merged = restaurant
            restaurant_list.append(merged)
            total_restaurants += 1

        restaurant_list.sort(key=lambda r: r.get("distance") or 9999)
        locations.append({
            "name": loc_data["name"],
            "lat": loc_data["lat"],
            "lng": loc_data["lng"],
            "restaurants": restaurant_list,
        })

    locations.sort(key=lambda l: l["lat"])

    LOC_NAMES = {0: "Khilgaon", 1: "Banasree"}
    for i, loc in enumerate(locations):
        loc["name"] = LOC_NAMES.get(i, f"Location {i}")

    output = {
        "locations": locations,
        "cuisines": all_cuisines,
        "popularBrands": all_popular_brands,
        "totalRestaurants": total_restaurants,
        "totalDishes": total_dishes,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    for loc in locations:
        print(f"  Location: lat={loc['lat']}, lng={loc['lng']}")
        print(f"    Restaurants: {len(loc['restaurants'])}")
        with_menu = sum(1 for r in loc['restaurants'] if 'menus' in r and r['menus'])
        print(f"    With menus:  {with_menu}")
    print(f"\n  Total restaurants: {total_restaurants}")
    print(f"  Total dishes:      {total_dishes}")
    print(f"  Cuisines:          {len(all_cuisines)}")
    print(f"  Popular brands:    {len(all_popular_brands)}")
    print(f"\n  Output: {OUTPUT_FILE}")
    print(f"  File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
