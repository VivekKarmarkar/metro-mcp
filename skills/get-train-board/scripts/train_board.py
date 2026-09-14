#!/usr/bin/env python3
"""train_board.py "<station name or id>" [LINE] --delay="<answer from /check-delay>" [--window=N] [--lines]

The bundled code for /get-train-board (Vivek's algorithm):
  1. search_stations           name -> station ids + the lines through them
  2. get_stations_by_line      the line's stations — this is always the station SET
  3. sort into travel order    branched lines (A, F, 5): a hand-written chain (training knowledge) that only ORDERS
                               the fetched stations; at a branch point the branch through the asked-for station is
                               shown, else the branch that has trains (one prediction call per branch decides), and
                               the other branch is named in a footer.  Any other line: spanning tree over the fetched
                               coordinates -> longest path through the station, oriented so the feed's SOUTH direction
                               (station-id numbers increasing) runs down the board.
  4. get_station_predictions   by id, one call at a time, at the stations in the window (asked-for station +/- N, +2 margin)
  5. render                    two-line direction headers (<Borough>-bound / -> terminus), minutes per direction,
                               trains marked; the delay line is --delay, which the skill obtains by invoking /check-delay
                               (this code never reads incidents and refuses to render without --delay)
--lines: print the lines through the station and stop (for the no-line case).  Exit 2 with a message on ambiguity,
unknown station, missing --delay, or a tool error.

Talks JSON-RPC over HTTP straight to the metro MCP server (URL read from ~/.claude.json mcpServers.metro, with the
known URL as fallback), not through the session's MCP client — so nothing here can stall the session.  The User-Agent
header is set because the server answers 403 to python-urllib's default.  Boroughs for the "-bound" wording come from
data/nyc_boroughs.json (simplified NYC borough outlines; point-in-polygon on the coordinates the tool returns)."""
import sys, json, math, re, datetime as dt, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
def server_url():
    try: return json.load(open(Path.home() / ".claude.json"))["mcpServers"]["metro"]["url"]
    except Exception: return "https://metro-mcp.anuragd.me/mcp"
URL = server_url()
HDR = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26", "User-Agent": "curl/8.5.0"}
BORO = json.load(open(HERE.parent / "data/nyc_boroughs.json"))["boroughs"]

# Hand-written travel orders for the lines that branch, written north/west terminus first (the feed's SOUTH direction).
# A list inside the chain is a branch point: [(label, chain), (label, chain)].  Ids are those the tool returns.
ORDERS = {
    "F": ["F01", "F02", "F03", "F04", "F05", "F06", "F07", "G08", "G09", "G10", "G11", "G12", "G13", "G14", "G15", "G16", "G18", "G19", "G20",
          [("53 St", ["G21", "F09", "F11", "F12"]), ("63 St", ["B04", "B06", "B08", "B10"])],
          "D15", "D16", "D17", "D18", "D19", "D20", "D21", "F14", "F15", "F16", "F18", "A41",
          "F20", "F21", "F22", "F23", "F24", "F25", "F26", "F27", "F29", "F30", "F31", "F32", "F33", "F34", "F35", "F36", "F38", "F39", "D42", "D43"],
    "A": ["A02", "A03", "A05", "A06", "A07", "A09", "A10", "A11", "A12", "A14", "A15", "A16", "A17", "A18", "A19", "A20", "A21", "A22", "A24",
          "A25", "A27", "A28", "A30", "A31", "A32", "A33", "A34", "A36", "A38", "A40", "A41", "A42", "A43", "A44", "A45", "A46", "A47", "A48",
          "A49", "A50", "A51", "A52", "A53", "A54", "A55", "A57", "A59", "A60", "A61",
          [("Lefferts Blvd", ["A63", "A64", "A65"]),
           ("Rockaways", ["H01", "H02", "H03", "H04", [("Far Rockaway", ["H06", "H07", "H08", "H09", "H10", "H11"]),
                                                       ("Rockaway Park", ["H12", "H13", "H14", "H15"])]])]],
    "5": [[("Dyre Av", ["501", "502", "503", "504", "505"]), ("Nereid Av", ["204", "205", "206", "207", "208", "209", "210", "211", "212"])],
          "213", "214", "215", "216", "217", "218", "219", "220", "221", "222", "416", "621", "626", "629", "631", "635", "640",
          "418", "419", "420", "423", "234", "235", "239",
          [("Flatbush Av", ["241", "242", "243", "244", "245", "246", "247"]),
           ("New Lots Av", ["248", "249", "250", "251", "252", "253", "254", "255", "256", "257"])]],
}
LINE_CODE = {"SIR": "SI", "STATEN ISLAND": "SI"}

