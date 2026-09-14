#!/usr/bin/env python
"""station_board — the richer train board for one station, before you get there.
usage: station_board.py "<station name or id>" [LINE ...] [--window N]
For each line through the station (default: every line with a travel order that serves it):
delay status, a horizontal local strip (N stations each side), next-arrival shading per direction
in NYC platform wording, and where the trains are. Writes text + PNG under plots/boards/."""
import sys, json, re, datetime as dt
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch
import metro_live as ml

args = [a for a in sys.argv[1:] if not a.startswith("--")]
window = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("--window=")), 3))
query = args[0]; lines_req = [a.upper() for a in args[1:]]

def resolve(query, line, st):
    q = query.strip().lower()
    if q.upper() in st: return q.upper()
    hits = [i for i, s in st.items() if s["name"].lower() == q] or [i for i, s in st.items() if q in s["name"].lower()]
    if len(hits) == 1: return hits[0]
    raise SystemExit(f"'{query}' → {len(hits)} matches on the {line}: {[st[i]['name'] for i in hits]}")

ABBR = {"47-50 Sts-Rockefeller Ctr": "47-50 Sts", "42 St-Bryant Pk": "42 St-Bryant", "34 St-Herald Sq": "34 St-Herald",
        "Lexington Av/63 St": "Lex Av/63 St", "Lexington Av/53 St": "Lex Av/53 St", "Broadway-Lafayette St": "Bway-Lafayette",
        "Delancey St-Essex St": "Delancey", "East Broadway": "East Bway", "Jay St-MetroTech": "Jay St", "W 4 St-Wash Sq": "W 4 St",
        "Coney Island-Stillwell Av": "Coney Island", "W 8 St-NY Aquarium": "W 8 St", "Jamaica-179 St": "Jamaica-179",
        "Kew Gardens-Union Tpke": "Kew Gardens", "Jackson Hts-Roosevelt Av": "Jackson Hts", "Forest Hills-71 Av": "Forest Hills",
        "63 Dr-Rego Park": "63 Dr", "Grand Av-Newtown": "Grand Av", "15 St-Prospect Park": "15 St", "Fort Hamilton Pkwy": "Ft Hamilton",
        "21 St-Queensbridge": "21 St", "Roosevelt Island": "Roosevelt I", "Court Sq-23 St": "Court Sq"}
def short(name, n=12):
    name = ABBR.get(name, name)
    if len(name) > n: name = name.split("-")[0] if len(name.split("-")[0]) >= 4 else name
    return name if len(name) <= n else name[:n - 1] + "…"

