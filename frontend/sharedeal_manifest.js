window.sharedeal_manifest = {
  "store": "ShareDeal",
  "api_base": "https://sharedealnow.com/api/v1",
  "headers": {
    "User-Agent": "Dart/3.12 (dart:io)",
    "Accept": "application/json",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/json",
    "Authorization": "Bearer"
  },
  "catalog_pages": "POST /products  {\"page\": \"{n}\"}",
  "category_filter": "POST /products  {\"category_id\": \"{id}\"}",
  "pagination": "Laravel: {current_page, last_page, per_page, total, next_page_url}"
};
