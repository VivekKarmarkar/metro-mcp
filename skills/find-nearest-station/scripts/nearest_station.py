#!/usr/bin/env python3
"""nearest_station.py "<street address | place | lat,lon>" [--n=4]

The bundled code for /find-nearest-station (single skill):
  1. coordinates — "lat,lon" is used as given; any other text is geocoded with Nominatim (OpenStreetMap), limited to
     the New York City area.  A street address geocodes reliably; a business name often does not, so the skill first
     resolves a name to its street address (training knowledge + web search) and passes the address here.
  2. get_all_stations — the metro MCP tool, one call, JSON-RPC over HTTP straight to the server (URL from
     ~/.claude.json, the known URL as fallback; User-Agent set because the server answers 403 to python-urllib's
     default).  The station set is fetched at run time, never bundled.
  3. straight-line distance from the point to every station; a station complex (same name within 250 m, e.g. the
     A C E and B D F M levels of W 4 St) is shown once with all its lines; the N nearest are printed with the
     distance and a walking time at 3 mph.  A note is added when the nearest station is more than a mile away.
Exit 2 when the text cannot be geocoded (the skill then finds a street address and retries) or on a tool error.
Nothing station-specific or place-specific is hard-coded; the examples in ../examples are proof, not scope."""
import sys, json, math, re, time, urllib.request, urllib.parse
from pathlib import Path
NYC_BOX = "-74.30,40.95,-73.65,40.45"   # lon_min,lat_max,lon_max,lat_min — the five boroughs and a margin
def server_url():
    try: return json.load(open(Path.home() / ".claude.json"))["mcpServers"]["metro"]["url"]
    except Exception: return "https://metro-mcp.anuragd.me/mcp"
URL = server_url()
HDR = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26", "User-Agent": "curl/8.5.0"}

args = [a for a in sys.argv[1:] if not a.startswith("--")]; opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
if not args: print(__doc__); sys.exit(2)
query = " ".join(args).strip(); n = int(opts.get("n", 4))

# ---------- 1. coordinates ----------
def geocode(q):
    """The text as given first (the viewbox already limits hits to the NYC area, which includes Hoboken and Jersey City);
    if nothing comes back and the text names no New York place, once more with ', New York, NY' appended.  Nominatim's
    policy: one request per second, identifying User-Agent."""
    tries = [q] + ([] if re.search(r"\b(new york|ny|nj|nyc|brooklyn|queens|bronx|manhattan|staten island|hoboken|jersey city)\b", q, re.I) else [q + ", New York, NY"])
    for i, t in enumerate(tries):
        if i: time.sleep(1.1)
        u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": t, "format": "jsonv2", "limit": 1, "viewbox": NYC_BOX, "bounded": 1})
        req = urllib.request.Request(u, headers={"User-Agent": "find-nearest-station/1 (Claude Code skill)"})
        hits = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        if hits: h = hits[0]; return float(h["lat"]), float(h["lon"]), h.get("display_name", t)
    return None
m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", query)
if m: lat, lon, label = float(m.group(1)), float(m.group(2)), f"{m.group(1)}, {m.group(2)}"
else:
    g = geocode(query)
    if not g: print(f"could not geocode '{query}' — give a street address (number, street, borough) or lat,lon"); sys.exit(2)
    lat, lon, label = g

# ---------- 2. the station set (get_all_stations, one call) ----------
def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    raw = urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=HDR, method="POST"), timeout=30).read().decode()
    data = [l[5:] for l in raw.splitlines() if l.startswith("data:")]
    return json.loads(data[-1]) if data else json.loads(raw)
rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "find-nearest-station", "version": "1"}})
r = rpc("tools/call", {"name": "get_all_stations", "arguments": {"city": "nyc"}})["result"]
if r.get("isError"): print(f"tool error from get_all_stations: {r['content'][0]['text']}"); sys.exit(2)
d = json.loads(r["content"][0]["text"]); st = d.get("stations", d)

# ---------- 3. nearest ----------
def dist_mi(a, b, c, e):
    R = 3958.8; p1, p2 = math.radians(a), math.radians(c); dp = p2 - p1; dl = math.radians(e - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))
rows = sorted(((dist_mi(lat, lon, s["coordinates"]["lat"], s["coordinates"]["lon"]), s) for s in st), key=lambda x: x[0])
out = []
for dm, s in rows:
    g = next((o for o in out if o["name"] == s["name"] and dist_mi(o["lat"], o["lon"], s["coordinates"]["lat"], s["coordinates"]["lon"]) < 0.16), None)
    if g: g["lines"] |= set(s["lines"]); g["ids"].append(s["id"]); continue
    out.append({"name": s["name"], "ids": [s["id"]], "lines": set(s["lines"]), "mi": dm, "lat": s["coordinates"]["lat"], "lon": s["coordinates"]["lon"]})
    if len(out) == n: break
short_label = ", ".join(label.split(", ")[:4]) if not m else label
print(f"{short_label}  ({lat:.4f}, {lon:.4f})")
for o in out:
    lines = " ".join(sorted((l for l in o["lines"] if not l.endswith("X")), key=lambda x: (len(x), x)))
    print(f"{o['mi']:.2f} mi  ~{o['mi'] * 20:.0f} min walk  {o['name']} ({lines})  [{', '.join(o['ids'])}]")
if out and out[0]["mi"] > 1.0: print(f"note: the nearest subway station is {out[0]['mi']:.1f} mi away — this spot may be outside the subway's reach (straight-line distances; water in between makes the walk longer)")
