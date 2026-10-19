# scratch/import_geojson.py
import json
import os
import urllib.request
import urllib.parse
import ssl

MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

def fetch_osm_streets_bbox():
    bbox = "(-29.65,-51.15,-29.53,-51.02)"
    query = f"""[out:json][timeout:25];
way["highway"]["name"]{bbox};
out tags;
"""
    ctx = ssl._create_unverified_context()
    for mirror in MIRRORS:
        url = mirror + "?data=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"User-Agent": "PointLanches/1.0"})
        print(f"Tentando servidor {mirror}...")
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                elements = data.get("elements", [])
                names = set()
                for el in elements:
                    name = el.get("tags", {}).get("name", "").strip()
                    if name:
                        names.add(name)
                if names:
                    print(f"Sucesso com {mirror}: {len(names)} vias encontradas!")
                    return sorted(list(names))
        except Exception as e:
            print(f"Erro no servidor {mirror}: {e}")
    return []

if __name__ == "__main__":
    local_path = r"C:\Users\Herval\Downloads\export.geojson"
    streets = []
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                geo = json.load(f)
            for feat in geo.get("features", []):
                props = feat.get("properties", {})
                name = props.get("name", "").strip()
                if name:
                    streets.append(name)
        except Exception as e:
            print("Erro ao ler export.geojson local:", e)

    print(f"Ruas do arquivo local export.geojson: {len(streets)}")
    if not streets:
        print("Consultando espelhos Overpass API...")
        streets = fetch_osm_streets_bbox()

    if streets:
        print(f"Total: {len(streets)} vias obtidas!")
        print("Primeiras 25 vias:")
        for s in streets[:25]:
            print(" -", s)
        out_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": s, "highway": "residential"},
                    "geometry": None
                }
                for s in streets
            ]
        }
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(out_geojson, f, ensure_ascii=False, indent=2)
        print(f"Salvo em {local_path} com {len(streets)} ruas!")
