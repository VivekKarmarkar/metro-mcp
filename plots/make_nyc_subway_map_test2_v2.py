#!/usr/bin/env python
"""
Test 2 (v2) - NYC subway map from get_all_stations(city=nyc), revised after feedback:
land/water base, borough + New Jersey boundaries, map rotated so Manhattan runs north-south and
sits centred in the frame.

FORMAL SPEC (additions to v1; v1 spec unchanged for stations, labels, MST segments, colors)
Variables
  boroughs   DYNAMIC  5 shoreline-clipped MultiPolygons, NYC Planning (services5.arcgis.com NYC_Borough_Boundary)
  context    DYNAMIC  Census cb_2023 county 1:500k polygons: all NJ counties + Nassau + Westchester
  phi        COMPUTED bearing (from true north, clockwise) of the principal axis of the Manhattan
                      stations (PCA); stations are assigned to Manhattan by point-in-polygon
  cx, cy     COMPUTED centroid of the Manhattan stations (rotation centre and frame centre in x)
Mapping    lon/lat -> km (v1) -> rotate counter-clockwise by phi about (cx, cy). After this the
           Manhattan axis is vertical. Same rotation applied to every station and every polygon.
Constraints
  C7 HARD  water = axes background (light blue); land = polygons (light, non-blue); NYC land
           slightly lighter than out-of-city land so the city boundary reads
  C8 HARD  every borough boundary and every NJ county boundary drawn as a thin outline
  C9 HARD  labels for Manhattan, Brooklyn, Queens, Bronx, Staten Island, New Jersey
  C10 HARD frame centred on cx horizontally: x in [cx - W, cx + W], W = max |x' - cx| + margin
  C11 HARD a true-north arrow is drawn (north is no longer up after rotation)
  C5 (v1) PNG width + height <= 10000 px
Invariant  the rotation is a rigid motion: distances, angles, and the MST are unchanged from v1
Postcondition plots/nyc_subway_map_test2_v2.{png,pdf}; edges drawn == 912 as in v1
"""
import json, math, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MPoly
from matplotlib.path import Path
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import minimum_spanning_tree

SRC = "metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json"
BORO = "plots/geo/nyc_boroughs_arcgis.geojson"
CTX = "plots/geo/census_counties_500k_nj_ny.geojson"
STEM = "plots/nyc_subway_map_test2_v2"

COLORS = {  # MTA Brand Colors / Subway, SIR & ADA (mta.info/document/168976)
    "1": "#D82233", "2": "#D82233", "3": "#D82233",
    "4": "#009952", "5": "#009952", "6": "#009952",
    "7": "#9A38A1",
    "A": "#0062CF", "C": "#0062CF", "E": "#0062CF",
    "B": "#EB6800", "D": "#EB6800", "F": "#EB6800", "M": "#EB6800",
    "G": "#799534",
    "J": "#8E5C33", "Z": "#8E5C33",
    "L": "#7C858C",
    "N": "#F6BC26", "Q": "#F6BC26", "R": "#F6BC26", "W": "#F6BC26",
    "S": "#7C858C",
    "SIR": "#08179C",
}
SKIP = {"6X", "7X", "FX"}
MAX_EDGE_KM = 7.0
WATER, LAND_NYC, LAND_OUT = "#cfe3f2", "#f4f1ea", "#e9e5dc"
EDGE_NYC, EDGE_OUT = "#6f6f6f", "#a0a0a0"

# ---------- projection (v1) ----------
lat0 = math.radians(40.71)
KM = 111.2
def proj(lon, lat):
    return lon * math.cos(lat0) * KM, lat * KM

data = json.load(open(SRC))
st = data["stations"]
assert len(st) == 496
for s in st:
    s["x"], s["y"] = proj(s["coordinates"]["lon"], s["coordinates"]["lat"])

