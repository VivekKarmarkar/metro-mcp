---
name: get-route-info
description: Composite skill for one or more NYC subway lines — invokes /check-delay per line for "is it delayed right now" and calls the metro MCP get_route_info tool itself for what the line is (name, endpoints, hours, express/local pattern). Use whenever the user names one or several NYC subway lines and wants to know about them — "tell me about the F and the C", "what's the deal with the 7 today", "status and info for A, C, E", "which of these lines is delayed and where do they run" — or types /get-route-info. Takes one or more lines; with none it asks once; if the reply still names no line it returns null. NYC only.
---

# get-route-info

One question, one skill plus one tool: *"for each of these lines, is it delayed right now, and what is it?"*

- **Delay right now** comes from invoking **`/check-delay <line>`** for each line — this skill composes that skill; it does not re-implement it.
- **What the line is** comes from `get_route_info(city=nyc, routeId=…)` — static timetable text: long name, endpoints, hours, express/local pattern. It says nothing about current conditions, which is why the two are paired.

## Arguments

`<line> [<line> ...]` — one or more NYC subway lines, separated by spaces, commas, "and". Any casual form works (`F`, `the F train`, `[C]`, `SIR`, `7 express`).

Examples:
- `/get-route-info F`
- `/get-route-info F C`
- `/get-route-info the F, the C and the 7`
- `/get-route-info` — no lines: ask once (Step 1)

## Workflow

### Step 1 — Resolve the lines

1. Split the input into tokens; decide which are lines with check-delay's code map (read it in `~/.claude/skills/check-delay/SKILL.md` — it is not copied here). Keep the ones that map to a line; note the ones that don't.
2. **At least one valid line** → proceed with those. If some tokens were dropped, say so in one line at the top of the answer ("ignored: xyz").
3. **No input, or nothing maps to a line** → ask exactly once, plainly: *"Which line(s)?"* Stop and wait.
4. **The reply still names no line** (empty, "none", "never mind", nonsense) → output the literal word `null` and stop. No tool calls. Don't guess.

`get_route_info` accepts these route ids: `A B C D E F G J L M N Q R W Z 1 2 3 4 5 6 7 SI`. Express variants (`6X 7X FX`) use their base id. The shuttles (`GS`, `FS`, `H`) are not in that list — for them, still report the delay part and say route info isn't available from the tool.

### Step 2 — per line, in the user's order, one at a time

1. Invoke **`/check-delay <line>`** and keep its answer (the delay lines).
2. Call `mcp__metro__get_route_info` with `{"city": "nyc", "routeId": "<id>"}` — one call, not batched.

If a call errors or hangs, say which one and stop; don't retry silently.

### Step 3 — Answer, one block per line

```
F — Queens Blvd Express/6 Av Local
F line — delay right now: YES   (newest alert 22:09Z, ~1 h 39 min ago)
• [Delays] Uptown [F] trains are running with delays while we perform track maintenance near Ditmas Av.
Planned work on the F: 16 advisories (not delays) — say "details" if you want them.
Route: Trains operate at all times between Jamaica-179 St, Queens, and Coney Island-Stillwell Av, Brooklyn. On weekdays, trains operate via 53 St … (description verbatim)

C — 8 Avenue Local
C line — delay right now: NO   (no live alerts for the C)
Planned work on the C: 9 advisories — say "details" if you want them.
Route: Trains operate between 168 St, Manhattan, and Euclid Av, Brooklyn, daily from about 6 AM to 11 PM.
```

Rules:
- The first line of each block is `<id> — <longName>` from `get_route_info`.
- The delay lines are `/check-delay`'s answer for that line, pasted unchanged — it already carries the yes/no, the alert texts, the "ago" figure and the planned-work count.
- `Route:` is the tool's `description` verbatim — it is the MTA's own timetable text and is already written for riders. Don't paraphrase it, don't trim it.
- Blocks in the user's order, separated by a blank line. Nothing after the last block.

## Notes

- Composition: this skill invokes `/check-delay` once per line, then adds one `get_route_info` call. It bundles no code. Rebuilt as a real composition 2026-09-13; description and example brought in line with check-delay's real output the same day.
- Built 2026-09-12 from Tests 3 and 4 of the metro-mcp project (see `metro_mcp_nyc_subway_tools_skills_blueprint.md` there).
