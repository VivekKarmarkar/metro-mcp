#!/usr/bin/env python
"""
Test 2 - reconstruct the NYC subway map from get_all_stations(city=nyc) output (Test 1).

FORMAL SPEC
Variables
  stations  DYNAMIC   496 records {id, name, lines[], coordinates{lat,lon}} from the Test 1 JSON
  routes    COMPUTED  line codes present, minus express variants (6X, 7X, FX): they stop at a
                      subset of the parent route's stations and share its color
  COLORS    CONSTANT  official MTA hex per route (MTA brand colors; jsvine/mta-colors)
  lat0      CONSTANT  40.71 deg, reference latitude for the projection
  x, y      COMPUTED  x = lon * cos(lat0), y = lat   (equirectangular, locally shape-preserving)
Constraints
  C1 HARD  every station drawn exactly once as a marker at (x, y)
  C2 HARD  every station name labelled at least once; same name within ~300 m labelled once
  C3 HARD  each route's stations joined by its minimum spanning tree (|S_r| - 1 edges), minus any
           edge longer than MAX_EDGE_KM (only the S code, which lumps 3 disconnected shuttles, has such edges)
  C4 HARD  equal aspect in projected coordinates (no squish)
  C5 HARD  PNG width + height <= 10000 px (Telegram photo limit)
  C6 SOFT  label overlap minimized (rotation, small font); full legibility only in the PDF at zoom
Objective  a recognizable map; maximize label legibility subject to C5
Mapping    lon in [-74.252, -73.755], lat in [40.513, 40.903]  ->  figure axes, equal aspect
Invariant  colors follow the MTA trunk-color convention; markers are neutral (white/black) so a
           station served by several routes is not painted with any one of them
Algorithm  per route: minimum spanning tree over projected Euclidean distance -> draw edges in the
           route color; then markers; then de-duplicated labels; legend per color group; save PNG + PDF
Postcondition  plots/nyc_subway_map_test2.{png,pdf} exist; edges drawn == sum(|S_r| - 1) - len(dropped)
"""
import json, math, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import minimum_spanning_tree

SRC = "metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json"
OUT_DIR = "plots"
STEM = f"{OUT_DIR}/nyc_subway_map_test2"

COLORS = {  # MTA Brand Colors / Subway, SIR & ADA (mta.info/document/168976)
    "1": "#D82233", "2": "#D82233", "3": "#D82233",              # Red
    "4": "#009952", "5": "#009952", "6": "#009952",              # Dark Green
    "7": "#9A38A1",                                              # Purple
    "A": "#0062CF", "C": "#0062CF", "E": "#0062CF",              # Blue
    "B": "#EB6800", "D": "#EB6800", "F": "#EB6800", "M": "#EB6800",  # Orange
    "G": "#799534",                                              # Light Green
    "J": "#8E5C33", "Z": "#8E5C33",                              # Brown
    "L": "#7C858C",                                              # Grey
    "N": "#F6BC26", "Q": "#F6BC26", "R": "#F6BC26", "W": "#F6BC26",  # Yellow
    "S": "#7C858C",                                              # Grey (shuttles)
    "SIR": "#08179C",                                            # MTA Blue (the SIR bullet; "Teal" #008EB7 is the T bullet)
}
SKIP = {"6X", "7X", "FX"}

data = json.load(open(SRC))
st = data["stations"]
assert len(st) == data["totalStations"] == 496, len(st)

lat0 = math.radians(40.71)
KM_PER_DEG = 111.2
MAX_EDGE_KM = 7.0   # longest real gap is A: Howard Beach -> Broad Channel, 5.9 km; S inter-shuttle chords are 8.3 and 13.7 km
for s in st:
    s["x"] = s["coordinates"]["lon"] * math.cos(lat0) * KM_PER_DEG
    s["y"] = s["coordinates"]["lat"] * KM_PER_DEG

routes = sorted({l for s in st for l in s["lines"]} - SKIP, key=lambda r: (len(r), r))
missing = [r for r in routes if r not in COLORS]
assert not missing, f"no color for {missing}"

fig, ax = plt.subplots(figsize=(36, 37))

# --- C3: per-route spanning tree segments ---
edge_count, expected, dropped = 0, 0, []
for r in routes:
    S = [s for s in st if r in s["lines"]]
    if len(S) < 2:
        continue
    P = np.array([[s["x"], s["y"]] for s in S])
    D = squareform(pdist(P))
    D[(D == 0) & ~np.eye(len(S), dtype=bool)] = 1e-9   # coincident stations still get an edge
    T = minimum_spanning_tree(D).tocoo()
    for i, j, w in zip(T.row, T.col, T.data):
        if w > MAX_EDGE_KM:
            dropped.append((r, round(float(w), 1), S[i]["name"], S[j]["name"]))
            continue
        ax.plot([P[i, 0], P[j, 0]], [P[i, 1], P[j, 1]], color=COLORS[r], lw=2.5,
                alpha=0.9, solid_capstyle="round", zorder=1)
        edge_count += 1
    expected += len(S) - 1
    if T.nnz != len(S) - 1:
        print(f"WARNING route {r}: {T.nnz} edges for {len(S)} stations", file=sys.stderr)

# --- C1: markers (neutral) ---
ax.scatter([s["x"] for s in st], [s["y"] for s in st], s=28, facecolor="white",
           edgecolor="black", linewidths=0.8, zorder=3)

# --- C2: labels, de-duplicated per (name, ~300 m cell) ---
seen, n_labels = set(), 0
for s in st:
    key = (s["name"], round(s["coordinates"]["lat"] / 0.003), round(s["coordinates"]["lon"] / 0.003))
    if key in seen:
        continue
    seen.add(key)
    ax.annotate(s["name"], (s["x"], s["y"]), xytext=(3, 3), textcoords="offset points",
                fontsize=5.5, rotation=30, rotation_mode="anchor", ha="left", va="bottom",
                color="#222222", zorder=4)
    n_labels += 1

ax.set_aspect("equal")   # C4
ax.set_axis_off()

groups = {}
for r in routes:
    groups.setdefault(COLORS[r], []).append(r)
handles = [Line2D([0], [0], color=c, lw=6, label="  ".join(rs)) for c, rs in groups.items()]
ax.legend(handles=handles, loc="upper left", fontsize=16, frameon=False,
          title="Lines (MTA brand colors, mta.info/document/168976)", title_fontsize=18)
ax.set_title("NYC Subway - 496 stations from metro MCP get_all_stations(city=nyc)\n"
             "segments = per-line minimum spanning tree over station coordinates; "
             "express variants 6X/7X/FX omitted (same stations, same colors); "
             "S = 3 separate shuttles, so S edges over 7 km are not drawn",
             fontsize=20, loc="left")

fig.savefig(f"{STEM}.png", dpi=100, bbox_inches="tight", facecolor="white")
fig.savefig(f"{STEM}.pdf", bbox_inches="tight", facecolor="white")

from PIL import Image
w, h = Image.open(f"{STEM}.png").size
print("dropped edges (> MAX_EDGE_KM):", dropped)
print(f"routes={len(routes)} edges={edge_count} expected={expected - len(dropped)} labels={n_labels} "
      f"png={w}x{h} (w+h={w+h}) C5_ok={w+h <= 10000}")