def rings(feature):
    g = feature["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [np.array([proj(x, y) for x, y in poly[0]]) for poly in polys]   # exterior rings

boros = {f["properties"]["BoroName"]: rings(f) for f in json.load(open(BORO))["features"]}
ctx = json.load(open(CTX))["features"]
ctx = [f for f in ctx if not (f["properties"]["STATEFP"] == "36" and f["properties"]["NAME"] in
       {"Bronx", "Kings", "New York", "Queens", "Richmond"})]   # NYC comes from the detailed source
ctx_rings = {f["properties"]["NAME"] + (" NJ" if f["properties"]["STATEFP"] == "34" else " NY"): rings(f) for f in ctx}

# ---------- rotation: Manhattan principal axis -> vertical ----------
P_all = np.array([[s["x"], s["y"]] for s in st])
in_man = np.zeros(len(st), dtype=bool)
for ring in boros["Manhattan"]:
    in_man |= Path(ring).contains_points(P_all)
M = P_all[in_man]
cx, cy = M.mean(axis=0)
_, _, Vt = np.linalg.svd(M - (cx, cy), full_matrices=False)
d = Vt[0] if Vt[0][1] >= 0 else -Vt[0]
phi = math.atan2(d[0], d[1])                       # bearing of the axis, clockwise from north
R = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])   # CCW by phi
def rot(pts):
    return (np.asarray(pts) - (cx, cy)) @ R.T + (cx, cy)
print(f"Manhattan stations: {in_man.sum()}  axis bearing phi = {math.degrees(phi):.1f} deg  (map rotated CCW by that)")

P_all = rot(P_all)
for s, (x, y) in zip(st, P_all):
    s["x"], s["y"] = float(x), float(y)
boros = {k: [rot(r) for r in v] for k, v in boros.items()}
ctx_rings = {k: [rot(r) for r in v] for k, v in ctx_rings.items()}

# ---------- frame (C10) ----------
margin = 1.5
W = np.abs(P_all[:, 0] - cx).max() + margin
x0, x1 = cx - W, cx + W
y0, y1 = P_all[:, 1].min() - margin, P_all[:, 1].max() + margin
w_km, h_km = x1 - x0, y1 - y0
long_in = 36.0
figsize = (long_in, long_in * h_km / w_km) if w_km >= h_km else (long_in * w_km / h_km, long_in)
fig, ax = plt.subplots(figsize=figsize)
fig.patch.set_facecolor("white")
ax.set_facecolor(WATER)                                            # C7 water

# ---------- land + boundaries (C7, C8) ----------
for name, rs in ctx_rings.items():
    for r in rs:
        ax.add_patch(MPoly(r, closed=True, facecolor=LAND_OUT, edgecolor=EDGE_OUT, lw=0.6, zorder=0.2))
for name, rs in boros.items():
    for r in rs:
        ax.add_patch(MPoly(r, closed=True, facecolor=LAND_NYC, edgecolor=EDGE_NYC, lw=0.9, zorder=0.3))

# ---------- region labels (C9) ----------
def centroid(ring):
    x, y = ring[:, 0], ring[:, 1]
    a = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
    if abs(a) < 1e-9:
        return ring.mean(axis=0)
    cxx = np.sum((x[:-1] + x[1:]) * (x[:-1] * y[1:] - x[1:] * y[:-1])) / (6 * a)
    cyy = np.sum((y[:-1] + y[1:]) * (x[:-1] * y[1:] - x[1:] * y[:-1])) / (6 * a)
    return np.array([cxx, cyy])
def biggest(rs):
    return max(rs, key=lambda r: abs(0.5 * np.sum(r[:-1, 0] * r[1:, 1] - r[1:, 0] * r[:-1, 1])))
label_style = dict(fontsize=34, color="#8a8a8a", alpha=0.75, ha="center", va="center",
                   fontweight="bold", zorder=2.5)
for name in ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]:
    c = centroid(biggest(boros[name]))
    ax.text(c[0], c[1], name.upper(), **label_style)
hud = centroid(biggest(ctx_rings["Hudson NJ"]))
ax.text(hud[0] - 4.0, hud[1], "NEW JERSEY", rotation=90, **label_style)

