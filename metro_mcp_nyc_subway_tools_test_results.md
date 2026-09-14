# Metro MCP — NYC Subway Tools — Test Results

Tests file: [metro_mcp_nyc_subway_tools_tests.md](metro_mcp_nyc_subway_tools_tests.md)
Tool list: [metro_mcp_nyc_subway_tools.md](metro_mcp_nyc_subway_tools.md)

## Test 1 — get_all_stations

### Test (copied from tests file)

- **Tool:** `get_all_stations`
- **Arguments:** `{"city": "nyc"}`
- **Action:** call the tool once with the argument above.
- **Expected:** returns the full NYC subway station list with coordinates, without hanging or prompting for permission.

### Result

- **Run:** 2026-09-12, session in auto permission mode
- **Status:** PASS — returned promptly, no hang observed on the agent side
- **Response size:** 58,000 characters; the harness saved it to a file instead of inlining it (result exceeded the inline token cap). Not a tool failure.
- **Raw output (full, pretty-printed):** [metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json](metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json)

**Response shape:** `{city, totalStations, stations: [{id, name, lines, coordinates: {lat, lon}, address}]}`

| Field | Value |
|---|---|
| city | nyc |
| totalStations | 496 |
| stations array length | 496 |
| stations missing coordinates | 0 |
| stations with non-null address | 0 |
| distinct line codes | 1, 2, 3, 4, 5, 6, 6X, 7, 7X, A, B, C, D, E, F, FX, G, J, L, M, N, Q, R, S, SIR, W, Z |

**First 3 stations:**

```json
{"id":"101","name":"Van Cortlandt Park-242 St","lines":["1"],"coordinates":{"lat":40.889248,"lon":-73.898583},"address":null}
{"id":"103","name":"238 St","lines":["1"],"coordinates":{"lat":40.884667,"lon":-73.90087},"address":null}
{"id":"104","name":"231 St","lines":["1"],"coordinates":{"lat":40.878856,"lon":-73.904834},"address":null}
```

**Last 2 stations:**

```json
{"id":"S30","name":"Tompkinsville","lines":["SIR"],"coordinates":{"lat":40.636949,"lon":-74.074835},"address":null}
{"id":"S31","name":"St George","lines":["SIR"],"coordinates":{"lat":40.643748,"lon":-74.073643},"address":null}
```

**Sample — Times Sq-42 St appears 4 times (one entry per platform complex / station ID):**

```json
{"id":"127","name":"Times Sq-42 St","lines":["1","2","3"],"coordinates":{"lat":40.75529,"lon":-73.987495},"address":null}
{"id":"725","name":"Times Sq-42 St","lines":["7","7X"],"coordinates":{"lat":40.755477,"lon":-73.987691},"address":null}
{"id":"902","name":"Times Sq-42 St","lines":["S"],"coordinates":{"lat":40.755983,"lon":-73.986229},"address":null}
{"id":"R16","name":"Times Sq-42 St","lines":["N","Q","R","W"],"coordinates":{"lat":40.754672,"lon":-73.986754},"address":null}
```

**Observations:**

- Station IDs are MTA GTFS stop IDs (e.g. 127 = Times Sq-42 St on 1/2/3), matching the `stationId` format that `get_station_transfers` expects.
- 496 NYC stations + 102 DC stations = 598, matching the "598 stations" claim on the server's landing page.
- `address` is null for NYC stations (DC stations carry street addresses).
- Express-variant line codes (6X, 7X, FX) and the Staten Island Railway (SIR) are included.

## Test 2 — reconstruct the subway map from Test 1 output (based on tool 1)

### Test — v1 (copied from tests file)

- **Tool:** `get_all_stations` — no new tool call; uses the data already returned by Test 1.
- **Input:** [metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json](metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json) (496 stations, each with id, name, lines, lat/lon).
- **Action:**
  1. Plot every station at its latitude/longitude (geo plot).
  2. Label each station with its name.
  3. Color each station and line segment by the line's official MTA color (looked up via web search).
  4. Join the stations of each line into a polyline.
- **Output:** a plot image saved in a new subfolder, linked from the results file, and shared on Telegram.
- **Expected:** a recognizable NYC subway map — Manhattan trunk lines in their trunk colors, the boroughs laid out geographically.

### Result — v1

- **Run:** 2026-09-12
- **Status:** PASS — a recognizable map was produced from the Test 1 data alone.
- **Plot (PNG, 2767 × 2932 px):** [plots/nyc_subway_map_test2.png](plots/nyc_subway_map_test2.png)
- **Plot (PDF, vector — zoom in for station names):** [plots/nyc_subway_map_test2.pdf](plots/nyc_subway_map_test2.pdf)
- **Script:** [plots/make_nyc_subway_map_test2.py](plots/make_nyc_subway_map_test2.py) — the formal spec (variables, constraints, mapping, invariants, algorithm) is in its docstring.
- **Environment:** project venv `.venv` — Python 3.10.12, matplotlib 3.10.9, numpy 2.2.6, scipy 1.15.3.

**Method**