def short(n, w=15):
    """Fit a station name into w chars: the longest cut at a '-', '/' or space that still fits; else truncate."""
    if len(n) <= w: return n
    cands = [n[:m.start()].rstrip() for m in re.finditer(r"[-/ ]", n)]
    cands = [c for c in cands if 4 <= len(c) <= w and not re.fullmatch(r"[\d\s-]+", c) and len(c.split()[-1]) > 1]
    return max(cands, key=len) if cands else n[:w - 1] + "…"
def pip(x, y, poly):
    inside = False
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[i - 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: inside = not inside
    return inside
def borough(s):
    lat, lon = s["coordinates"]["lat"], s["coordinates"]["lon"]
    return next((b for b, polys in BORO.items() if any(pip(lon, lat, p) for p in polys)), None)

# ---------- tool calls (one at a time) ----------
def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    raw = urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=HDR, method="POST"), timeout=30).read().decode()
    data = [l[5:] for l in raw.splitlines() if l.startswith("data:")]
    return json.loads(data[-1]) if data else json.loads(raw)
def tool(name, args):
    r = rpc("tools/call", {"name": name, "arguments": args})["result"]
    if r.get("isError"): raise SystemExit(f"tool error from {name}: {r['content'][0]['text']}")
    return json.loads(r["content"][0]["text"])

args = [a for a in sys.argv[1:] if not a.startswith("--")]; opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
flags = {a[2:] for a in sys.argv[1:] if a.startswith("--") and "=" not in a}
if not args: print(__doc__); sys.exit(2)
query = args[0]; line = args[1].upper() if len(args) > 1 else None; line = LINE_CODE.get(line, line)
window = int(opts.get("window", 3)); delay = opts.get("delay")
rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "get-train-board", "version": "3"}})

# ---------- 1. station -> ids + lines (search_stations) ----------
def search(q):
    q = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", q, flags=re.I).strip()
    d = tool("search_stations", {"city": "nyc", "query": q}); res = d.get("results") or d.get("stations") or []
    return {"exact": [s for s in res if s["name"].lower() == q.lower()], "all": res}
if re.fullmatch(r"[A-Z]?[0-9]{2,3}|[A-Z][0-9]{2}", query.upper()): found = {"exact": [{"id": query.upper(), "name": query.upper(), "lines": []}], "all": []}
else: found = search(query)
hits = found["exact"] or found["all"]
if not hits: print(f"no station matches '{query}'"); sys.exit(2)
if "lines" in flags or line is None:
    lines = sorted({l for h in hits for l in h["lines"] if not l.endswith("X")}, key=lambda r: (len(r), r))
    print("LINES:", " ".join(lines) if lines else "none")
    if line is None: sys.exit(0)
serves = lambda h: not h["lines"] or line in h["lines"] or line + "X" in h["lines"]
cand = [h for h in hits if serves(h)] or [h for h in found["all"] if serves(h)]
hits = hits if cand and cand[0] in hits else found["all"]
if not cand:
    print(f"the {line} does not stop at {hits[0]['name']}. Lines there: " + " ".join(sorted({l for h in hits for l in h['lines'] if not l.endswith('X')}))); sys.exit(2)
if len(cand) > 1 and len({h["id"] for h in cand}) > 1: print(f"'{query}' matches several stations on the {line}: " + ", ".join(f"{h['id']} {h['name']}" for h in cand)); sys.exit(2)
sid = cand[0]["id"]
if not delay: print(f"no --delay given: invoke /check-delay {line} first and pass its answer as --delay=\"...\""); sys.exit(2)

# ---------- 2. the line's stations (the station set) ----------
st = {s["id"]: s for s in tool("get_stations_by_line", {"city": "nyc", "lineCode": line})["stations"]}
if sid not in st: print(f"{sid} is not on the {line}"); sys.exit(2)
name_of = lambda i: st[i]["name"] if i in st else i