# ---------- network (v1, unchanged) ----------
routes = sorted({l for s in st for l in s["lines"]} - SKIP, key=lambda r: (len(r), r))
edge_count, expected, dropped = 0, 0, []
for r in routes:
    S = [s for s in st if r in s["lines"]]
    if len(S) < 2:
        continue
    P = np.array([[s["x"], s["y"]] for s in S])
    D = squareform(pdist(P))
    D[(D == 0) & ~np.eye(len(S), dtype=bool)] = 1e-9
    T = minimum_spanning_tree(D).tocoo()
    for i, j, w in zip(T.row, T.col, T.data):
        if w > MAX_EDGE_KM:
            dropped.append((r, round(float(w), 1), S[i]["name"], S[j]["name"])); continue
        ax.plot([P[i, 0], P[j, 0]], [P[i, 1], P[j, 1]], color=COLORS[r], lw=2.5, alpha=0.95,
                solid_capstyle="round", zorder=3)
        edge_count += 1
    expected += len(S) - 1
ax.scatter([s["x"] for s in st], [s["y"] for s in st], s=28, facecolor="white",
           edgecolor="black", linewidths=0.8, zorder=4)
seen, n_labels = set(), 0
for s in st:
    key = (s["name"], round(s["coordinates"]["lat"] / 0.003), round(s["coordinates"]["lon"] / 0.003))
    if key in seen:
        continue
    seen.add(key)
    ax.annotate(s["name"], (s["x"], s["y"]), xytext=(3, 3), textcoords="offset points",
                fontsize=5.5, rotation=30, rotation_mode="anchor", ha="left", va="bottom",
                color="#222222", zorder=5)
    n_labels += 1

# ---------- frame, legend, north arrow (C10, C11) ----------
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
ax.set_aspect("equal")
ax.set_xticks([]); ax.set_yticks([])
for sp in ax.spines.values():
    sp.set_edgecolor("#888888")
groups = {}
for r in routes:
    groups.setdefault(COLORS[r], []).append(r)
handles = [Line2D([0], [0], color=c, lw=6, label="  ".join(rs)) for c, rs in groups.items()]
leg = ax.legend(handles=handles, loc="upper left", fontsize=16, frameon=True, framealpha=0.9,
                facecolor="white", edgecolor="#bbbbbb",
                title="Lines (MTA brand colors, mta.info/document/168976)", title_fontsize=18)
leg.set_zorder(10)
# north arrow: true north = the unit vector (0,1) rotated by phi
n = R @ np.array([0.0, 1.0])
ax_, ay_ = x1 - 3.5, y1 - 6.0
ax.annotate("", xy=(ax_ + 3.0 * n[0], ay_ + 3.0 * n[1]), xytext=(ax_, ay_),
            arrowprops=dict(arrowstyle="-|>", lw=2.5, color="#333333"), zorder=10)
ax.text(ax_ + 3.6 * n[0], ay_ + 3.6 * n[1], "N", fontsize=22, ha="center", va="center",
        color="#333333", fontweight="bold", zorder=10)
ax.set_title("NYC Subway - 496 stations from metro MCP get_all_stations(city=nyc)   [v2: land/water base, "
             f"borough + NJ boundaries, rotated {math.degrees(phi):.0f}° so Manhattan runs north-south]\n"
             "segments = per-line minimum spanning tree over station coordinates; express variants 6X/7X/FX omitted; "
             "S = 3 separate shuttles, so S edges over 7 km are not drawn",
             fontsize=18, loc="left")

fig.savefig(f"{STEM}.png", dpi=100, bbox_inches="tight", facecolor="white")
fig.savefig(f"{STEM}.pdf", bbox_inches="tight", facecolor="white")
from PIL import Image
w, h = Image.open(f"{STEM}.png").size
print("dropped edges:", dropped)
print(f"routes={len(routes)} edges={edge_count} expected={expected - len(dropped)} labels={n_labels} "
      f"frame={w_km:.1f}x{h_km:.1f} km png={w}x{h} (w+h={w+h}) C5_ok={w+h <= 10000}")