1. **Projection:** x = lon · cos(40.71°) · 111.2 km, y = lat · 111.2 km; equal aspect, so distances and angles are locally true.
2. **Stations:** 496 markers, white fill with black edge. Markers are neutral on purpose: a station served by several lines is not painted with any one of them.
3. **Labels:** 474. Same-name records within ~300 m are labelled once (e.g. the four `Times Sq-42 St` records, IDs 127 / 725 / 902 / R16, get one label).
4. **Line segments:** the tool returns no station order along a line, so for each route the stations are joined by a **minimum spanning tree** over projected distance. A subway route is topologically a tree and adjacent stations are each other's nearest neighbours, so the MST reproduces the track, branches included. 24 routes drawn (27 codes minus the express variants 6X / 7X / FX, which stop at subsets of their parent route's stations in the same color). 912 segments drawn.
5. **Colors:** *MTA Brand Colors / Subway, SIR & ADA* — <https://www.mta.info/document/168976> — read from the PDF text and confirmed against the rendered page.

| Color group | Hex | Routes |
|---|---|---|
| Red | #D82233 | 1 2 3 |
| Dark Green | #009952 | 4 5 6 |
| Purple | #9A38A1 | 7 |
| Blue | #0062CF | A C E |
| Orange | #EB6800 | B D F M |
| Light Green | #799534 | G |
| Brown | #8E5C33 | J Z |
| Grey | #7C858C | L, S (shuttles) |
| Yellow | #F6BC26 | N Q R W |
| MTA Blue | #08179C | SIR |

   Note: the document's "Teal" #008EB7 is the **T** bullet (planned Second Avenue line), not SIR — the text layer alone would have mis-assigned it; the rendered page settled it. The older Pantone-derived set (jsvine/mta-colors, e.g. 1/2/3 = #EE352E) was not used.

**Long-edge audit** — every MST edge longer than 3 km, checked by hand before choosing a cutoff:

| Route | km | From → To | Verdict |
|---|---|---|---|
| S | 13.7 | Prospect Park → Broad Channel | bogus: Franklin Av shuttle → Rockaway Park shuttle |
| S | 8.3 | Grand Central-42 St → Franklin Av | bogus: 42 St shuttle → Franklin Av shuttle |
| A | 5.9 | Howard Beach-JFK Airport → Broad Channel | real (across Jamaica Bay) |
| D | 5.4 | 125 St → 59 St-Columbus Circle | real (express run) |
| Q | 3.5 | Canal St → DeKalb Av | real (Manhattan Bridge) |
| B | 3.2 | Grand St → DeKalb Av | real (Manhattan Bridge) |
| D | 3.2 | Grand St → DeKalb Av | real (Manhattan Bridge) |
| 5 | 3.1 | 125 St → 86 St | real (express run) |

   The code `S` lumps three disconnected shuttles (42 St, Franklin Av, Rockaway Park), so the MST bridged them. Rule adopted: **drop any MST edge longer than 7 km**. That removes exactly the two S chords and nothing else.

**Constraint checks**

| Constraint | Result |
|---|---|
| C1 every station drawn once | 496 markers |
| C2 every name labelled ≥ once | 474 labels after de-duplication |
| C3 each route joined by its spanning tree | 912 edges = Σ(|S_r| − 1) − 2 dropped |
| C4 equal aspect | set |
| C5 PNG width + height ≤ 10000 (Telegram) | 2767 + 2932 = 5699 |
| C6 (soft) label overlap | overlaps in Manhattan below 59 St at PNG scale; legible in the PDF at zoom |

**Known limitations**

- Labels overlap in dense Manhattan at PNG scale (soft constraint C6); use the PDF.
- Express runs appear as straight chords (e.g. D: 125 St → 59 St) — the data has station points only, no track geometry.
- Routes sharing a trunk are drawn on top of each other with no parallel offset (same color, so no information is lost).
- The dataviz palette validator FAILS on the MTA palette (lightness band, chroma floor, CVD separation, yellow contrast). Expected: the palette is the MTA's own and is semantically fixed; the legend carries the route letters as the secondary encoding.

### Test — v2 (copied from tests file)

Feedback (Telegram voice note, 2026-09-12): the v1 plot was "not good, very confusing" — no water/land context, no borough boundaries, and not oriented like the familiar map.

- **Tool:** `get_all_stations` — still no new tool call; same Test 1 data.
- **Input:** the Test 1 JSON, plus base-map data: NYC borough polygons (NYC Planning ArcGIS `NYC_Borough_Boundary`) and Census 1:500k county polygons for New Jersey, Nassau, Westchester and Rockland (`plots/geo/`).
- **Action** (on top of v1 steps 1–4):
  5. Draw water in light blue and land in a light, non-blue color.
  6. Draw the boundaries of Manhattan, Brooklyn, Queens, Bronx, Staten Island and New Jersey, and label them.
  7. Rotate the map so Manhattan runs north–south and sits centred in the frame; add a north arrow.
- **Output:** `plots/nyc_subway_map_test2_v2.png` and `.pdf`, linked from the results file, shared on Telegram.
- **Expected:** a map that reads like the familiar subway map — water/land context, borough names, Manhattan vertical in the middle.

