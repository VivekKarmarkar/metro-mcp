---
name: find-metro
description: >-
  "/find-metro <from> to <to>" — a NYC subway trip from where you are to where you are going, planned without leaving the session: the nearest stations at both ends, the route (one seat, one convenient change, or two when nothing shorter exists), every leg checked against right now (delays, reroutes, express or local, the next trains), answered as a few short numbered steps. Use when the user names two NYC places and wants to get from one to the other: "find metro from X to Y", "how do I get from X to Y", "I'm at X, going to Y", or types /find-metro. Composite: invokes /find-nearest-station at both ends, /check-delay for each line and /get-train-board for each leg, and makes its own get_stations_by_line and get_station_transfers calls. Both places required; one or both missing → null. NYC only.
---

# find-metro — composite

Composite skill: it **invokes** `/find-nearest-station` (from, then to), `/check-delay` (each line in the route) and `/get-train-board` (each leg), and makes two tool calls of its own, `get_stations_by_line` and `get_station_transfers`. It re-implements none of those skills and bundles no code. Training knowledge supplies the route as a **prior**; the skills and tools verify or correct it for **today**. This file mirrors the workflow in the metro-mcp project's `problem_statement.md`; that file is the spec. What the invoked skills print — the station listings, the delay answers, the boards — is read, not shown: none of it goes into the reply, whatever those skills' own "print verbatim" rules say.

```
/find-nearest-station <from>, /find-nearest-station <to>   → candidate stations at each end (all the skill prints), with ids
prior (you)                                                 → one seat · one change at T · two changes if nothing shorter
/check-delay <line>  ×lines                                 → live alerts; the planned-work advisories scanned for the route
mcp__metro__get_stations_by_line  ×lines   (own call)       → S_from, T, S_to really are on the line
mcp__metro__get_station_transfers <T id>   (own call)       → a listed link T ↔ other line's station, walk minutes
/get-train-board <id> <line> at S_from, T, S_to if in doubt → served right now, express or local, next trains
answer                                                      → short numbered steps, one glance — the reply is that block alone
```

## Arguments

`<from> to <to>` — two places: names, street addresses or coordinates, in any casual form ("from X to Y", "X → Y", "I'm at X, going to Y").

## Workflow

### Step 0 — the places
- Both given and clear → go on.
- **One or both missing → output the literal word `null` and stop.** No question, no calls.
- A garbled name that search resolves to one place is clear: pass it on as resolved; a second, less likely match is named in the Alternative line, not asked about.
- A place that is not clear — a name search cannot settle, or an area rather than a point (a park, a neighbourhood) — → ask once, plainly ("<name> in <area> or <other name> in <other area>?", "Where in <the area>?"). A name still unclear after the reply → `null`. An area with no answer (the reply names no point — "anywhere", "just go", "don't know") → its geocoded centre, marked "(centre)" in the title.

### Step 1 — stations (invoke, twice)
Invoke `/find-nearest-station <from>`, then `/find-nearest-station <to>`. Keep **every candidate the skill prints** (four by default) at each end, with lines, walk minutes and the station ids in brackets: the nearest station is not always the best one, a few more minutes' walk can save a change. If the skill prints its "more than a mile away" note for either end, say the subway does not reach that place and stop.

### Step 2 — the prior (you, training knowledge — held in your head, never written to the user)
From the candidates' lines, propose up to two routes:
- **one seat** if a candidate pair shares a line;
- otherwise **one change** at a convenient station T — same complex or passageway, cross-platform when you know it;
- if no candidate pair gives one seat or one change, **two changes**, or one change plus a longer walk — whichever is shorter door to door.

For each route: line, direction in platform wording (Manhattan-bound / Brooklyn-bound / Queens-bound / Bronx-bound, uptown / downtown inside Manhattan), the stops, T, and an estimated ride at ≈2 min per stop. Do not invent stations or transfers — anything you are unsure of is exactly what Step 3 checks. Lines that do not run at this hour are not proposed — training knowledge, a prior like the rest; when in doubt the board decides.

