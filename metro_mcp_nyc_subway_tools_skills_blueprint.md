# Metro MCP — NYC Subway Tools — Skills Blueprint

Tool list: [metro_mcp_nyc_subway_tools.md](metro_mcp_nyc_subway_tools.md) · Tool tests: [metro_mcp_nyc_subway_tools_tests.md](metro_mcp_nyc_subway_tools_tests.md) · Skill tests: [metro_mcp_nyc_subway_tools_skills_tests.md](metro_mcp_nyc_subway_tools_skills_tests.md) · Skill test results (run status, history, audit): [metro_mcp_nyc_subway_tools_skills_test_results.md](metro_mcp_nyc_subway_tools_skills_test_results.md)

## The idea

A tool answers a *tool-shaped* question ("give me every NYC incident"). A person asks an *intent-shaped* question ("is there a delay on the F?"). The gap between the two — normalising the input, choosing the call, filtering the response, phrasing the answer — is what a skill encodes:

```
human intent  →  [skill: normalise · call · filter · phrase]  →  answer
```

Skills are shipped **globally** (`~/.claude/skills/<name>/`) and scoped exactly to the intent below — nothing more. A skill whose algorithm needs code bundles that code (the implementation that ran its example tests; the examples are its proof, never its scope); a skill that is pure workflow ships as prose only.

## Vivek's taxonomy (the spec every skill must satisfy)

- **Single skill:** one skill, one or more tool calls, calls no other skill.
- **Composite skill:** calls one or more other skills — reusing the battle-tested one that already does part of the job — and, on top of that, possibly one or more tool calls of its own. A composite never re-implements what an existing skill already does. (Unix philosophy.)

## Template for an entry

- **Skill:** `/name` — path · single / composite
- **Intent:** the human question
- **Input:** what it takes; what happens with no input
- **Calls:** skills it invokes; tools it calls itself
- **Mapping:** how calls become the answer
- **Output:** the answer shape
- **Null rule:** when it returns `null`
- **Bundled files:** everything shipped besides SKILL.md
- **Tests:** numbers in the skill tests file; run status in the skill test results file

---

## 1. `/check-delay <line>` — single

