# Metro MCP — NYC Subway Tools — Tests

Tool list: [metro_mcp_nyc_subway_tools.md](metro_mcp_nyc_subway_tools.md)

Protocol: one tool call at a time, so any hang is immediately visible in the terminal.

## Test 1 — get_all_stations

- **Tool:** `get_all_stations`
- **Arguments:** `{"city": "nyc"}`
- **Action:** call the tool once with the argument above.
- **Expected:** returns the full NYC subway station list with coordinates, without hanging or prompting for permission.

## Test 2 — reconstruct the subway map from Test 1 output (based on tool 1)

### v1 — original

- **Tool:** `get_all_stations` — no new tool call; uses the data already returned by Test 1.
- **Input:** [metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json](metro_mcp_nyc_subway_tools_test1_get_all_stations_nyc.json) (496 stations, each with id, name, lines, lat/lon).
- **Action:**
  1. Plot every station at its latitude/longitude (geo plot).
  2. Label each station with its name.
  3. Color each station and line segment by the line's official MTA color (looked up via web search).
  4. Join the stations of each line into a polyline.
- **Output:** a plot image saved in a new subfolder, linked from the results file, and shared on Telegram.
- **Expected:** a recognizable NYC subway map — Manhattan trunk lines in their trunk colors, the boroughs laid out geographically.

### v2 — revised after feedback on the v1 plot

Feedback (Telegram voice note, 2026-09-12): the v1 plot was "not good, very confusing" — no water/land context, no borough boundaries, and not oriented like the familiar map.

- **Tool:** `get_all_stations` — still no new tool call; same Test 1 data.
- **Input:** the Test 1 JSON, plus base-map data: NYC borough polygons (NYC Planning ArcGIS `NYC_Borough_Boundary`) and Census 1:500k county polygons for New Jersey, Nassau, Westchester and Rockland (`plots/geo/`).
- **Action** (on top of v1 steps 1–4):
  5. Draw water in light blue and land in a light, non-blue color.
  6. Draw the boundaries of Manhattan, Brooklyn, Queens, Bronx, Staten Island and New Jersey, and label them.
  7. Rotate the map so Manhattan runs north–south and sits centred in the frame; add a north arrow.
- **Output:** `plots/nyc_subway_map_test2_v2.png` and `.pdf`, linked from the results file, shared on Telegram.
- **Expected:** a map that reads like the familiar subway map — water/land context, borough names, Manhattan vertical in the middle.

## Test 3 — get_incidents (tool 2)

- **Tool:** `get_incidents`
- **Arguments:** `{"city": "nyc"}`
- **Action:** call the tool once with the argument above.
- **Expected:** returns the current NYC subway incidents / service advisories, without hanging or prompting for permission.

## Test 4 — get_route_info (tool 3)

- **Tool:** `get_route_info`
- **Arguments:** `{"city": "nyc", "routeId": "F"}` and then, as a separate call, `{"city": "nyc", "routeId": "C"}`
- **Action:** call the tool once per route, one call at a time (F first, then C).
- **Expected:** for each route, its details and service patterns, without hanging or prompting for permission.

## Test 5 — get_stations_by_line (tool 6)

- **Tool:** `get_stations_by_line`
- **Arguments:** `{"city": "nyc", "lineCode": "F"}`
- **Action:** call the tool once with the arguments above.
- **Expected:** the stations on the F line, without hanging or prompting for permission. Open question the result should settle: are the stations returned in track order (needed for the in-car strip-map drawing), or unordered?

## Test 6 — get_station_predictions (tool 4), sparse sweep along the F

- **Tool:** `get_station_predictions`
- **Arguments:** `{"city": "nyc", "stationName": "<name>"}`, one call per station, one at a time.
- **Stations (F, 6 Av stretch, in Jamaica → Coney Island travel order, from Test 5):**
  1. Broadway-Lafayette St — first, alone, to see the shape of a prediction (fields, whether a train id / direction / minutes are present, whether all lines at the station are returned)
  2. then a consecutive sweep: 47-50 Sts-Rockefeller Ctr → 42 St-Bryant Pk → 34 St-Herald Sq → 23 St → 14 St → W 4 St-Wash Sq
- **Action:** call the tool once per station, sequentially; no new call to tool 6 (Test 5's station list is reused).
- **Expected:** live arrivals per station without hanging or prompting. Question to settle: walking the stretch in travel order, do the F countdowns per direction show local minima that place each train between two stations (the "where is the train" reconstruction)?

### Test 6 — revision after the first run

- Calling by **name** stalls the session for any station whose name is shared by more than one station id (34 St-Herald Sq = D17 + R17; 23 St has 6 ids; 14 St has 3; W 4 St-Wash Sq has 2). The server returns an error result asking for an exact id; Claude Code does not deliver that error and sits on a dialog until interrupted. 76 of 379 NYC station names are duplicated.
- Revised action: call by **station id** for every station after the first three — `D17`, `D18`, `D19`, `D20` — one call at a time. Same expected outcome.

## Test 7 — search_stations (tool 7)

*Entry written after the run (2026-09-13 07:35Z, through the since-deleted `/search-stations` skill); the standing protocol says tests go here first — this one did not, recorded here so the tests file is complete.*

- **Call:** `search_stations(city=nyc, query="York St")` — expect one match (F18, F/FX). Then `search_stations(city=nyc, query="14 St")` — expect several matches across trunks (the name → id step that keeps `get_station_predictions` off ambiguous names).
- **Result:** see the results file, section "Test 7".

## Test 8 — get_station_transfers (tool 5)

- **Call:** `get_station_transfers(city=nyc, stationId="A32")` — W 4 St-Wash Sq (A C E on the 8 Av level, B D F M on the 6 Av level). Expect: what the tool means by a "transfer" — the other lines / platforms / station ids reachable without leaving the station, and whether it knows about out-of-system passageways.
- **Then (only if the first call returns instantly):** `get_station_transfers(city=nyc, stationId="127")` — Times Sq-42 St, the biggest complex (1 2 3, 7, N Q R W, S, and the passageway to A C E at Port Authority).
- One call at a time; record the raw shape.
