# Problem statement — "I'm at X, I want to get to Y"

Dictated by Vivek 2026-09-13 (terminal voice; transcript reconciled — "s survived" = S_y, "the wire station" = the Y station). This file holds the problem. The workflow to solve it, the tests, the skills shipped from it and the other markdown files come after, in that order.

## The problem (Vivek's words, reconciled)

I'm at location X and I want to go to location Y. I want to solve this **without switching context**: I'm busy on a Claude Code project, in a Claude Code session. I don't want to open Google Maps, call people, figure out which the nearest station is, walk there and look at the times, switch apps — nothing. I stay in the session and I want the answer **now**.

## What the answer looks like (Vivek's sketch)

1. Run `/find-nearest-station` on X (the departure point) → **S_x**, the departure station. Run it on Y (the arrival point) → **S_y**, the arrival station. There is also getting from X to S_x and from S_y to Y.
2. Which train lines pass through S_x? `/get-train-board` tells you the lines through a station, the delays on them, and when the trains are coming. Get the board for S_y too, so you know whether the same line can be used.
3. If not, you have to change somewhere: one of the lines from S_x meets one of the lines arriving at S_y. The full station list of a line (we already fetch it) gives the intersection station. It may be more complicated: more than one exchange point, or a route with more changes that is quicker.
4. **Training data is the prior.** From the place names alone, Claude should already have an idea of the nearest stations, of S_x and S_y, of a plausible route, and of the *elegant* exchange points — the ones that are convenient for the traveler. That prior does not reflect today. The tools and skills are what tell you, right now, whether there is a delay, whether a line has been rerouted, what is actually running. So: use the prior as the starting point, use the skills and tools to verify and correct it, and get to a final answer — quickly.

## What we already have (Claude's mapping, subordinate to the above)

