#!/usr/bin/env python
"""
F-line strip map prototype: stations in travel order, next-F closeness per direction, train positions,
delay status. Data from the metro MCP server over HTTP (same tools: get_station_predictions, get_incidents).
"""
import json, sys, re, datetime as dt, urllib.request, concurrent.futures as cf
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Circle

URL = "https://metro-mcp.anuragd.me/mcp"
F_ORANGE = "#EB6800"
HDR = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26", "User-Agent": "curl/8.5.0"}

def rpc(method, params, id_=1, timeout=30):
    body = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params}).encode()
    req = urllib.request.Request(URL, data=body, headers=HDR, method="POST")
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode()
    data = [l[5:] for l in raw.splitlines() if l.startswith("data:")]
    return json.loads(data[-1]) if data else json.loads(raw)

def tool(name, args):
    r = rpc("tools/call", {"name": name, "arguments": args})["result"]
    txt = r["content"][0]["text"]
    if r.get("isError"): raise RuntimeError(txt)
    return json.loads(txt)

# ---- 1. stations in travel order (Test 5 ids) ----
ORDER = [  # Jamaica -> Coney Island; ("branch", [...]) marks the two Manhattan approaches
 "F01","F02","F03","F04","F05","F06","F07",
 "G08","G09","G10","G11","G12","G13","G14","G15","G16","G18","G19","G20","G21",
 ("branch53", ["F09","F11","F12"]), ("branch63", ["B04","B06","B08","B10"]),
 "D15","D16","D17","D18","D19","D20","D21",
 "F14","F15","F16","F18","A41",
 "F20","F21","F22","F23","F24","F25","F26","F27",
 "F29","F30","F31","F32","F33","F34","F35","F36","F38","F39",
 "D42","D43"]
st = {s["id"]: s for s in json.load(open("metro_mcp_nyc_subway_tools_test5_get_stations_by_line_nyc_F.json"))["stations"]}
flat = [x for x in ORDER if isinstance(x, str)] + [i for x in ORDER if not isinstance(x, str) for i in x[1]]
assert set(flat) == set(st), (set(flat) ^ set(st))

# ---- 2. one pass of predictions, all stations ----
rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "f-strip", "version": "0"}})
t_start = dt.datetime.now(dt.timezone.utc)
def poll(sid):
    try: return sid, tool("get_station_predictions", {"city": "nyc", "stationName": sid})
    except Exception as e: return sid, {"error": str(e)}
with cf.ThreadPoolExecutor(8) as ex: preds = dict(ex.map(poll, flat))
NOW = dt.datetime.now(dt.timezone.utc)
errors = {k: v["error"] for k, v in preds.items() if "error" in v}

def f_arrivals(sid, dirn):
    rows = [p for p in preds.get(sid, {}).get("predictions", []) if p["line"] in ("F", "FX") and p["direction"] == ("SOUTH" if dirn == "S" else "NORTH")]
    out = []
    for p in rows:
        t = dt.datetime.fromisoformat(p["arrivalTime"].replace("Z", "+00:00"))
        out.append((t, p["minutesAway"], p["arrivalStatus"]))
    return sorted(out)

# active branch = the one with any F arrivals in this pass
def served(ids): return sum(len(f_arrivals(i, "S")) + len(f_arrivals(i, "N")) for i in ids)
b53, b63 = dict(ORDER[20:22])["branch53"], dict(ORDER[20:22])["branch63"]
active, inactive = (b63, b53) if served(b63) >= served(b53) else (b53, b63)
order = [x for x in ORDER if isinstance(x, str)]
order = order[:order.index("D15")] + active + order[order.index("D15"):]

