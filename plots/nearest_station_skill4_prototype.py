#!/usr/bin/env python3
"""nearest_station.py LAT LON [N]  — the N nearest NYC subway stations to a point (straight line), from the
metro MCP's get_all_stations output (Test 1 JSON), grouped so one station complex served by several trunks
(same name within 250 m) shows once with all its lines."""
import sys, json, math
lat, lon = float(sys.argv[1]), float(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 4
d = json.load(open("/home/vivekkarmarkar/Python Files/metro-mcp/metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json"))
st = d.get("stations", d)
def dist_mi(a, b, c, e):
    R = 3958.8; p1, p2 = math.radians(a), math.radians(c); dp = p2 - p1; dl = math.radians(e - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))
rows = sorted(((dist_mi(lat, lon, s["coordinates"]["lat"], s["coordinates"]["lon"]), s) for s in st), key=lambda r: r[0])
out = []
for dm, s in rows:
    g = next((o for o in out if o["name"] == s["name"] and dist_mi(o["lat"], o["lon"], s["coordinates"]["lat"], s["coordinates"]["lon"]) < 0.16), None)
    if g: g["lines"] |= set(s["lines"]); g["ids"].append(s["id"]); continue
    out.append({"name": s["name"], "ids": [s["id"]], "lines": set(s["lines"]), "mi": dm, "lat": s["coordinates"]["lat"], "lon": s["coordinates"]["lon"]})
    if len(out) == n: break
for o in out:
    lines = " ".join(sorted((l for l in o["lines"] if not l.endswith("X")), key=lambda r: (len(r), r)))
    print(f"{o['mi']:.2f} mi  ~{o['mi'] * 20:.0f} min walk  {o['name']} ({lines})  [{', '.join(o['ids'])}]")
