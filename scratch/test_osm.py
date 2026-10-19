import urllib.request
import urllib.parse
import json
import ssl

query = """[out:json][timeout:25];
area["name"="Dois Irmãos"]["admin_level"="8"]->.a;
way(area.a)["highway"]["name"];
out tags;
"""

urls = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

ctx = ssl._create_unverified_context()

for base in urls:
    try:
        url = base + "?data=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"User-Agent": "PointLanches/1.0"})
        print(f"Trying {base}...")
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elements = data.get("elements", [])
            print(f"Success! Elements: {len(elements)}")
            names = set()
            for el in elements:
                n = el.get("tags", {}).get("name", "").strip()
                if n:
                    names.add(n)
            print(f"Unique street names: {len(names)}")
            with open("scratch/osm_streets.json", "w", encoding="utf-8") as out:
                json.dump(sorted(list(names)), out, ensure_ascii=False, indent=2)
            break
    except Exception as e:
        print(f"Error {base}: {e}")