- **Skill:** `~/.claude/skills/check-delay/` · single
- **Intent:** "Is there a delay on the F line?"
- **Input:** a line in any casual form. No line → ask "Which line?" once. Still none → `null`.
- **Calls:** tool `get_incidents(nyc)` — one call.
- **Mapping:** normalise the line to the feed's code (`SI` = SIR, `GS`/`FS`/`H` = shuttles, `6X/7X/FX` → base line); keep records naming it; `lmm:alert:` = live (a "Delays" alert = YES), `lmm:planned_work:` = advisories.
- **Output:** one screen — `F line — delay right now: YES/NO` (with the newest alert's stamp and how long ago), live alerts verbatim with `[type]`, planned-work count; the advisories themselves only on a follow-up "details".
- **Null rule:** no line after one ask → `null`, no tool call.
- **Bundled files:** none (prose only).
- **Tests:** 1.1–1.3.

## 2. `/get-route-info <lines…>` — composite

- **Skill:** `~/.claude/skills/get-route-info/` · composite
- **Intent:** "For each of these lines: is it delayed, and what is it?"
- **Input:** one or more lines. None → ask once. Nonsense → `null`.
- **Calls:** skill **`/check-delay <line>`** per line; tool `get_route_info(nyc, id)` per line.
- **Mapping:** per line, one block: `<id> — <longName>`, then `/check-delay`'s answer unchanged, then `Route:` = the tool's `description` verbatim.
- **Output:** one block per line, in the user's order.
- **Null rule:** no line after one ask → `null`.
- **Bundled files:** none (prose only).
- **Tests:** 2.1–2.3.

## 3. `/get-train-board <station> [line]` — composite

- **Skill:** `~/.claude/skills/get-train-board/` · composite
- **Intent:** the richer train board, before you get to the station: for a station (and a line, or every line through it) — is the line delayed, and a local picture: the few stations each side in travel order, minutes to the next train in each direction in NYC platform wording (Manhattan-bound / Brooklyn-bound / Queens-bound → terminus), where the trains are.
- **Input:** station (name or id) — none → ask "Which station?" once, still none → `null`. Line optional — none → ask "Do you have a train line in mind?" once, still none → one board per line through the station, each in its own message.
- **Calls:** skill **`/check-delay <line>`** first — its answer becomes the board's delay line, and the code refuses to draw without it. Then the bundled code, talking JSON-RPC over HTTP straight to the metro server (not through the session's MCP client, so it cannot stall the session), one call at a time: `search_stations` (name → id + lines), `get_stations_by_line` (the line's stations — always the station set), `get_station_predictions` by id (the stations in the window, plus one station per branch when a fork is in the picture).
- **Mapping (Vivek's algorithm):** (1) fetch the line's stations → (2) sort into travel order — hand-written chains (training knowledge) for the lines that fork: **A** (Lefferts Blvd / Rockaways, then Far Rockaway / Rockaway Park), **F** (53 St / 63 St), **5** (Dyre Av / Nereid Av; Flatbush Av / New Lots Av); a chain only orders the fetched stations and, at a fork, shows the branch through the station or, before the fork, the branch that has trains; geometry (spanning tree over the coordinates, longest path through the station, oriented so the feed's SOUTH direction = station ids increasing) for every other line. Known limitation (found 2026-09-14 by /plan-trip's example 5.2): a line whose station list carries two branches that are not hand-ordered — the 2, whose list holds both the Flatbush Av and New Lots Av branches — gets them spliced by geometry beyond the fork: the header can name the other branch's terminus and the "not stopping here right now" footer can name the other branch's stations. Rows up to the fork are right → (3) poll predictions in the window and thread trains by absolute arrival time → (4) draw, with `/check-delay`'s answer on top.
- **Output:** the compact board — `<line> · <station> · <HH:MM>Z`; the delay line; two header lines per direction: `<Borough>-bound` (only when the trains ahead cross into another borough) over `→ <terminus>` / `← <terminus>` (`last stop` at the end of the line); one row per station in travel order (3 each side by default; `--window=N`), minutes to the next train per direction, `now ●` = a train is there; footers only when needed: "not stopping here right now: …" (stations in the window with no predictions), "branch not shown: …" (the other fork), "no prediction data for: …" (a tool error). When nothing in the window has a prediction: "no <line> trains serving this stretch right now" and the delay line.
- **Null rule:** no station after one ask → `null`.
- **Bundled files:** `scripts/train_board.py` (stdlib only; server URL read from `~/.claude.json`; a User-Agent is set because the server answers 403 to python-urllib's default) · `data/nyc_boroughs.json` (simplified NYC borough outlines — point-in-polygon on the coordinates the tool returns gives the "-bound" word; no station data is bundled).
- **Tests:** 3.1–3.11.

## 4. `/find-nearest-station <place>` — single

- **Skill:** `~/.claude/skills/find-nearest-station/` · single
- **Intent:** "I'm around here — what's the nearest subway station?" From any NYC place — a business, landmark, street address or coordinates, even a garbled name from voice.
- **Input:** a place. None → ask "Where are you?" once. Still none → `null`.
- **Calls:** no skill. The model resolves the place to a street address (training knowledge; web search when unsure). The bundled code then geocodes the address with Nominatim (not a metro tool; bounded to the NYC area) and makes **one** metro call, `get_all_stations`, over HTTP straight to the server — the station set is fetched at run time, never bundled.
- **Mapping:** straight-line distance from the point to every station; a complex (same name within 250 m) shown once with all its lines; the nearest few with distance and a walking time at 3 mph; a note when the nearest is over a mile away.
- **Output:** the resolved place in one line, then one line per station: `0.17 mi  ~3 min walk  York St (F)  [F18]`; ends with the nearest station's name for `/get-train-board`.
- **Null rule:** no place after one ask → `null`, no tool call. A place the code cannot geocode → exit 2, one retry with a fuller address, then say so.
- **Bundled files:** `scripts/nearest_station.py` (stdlib only) · `examples/README.md` — the five dictated places it was proven on (tests 4.1–4.5), proof not scope.
- **Tests:** 4.1–4.9.

## 5. `/find-metro <from> to <to>` — composite (named `/plan-trip` while it was being tested)

- **Skill:** `~/.claude/skills/find-metro/` · composite · shipped 2026-09-14 06:39:20Z after Vivek accepted the output shape on the seven test outputs (the earlier `/plan-trip` build was removed at 05:26Z on his instruction).
- **Intent:** "Find metro from here to there" — "I'm at X and I want to get to Y, now, without leaving this session." (problem_statement.md)
- **Input:** two places (names, addresses or coordinates), from and to. One or both missing → `null`, no question. A place that is unclear (garbled, two matches, an area) → ask once; a name still unclear → `null`; an area with no answer → its geocoded centre, marked "(centre)".
- **Calls:** skills **`/find-nearest-station`** (X, then Y), **`/check-delay <line>`** per line in the route, **`/get-train-board <station> <line>`** at S_x, at the change station, and at S_y when planned work casts doubt (each board invokes `/check-delay` again for its line — accepted, one feed fetch each); tools of its own, in-session: `get_stations_by_line` (the route's stations really are on the line), `get_station_transfers` (a listed link between the change station and the other line's station, with walk minutes; in-complex vs passageway vs sidewalk is training knowledge).
- **Mapping:** the workflow in problem_statement.md — every candidate station the skill prints at each end; the route from training knowledge as a stated prior (one seat, one convenient change, or two changes when nothing shorter exists; ride ≈2 min per stop, an estimate); every leg verified by the calls above; a correction surfaces as the route given or in the Alternative line, a held prior is not announced; door-to-door from live waits plus estimated rides.
- **Output:** short numbered steps (walk, train with time and stops, change, walk), then "Delays: none" or "Delay on the <line>: why", then one optional "Alternative:" line — problem_statement.md step 5, set by Vivek 2026-09-14 ~01:40 EDT (the verbose numbered steps and the labelled three-line draft both rejected).
- **Null rule:** one or both places missing → `null`, no question, no calls; a place still unclear after one question → `null`. Either end more than a mile from any station → say the subway does not reach it, stop.
- **Bundled files:** `examples/README.md` — the seven outputs the shape was confirmed on (tests 5.1, 5.2, 5.6–5.10), byte-identical to the results file's record; proof, not scope. No code.
- **Tests:** 5.1–5.11.

---

## Lessons for every skill built on these tools

1. **Never pass a station *name* to `get_station_predictions` unless it is unique.** 76 of 379 NYC station names map to more than one id; the server returns an error for a duplicate name and Claude Code stalls on that error at a dialog. Resolve names to ids first (`search_stations`) and call by id.
2. **The station-id form works** for `get_station_predictions` (D17, D18, D19, D20, L01…L11 verified).
3. Predictions carry no train id; `minutesAway` is relative to the call time, `arrivalTime` is absolute UTC — thread trains by `arrivalTime`. The feed flags one train as `ARRIVING` at several consecutive stations; a record older than a minute is a train that has left.
4. `get_stations_by_line` returns stations sorted by id, not travel order — ordering is the skill's job. Id numbering increases along the feed's SOUTH direction.
