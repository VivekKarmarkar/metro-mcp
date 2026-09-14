"""metro_live — shared pieces for the NYC line/station pictures.
Polling by station id over HTTP against the metro MCP server (same tools as in-session),
per-line travel order, train threading by absolute arrival time, delay status, borough lookup."""
import json, datetime as dt, urllib.request, concurrent.futures as cf
from pathlib import Path as _P
from matplotlib.path import Path

ROOT = _P(__file__).resolve().parent.parent
URL = "https://metro-mcp.anuragd.me/mcp"
HDR = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
       "MCP-Protocol-Version": "2025-03-26", "User-Agent": "curl/8.5.0"}
LINE_COLORS = {"1":"#D82233","2":"#D82233","3":"#D82233","4":"#009952","5":"#009952","6":"#009952","7":"#9A38A1",
               "A":"#0062CF","C":"#0062CF","E":"#0062CF","B":"#EB6800","D":"#EB6800","F":"#EB6800","M":"#EB6800",
               "G":"#799534","J":"#8E5C33","Z":"#8E5C33","L":"#7C858C","N":"#F6BC26","Q":"#F6BC26","R":"#F6BC26","W":"#F6BC26",
               "S":"#7C858C","SIR":"#08179C"}
LONG_NAME = {"F": "Queens Blvd Express/6 Av Local"}

# Travel order per line, first terminal -> last terminal. Alternatives are (tag, [ids]) inserted at that point;
# the live one is chosen from the poll. Only the F so far (Test 5 station set).
TRAVEL_ORDER = {
 "F": ["F01","F02","F03","F04","F05","F06","F07",
       "G08","G09","G10","G11","G12","G13","G14","G15","G16","G18","G19","G20","G21",
       ("53 St", ["F09","F11","F12"]), ("63 St", ["B04","B06","B08","B10"]),
       "D15","D16","D17","D18","D19","D20","D21","F14","F15","F16","F18","A41",
       "F20","F21","F22","F23","F24","F25","F26","F27","F29","F30","F31","F32","F33","F34","F35","F36","F38","F39","D42","D43"],
}
STATION_FILES = {"F": ROOT / "metro_mcp_nyc_subway_tools_test5_get_stations_by_line_nyc_F.json"}

def rpc(method, params, id_=1, timeout=30):
    body = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params}).encode()
    raw = urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=HDR, method="POST"), timeout=timeout).read().decode()
    data = [l[5:] for l in raw.splitlines() if l.startswith("data:")]
    return json.loads(data[-1]) if data else json.loads(raw)

def tool(name, args):
    r = rpc("tools/call", {"name": name, "arguments": args})["result"]
    txt = r["content"][0]["text"]
    if r.get("isError"): raise RuntimeError(txt)
    return json.loads(txt)

def init(): rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "metro_live", "version": "0"}})

def stations(line):
    return {s["id"]: s for s in json.load(open(STATION_FILES[line]))["stations"]}

_boro = None
def borough_of(lat, lon):
    global _boro
    if _boro is None:
        g = json.load(open(ROOT / "plots/geo/nyc_boroughs_arcgis.geojson"))
        _boro = []
        for f in g["features"]:
            geom = f["geometry"]; polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            for poly in polys: _boro.append((f["properties"]["BoroName"], Path(poly[0])))
    for name, path in _boro:
        if path.contains_point((lon, lat)): return name
    return None

def poll(ids, workers=8):
    """One pass of get_station_predictions by id. Returns ({id: response|{'error'}}, polled_at)."""
    def one(sid):
        try: return sid, tool("get_station_predictions", {"city": "nyc", "stationName": sid})
        except Exception as e: return sid, {"error": str(e)}
    with cf.ThreadPoolExecutor(workers) as ex: out = dict(ex.map(one, ids))
    return out, dt.datetime.now(dt.timezone.utc)

def arrivals(preds, sid, line, fwd):
    """Sorted [(arrival_dt, minutesAway, status)] for `line` at `sid`, direction fwd=True means SOUTH in the feed."""
    want = "SOUTH" if fwd else "NORTH"
    rows = [p for p in preds.get(sid, {}).get("predictions", []) if p["line"] in (line, line + "X") and p["direction"] == want]
    return sorted((dt.datetime.fromisoformat(p["arrivalTime"].replace("Z", "+00:00")), p["minutesAway"], p["arrivalStatus"]) for p in rows)

def resolve_order(line, preds, must_include=None):
    """Flatten TRAVEL_ORDER[line]; where alternatives exist keep the branch with arrivals in `preds` (or the first)."""
    out, alts = [], []
    for x in TRAVEL_ORDER[line]:
        if isinstance(x, str): out.append(x)
        else: alts.append(x)
    if alts:
        served = {tag: sum(len(arrivals(preds, i, line, True)) + len(arrivals(preds, i, line, False)) for i in ids) for tag, ids in alts}
        best = next((a for a in alts if must_include in a[1]), None) or max(alts, key=lambda a: served[a[0]])
        k = out.index("D15") if line == "F" else len(out)
        out = out[:k] + best[1] + out[k:]
        inactive = [i for tag, ids in alts if tag != best[0] for i in ids]
        return out, best[0], inactive
    return out, None, []

