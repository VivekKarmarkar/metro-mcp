#!/usr/bin/env python
"""board_compact — phone-width station board: one row per station, minutes per direction, trains marked."""
import sys, re
import metro_live as ml
q = sys.argv[1]; line = (sys.argv[2] if len(sys.argv) > 2 else "F").upper(); window = 3
st = ml.stations(line)
def resolve(q):
    if q.upper() in st: return q.upper()
    h = [i for i, s in st.items() if s["name"].lower() == q.lower()] or [i for i, s in st.items() if q.lower() in s["name"].lower()]
    if len(h) != 1: raise SystemExit(f"{q}: {len(h)} matches")
    return h[0]
ml.init(); sid = resolve(q)
order0, _, _ = ml.resolve_order(line, {}, sid); k0 = order0.index(sid)
cand = set(order0[max(0, k0 - window - 2): k0 + window + 3]) | {i for x in ml.TRAVEL_ORDER[line] if not isinstance(x, str) for i in x[1]}
preds, now = ml.poll(sorted(cand)); order, branch, _ = ml.resolve_order(line, preds, sid)
k = order.index(sid); win = order[max(0, k - window): k + window + 1]
head, live, planned = ml.delay_status(line)
tf, tb = ml.train_positions(order, preds, line, True, now), ml.train_positions(order, preds, line, False, now)
f_lbl, b_lbl = ml.bound_label(order, k, True, st), ml.bound_label(order, k, False, st)
def short_dir(l): return "last stop" if l.startswith("terminal") else l.split(" →")[0].replace("-bound", "")
def mins(s, fwd):
    a = ml.arrivals(preds, s, line, fwd)
    if not a: return "—"
    g, m = ml.glyph(a, now); return "now" if m <= 0.75 else f"{m:.0f}"
def at(s, trains): return any(t["at"] and t["next"] == s for t in trains)
def between(s, trains): return any((not t["at"]) and t["next"] == s for t in trains)
name = st[sid]["name"]
out = [f"{line} · {name} · {now.strftime('%H:%M')}Z", ("no delay" if "NO" in head else head.lower()) + f" · {planned} planned advisories", ""]
out.append(f"{'':16}{'→ ' + short_dir(f_lbl):>12}{'← ' + short_dir(b_lbl):>13}")
for s in win:
    if between(s, tf): out.append(f"{'':16}{'  ● ↓':>12}")
    mark = "▸" if s == sid else " "
    nm = ml.short(st[s]["name"])
    out.append(f"{mark}{nm:<15}{mins(s, True) + (' ●' if at(s, tf) else ''):>12}{mins(s, False) + (' ●' if at(s, tb) else ''):>13}")
    if between(s, tb):
        pass
out += ["", "minutes to the next train · ● = a train is there now"]
for i in live: out.append(f"! {i['description'].splitlines()[0]}")
print("\n".join(out))