ml.init()
lines = lines_req or [L for L in ml.TRAVEL_ORDER if any(query.lower() in (s["name"].lower(), s["id"].lower()) or query.upper() == s["id"] for s in ml.stations(L).values())]
if not lines: raise SystemExit(f"no line with a travel order serves '{query}' yet (have: {list(ml.TRAVEL_ORDER)})")
out_dir = ml.ROOT / "plots/boards"; out_dir.mkdir(exist_ok=True)
for line in lines:
    st = ml.stations(line); sid = resolve(query, line, st)
    flat = [x for x in ml.TRAVEL_ORDER[line] if isinstance(x, str)] + [i for x in ml.TRAVEL_ORDER[line] if not isinstance(x, str) for i in x[1]]
    # poll a window ±(N+2) around the station on every branch, so trains just outside the picture are seen
    order0, _, _ = ml.resolve_order(line, {}, sid)
    k0 = order0.index(sid) if sid in order0 else next(i for i, s in enumerate(order0) if s == sid)
    cand = set(order0[max(0, k0 - window - 2): k0 + window + 3]) | {i for x in ml.TRAVEL_ORDER[line] if not isinstance(x, str) for i in x[1]}
    preds, now = ml.poll(sorted(cand))
    order, branch, inactive = ml.resolve_order(line, preds, sid)
    k = order.index(sid); lo, hi = max(0, k - window), min(len(order), k + window + 1); win = order[lo:hi]
    fwd_lbl, back_lbl = ml.bound_label(order, k, True, st), ml.bound_label(order, k, False, st)
    fwd_short = "train terminating here" if fwd_lbl.startswith("terminal") else fwd_lbl.split(" →")[0] + " train"
    back_short = "train terminating here" if back_lbl.startswith("terminal") else back_lbl.split(" →")[0] + " train"
    if fwd_lbl.startswith("terminal"): fwd_lbl = "arrivals — this is the last stop"
    if back_lbl.startswith("terminal"): back_lbl = "arrivals — this is the last stop"
    head, live, planned = ml.delay_status(line)
    tf, tb = ml.train_positions(order, preds, line, True, now), ml.train_positions(order, preds, line, False, now)
    # ---------- text, horizontal ----------
    W = 13; name = st[sid]["name"]
    def cell(s, fwd):
        g, m = ml.glyph(ml.arrivals(preds, s, line, fwd), now)
        txt = f"{g} {'—' if m is None else f'{m:.0f}m'}"
        return f"[{txt}]" if s == sid else f" {txt} "
    def center(s): return s.center(W)
    top = "".join(center(cell(s, True)) for s in win)
    bot = "".join(center(cell(s, False)) for s in win)
    names = "".join(center((short(st[s]["name"]).upper() if s == sid else short(st[s]["name"]))) for s in win)
    # line row with train markers: ▶ moves right (fwd), ◀ moves left
    seg = ["━" * W for _ in win]; dots = list(seg)
    for i, s in enumerate(win): dots[i] = ("━" * (W // 2 - 1)) + ("◆" if s == sid else "●") + ("━" * (W - W // 2))
    row = list("".join(dots))
    def mark(train, fwd):
        s = train["next"]
        if s not in win and not (train["at"] and s in win): return
        i = win.index(s); c = i * W + W // 2 - 1
        if train["at"]: pos = c + (1 if fwd else -1) * 1
        else: pos = c - W // 2 if fwd else c + W // 2
        if 0 <= pos < len(row) and row[pos] == "━": row[pos] = "▶" if fwd else "◀"
    for t in tf: mark(t, True)
    for t in tb: mark(t, False)
    def nearest_beyond(trains, edge, before):
        cands = [t for t in trains if t["next"] not in win and (order.index(t["next"]) < lo if before else order.index(t["next"]) > hi - 1) and edge in t["chain"]]
        if not cands: return None
        t = min(cands, key=lambda t: t["chain"][edge]); return round((t["chain"][edge] - now).total_seconds() / 60)
    nb_f, nb_b = nearest_beyond(tf, win[0], True), nearest_beyond(tb, win[-1], False)
    lines_txt = [f"{line}  {ml.LONG_NAME.get(line, '')}   ·  {name}  ·  {now.strftime('%H:%M')}Z", head]
    for i in live: lines_txt.append(f"  • [{i['type']}] {i['description'].splitlines()[0]}")
    lines_txt += [f"Planned work on the {line}: {planned} advisories." + (f"   Manhattan approach in service: {branch}." if branch else ""), "",
                  f"  ◀ {back_lbl}" + " " * max(2, len(win) * W - len(f"  ◀ {back_lbl}") - len(f"{fwd_lbl} ▶")) + f"{fwd_lbl} ▶",
                  f"  next {fwd_short} at each station:", top, "".join(row), names, bot,
                  f"  next {back_short} at each station:", "",
                  f"  ● ≤1 min  ◉ 2–4  ◎ 5–9  ○ 10+  · none   ▶ {fwd_short}   ◀ {back_short}"]
    if nb_f is not None: lines_txt.append(f"  next {fwd_short} beyond the picture reaches {short(st[win[0]]['name'])} in {nb_f} min")
    if nb_b is not None: lines_txt.append(f"  next {back_short} beyond the picture reaches {short(st[win[-1]]['name'])} in {nb_b} min")
    lines_txt.append("  " + " · ".join(f"{short(st[s]['name'])} = {st[s]['name']}" for s in win if short(st[s]["name"]) != st[s]["name"]))
    text = "\n".join(lines_txt)
    stem = out_dir / f"{line}_{re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')}"
    open(f"{stem}.txt", "w").write(text); print(text); print()
    # ---------- PNG, horizontal ----------
    n = len(win); color = ml.LINE_COLORS[line]; L = -3.6
    fig, ax = plt.subplots(figsize=(1.6 * n + 4.9, 5.0)); ax.set_xlim(L - 0.1, n - 0.1); ax.set_ylim(-2.9, 3.0); ax.set_aspect("equal"); ax.axis("off")
    ax.plot([-0.6, n - 0.4], [0, 0], color=color, lw=7, solid_capstyle="round", zorder=1)
    def alpha(m): return 0.0 if m is None else max(0.12, 1 - min(m, 15) / 15)
    for i, s in enumerate(win):
        for fwd, y in ((True, 0.9), (False, -0.9)):
            arr = ml.arrivals(preds, s, line, fwd); g, m = ml.glyph(arr, now)
            if arr:
                ax.add_patch(Circle((i, y), 0.26, facecolor=color, alpha=alpha(m), edgecolor=color, lw=1.3, zorder=3))
                ax.text(i, y + (0.47 if fwd else -0.5), f"{m:.0f} min", ha="center", va="center", fontsize=8, color="#333")
            else: ax.add_patch(Circle((i, y), 0.26, facecolor="white", edgecolor="#bbbbbb", lw=1.1, zorder=3))
        ax.add_patch(Circle((i, 0), 0.17 if s == sid else 0.13, facecolor="white", edgecolor="#222", lw=2 if s == sid else 1.2, zorder=4))
        ax.text(i, -1.75 - (0.3 if i % 2 else 0), short(st[s]["name"]), ha="center", va="top", fontsize=9 if s == sid else 8,
                fontweight="bold" if s == sid else "normal", color=color if s == sid else "#111")
    for t in tf:
        if t["next"] in win: i = win.index(t["next"]); x = i if t["at"] else i - 0.5; ax.annotate("", xy=(x + 0.2, 0.4), xytext=(x - 0.2, 0.4), arrowprops=dict(arrowstyle="-|>", lw=2.6, color=color), zorder=6)
    for t in tb:
        if t["next"] in win: i = win.index(t["next"]); x = i if t["at"] else i + 0.5; ax.annotate("", xy=(x - 0.2, -0.4), xytext=(x + 0.2, -0.4), arrowprops=dict(arrowstyle="-|>", lw=2.6, color=color), zorder=6)
    ax.text(L, 0.9, "next " + fwd_short + "\n" + fwd_lbl + " ▶", ha="left", va="center", fontsize=8.5, color="#333")
    ax.text(L, -0.9, "next " + back_short + "\n◀ " + back_lbl, ha="left", va="center", fontsize=8.5, color="#333")
    ax.text(L, 2.85, f"{line}  {name}", fontsize=14, fontweight="bold", color=color, va="top")
    ax.text(n - 0.2, 2.85, now.strftime("%H:%M") + "Z", fontsize=9, color="#666", va="top", ha="right")
    ax.text(L, 2.3, head + ((" — " + live[0]["description"].splitlines()[0][:80]) if live else "") + f"   ·   planned work: {planned} advisories", fontsize=8.5, color="#b00000" if "YES" in head else "#226622", va="top")
    foot = []
    if nb_f is not None: foot.append(f"next {fwd_short} beyond the picture reaches {short(st[win[0]]['name'])} in {nb_f} min")
    if nb_b is not None: foot.append(f"next {back_short} beyond the picture reaches {short(st[win[-1]]['name'])} in {nb_b} min")
    ax.text(L, -2.4, "   ·   ".join(foot), fontsize=7.5, color="#444", va="top")
    ax.text(L, -2.75, "circle shade = how soon the next train arrives (dark = now, faint = 15+ min, hollow = none)   ·   arrows = trains", fontsize=7, color="#777", va="top")
    fig.savefig(f"{stem}.png", dpi=140, bbox_inches="tight", facecolor="white"); plt.close(fig)
    json.dump({"line": line, "station": sid, "polled_at": now.isoformat(), "window": win, "branch": branch, "trains_fwd": tf, "trains_back": tb, "live": live, "planned": planned}, open(f"{stem}.json", "w"), indent=1, default=str)
    print(f"→ {stem}.png / .txt / .json\n")