# ---- 3. thread trains along the order using absolute arrival times ----
def chains(dirn, window_min=10):
    seq = order if dirn == "S" else order[::-1]
    avail = {s: [a for a in f_arrivals(s, dirn) if a[0] >= NOW - dt.timedelta(minutes=1)] for s in seq}
    used = {s: set() for s in seq}; out = []
    for i, s0 in enumerate(seq):
        for a0 in avail[s0]:
            if a0[0] in used[s0]: continue
            chain = [(s0, a0)]; used[s0].add(a0[0]); prev = a0[0]
            for s in seq[i + 1:]:
                nxt = [a for a in avail[s] if a[0] not in used[s] and prev < a[0] <= prev + dt.timedelta(minutes=window_min)]
                if not nxt:
                    if avail[s]: break      # station served but no matching arrival -> chain ends
                    continue                # station not served in this direction now (express skip / terminal) -> pass through
                chain.append((s, nxt[0])); used[s].add(nxt[0][0]); prev = nxt[0][0]
            if len(chain) >= 2: out.append(chain)
    return sorted(out, key=lambda c: c[0][1][0])

def positions(dirn):
    seq = order if dirn == "S" else order[::-1]; out = []
    for c in chains(dirn):
        s0, (t0, m0, status) = c[0]; k = seq.index(s0)
        at = status == "ARRIVING" or (t0 - NOW).total_seconds() <= 45
        prev = next((seq[j] for j in range(k - 1, -1, -1) if f_arrivals(seq[j], dirn) or j == 0), None)
        out.append({"at": s0 if at else None, "before": s0, "after_prev": prev, "eta_min": max(0, round((t0 - NOW).total_seconds() / 60)), "stops": len(c)})
    return out

# ---- 4. delay status (check-delay rules) ----
inc = tool("get_incidents", {"city": "nyc"})["incidents"]
live = [i for i in inc if i["id"].startswith("lmm:alert:") and "F" in i["linesAffected"]]
planned = [i for i in inc if i["id"].startswith("lmm:planned_work:") and "F" in i["linesAffected"]]
delays = [i for i in live if i["type"] == "Delays"]
if delays: delay_line = f"DELAY RIGHT NOW: YES  ({len(delays)} live alert{'s' if len(delays) > 1 else ''})"
elif live: delay_line = f"no delay alert, but live disruption: {', '.join(i['type'] for i in live)}"
else: delay_line = "DELAY RIGHT NOW: NO  (no live alerts for the F)"

# ---- 5a. text strip ----
def glyph(arr):
    if not arr: return ("·", None)
    t, m, status = arr[0]; mins = 0 if status == "ARRIVING" else max(0, (t - NOW).total_seconds() / 60)
    return (("●" if mins <= 1 else "◉" if mins <= 4 else "◎" if mins <= 9 else "○"), mins)
posS, posN = positions("S"), positions("N")
lines = []
lines.append(f"F  Queens Blvd Express/6 Av Local        polled {NOW.strftime('%H:%M')}Z  ({len(flat)} stations, {len(errors)} errors)")
lines.append(delay_line)
for i in live: lines.append(f"  • [{i['type']}] {i['description'].splitlines()[0]}")
lines.append(f"Planned work on the F: {len(planned)} advisories.   Manhattan approach in service now: {'63 St' if active is b63 else '53 St'} (the {'53 St' if active is b63 else '63 St'} stations get no F right now)")
lines.append("")
lines.append("  SOUTHBOUND → Coney Island         station                       NORTHBOUND → Jamaica")
lines.append("  next F                                                          next F")
def fmt(g): return f"{g[0]} {'—' if g[1] is None else f'{g[1]:4.0f}m'}"
for k, sid in enumerate(order):
    gS, gN = glyph(f_arrivals(sid, "S")), glyph(f_arrivals(sid, "N"))
    # trains between previous station and this one
    tS = [p for p in posS if p["before"] == sid and not p["at"]]
    tN = [p for p in posN if p["after_prev"] == sid and not p["at"]]  # northbound: passes this station next after "before"
    if k > 0 and (tS or tN):
        lines.append(f"  {'▼ train' if tS else '       ':>10}         ┃              {'▲ train' if tN else ''}")
    atS = any(p["at"] == sid for p in posS); atN = any(p["at"] == sid for p in posN)
    name = st[sid]["name"][:28]
    lines.append(f"  {fmt(gS):>10} {'▼' if atS else ' '}   ┃ {name:<28} {'▲' if atN else ' '}  {fmt(gN)}")