### Step 3 — verify (the composite's own metro calls in-session, one at a time, in this order)
1. **`/check-delay <line>`** for each line in the route. If planned work is counted, apply check-delay's "details" rule yourself — list the advisories from the feed it just fetched, no second call and no second invocation — and scan them for the route's stations and direction: a suspended segment kills a route; "runs approximately every N minutes" sets the wait. (Each `/get-train-board` in item 4 below invokes `/check-delay` again for its line — accepted: one feed fetch each.)
2. **`mcp__metro__get_stations_by_line {"city":"nyc","lineCode":"<line>"}`** — your own call — for each line: S_from, T and S_to must all be in the list (ids come from `/find-nearest-station`'s output and from this list). A wrong prior fails here. The list is id-sorted, not travel order; a late-night list can carry another line's local stops and both of a line's branches — information, not an error.
3. **`mcp__metro__get_station_transfers {"city":"nyc","stationId":"<T's id>"}`** — your own call — when there is a change: the other line's station must be listed, with `walkTimeMinutes`. The tool proves a listed link and its walk time; whether it is in-complex, a passageway or a sidewalk is training knowledge (its only `transferType` value is "nearby"). Not listed → treat the change as a street walk, or pick another T.
4. **`/get-train-board <S_from's id> <line>`** (the id from Step 1's listing — get-train-board takes an id; a name shared on that line makes it stop and ask which) — the line stops at S_from right now, the direction header, the next train toward T or S_to. **`/get-train-board <T's id> <line 2>`** — the next train toward S_to. **`/get-train-board <S_to's id> <line 2>`** when planned work casts doubt on the far end, or when the line skips S_to by day; "no <line> trains serving this stretch right now" ends that route. When the next train is beyond the board's window, run get-train-board's `train_board.py` command again with a wider `--window=N` added after `--delay=…` (the window is a flag of its script, not an argument the skill takes) before calling the following train an estimate.

Reading the boards: the "not stopping here right now" footer, or local stops in the window showing far-away minutes while S_from shows a near train, means the line is running **express** there right now (fewer stops, shorter ride); a "—" column on one side means no trains that way at those stations right now. If the walk to S_from is longer than the next train's minutes, plan on the following train (from a wider board, from an advisory's headway, or stated as an estimate). For a line whose station list carries two branches, or another line's stations at night, the board's header terminus can be wrong and a "not stopping here right now" footer can name the other branch's stations (get-train-board's own SKILL.md names the forks its code orders by hand) — a board artefact, not a service fact: use platform wording and ignore that footer beyond the fork.

### Step 4 — correct
Any check fails (not on the line, not served now, reroute, awkward change, the clock) → fall back to the second route or re-propose from the candidates, re-verify what changed. A prior that held is not announced; a correction shows up only as the route given, or in the Alternative line.

### Step 5 — answer: short numbered steps, one glance (the shape Vivek confirmed 2026-09-14 ~01:50 EDT)
```
**X → Y** (HH:MM AM/PM, about T min)
1. Walk N min to S_from.
2. <Line> <direction>, HH:MM. K stops to T.
3. Change to the <line 2> <direction>, M-min walk. K2 stops to S_to.
4. Walk N2 min.
Delays: none.        or        Delay on the <line>: <why, a few words>.
Alternative: <one line, only when there is one worth taking>.
```
- The reply is this block alone — nothing before the title: no narrated prior, no list of what was checked, none of the invoked skills' printouts; nothing after the Alternative line.
- Each step one short line, at most two sentences. No labels other than "Delays" / "Delay on the …" and "Alternative", no comma-chained clauses.
- Times are the rider's clock (New York, from `TZ=America/New_York date`); the title carries the check time and the door-to-door estimate. "About" marks an estimate (a headway, a derived arrival); a bare time comes from a board.
- If the first train leaves before the walk gets you there, name the one you can catch: "HH:MM if you hurry, else about HH:MM".
- A trip with a stop on the way is one plan: the stop is a step ("Walk N min to <the stop>."), with when to leave it ("Leave <the stop> by HH:MM."). A leg under ~15 min on foot is a walk, not a train.
- An area start or end is marked in the title, "X (centre)".
- The Delay line names only the rider's lines and direction; an alert for the other direction is "Delays: none your way (<line> delays are <the other direction>)". A delayed alternative says so in its line.

On a tool error in any skill: report it and stop. Never call `get_station_predictions` or `search_stations` in-session (a shared station name stalls the session).

## Null rule
One or both places missing → `null`, no question, no calls. A place still unclear after one question → `null`.

## Files
- `examples/README.md` — the seven outputs this shape was confirmed on (tests 5.1, 5.2, 5.6–5.10), byte-identical to the metro-mcp project's results file, where every run's skill outputs, tool results and boards are recorded with transcript times. Proof of the method, not a lookup table: no place, station or route in this file is required or looked up by the skill.
- Spec and workflow: metro-mcp project, `problem_statement.md` and `metro_mcp_nyc_subway_tools_skills_blueprint.md` entry 5; tests 5.1–5.11 in `metro_mcp_nyc_subway_tools_skills_tests.md`.