# ---------- 4 (early). predictions by id, one call at a time, cached ----------
preds = {}
def fetch(i):
    if i not in preds:
        try: preds[i] = tool("get_station_predictions", {"city": "nyc", "stationName": i})
        except SystemExit as e: preds[i] = {"error": str(e)}
    return preds[i]
def arrivals(s, fwd):
    want = "SOUTH" if fwd else "NORTH"
    rows = [p for p in preds.get(s, {}).get("predictions", []) if p["line"] in (line, line + "X") and p["direction"] == want]
    return sorted((dt.datetime.fromisoformat(p["arrivalTime"].replace("Z", "+00:00")), p["arrivalStatus"]) for p in rows)

# ---------- 3. travel order ----------
def flat(seq): return [x for x in seq if isinstance(x, str)] + [i for x in seq if not isinstance(x, str) for _, sub in x for i in flat(sub)]
def resolve(seq, picks, groups, base=0, edge=None):
    """Flatten a chain, choosing one alternative per branch point: the one holding the asked-for station, else picks[key], else the first."""
    out = []
    for x in seq:
        if isinstance(x, str): out.append(x); continue
        key = tuple(lab for lab, _ in x); forced = next((i for i, (lab, sub) in enumerate(x) if sid in flat(sub)), None)
        idx = forced if forced is not None else picks.get(key, 0)
        groups.append({"key": key, "pos": base + len(out), "edge": out[-1] if out else edge, "alts": x, "idx": idx, "forced": forced is not None})
        out += resolve(x[idx][1], picks, groups, base + len(out), out[-1] if out else edge)
    return out
notes = []
def order_through():
    seq = ORDERS.get(line)
    if seq and sid in flat(seq):
        groups = []; order = resolve(seq, {}, groups); k = order.index(sid); picks = {}
        for g in groups:
            span = max(len(flat(sub)) for _, sub in g["alts"])
            near = g["pos"] - (window + 2) <= k <= g["pos"] + span + window + 2
            if g["forced"] or not near: continue
            counts = []
            for lab, sub in g["alts"]:
                first = next((i for i in flat(sub) if i in st), None)
                if first: fetch(first)
                counts.append(len(arrivals(first, True)) + len(arrivals(first, False)) if first else -1)
            best = max(range(len(counts)), key=lambda i: counts[i])
            if counts[best] > 0: picks[g["key"]] = best
        groups = []; order = resolve(seq, picks, groups)
        known = set(flat(seq)); stray = [i for i in st if i not in known]
        order = [i for i in order if i in st] + stray; k = order.index(sid)
        def ends(sub):   # the far end(s) of a chain: its last id, or every end of a nested branch point
            last = sub[-1]
            return [i for _, s in last for i in ends(s)] if isinstance(last, list) else [last]
        win = set(order[max(0, k - window): k + window + 1])
        for g in groups:
            if g["forced"]: continue
            shown = [i for i in flat(g["alts"][g["idx"]][1]) if i in st]
            if g["edge"] in win or any(i in win for i in shown):
                for i, (lab, sub) in enumerate(g["alts"]):
                    if i != g["idx"]:
                        ids = [j for j in flat(sub) if j in st]; far = [short(name_of(e)) for e in ends(sub) if e in st]
                        if ids: notes.append(f"branch not shown: {lab} — {short(name_of(ids[0]))} … {' / '.join(far)}" if g["pos"] > 0 else f"branch not shown: {lab} — {short(name_of(ids[-1]))} … {short(name_of(ids[0]))}")
        if stray: notes.append("not placed in the travel order: " + ", ".join(st[i]["name"] for i in stray))
        return order
    if seq: notes.append(f"{name_of(sid)} is not in the hand-written {line} order — ordered by geometry instead")
    c = math.cos(math.radians(40.71)); ids = list(st)
    xy = {i: (st[i]["coordinates"]["lon"] * c * 111.2, st[i]["coordinates"]["lat"] * 111.2) for i in ids}
    d = lambda a, b: math.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1])
    intree = {ids[0]}; adj = {i: [] for i in ids}
    while len(intree) < len(ids):
        a, b = min(((a, b) for a in intree for b in ids if b not in intree), key=lambda e: d(*e)); intree.add(b)
        if d(a, b) <= 7: adj[a].append(b); adj[b].append(a)   # > 7 km = not the same track (the three shuttles under one code)
    def farthest(start, block=None):
        best = [start]; stack = [[start]]
        while stack:
            path = stack.pop(); best = path if len(path) > len(best) else best
            stack += [path + [m] for m in adj[path[-1]] if m not in path and m != block]
        return best
    arms = sorted((farthest(n, block=sid) for n in adj[sid]), key=len, reverse=True)
    order = (arms[0][::-1] if arms else []) + [sid] + (arms[1] if len(arms) > 1 else [])
    num = lambda i: int(m.group()) if (m := re.search(r"\d+", i)) else 0
    inc = sum(num(b) > num(a) for a, b in zip(order, order[1:])); dec = sum(num(b) < num(a) for a, b in zip(order, order[1:]))
    return order[::-1] if dec > inc else order