lines.append("")
lines.append("  ● ≤1 min   ◉ 2–4   ◎ 5–9   ○ 10+   · no F arrivals in this direction (express skip, terminal, or not served now)")
if inactive: lines.append("  not served now: " + ", ".join(st[i]["name"] for i in inactive))
text = "\n".join(lines)
open("plots/f_strip_map.txt", "w").write(text); print(text)

# ---- 5b. PNG ----
n = len(order); fig_h = 0.42 * n + 2.2
fig, ax = plt.subplots(figsize=(9, fig_h)); ax.set_xlim(-3.2, 3.2); ax.set_ylim(-1, n + 1.8); ax.axis("off")
ax.plot([0, 0], [0, n - 1], color=F_ORANGE, lw=6, solid_capstyle="round", zorder=1)
def alpha(mins): return 0.0 if mins is None else max(0.12, 1 - min(mins, 15) / 15)
for k, sid in enumerate(order):
    y = n - 1 - k
    for dirn, x in (("S", -0.55), ("N", 0.55)):
        arr = f_arrivals(sid, dirn); g = glyph(arr)
        if arr: ax.add_patch(Circle((x, y), 0.19, facecolor=F_ORANGE, alpha=alpha(g[1]), edgecolor=F_ORANGE, lw=1.2, zorder=3)); ax.text(x + (-0.3 if dirn == "S" else 0.3), y, f"{g[1]:.0f}m", ha="right" if dirn == "S" else "left", va="center", fontsize=7, color="#444")
        else: ax.add_patch(Circle((x, y), 0.19, facecolor="white", edgecolor="#bbbbbb", lw=1.0, zorder=3))
    ax.add_patch(Circle((0, y), 0.13, facecolor="white", edgecolor="#333", lw=1.2, zorder=4))
    ax.text(1.05, y, st[sid]["name"], ha="left", va="center", fontsize=8, color="#222")
for p in posS:
    k = order.index(p["before"]); y = n - 1 - k + (0 if p["at"] else 0.5)
    ax.annotate("", xy=(-1.05, y - 0.22), xytext=(-1.05, y + 0.22), arrowprops=dict(arrowstyle="-|>", lw=2.2, color=F_ORANGE), zorder=5)
for p in posN:
    k = order.index(p["before"]); y = n - 1 - k - (0 if p["at"] else 0.5)
    ax.annotate("", xy=(2.6 + 0.0, y + 0.22), xytext=(2.6, y - 0.22), arrowprops=dict(arrowstyle="-|>", lw=2.2, color=F_ORANGE), zorder=5)
ax.text(-1.05, n + 0.2, "S-bound\nnext F", ha="center", va="bottom", fontsize=8, color="#444")
ax.text(0.55, n + 0.2, "N-bound\nnext F", ha="center", va="bottom", fontsize=8, color="#444")
ax.text(-3.1, n + 1.5, f"F   Queens Blvd Express/6 Av Local     {NOW.strftime('%Y-%m-%d %H:%M')}Z", fontsize=12, fontweight="bold", color=F_ORANGE, va="bottom")
ax.text(-3.1, n + 1.05, delay_line + (("  —  " + live[0]["description"].splitlines()[0][:70]) if live else ""), fontsize=8.5, color="#b00000" if delays else "#226622", va="bottom")
ax.text(-3.1, -0.9, "circle shade = how soon the next F arrives (dark = now, faint = 15+ min, hollow = no F this direction); arrows = trains", fontsize=7, color="#666")
fig.savefig("plots/f_strip_map.png", dpi=130, bbox_inches="tight", facecolor="white")
json.dump({"polled_at": NOW.isoformat(), "active_branch": "63St" if active is b63 else "53St", "errors": errors,
           "predictions_F": {sid: {"S": [[a[0].isoformat(), a[1], a[2]] for a in f_arrivals(sid, "S")], "N": [[a[0].isoformat(), a[1], a[2]] for a in f_arrivals(sid, "N")]} for sid in order},
           "trains_S": posS, "trains_N": posN, "live_alerts": live, "planned_count": len(planned)},
          open("plots/f_strip_map_data.json", "w"), indent=1)
print(f"\nsaved plots/f_strip_map.png, plots/f_strip_map.txt, plots/f_strip_map_data.json; poll took {(NOW - t_start).total_seconds():.0f}s; errors={errors}")
