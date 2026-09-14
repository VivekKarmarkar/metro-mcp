# Metro MCP — NYC Subway Tools — Skills Tests

The tests Vivek ran or specified for the skills he asked for. Blueprint: [metro_mcp_nyc_subway_tools_skills_blueprint.md](metro_mcp_nyc_subway_tools_skills_blueprint.md). Results: [metro_mcp_nyc_subway_tools_skills_test_results.md](metro_mcp_nyc_subway_tools_skills_test_results.md).

**Vivek's taxonomy (his spec):** a **single** skill = one skill, one or more tool calls, calls no other skill. A **composite** skill = calls one or more other skills, and possibly one or more tool calls of its own on top.

---

## Skill 1 — `/check-delay <line>` · single · tool: get_incidents

| # | test | expected |
|---|---|---|
| 1.1 | `/check-delay F` | delay-right-now YES/NO for the F, live alerts verbatim, planned-work count |
| 1.2 | `/check-delay` (no line) → reply "yolo lol" | asks "Which line?" once, then outputs `null` |
| 1.3 | `/check-delay C line` | delay status for the C |

## Skill 2 — `/get-route-info <lines…>` · composite · calls `/check-delay` per line + tool: get_route_info per line

| # | test | expected |
|---|---|---|
| 2.1 | `/get-route-info L` | block for the L: `/check-delay L`'s answer, then the route description |
| 2.2 | `/get-route-info F` | same for the F |
| 2.3 | `/get-route-info` (no lines) → nonsense reply | asks once, then `null` |

## Skill 3 — `/get-train-board <station> [line]` · composite · calls `/check-delay` + tools: search_stations, get_stations_by_line, get_station_predictions

Vivek's algorithm: (1) get_stations_by_line for the line → (2) sort into travel order (training knowledge + geometry) → (3) get_station_predictions at a few stations to place the trains → (4) `/check-delay` for the status → (5) draw the local board around the station: horizontal window, NYC direction wording with the terminus, minutes per direction, trains marked.

| # | test | expected |
|---|---|---|
| 3.1 | `/get-train-board York St F` | the F board around York St |
| 3.2 | `/get-train-board Roosevelt Island C line` | the C doesn't stop there → say so, list the lines that do (F, M) |
| 3.3 | `/get-train-board Roosevelt Island M` | M board, or "no M trains serving this stretch right now" when the M isn't running there |
| 3.4 | `/get-train-board 14th St L` | the L board around 14 St-Union Sq — **this is the one that failed** on the monolith build ("no board for the L yet"); any line must work |
| 3.5 | `/get-train-board 42 St-Bryant Pk F` · `Coney Island-Stillwell Av F` (terminal) · `Jay St-MetroTech` (no line → one board per line through it) | boards; terminal reads "last stop"; no-line case prints a board per line |
| 3.6 | `/get-train-board` (no station) → nonsense reply | asks "Which station?" once, then `null` |
| 3.7 | `/get-train-board York St` (no line) → "no" | asks "Do you have a train line in mind?" once, then one board per line through York St |
| 3.8 | `/get-train-board W 4th St` (no line) → "all lines" | asks once; then `/check-delay <line>` + one board per line through W 4 St-Wash Sq (A B C D E F M), each board in its own message |
| 3.9 | `/get-train-board Rockaway Blvd A` · `Broad Channel A` · `E 180 St 5` | lines that fork: the board follows one branch (the one with trains) and names the other in a "branch not shown" footer; travel order correct on both sides of the fork |
| 3.10 | `/get-train-board 47-50 Sts F` | the F's Manhattan branch (53 St / 63 St) is chosen from the live data, the other named in the footer — re-run on a weekday, when the F runs via 53 St |
| 3.11 | `train_board.py "York St" F` with no `--delay` | the bundled code refuses (exit 2): the board cannot be drawn without `/check-delay`'s answer |

## Skill 4 — `/find-nearest-station <place>` · single · tool: get_all_stations (+ Nominatim geocoding, not a metro tool)