order = order_through(); k = order.index(sid); win = order[max(0, k - window): k + window + 1]
name = {i: st[i]["name"] for i in order}

# ---------- 4. predictions at the window + margin ----------
poll_ids = order[max(0, k - window - 2): k + window + 3]
for i in poll_ids: fetch(i)
now = dt.datetime.now(dt.timezone.utc)
def trains(fwd):
    seq = order if fwd else order[::-1]
    avail = {s: [a for a in arrivals(s, fwd) if a[0] >= now - dt.timedelta(minutes=1)] for s in seq}; used = {s: set() for s in seq}; out = []
    for i, s0 in enumerate(seq):
        for a0 in avail[s0]:
            if a0[0] in used[s0]: continue
            chain = [(s0, a0)]; used[s0].add(a0[0]); prev = a0[0]
            for s in seq[i + 1:]:
                nxt = [a for a in avail[s] if a[0] not in used[s] and prev < a[0] <= prev + dt.timedelta(minutes=10)]
                if not nxt:
                    if avail[s]: break
                    continue
                chain.append((s, nxt[0])); used[s].add(nxt[0][0]); prev = nxt[0][0]
            if len(chain) >= 2 or s0 == seq[0]:
                t0, status = a0; out.append({"next": s0, "at": status == "ARRIVING" or (t0 - now).total_seconds() <= 45})
    return out

# ---------- 5. render ----------
def head(fwd):
    ahead = order[k + 1:] if fwd else (order[k - 1::-1] if k > 0 else [])
    if not ahead: return "", "last stop"
    here = borough(st[sid]); nb = next((b for b in (borough(st[s]) for s in ahead) if b and b != here), None)
    return (f"{nb}-bound" if nb else ""), ("→ " if fwd else "← ") + short(name[ahead[-1]])
def mins(s, fwd):
    a = [x for x in arrivals(s, fwd) if x[0] >= now - dt.timedelta(minutes=1)]   # a record older than a minute is a train that has left
    if not a: return "—"
    m = max(0, (a[0][0] - now).total_seconds() / 60); return "now" if m <= 0.75 or a[0][1] == "ARRIVING" and m <= 1.5 else f"{m:.0f}"
tf, tb = trains(True), trains(False); at = lambda s, tr: any(t["at"] and t["next"] == s for t in tr)
skipped = [s for s in win if s != sid and not arrivals(s, True) and not arrivals(s, False)]
headline = f"{line} · {name[sid]} · {now.strftime('%H:%M')}Z"
if not any(arrivals(s, d) for s in win for d in (True, False)):
    print(headline); print(f"no {line} trains serving this stretch right now"); print(delay); sys.exit(0)
(h1f, h2f), (h1b, h2b) = head(True), head(False)
wl = max(len(h1f), len(h2f), 8) + 1; wr = max(len(h1b), len(h2b), 8) + 1
out = [headline, delay, ""]
if h1f or h1b: out.append(f"{'':17}{h1f:>{wl}}{h1b:>{wr}}")
out.append(f"{'':17}{h2f:>{wl}}{h2b:>{wr}}")
for s in win:
    if s in skipped: continue
    out.append(f"{'▸' if s == sid else ' '}{short(name[s]):<16}{mins(s, True) + (' ●' if at(s, tf) else ''):>{wl}}{mins(s, False) + (' ●' if at(s, tb) else ''):>{wr}}")
out += ["", "minutes to the next train · ● = a train is there now"]
if skipped: out.append("not stopping here right now: " + ", ".join(name[s] for s in skipped))
out += notes
errs = [i for i in poll_ids if "error" in preds.get(i, {})]
if errs: out.append("no prediction data for: " + ", ".join(name.get(i, i) for i in errs))
print("\n".join(out))
