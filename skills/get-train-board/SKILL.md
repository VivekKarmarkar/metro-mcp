---
name: get-train-board
description: The richer train board for a NYC subway station, before you get there — for a station (and a line, or every line through it), a compact board: is the line delayed, and the few stations each side in travel order with minutes to the next train in each direction in NYC platform wording (Manhattan-bound, Brooklyn-bound, Queens-bound → terminus), trains marked. Use whenever the user names a NYC subway station and wants to know what's coming, how long until the train, what's the deal at or around a station, "F at Roosevelt Island", "should I leave now for the train", or types /get-train-board. Composite: invokes /check-delay for the delay status; its bundled code calls search_stations, get_stations_by_line and get_station_predictions. Station required (ask once, then null); line optional (ask once, then one board per line through the station).
---

# get-train-board — composite

Composite skill: it **invokes `/check-delay`** for the delay status, and its bundled code makes the three tool calls Vivek's algorithm needs (station lookup, the line's stations, predictions). It never re-implements check-delay, and the code refuses to draw a board without check-delay's answer.

```
/check-delay <line>                               → the delay answer
scripts/train_board.py "<station>" <LINE> --delay="<that answer, lines joined with ' · '>"
   1 search_stations        name → id + lines through it
   2 get_stations_by_line   the line's stations — always the station set
   3 sort into travel order hand-written chains for the lines that fork (A, F, 5): they only ORDER the fetched
                            stations and, at a fork, show the branch through the station or the one with trains;
                            every other line: spanning tree over the coordinates → longest path through the station
   4 get_station_predictions by id, one call at a time, at the stations around the one asked for
   5 draw the board
```

## Arguments

`<station> [line]` — station name (or id); optional line code (`SIR` is accepted for `SI`).

## Workflow

### Step 1 — the station
- Given → go on.
- Not given → ask once: *"Which station?"* Still none → output `null` and stop.

### Step 2 — the line
- Given → one board.
- Not given → ask once: *"Do you have a train line in mind?"* A line named → one board. Still none → run
  `python3 ~/.claude/skills/get-train-board/scripts/train_board.py "<station>" --lines` to get `LINES: …`, then one board **per line**, each in its own message (own code block; own reply on Telegram).

### Step 3 — per line
1. Invoke **`/check-delay <LINE>`**. Take its whole answer and join its lines with ` · ` (headline · live alert texts · planned-work count). That string is the `--delay` value — pass it unchanged.
2. Run:
   ```bash
   python3 ~/.claude/skills/get-train-board/scripts/train_board.py "<station>" <LINE> --delay="<that string>"
   ```
3. Print the output verbatim in a code block. Nothing else — no summary, no advice.

Exit code 2 = the script says why: the line doesn't stop at that station (it lists the lines that do — say that), the name matches several stations on that line (ask which), `--delay` is missing (go back to 1), or a tool error. **On a tool error, report it and stop. Never call `get_station_predictions` or `search_stations` in-session as a fallback: a station name shared by several stations stalls the session (blueprint, Lesson 1).**

## Reading the board (for you, not to print)
- Header, two lines: `<Borough>-bound` (present only when the trains ahead cross into another borough) over `→ <terminus>` / `← <terminus>`; `last stop` when the station is the end of the line.
- Rows = stations in travel order, 3 each side by default (`--window=N` changes it), `▸` = the one asked for. Left column = trains heading to the left header's terminus; right column = the other way.
- `now ●` = a train is there; `—` = nothing in that direction right now; "not stopping here right now" = the line is skipping that station (express, other branch, not running there at this hour); "branch not shown" = the line forks inside the picture and the other fork is named; "no prediction data for" = the tool errored for that station.

## Files
- `scripts/train_board.py` — the bundled code (stdlib only). It talks JSON-RPC over HTTP straight to the metro server, one call at a time — not through the session's MCP client, so it cannot stall the session. Server URL from `~/.claude.json` (`mcpServers.metro.url`, the known URL as fallback); a `User-Agent` is set because the server answers 403 to python-urllib's default.
- `data/nyc_boroughs.json` — simplified NYC borough outlines (NYC Planning boundaries, 30 m tolerance). Point-in-polygon on the coordinates the tool returns gives the borough for the "-bound" word. No station data is bundled.
- Spec: metro-mcp project, `metro_mcp_nyc_subway_tools_skills_blueprint.md` entry 3; tests in `metro_mcp_nyc_subway_tools_skills_tests.md`.