Vivek's dictation (2026-09-13, terminal voice, garbled — the names below are the transcript's, reconciled in the results file): from a place, find the nearest subway station(s). He knows the right answers; a test passes if the station reported matches his. If these pass, the skill ships globally with the code that ran them and these examples bundled as its proof — never hard-coded as its scope; it must generalise to any place.

| # | test (place, as dictated) | expected |
|---|---|---|
| 4.1 | "Fontaine Has" — the fancy Indian chai / tea shop in DUMBO, Brooklyn | the nearest station(s) to the shop, with distance |
| 4.2 | "Aileen's cheesecake" (Eileen's Special Cheesecake, Nolita) | nearest station(s) |
| 4.3 | "Punjabi Delhi, East Village" (Punjabi Deli, E 1st St) | nearest station(s) |
| 4.4 | "Kaatirol company, close to Times Square" (The Kati Roll Company, Midtown) | nearest station(s) |
| 4.5 | "Sarwana Bhavan on Lexington Avenue" (Saravana Bhavan; there may be more than one on Lexington Av — report each) | nearest station(s) |

Vivek's verdict 2026-09-14 ~02:25Z: all five right → ship. Tests of the shipped skill (written before running):

| # | test | expected |
|---|---|---|
| 4.6 | `/find-nearest-station Brooklyn Museum` — a landmark, not a business | Eastern Pkwy-Brooklyn Museum (2 3) as the nearest, well under 0.2 mi; the name should geocode without a street address |
| 4.7 | `/find-nearest-station 40.7484,-73.9857` — coordinates only (the Empire State Building) | 34 St-Herald Sq (B D F M N Q R W) and 33 St (6) within ~0.15 mi; no geocoding step |
| 4.8 | `/find-nearest-station Hoboken Terminal` — a real place outside the subway's reach | reports the nearest NYC subway station honestly (Christopher St / WTC area, more than a mile away, across the river) and prints the "more than a mile" note; does not invent a closer station |
| 4.9 | `nearest_station.py "Fontaine Has, DUMBO"` — a garbled name straight into the code | exit 2 "could not geocode" (the SKILL's Step 2 is what resolves names; the code must not guess) |

---

Skills that were built without being asked for, and were deleted 2026-09-13 (08:03Z): `/get-stations-by-line`, `/get-station-predictions`, `/search-stations`.

## Skill 5 — `/find-metro <X> to <Y>` · composite · calls `/find-nearest-station` ×2, `/check-delay` per line, `/get-train-board` per leg + tools: get_stations_by_line, get_station_transfers

The problem and the workflow: [problem_statement.md](problem_statement.md). Tests written 2026-09-14 03:06:34Z (transcript time), before any workflow run (first run 03:06:56Z); the nearest-station legs for Chelsea Market and Thai Villa had been run by Vivek at 02:36–02:37Z, so their expected stations were known, not predicted. A test passes when the plan follows the workflow (stations from the skill, prior stated, every check made, corrections named) and Vivek agrees with the route.

| # | test | expected |
|---|---|---|
| 5.1 | `/find-metro Fontainhas to Saravanaa Bhavan on Lexington` (DUMBO → Curry Hill) | S_x York St (F), S_y 28 St (6); one change — prior: F Manhattan-bound to Broadway-Lafayette St, in-complex change to the uptown 6 at Bleecker St, 6 to 28 St; `get_station_transfers` confirms the Bway-Lafayette ↔ Bleecker St link with walk minutes; live next trains at York St and Bleecker St; delay lines for F and 6 |
| 5.2 | `/find-metro Chelsea Market to Brooklyn Museum` | nearest ≠ best: 14 St (A C E) / 8 Av (L) are nearest, but the one-seat ride is the 2/3 from 14 St (1 2 3, 0.38 mi walk) to Eastern Pkwy-Brooklyn Museum; the plan says so and offers the L (8 Av → 6 Av) + change to the 2/3 as the alternative |
| 5.3 | `/find-metro Thai Villa to Eileen's cheesecake` | one seat either way: the 6 from 23 St to Spring St (4 stops, 1-min walk) or the R/W from 23 St to Prince St (3 stops, 4-min walk); the plan picks by live next trains and says why |
| 5.4 | `/find-metro Kati Roll Company (39th St) to Barclays Center` — a route the planned-work feed can break | prior: D express 42 St-Bryant Pk → Atlantic Av-Barclays Ctr; the plan reads `/check-delay D` details ("No [D] between 34 St-Herald Sq and Atlantic Av" when active) and the boards, and falls back to the N/Q/R from Times Sq or 34 St-Herald Sq when the D is not running there — stating the correction |
| 5.5 | `/find-metro` with nothing, or with one place only ("/find-metro Fontainhas") | `null` at once — no question, no calls (Vivek, 2026-09-14 ~01:50 EDT: "even if one argument is not given, return null"); a place that is unclear ("Shukha", "Central Park") gets one question instead |

Round 2 — dictated by Vivek 2026-09-14 ~03:35Z after seeing 5.1 and 5.2 re-rendered as numbered steps ("this is the shape I want"). Names reconciled from the voice transcript; the resolution is confirmed at run time by `/find-nearest-station`'s own lookup. Written before any run.

| # | test (as dictated → reconciled) | expected |
|---|---|---|
| 5.6 | "the chai place in DUMBO, Fontainhas Dukaan" → "Hyderabadi's icon, like, 9th Ave" → Hyderabadi Zaiqa, 9th Ave in Hell's Kitchen | S_x York St (F); S_y 50 St (C E) or 50 St (1); one change — prior: F to W 4 St-Wash Sq, same complex to an uptown E or C to 50 St; the live E reroute and "C service ends early" advisories read and applied |
| 5.7 | "at Hudson Yards, want to get to Shukha (s-h-u-k-h-a)" → Shuka, 38 MacDougal St, SoHo (or Shukette, 230 9th Av, Chelsea — the search decides; both named) | S_x 34 St-Hudson Yards (7); to SoHo: one change at Times Sq / 42 St-Port Authority (passageway, get_station_transfers) to a downtown A C E to Spring St or W 4 St; to Chelsea instead: 7 to Times Sq then the 1 or C/E downtown to 23 St |
| 5.8 | "at Times Square, going to the Ralph Lauren coffee shop on the Upper East Side" → Ralph's Coffee, 888 Madison Av at E 72nd St | two ways compared: 42 St shuttle to Grand Central + uptown 6 to 68 St-Hunter College (two seats, short walk) vs the Q from Times Sq to 72 St (one seat, ~10 min walk); the plan picks by live waits and says why |
| 5.9 | "at 66 Perry St; banana pudding at the nearest Magnolia Bakery first (it's close by), then all the way to the Seinfeld diner" → Magnolia Bakery, 401 Bleecker St at W 11th; Tom's Restaurant, 2880 Broadway at W 112th St | a trip with a stop on the way: the Magnolia leg is a walk (~3 min), no train; then Christopher St-Stonewall (1) uptown, one seat, to Cathedral Pkwy (110 St); the live "downtown [1] delays" alert is read (other direction) and the planned uptown-1 skips checked |
| 5.10 | "at Central Park, want to see the Friends apartment building" → 90 Bedford St at Grove St, West Village | the start is a whole park: the skill asks once "where in Central Park?"; with no answer it uses the geocoded centre, says so, and plans from the nearest station there — one seat on the 1 (or the C) down to Christopher St-Stonewall / W 4 St |
| 5.11 | `/find-metro Mango Mango on 14th St to Roosevelt Island` — Vivek's test on the shipped skill (dictated 2026-09-14 ~02:45 EDT, written before the run) | "Mango Mango" = Mango Mango Dessert, its 14th St shop (address by search); Roosevelt Island is an area → one question "where on Roosevelt Island?", else the centre, marked — its only station is Roosevelt Island (F). Prior: one seat on the uptown F from 14 St (F M) at 6th Ave (7 stops, via 63 St) if the shop is near 6th Ave; otherwise the Q uptown from 14 St-Union Sq to Lexington Av/63 St and the F one stop. Live checks: the planned "No Jamaica-bound [F] service at 57 St, Lexington Av/63 St, Roosevelt Island …" and the E-via-63 St reroute read from `/check-delay` details and settled by the boards at S_from and Roosevelt Island; answer in the short numbered-step shape |
