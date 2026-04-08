import httpx
import json
import base64
from datetime import datetime, timezone

def double_b64(val):
    s = base64.b64encode(val.encode("utf-8")).decode("utf-8")
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")

headers_base = {
    "accept": "application/json",
    "accept-charset": "UTF-8",
    "accept-encoding": "gzip",
    "content-type": "application/json",
    "host": "api.foodibd.com",
    "origin": "foodi-prod-android 8.0.3 16 1b5a4567bbcb95d4",
    "user-agent": "ktor-client",
    "x-requested-with": "XMLHttpRequest",
}

LAT = "23.7480914"
LON = "90.4344348"

def bootstrap():
    headers = dict(headers_base)
    r = httpx.get(
        "https://api.foodibd.com/restaurants-go/api/v2/all-branch",
        params={"longitude": LON, "latitude": LAT, "serviceType": "1", "page": "1", "limit": "1", "tags": "-1"},
        headers=headers, timeout=15,
    )
    cf_ray = r.headers.get("cf-ray-status-id-tn", "")
    if not cf_ray:
        raise Exception("No cf-ray from bootstrap")
    headers["sxsrf"] = double_b64(cf_ray)
    return headers

def get_branch_detail(headers, branch_id):
    avail_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    r = httpx.get(
        "https://api.foodibd.com/restaurants/api/Branch/v2/GetBranchDetail",
        params={
            "branchId": str(branch_id),
            "userLat": LAT, "userLong": LON,
            "orderType": "1", "availibilityTime": avail_time,
        },
        headers=headers, timeout=15,
    )
    if r.status_code == 401:
        raise Exception("401 - sxsrf expired")
    cf_ray = r.headers.get("cf-ray-status-id-tn", "")
    if cf_ray:
        headers["sxsrf"] = double_b64(cf_ray)
    return r.status_code, r.json() if r.status_code == 200 else r.text

headers = bootstrap()
status, data = get_branch_detail(headers, 4121)
if status == 200:
    detail = data["data"]
    print("Top-level keys:", list(detail.keys()))
    cats = detail.get("categories", [])
    menus = detail.get("menus", {})
    print(f"Categories ({len(cats)}):")
    for c in cats:
        print(f"  {json.dumps(c, indent=4)[:200]}")
    print(f"\nMenus (type={type(menus).__name__}, len={len(menus)}):")
    for mname, mdata in list(menus.items())[:2]:
        print(f"  Menu '{mname}' (type={type(mdata).__name__}):")
        if isinstance(mdata, dict):
            print(f"    Keys: {list(mdata.keys())}")
            for k, v in list(mdata.items())[:1]:
                print(f"    {k}: {json.dumps(v, indent=4)[:300]}")
        elif isinstance(mdata, list):
            print(f"    {len(mdata)} items")
            if mdata:
                print(f"    Sample: {json.dumps(mdata[0], indent=4)[:300]}")