### Result — v2

- **Run:** 2026-09-12
- **Status:** PASS
- **Plot (PNG, 2556 × 2848 px):** [plots/nyc_subway_map_test2_v2.png](plots/nyc_subway_map_test2_v2.png)
- **Plot (PDF, vector — zoom in for station names):** [plots/nyc_subway_map_test2_v2.pdf](plots/nyc_subway_map_test2_v2.pdf)
- **Script:** [plots/make_nyc_subway_map_test2_v2.py](plots/make_nyc_subway_map_test2_v2.py) — v1 script left untouched; v2 adds the base map and rotation on top of the same network.
- **Network:** identical to v1 (496 stations, 474 labels, 24 routes, 912 segments, same 2 S chords dropped). The rotation is a rigid motion, so distances and the spanning trees are unchanged.

**Base map data (new subfolder `plots/geo/`)**

| Layer | Source | File |
|---|---|---|
| Five boroughs, shoreline-clipped, high detail (6k–36k vertices each) | NYC Planning, ArcGIS FeatureServer `NYC_Borough_Boundary` | `plots/geo/nyc_boroughs_arcgis.geojson` |
| New Jersey (all 21 counties) + Nassau, Westchester, Rockland for context | US Census cartographic boundaries 2023, counties, 1:500k (`cb_2023_us_county_500k`) | `plots/geo/census_counties_500k_nj_ny.geojson` |

   NYC Open Data's own borough-boundary endpoints returned "not found" for both dataset IDs tried; the NYC Planning ArcGIS mirror of the same layer worked.

**What v2 does on top of v1**