def thread_trains(order, preds, line, fwd, now, window_min=10):
    """Chains of (station, arrival) per train, threaded along travel order by absolute arrival time."""
    seq = order if fwd else order[::-1]
    avail = {s: [a for a in arrivals(preds, s, line, fwd) if a[0] >= now - dt.timedelta(minutes=1)] for s in seq}
    used = {s: set() for s in seq}; out = []
    for i, s0 in enumerate(seq):
        for a0 in avail[s0]:
            if a0[0] in used[s0]: continue
            chain = [(s0, a0)]; used[s0].add(a0[0]); prev = a0[0]
            for s in seq[i + 1:]:
                nxt = [a for a in avail[s] if a[0] not in used[s] and prev < a[0] <= prev + dt.timedelta(minutes=window_min)]
                if not nxt:
                    if avail[s]: break
                    continue
                chain.append((s, nxt[0])); used[s].add(nxt[0][0]); prev = nxt[0][0]
            if len(chain) >= 2 or s0 == seq[0]: out.append(chain)
    return sorted(out, key=lambda c: c[0][1][0])

def train_positions(order, preds, line, fwd, now):
    """[{'next': station the train reaches next, 'at': bool, 'eta_min': int}] — 'at' when ARRIVING or <=45 s away."""
    out = []; origin = (order if fwd else order[::-1])[0]
    for c in thread_trains(order, preds, line, fwd, now):
        s0, (t0, m0, status) = c[0]
        eta = max(0, round((t0 - now).total_seconds() / 60))
        out.append({"next": s0, "at": s0 == origin or status == "ARRIVING" or (t0 - now).total_seconds() <= 45,
                    "eta_min": eta, "chain": {st_: a[0] for st_, a in c}})
    return out

def delay_status(line):
    """check-delay rules applied to get_incidents(nyc). Returns (headline, live_alerts, planned_count)."""
    code = {"SIR": "SI"}.get(line, line)
    inc = tool("get_incidents", {"city": "nyc"})["incidents"]
    live = [i for i in inc if i["id"].startswith("lmm:alert:") and code in i["linesAffected"]]
    planned = [i for i in inc if i["id"].startswith("lmm:planned_work:") and code in i["linesAffected"]]
    delays = [i for i in live if i["type"] == "Delays"]
    if delays: head = f"DELAY RIGHT NOW: YES ({len(delays)} live alert{'s' if len(delays) > 1 else ''})"
    elif live: head = "no delay alert, but a live disruption: " + ", ".join(i["type"] for i in live)
    else: head = f"DELAY RIGHT NOW: NO — no live alerts for the {line}"
    return head, live, len(planned)

def bound_label(order, k, fwd, st):
    """NYC platform wording for a direction at order[k]: '<Borough>-bound → <terminus>' or '<terminus>-bound'."""
    ahead = order[k + 1:] if fwd else order[k - 1::-1] if k > 0 else []
    here = borough_of(st[order[k]]["coordinates"]["lat"], st[order[k]]["coordinates"]["lon"])
    terminus = st[ahead[-1]]["name"] if ahead else st[order[k]]["name"]
    if not ahead: return f"terminal — {terminus}"
    nb = next((b for b in (borough_of(st[s]["coordinates"]["lat"], st[s]["coordinates"]["lon"]) for s in ahead) if b and b != here), None)
    short = terminus.split("-")[0] if terminus.startswith("Coney Island") else terminus
    return f"{nb}-bound → {short}" if nb else f"{short}-bound"

def glyph(arr, now):
    """(symbol, minutes) for the next arrival: ● ≤1  ◉ 2–4  ◎ 5–9  ○ 10+  · none."""
    if not arr: return "·", None
    t, m, status = arr[0]; mins = 0 if status == "ARRIVING" else max(0, (t - now).total_seconds() / 60)
    return ("●" if mins <= 1 else "◉" if mins <= 4 else "◎" if mins <= 9 else "○"), mins

ABBR = {"47-50 Sts-Rockefeller Ctr": "47-50 Sts", "42 St-Bryant Pk": "42 St-Bryant", "34 St-Herald Sq": "34 St-Herald",
        "Lexington Av/63 St": "Lex Av/63 St", "Lexington Av/53 St": "Lex Av/53 St", "Broadway-Lafayette St": "Bway-Lafayette",
        "Delancey St-Essex St": "Delancey", "East Broadway": "East Bway", "Jay St-MetroTech": "Jay St", "W 4 St-Wash Sq": "W 4 St",
        "Coney Island-Stillwell Av": "Coney Island", "W 8 St-NY Aquarium": "W 8 St", "Jamaica-179 St": "Jamaica-179",
        "Kew Gardens-Union Tpke": "Kew Gardens", "Jackson Hts-Roosevelt Av": "Jackson Hts", "Forest Hills-71 Av": "Forest Hills",
        "63 Dr-Rego Park": "63 Dr", "Grand Av-Newtown": "Grand Av", "15 St-Prospect Park": "15 St", "Fort Hamilton Pkwy": "Ft Hamilton",
        "21 St-Queensbridge": "21 St", "Roosevelt Island": "Roosevelt I", "Court Sq-23 St": "Court Sq"}
def short(name, n=14):
    name = ABBR.get(name, name)
    return name if len(name) <= n else name[:n - 1] + "…"
