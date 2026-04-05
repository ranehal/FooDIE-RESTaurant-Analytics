import json

har = json.load(open(r'C:\PROJECTS\FooDIEscraper\FooDIE_restaurants\cdn.foodibd.com_2026_07_24_05_53_49 restaurants and dishes.har', encoding='utf-8'))
for e in har['log']['entries']:
    url = e['request']['url']
    if 'GetBranchDetail' in url:
        print("URL:", url[:150])
        print("Method:", e['request']['method'])
        for h in e['request']['headers']:
            name = h['name']
            if name in ('host', 'origin', 'user-agent', 'authorization', 'sxsrf'):
                print(f"  {name}: {h['value'][:100]}")
        break