1. **Water / land:** axes background light blue `#cfe3f2` = water; NYC land `#f4f1ea`; out-of-city land `#e9e5dc` (slightly darker so the city limit reads); borough outlines `#6f6f6f`, county outlines `#a0a0a0`.
2. **Boundaries:** every borough polygon and every NJ / context county polygon is outlined, so Manhattan–Bronx, Brooklyn–Queens, Queens–Nassau, Bronx–Westchester and the NJ county lines all show.
3. **Region labels:** MANHATTAN, BROOKLYN, QUEENS, BRONX, STATEN ISLAND at each borough polygon's centroid; NEW JERSEY vertical, west of Hudson County. (Nassau, Westchester and Rockland are drawn but not labelled — not in the request.)
4. **Rotation:** stations inside the Manhattan polygon (153 of 496, by point-in-polygon) → principal axis by SVD → bearing **22.9° east of north** → everything (stations and polygons) rotated counter-clockwise by 22.9° about the Manhattan station centroid, so Manhattan runs straight north–south. (The Manhattan street grid is ~29°; the island's overall axis from the Battery to Inwood is ~23°, which is what the stations measure.)
5. **Framing:** x-limits symmetric about the Manhattan centroid (± 25.6 km), y-limits from the southernmost to northernmost station ± 1.5 km. Frame 51.3 × 56.1 km.
6. **North arrow:** true north drawn top-right; it points 22.9° left of vertical because of the rotation.

**Constraint checks (v2 additions)**

| Constraint | Result |
|---|---|
| C7 water = background, land = polygons, non-blue | done |
| C8 borough + NJ boundaries outlined | done, 5 boroughs + 24 context counties |
| C9 six region labels | done |
| C10 frame centred on Manhattan | x ∈ [cx − 25.6, cx + 25.6] km |
| C11 north arrow present | done |
| C5 PNG w + h ≤ 10000 | 2556 + 2848 = 5404 |
| invariant: network unchanged | 912 edges, same dropped list |

**Eyeball pass:** first v2 render showed a sliver of Rockland County (NY) rendering as water in the top-left corner (the rotated frame reaches ~41.03° N there); fixed by adding Rockland to the context layer.

**Remaining limitations:** as v1 — labels overlap in lower Manhattan at PNG scale; express runs draw as straight chords; routes sharing a trunk overlap without offset. Borough labels sit over the network where the borough centroid is (Manhattan's lands over the Upper West Side).

## Test 3 — get_incidents (tool 2)

### Test (copied from tests file)

- **Tool:** `get_incidents`
- **Arguments:** `{"city": "nyc"}`
- **Action:** call the tool once with the argument above.
- **Expected:** returns the current NYC subway incidents / service advisories, without hanging or prompting for permission.

### Result

- **Run:** 2026-09-12 ~23:34 UTC, session in auto permission mode
- **Status:** PASS — returned promptly, inline (the response fit under the harness's inline cap this time, unlike Test 1), no hang observed on the agent side
- **Raw output:** [metro_mcp_nyc_subway_tools_test3_get_incidents_nyc.json](metro_mcp_nyc_subway_tools_test3_get_incidents_nyc.json) — because the result came back inline, the harness saved no file; this copy was re-emitted verbatim from the inline tool result and validated as JSON (179 records) before saving.

**Response shape:** `{city, incidents: [{id, description, linesAffected, severity, type, lastUpdated}]}`

| Field | Value |
|---|---|
| city | nyc |
| incidents | 179 |
| live alerts (`lmm:alert:…`) | 5 |
| planned work (`lmm:planned_work:…`) | 174 |
| records where severity == type | 179 of 179 |
| lastUpdated range | 2026-05-26T11:54Z → 2026-09-12T23:29Z |
| duplicate descriptions (same text, different id) | 35 |

**By type**

| type | count |
|---|---|
| Planned - Stops Skipped | 56 |
| Planned - Part Suspended | 39 |
| Boarding Change | 19 |
| Planned - Express to Local | 18 |
| Planned - Reroute | 17 |
| Reduced Service | 8 |
| Planned - Suspended | 7 |
| Extra Service | 5 |
| Delays | 4 |
| Special Schedule | 3 |
| Station Notice | 2 |
| Stops Skipped | 1 |

**Lines affected (count of incidents naming the line):** F 18 · A 17 · 2 17 · N 14 · 5 12 · SI 11 · G 11 · R 9 · E 9 · D 9 · C 9 · 7 9 · Q 8 · J 7 · 1 7 · 4 6 · M 5 · L 5 · B 5 · H 3 · 6 2 · 3 2 · W 1 · GS 1 · 7X 1

**The 5 live alerts (all updated 2026-09-12):**

```
Delays        | A,C,D | [A][C][D] trains are running with delays in both directions while we perform track maintenance along the line in Manhattan.
Delays        | F     | Uptown [F] trains are running with delays while we perform track maintenance near Ditmas Av.
Delays        | E,F   | Downtown [R] trains are running express from Forest Hills-71 Av to Jackson Heights-Roosevelt Av. / Expect [E][F][R] delays in both directions.
Stops Skipped | R     | (same text as above, filed separately against the R)
Delays        | C,E   | Uptown [C][E] trains are running with delays after we requested NYPD for people being disruptive on a train at W 4 St-Wash Sq.
```

**Observations**

- The feed is live: the newest alert's `lastUpdated` (23:29Z) is about five minutes before the call.
- `linesAffected` uses a different vocabulary from `get_all_stations`: **SI** here vs **SIR** there for Staten Island Railway; **GS** here for the 42 St shuttle vs **S** there; **H** here for the Rockaway Park shuttle, which the station list folds into **S**. Any join across the two tools needs a code map.
- `severity` and `type` carry the same string (179 of 179 records) — one of them is redundant.
- 35 descriptions repeat under different ids (recurring weekend work orders); the feed does not de-duplicate.
- Planned work dominates: 174 of 179 records; only 5 are live disruptions.

## Test 4 — get_route_info (tool 3)

### Test (copied from tests file)

- **Tool:** `get_route_info`
- **Arguments:** `{"city": "nyc", "routeId": "F"}` and then, as a separate call, `{"city": "nyc", "routeId": "C"}`
- **Action:** call the tool once per route, one call at a time (F first, then C).
- **Expected:** for each route, its details and service patterns, without hanging or prompting for permission.

### Result

- **Run:** 2026-09-12 ~23:58 UTC, session in auto permission mode
- **Status:** PASS — both calls returned immediately, inline, no hang observed on the agent side
- **Raw output (both records, re-emitted verbatim from the inline results):** [metro_mcp_nyc_subway_tools_test4_get_route_info_nyc_F_C.json](metro_mcp_nyc_subway_tools_test4_get_route_info_nyc_F_C.json)

**Response shape:** `{city, routeId, shortName, longName, description}` — five fields, all strings. No station list, no stop sequence, no colors, no timestamps.

| routeId | longName | description |
|---|---|---|
| F | Queens Blvd Express/6 Av Local | Trains operate at all times between Jamaica-179 St, Queens, and Coney Island-Stillwell Av, Brooklyn. On weekdays, trains operate via 53 St (serving Queens Plaza, Court Sq-23 St, Lexington Av/53 St, and 5 Av/53). During nights and weekends trains operate via 63 St (serving 21 St-Queensbridge, Roosevelt Island, Lexington Av/63 St, and 57 St). F trains operate local in Manhattan and express in Queens at all times except late nights when they operate local. |
| C | 8 Avenue Local | Trains operate between 168 St, Manhattan, and Euclid Av, Brooklyn, daily from about 6 AM to 11 PM. |

**Observations**

- The "service patterns" promised by the tool description are prose (the MTA GTFS `route_desc` text), not structured data — endpoints, hours, and express/local behaviour are all inside `description`.
- This is static timetable information. It says nothing about current conditions; pairing it with `get_incidents` (via `/check-delay`) is what gives a "what is this line and how is it doing right now" answer.
- Weekday-vs-weekend routing differences (F via 53 St vs 63 St) are only recoverable by reading the prose.

## Test 5 — get_stations_by_line (tool 6)

### Test (copied from tests file)

- **Tool:** `get_stations_by_line`
- **Arguments:** `{"city": "nyc", "lineCode": "F"}`
- **Action:** call the tool once with the arguments above.
- **Expected:** the stations on the F line, without hanging or prompting for permission. Open question the result should settle: are the stations returned in track order (needed for the in-car strip-map drawing), or unordered?

### Result

- **Run:** 2026-09-13 ~00:56 UTC, session in auto permission mode
- **Status:** PASS — returned immediately, inline, no hang observed on the agent side
- **Raw output (re-emitted verbatim from the inline result, validated as JSON):** [metro_mcp_nyc_subway_tools_test5_get_stations_by_line_nyc_F.json](metro_mcp_nyc_subway_tools_test5_get_stations_by_line_nyc_F.json)

**Response shape:** `{city, line, stations: [{id, name, lines, coordinates: {lat, lon}, address}]}` — the same station record as Test 1, filtered to one line.

| Field | Value |
|---|---|
| line | F |
| stations | 59 |
| same set as Test 1 stations whose `lines` contain F | yes (59 in Test 1) |
| returned in track order? | **No.** Returned sorted by station id (confirmed: ids are in ascending order) |
| stations served only by F / FX | 14 |

**Order actually returned — grouped by id prefix (each group is one stretch of track, in sequence within the group):**

| # | ids | count | first → last | which stretch of the F |
|---|---|---|---|---|
| 1 | A41 | 1 | Jay St-MetroTech | Downtown Brooklyn (shared with A/C) |
| 2 | B04–B10 | 4 | 21 St-Queensbridge → 57 St | 63 St tunnel — nights and weekends |
| 3 | D15–D21 | 7 | 47-50 Sts-Rockefeller Ctr → Broadway-Lafayette St | 6 Av line |
| 4 | D42–D43 | 2 | W 8 St-NY Aquarium → Coney Island-Stillwell Av | Coney Island end |
| 5 | F01–F07 | 7 | Jamaica-179 St → 75 Av | Hillside Av, Queens |
| 6 | F09–F12 | 3 | Court Sq-23 St → 5 Av/53 St | 53 St tunnel — weekdays |
| 7 | F14–F18 | 4 | 2 Av → York St | Rutgers St tunnel |
| 8 | F20–F27 | 8 | Bergen St → Church Av | Culver line, shared with G |
| 9 | F29–F39 | 10 | Ditmas Av → Neptune Av | Culver line, F only |
| 10 | G08–G21 | 13 | Forest Hills-71 Av → Queens Plaza | Queens Blvd |

**The real Jamaica → Coney Island order** is a chaining of those groups: 5 → 10 → (6 on weekdays | 2 nights and weekends) → 3 → 7 → 1 → 8 → 9 → 4. Inside each group the ids run in travel direction (Queens → Manhattan → Brooklyn), so the ids give the order *within* a stretch; the order *between* stretches has to come from somewhere else (a hand-written chain per line, or the nearest-endpoint / spanning-tree join used in Test 2).

**Observations**

- Both the weekday (53 St) and the night/weekend (63 St) branches are included — the tool returns every station the F serves in any pattern, not a single service pattern.
- No station order, no direction, no next-station links: the tool is a *set* of stations with coordinates.
- For the in-car strip-map idea: this gives the dots and their names, the coordinates give a way to chain the stretches, Test 2's palette gives the color, and the incidents feed gives delayed / not — but **"where the train is" is not available from any NYC tool** in this MCP (train positions are DC-only); the nearest proxy is `get_station_predictions` per station, still untested.

## Test 6 — get_station_predictions (tool 4), sparse sweep along the F

### Test (copied from tests file, including the revision)

- **Tool:** `get_station_predictions` — `{"city": "nyc", "stationName": "<name or id>"}`, one call per station, one at a time.
- **Stations (F, 6 Av stretch, Jamaica → Coney Island order):** Broadway-Lafayette St first (shape of a prediction), then 47-50 Sts-Rockefeller Ctr → 42 St-Bryant Pk → 34 St-Herald Sq → 23 St → 14 St → W 4 St-Wash Sq.
- **Revision after the first run:** call by station **id** (`D17`, `D18`, `D19`, `D20`) for every station whose name is duplicated.
- **Expected:** live arrivals per station; walking the stretch in travel order, do the F countdowns reveal train positions?

### Result

- **Run:** 2026-09-13 02:22Z – 02:48Z, 7 successful calls + 2 stalled attempts
- **Status:** PASS for the tool once called correctly; **one real finding about the harness** (below)
- **Data:** [metro_mcp_nyc_subway_tools_test6_get_station_predictions_F_sweep.json](metro_mcp_nyc_subway_tools_test6_get_station_predictions_F_sweep.json) — the F-line rows of every response (direction, minutesAway, arrivalTime, status) plus per-station totals and notes; the D-line rows are not saved.

**Prediction shape:** `{city, station: "<id>", predictions: [{line, destination, minutesAway, arrivalTime, arrivalStatus, cars, direction, track}]}`

| Field | What it actually holds |
|---|---|
| station | the resolved station id (D21, D15, …) |
| destination | **not** a destination — the GTFS stop id with direction suffix (`D21S`, `D21N`) |
| minutesAway | integer minutes relative to the moment of the call; `null` when arrivalStatus is ARRIVING |
| arrivalTime | absolute UTC timestamp — the field to use when combining calls made at different times |
| arrivalStatus | `SCHEDULED` for 176 of 178 rows seen; `ARRIVING` twice (a D at D15, a D at D20) — so the feed carries live state, not only timetable |
| direction | `NORTH` / `SOUTH` |
| cars, track | always null in every row seen |
| train / trip id | **none** — reconstruction is by matching times, not by id |

**The stall, and its cause (the "permission hang" from the earlier session):**

| step | what happened |
|---|---|
| `stationName: "34 St-Herald Sq"` (in-session, twice) | no result; session sat on a dialog Vivek read as a permission prompt; interrupted both times |
| allow rule `mcp__metro__*`, then `mcp__metro`, added to `~/.claude/settings.json` | no change — and per the docs agent both forms are valid, apply from the next tool call, and are checked before the auto-mode classifier, so permissions were never the cause |
| headless `claude -p` with the same call, 120 s timeout | nothing back either |
| **direct HTTP to the server** (curl, JSON-RPC `tools/call`) | **0.8 s, HTTP 200, `isError: true`**: "Multiple stations match this query: D17 — 34 St-Herald Sq; R17 — 34 St-Herald Sq; please call get_station_predictions again with an exact station ID." |
| same by curl for `42 St-Bryant Pk` (unique name) | 1.1 s, normal result |
| same by curl for `23 St` | error result listing 6 matches (130, 634, A30, D18, F09, R19) |
| same by curl for `D17`, `R17`, `D18` | normal results (31 / 39 / 16 predictions) |
| `stationName: "D17"` in-session, then `D18`, `D19`, `D20` | all returned instantly |

So: the server rejects ambiguous names by design and answers fast; **Claude Code does not deliver that MCP error result to the model and stalls at a dialog instead.** The three stations that worked by name (Broadway-Lafayette St, 47-50 Sts-Rockefeller Ctr, 42 St-Bryant Pk) are the three with unique names. 76 of 379 NYC station names are shared by more than one id. The docs agent found no documented dialog for MCP tool errors — errors are supposed to pass straight to Claude — so the stall itself is undocumented behaviour and a candidate bug report. Workaround: pass ids.

**Sweep data (F only), in travel order — call time in brackets:**

| id | station | called | F rows | first S | first N |
|---|---|---|---|---|---|
| D15 | 47-50 Sts-Rockefeller Ctr | 02:23Z | 14 | 02:30:06 | 02:29:44 |
| D16 | 42 St-Bryant Pk | 02:23Z | 14 | 02:30:35 | 02:28:18 |
| D17 | 34 St-Herald Sq | 02:45Z | 16 | 02:47:11 | 02:53:54 |
| D18 | 23 St | 02:46Z | 16 | 02:49:36 | 02:52:31 |
| D19 | 14 St | 02:47Z | 16 | 02:50:28 | 02:51:12 |
| D20 | W 4 St-Wash Sq | 02:48Z | 16 | 02:52:06 | 02:50:06 |
| D21 | Broadway-Lafayette St | 02:22Z | 14 | 02:28:42 | 02:42:53 |

**Reconstruction ("where is the train"):** because there is no train id, and because the interrupts put a 22-minute gap between the D16 and D17 calls, `minutesAway` cannot be compared across stations. `arrivalTime` can: a train is a chain of arrivals that increase along the travel order by a few minutes per station. Chaining with a 6-minute window, reference time 02:48Z:

```
SOUTHBOUND
 train 1: between 42 St-Bryant Pk and 34 St-Herald Sq
          34 St 02:47 -> 23 St 02:49 -> 14 St 02:50 -> W 4 St 02:52 -> Broadway-Lafayette 02:55
 train 2: approaching 47-50 Sts from the north
          47-50 02:58 -> 42 St 03:00 -> 34 St 03:03 -> 23 St 03:06 -> 14 St 03:06 -> W 4 St 03:08 -> Broadway-Lafayette 03:08
 train 3: approaching 47-50 Sts   03:15 -> 03:16 -> 03:17 -> 03:19 -> 03:21 -> 03:22 -> 03:25
 train 4: approaching 47-50 Sts   03:27 -> 03:28 -> 03:30 -> 03:31 -> 03:33 -> 03:34 -> 03:37

NORTHBOUND
 train 1: between Broadway-Lafayette St and W 4 St-Wash Sq
          W 4 St 02:50 -> 14 St 02:51 -> 23 St 02:52 -> 34 St 02:53
 train 2: between 34 St-Herald Sq and 42 St-Bryant Pk      42 St 02:51 -> 47-50 02:52
 train 3: approaching Broadway-Lafayette from the south   02:59 -> 03:02 -> 03:03 -> 03:04 -> 03:06 -> 03:08 -> 03:09

strip, F southbound, 6 Av stretch, 02:48Z:
[T2][T3][T4]->(47-50 Sts)——(42 St-Bryant Pk)——[T1]->(34 St-Herald Sq)——(23 St)——(14 St)——(W 4 St)——(Broadway-Lafayette St)
```

Headway between southbound trains: ~11–12 minutes (02:47 → 02:58 → 03:15 → 03:27 at 34 St), consistent with late-evening F service.

**Caveats**

- D21, D15, D16 were polled 25 minutes before D17–D20; chains that mix the two batches assume the schedule did not shift in between. A real strip map polls the stretch in one pass.
- The arrival times are `SCHEDULED` predictions; the two `ARRIVING` rows show the feed goes live as a train reaches a platform, but no row here was `ARRIVING` for an F.
- One sweep of the whole F is 59 calls; the stretch here is 7.

**Answer to the test question:** yes — walking the stretch in travel order and threading `arrivalTime`s places every train between two stations. The in-car strip map is buildable from tools 6 + 4 (+ Test 2's colours + the incidents feed for delayed / not), with ids instead of names.

## Prototype — F line strip map (built on tools 6 + 4 + 2, after Test 6)

- **Ask (Vivek, terminal voice):** for a given line, show whether it is delayed, draw the whole line, colour every station by how close the next train is, show where the trains are — the in-car strip map.
- **Script:** [plots/f_strip_map.py](plots/f_strip_map.py) → [plots/f_strip_map.txt](plots/f_strip_map.txt) (terminal strip), [plots/f_strip_map.png](plots/f_strip_map.png), [plots/f_strip_map_data.json](plots/f_strip_map_data.json) (every F prediction polled, train positions, live alerts).
- **How:** Test 5's 59 F stations put in travel order by a hand-written chain (both Manhattan approaches included; the live one is chosen from the data) → one pass of `get_station_predictions` by **id** for all 59 stations, over HTTP to the same MCP server (8 in parallel, 7 s, 0 errors) → trains threaded per direction by absolute `arrivalTime` → `get_incidents` filtered by the check-delay rules → text strip + PNG.
- **Run 2026-09-13 03:11Z:** no live F alerts; 16 planned advisories; 63 St approach in service (53 St stations get no F); 8 southbound and 6 northbound trains placed.
- **Cross-checks that fell out of the data:** (1) Queens Plaza shows no F either way — correct, the 63 St routing bypasses it; (2) northbound Avenue I / Bay Pkwy / Avenue N / Avenue P show no F — matches the planned-work advisory "Manhattan-bound F skips Avenue P, Avenue N, Bay Pkwy and Avenue I"; (3) southbound 4 Av-9 St / 15 St-Prospect Park / Fort Hamilton Pkwy show no F — matches "Coney Island-bound F … skip 4 Av-9 St, 15 St-Prospect Park and Fort Hamilton Pkwy"; (4) Queens local stations have F arrivals — late-night local service, as the route description says.
- **Known cosmetic issues in the PNG:** circles are ovals (axes not equal-aspect); northbound train arrows sit far right of the names.
- **Why HTTP from a script rather than 59 in-session tool calls:** one pass gives consistent timestamps, takes seconds, and never hits the ambiguous-name stall. The in-session tool path was verified separately (Test 6). A packaged skill would bundle this script.

## Prototype v2 — station board (horizontal, local, NYC direction wording)

- **Ask (Vivek, terminal voice, after seeing the v1 strip):** drop northbound/southbound for NYC lingo with the terminus (Manhattan-bound, Brooklyn-bound, Queens-bound → Coney Island / Jamaica); make it horizontal; make it *local* — a station as the input (optionally with lines), a few stations each side, so you get the richer train board before you reach the station.
- **Code:** [plots/metro_live.py](plots/metro_live.py) (shared: HTTP polling by id, per-line travel order, train threading, delay rules, borough lookup) and [plots/station_board.py](plots/station_board.py) (`station_board.py "<station>" [LINE…] [--window=N]` → text + PNG + JSON under `plots/boards/`). `plots/f_strip_map.py` (v1, whole line, vertical) is left as is.
- **Direction wording:** computed, not hard-coded — the next borough the train enters after the station gives "<Borough>-bound", the end of the chain gives "→ <terminus>"; at a terminal the arriving direction reads "arrivals — this is the last stop". Borough from the Test 2 polygons.
- **Examples run 2026-09-13 03:24Z (all F):** York St, Jay St-MetroTech, 42 St-Bryant Pk, Coney Island-Stillwell Av — `plots/boards/F_*.{txt,png,json}`. At 42 St the labels come out as "Brooklyn-bound → Coney Island" and "Queens-bound → Jamaica-179 St"; at York St, "Coney Island-bound" and "Manhattan-bound → Jamaica-179 St".
- **Polling:** window ± (N+2) stations plus both Manhattan branches, by id, one pass (~2 s). The extra margin lets the board say when the next train *beyond* the picture reaches its edge.
- **Still F-only:** every other line needs a travel-order chain in `metro_live.TRAVEL_ORDER` (the "training data" step). Station names are resolved within the requested line, so `23 St` on the F is unambiguous.
- **Fixed along the way:** JSON dump of datetimes; name collisions in 12-char columns (column width 13, abbreviations table); direction labels overlapping the bottom row in the PNG (moved to the left of each row); the "+N trains approaching" line (now: the nearest one and when it reaches the edge station).

## Skill shipped — `/get-train-board` (2026-09-13, ~06:10Z–07:00Z)

> **Superseded 2026-09-13 08:03Z** by the rebuild to Vivek's taxonomy — the skills, files and architecture described in this section no longer exist as stated. Current record: [metro_mcp_nyc_subway_tools_skills_test_results.md](metro_mcp_nyc_subway_tools_skills_test_results.md).

- **Global skill:** `~/.claude/skills/get-train-board/` — `SKILL.md`, `scripts/train_board.py`, `scripts/metro_live.py` (stdlib only), `data/stations_nyc.json`, `data/boroughs_nyc.json`, `data/lines/<LINE>.json` (cached `get_stations_by_line` results).
- **Input:** station (ask once → `null`); optional line (ask once → one board per line through the station).
- **Output:** the compact board — one row per station (3 each side), minutes to the next train per direction in NYC platform wording, `●` = train here, delay line on top; "no <line> trains serving this stretch right now" + the line's planned-work advisories when the stretch is empty.
- **Composite:** `get_stations_by_line` → travel order → `get_station_predictions` by id (one pass over HTTP) → train threading → `get_incidents` with the check-delay rules.
- **Travel order:** the F uses the hand-written chain (Test 5 results). Every other line is ordered automatically: minimum spanning tree over the line's stations, longest tree path through the requested station, oriented so id numbers increase along the feed's SOUTH direction. Verified on the L at 14 St-Union Sq (8 Av → 6 Av → 14 St → 3 Av → 1 Av → Bedford Av, correct) and the M at Roosevelt Island (no M at 07:00Z — late-night service — reported as such).
- **Vivek's tests from another session:** `York St F` (board), `Roosevelt Island C` (C doesn't stop there → lines F, M), `Roosevelt Island M`, `14th St L`. The last two exposed the F-only limitation, fixed by the automatic ordering above.
- **Not done:** the "ask which one" path for names shared by several stations is described in SKILL.md but only exercised by the script's exit-2 message; no travel-order review of the 22 lines the auto method hasn't been checked on.

## Test 7 — search_stations (tool 7), via `/search-stations`

> **Superseded 2026-09-13 08:03Z** by the rebuild to Vivek's taxonomy — the skills, files and architecture described in this section no longer exist as stated. Current record: [metro_mcp_nyc_subway_tools_skills_test_results.md](metro_mcp_nyc_subway_tools_skills_test_results.md).

- **Calls:** `search_stations(nyc, "York St")` → 1 match: F18 York St (F, FX). `search_stations(nyc, "14 St")` → 6 matches: 132 (1 2 3), 635 14 St-Union Sq (4 5 6), A31 (A C E), D19 (F M), L03 14 St-Union Sq (L), R20 14 St-Union Sq (N Q R W).
- **Status:** PASS — instant, over HTTP. Response field: `results` (list of station records: id, name, lines).
- **Use:** this is the name → id step every other skill needs; it is what makes `/get-station-predictions` safe (ids, never ambiguous names).

## Composition rebuild — 2026-09-13

> **Superseded 2026-09-13 08:03Z** by the rebuild to Vivek's taxonomy — the skills, files and architecture described in this section no longer exist as stated. Current record: [metro_mcp_nyc_subway_tools_skills_test_results.md](metro_mcp_nyc_subway_tools_skills_test_results.md).

Vivek's correction: he had asked for composite skills (skills calling skills); I had shipped monoliths, and `/get-train-board` failing on the L was the consequence (hard-coded F data instead of calling a stations skill). Rebuilt: three new single skills (`/get-stations-by-line`, `/get-station-predictions`, `/search-stations`), `/get-train-board` now composes them plus `/check-delay` and only renders, `/get-route-info` now invokes `/check-delay`. Old bundled scripts and station data removed from `/get-train-board`. End-to-end composed run for the L at 14 St-Union Sq verified at 07:36Z. See the blueprint's "Rebuilt as a composition" section for the table.

## Test 8 — get_station_transfers (tool 5) — 2026-09-13 18:4xZ

- **Call 1:** `get_station_transfers(city=nyc, stationId="A32")` → instant. `{city, stationId, stationName: "W 4 St-Wash Sq", totalTransfers: 1, transfers: [{toStationId: "D20", toStationName: "W 4 St-Wash Sq", walkTimeSeconds: 180, walkTimeMinutes: 3, transferType: "nearby"}]}` — the 6 Av level of the same complex.
- **Call 2:** `get_station_transfers(city=nyc, stationId="127")` → instant. Times Sq-42 St, 4 transfers: `725` Times Sq-42 St (the 7), `902` Times Sq-42 St (the 42 St shuttle), `R16` Times Sq-42 St (N Q R W) — 3 min each — and `A27` 42 St-Port Authority Bus Terminal (A C E), 5 min, all `transferType: "nearby"`.
- **What it is:** for one station id, the other station ids you can walk to inside the same complex or through a passageway, each with a walking time. It does not list the lines at the other end (join on `get_all_stations` / `search_stations` for that); one `transferType` value seen so far ("nearby"); times are round numbers (3 min in-complex, 5 min for the Port Authority passageway).
- **Status:** PASS. All 7 NYC tools now tested.