| piece | gives |
|---|---|
| `/find-nearest-station` (single) | S_x and S_y with distance, walk time, lines through each |
| `/get-train-board` (composite) | the lines through a station (`--lines`); per line: delay status via `/check-delay`, the next trains in each direction, the local strip with "not stopping here right now" (express / reroute / not running) |
| `/check-delay` (single) | live alerts and planned reroutes per line |
| `/get-route-info` (composite) | the line's timetable text: hours, express/local, weekday vs night/weekend routing |
| `get_stations_by_line` (called by get-train-board's code) | a line's full station list → where two lines meet |
| `get_station_transfers` (Test 8; parked until now) | for a station id, the ids you can walk to inside the complex or by passageway, with walk minutes → whether an exchange point is convenient |
| `get_station_predictions` by id (get-train-board's code) | actual next trains at any station, including a transfer station |

## Open questions — to settle when the workflow is defined (nothing decided yet)

- **Prior vs. verification:** what comes from training knowledge (candidate S_x, S_y, route, transfer points) and exactly which skill or tool verifies each part (a line's delay/reroute; that the transfer station is served right now; next-train times at S_x and at the transfer).
- **Transfers:** candidate exchange points from line intersections, filtered by `get_station_transfers` (same complex / passageway) and by training knowledge of the convenient ones; routes with more than one change; how alternatives are compared (fewest changes vs. quickest).
- **Live corrections:** planned-work reroutes change which stations a line serves ("F via 53 St", "no D between 34 St-Herald Sq and Atlantic Av"); the board's "not stopping here right now" already exposes this station by station.
- **Output shape:** X → walk → S_x (line, direction, next train, minutes) → [change at T, walk minutes] → S_y → walk → Y, with the delay line per leg; phone-readable, one screen.
- **The skill:** a composite that invokes `/find-nearest-station` twice, `/get-train-board` / `/check-delay` per leg, plus its own tool calls — named and specified in the blueprint before it is built.

## Next (Vivek's order)

1. Define the workflow — in this file.
2. Test it on real X → Y pairs (tests written before they are run).
3. Ship the skill(s) from it, bundling the tested code; examples as proof, never as scope.
4. Populate the other markdown files: blueprint, skills tests, skills results, context anchor.

---

## Workflow — `/find-metro <from> to <to>` (composite; called `/plan-trip` while under test) — defined 2026-09-14 03:06Z, revised 03:25Z after the audit

Prior first, then verification, then the answer. The composite's own metro calls are made in-session, one at a time; the skills it invokes make their calls from their own code over HTTP. Station names never go to `get_station_predictions`. Nothing an existing skill does is re-implemented — the composite invokes it.

0. **Input.** X and Y: places, addresses or coordinates, from and to. One or both missing → `null`, no question (Vivek, ~01:50 EDT: "even if one argument is not given, return null"). A place that is unclear → ask once; still unclear → `null`; an area with no answer → its centre, marked.
1. **Stations.** Invoke `/find-nearest-station X` and `/find-nearest-station Y`. Keep **every candidate the skill prints** (four by default) at each end, with lines and walk minutes — the nearest station is not always the best one: a few more minutes' walk can save a change. If the skill prints its "more than a mile away" note for either end, say the subway does not reach that place and stop.
2. **Prior (training knowledge).** From the candidates' lines, propose up to two routes: a one-seat ride if a candidate pair shares a line; otherwise one change at a convenient station T — same complex or passageway, cross-platform when known. If no candidate pair gives one seat or one change, propose a two-change route the same way, or one change plus a longer walk, whichever is shorter door to door. For each route: line, direction in platform wording (Manhattan-bound / Brooklyn-bound / Queens-bound / Bronx-bound, uptown / downtown inside Manhattan), the stops, T, and an estimated ride at ≈2 min per stop, stated as an estimate. These are priors, held in your head, never written to the user; do not invent stations or transfers. Lines that do not run at this hour are not proposed — training knowledge, a prior like the rest; when in doubt the board decides.
3. **Verify** with the tools and skills, in this order:
   - `/check-delay <line>` for each line in the route; when planned work is counted, apply check-delay's "details" rule yourself on the feed it just fetched (no second call) and scan the advisories for the route's stations and direction (a suspended segment kills a route; "runs approximately every N minutes" sets the wait). Each `/get-train-board` below invokes `/check-delay` again for its line — accepted: one feed fetch each, and get-train-board's contract stays intact.
   - `mcp__metro__get_stations_by_line {"city":"nyc","lineCode":"<line>"}` — the composite's own call — for each line: S_x, T and S_y must all be in the list (ids come from `/find-nearest-station`'s output and from this list). A wrong prior fails here. The list is id-sorted, not travel order; a late-night list can carry another line's local stops and both of a line's branches — information, not an error.
   - `mcp__metro__get_station_transfers {"city":"nyc","stationId":"<T's id>"}` — the composite's own call — when there is a change: the other line's station must be listed, with `walkTimeMinutes`. The tool proves a listed link and its walk time; whether it is in-complex, a passageway or a sidewalk is training knowledge (its only `transferType` value is "nearby"). Not listed → treat the change as a street walk, or pick another T.
   - `/get-train-board S_x <line>` → the line stops at S_x right now, the direction header, the next train toward T or S_y. `/get-train-board T <line 2>` → the next train toward S_y. `/get-train-board S_y <line 2>` when planned work casts doubt on the far end, or when the line skips S_y by day ("no <line> trains serving this stretch right now" ends that route). Boards are asked by station id (from the nearest-station listing). When the next train is beyond the board's window, run the board again with a wider `--window=N` before calling the following train an estimate. What the invoked skills print is read, not shown.
   - Reading the boards: the "not stopping here right now" footer, or local stops in the window showing far-away minutes while S_x shows a near train, means the line is running express there right now (fewer stops, shorter ride). If the walk to S_x is longer than the next train's minutes, plan on the following train (headway from an advisory, or from the board's spacing, or stated as an estimate). get-train-board hand-orders the forks of the A, F and 5 only; for a line whose station list carries two branches (the 2 in Brooklyn), the board's header terminus can be the other branch and a "not stopping here right now" footer can name the other branch's stations — a board artefact, not a service fact; use platform wording and ignore that footer beyond the fork.
4. **Correct.** If a check fails (not on the line, not served now, reroute, awkward change), fall back to the second route or re-propose from the candidates, re-verify what changed. What was corrected goes into the Alternative line, or nowhere; a prior that held is not announced.
5. **Answer** — short numbered steps, one glance. Vivek, 2026-09-14 ~00:45 and ~01:40 EDT: "one glance at the screen … the primary option, whether there is a delay or not, and an alternative option if you would like, in minimal words"; the labelled three-line draft ("Take: …") was "incomprehensible" — labels and comma-chained lines are out.
   ```
   **X → Y** (HH:MM AM/PM, about T min)
   1. Walk N min to S_x.
   2. <Line> <direction>, HH:MM. K stops to T.
   3. Change to the <line 2> <direction>, M-min walk. K2 stops to S_y.
   4. Walk N2 min.
   Delays: none.        or        Delay on the <line>: <why, a few words>.
   Alternative: <one line, only when there is one worth taking>.
   ```
   Each step one short line, at most two sentences. Times are the rider's clock (New York); "about" marks an estimate (a headway, a derived arrival), a bare time comes from a board. If the first train leaves before the walk gets you there, name the one you can catch ("12:37 AM if you hurry, else about 12:56"). A stop on the way is a step ("Walk 3 min along Bleecker to Magnolia."), with when to leave it. An area start or end is marked in the title, "X (centre)"; "where in X?" is asked once in the reply. What the tools corrected goes into Alternative, or nowhere. The numbered-step-with-sentences shape (00:15 EDT) and the three-line shape (00:45 EDT) are superseded; the results file keeps them as the record.

## Done means (the stopping criteria for the `/goal` on this file)

1. The workflow above exists in this file, and the shipped skill mirrors it.
2. Tests 5.1–5.5 are written in `metro_mcp_nyc_subway_tools_skills_tests.md` before any of them is run.
3. Two of them (5.1, 5.2) are run end to end by following the workflow, and their evidence trail — the skills' actual outputs, the tool results and the boards, with transcript times — is recorded in `metro_mcp_nyc_subway_tools_skills_test_results.md`.
4. `/find-metro` is shipped globally at `~/.claude/skills/find-metro/` as a composite: it invokes `/find-nearest-station`, `/check-delay` and `/get-train-board`, makes its own `get_stations_by_line` and `get_station_transfers` calls, bundles the seven test outputs as proof, and requires or looks up no place, station or route of its own — shipped 2026-09-14 06:39:20Z, after Vivek accepted the output shape (the `/plan-trip` build shipped during the /goal run was removed at 05:26Z on his instruction: he had asked to wait for that).
5. Blueprint entry 5, the skills tests file, the skills results file and `context_anchor.md` are updated.
6. A workflow of independent auditors has checked the result against this file and the blueprint; findings fixed and recorded.
7. Vivek has the worked examples in the reply; he tests on his end.
