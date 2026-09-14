# metro-mcp

Exploring the Metro MCP server's NYC subway tools from inside Claude Code, one tool call at a time, and turning them into skills — ending in `/find-metro`, which plans a subway trip from where you are to where you are going without leaving the coding session.

## Overview

The problem this project set out to solve is in [`problem_statement.md`](problem_statement.md): you are working on a coding project, you want to get somewhere (dinner, a shop, a friend's place), and you do not want to switch context to a maps app. The coding agent should do it. The Metro MCP exposes the MTA's live data as tools; the work here is converting human intent ("I'm at X, take me to Y") into repeatable, reliable results through those tools — first by testing each tool, then by writing small single-purpose skills, then a composite skill that reuses them.

Everything is recorded in markdown: the tool tests, the skill blueprint, the skill tests (written before they are run), the results with every output and every board reproduced verbatim, and the audit tables from independent reviewer agents. The skills themselves live in `~/.claude/skills/` and are mirrored in the [claude-code-os](https://github.com/VivekKarmarkar/claude-code-os) repo; this repo is the lab notebook.

## What is here

- **Tool tests** — all seven NYC tools of the Metro MCP (`get_all_stations`, `get_incidents`, `get_route_info`, `get_station_predictions`, `get_station_transfers`, `get_stations_by_line`, `search_stations`), each called once with a stated expectation, results recorded with the raw JSON.
- **A skill taxonomy and blueprint** — *single* skills (one skill, one or more tool calls, no other skill) and *composite* skills (call other skills, never re-implement them), with one entry per shipped skill and the lessons learned (for one: a station *name* shared by several stations must never go to `get_station_predictions`, it stalls the session).
- **Five shipped skills**, tested here and installed globally:
  - `/check-delay <line>` — is there a delay on the F right now? One `get_incidents` call, live alerts separated from planned work.
  - `/get-route-info <lines>` — composite: `/check-delay` per line plus the line's timetable text from `get_route_info`.
  - `/get-train-board <station> [line]` — composite: `/check-delay` plus a bundled script that draws a compact board (stations in travel order, minutes to the next train each way in platform wording, where the trains are).
  - `/find-nearest-station <place>` — any NYC place, even a garbled name from voice, to its nearest stations with walk times (Nominatim geocoding plus one `get_all_stations` call).
  - `/find-metro <from> to <to>` — composite: nearest stations at both ends, a route from training knowledge as a prior, every leg verified live (delays, reroutes, express or local, next trains), answered as a few short numbered steps.
- **Skill tests and results** — 1.1 through 5.11, including the seven worked trips `/find-metro` was proven on and two rounds of adversarial audits with every finding and its fix.
- **Plots** — the NYC subway map reconstructed from `get_all_stations` on a rotated base map of borough and county outlines, an F-line strip map with live train positions, and per-station boards; the scripts that made them are in `plots/`.

## Getting started

### Prerequisites

- [Claude Code](https://claude.com/claude-code).
- The Metro MCP registered at user scope:
  ```bash
  claude mcp add --scope user --transport http metro https://metro-mcp.anuragd.me/mcp
  ```
- Python 3.10 for the bundled skill scripts (standard library only) and, for the plots, a virtual environment with `matplotlib`, `numpy` and `scipy`.

### Installing the skills

Copy the five skill folders from the claude-code-os repo into `~/.claude/skills/`:

```bash
git clone https://github.com/VivekKarmarkar/claude-code-os
for s in check-delay get-route-info get-train-board find-nearest-station find-metro; do
  cp -r claude-code-os/skills/$s ~/.claude/skills/
done
```

### Usage

Inside a Claude Code session:

```
/check-delay F
/get-route-info F C
/get-train-board York St F
/find-nearest-station Eileen's cheesecake
/find-metro Fontainhas to Hyderabadi Zaiqa on 9th Ave
```

`/find-metro` answers in the shape confirmed on the seven test trips:

```
**Fontainhas → Hyderabadi Zaiqa** (12:22 AM, about 33 min)
1. Walk 7 min to High St.
2. A to Manhattan, 12:32 AM. 10 stops to 50 St.
3. Walk 4 min.
Delay on the A: maintenance in Manhattan.
Alternative: F from York St to W 4 St, then E or A uptown to 50 St. About 46 min; E and F delayed too.
```

Both places are required; one or both missing returns `null`. An unclear place gets one question.

### The plots

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install matplotlib numpy scipy
python plots/make_nyc_subway_map_test2_v2.py      # the subway map on its base map
python plots/f_strip_map.py                        # F-line strip map with live trains
python plots/station_board.py "York St" F          # a station board, text + PNG under plots/boards/
```

The plot scripts talk to the Metro MCP directly over HTTP (JSON-RPC), one call at a time, the same tools as in the session.

## Project structure

```
problem_statement.md                                   the problem, the workflow, the output shape, "Done means"
metro_mcp_nyc_subway_tools.md                          the seven NYC tools
metro_mcp_nyc_subway_tools_tests.md                    tool tests 1–8, written before they were run
metro_mcp_nyc_subway_tools_test_results.md             tool test results
metro_mcp_nyc_subway_tools_test*_*.json                raw tool output from the tests
metro_mcp_nyc_subway_tools_skills_blueprint.md         taxonomy, one entry per skill, lessons
metro_mcp_nyc_subway_tools_skills_tests.md             skill tests 1.1–5.11
metro_mcp_nyc_subway_tools_skills_test_results.md      every run's outputs, boards, corrections, audits
context_anchor.md                                      the project's timestamped decision log, in the author's words
plots/                                                 map, strip map and board scripts and their outputs
plots/geo/                                             NYC Planning borough polygons, Census county outlines
```

## Tech stack

- Claude Code skills (markdown), single and composite.
- Metro MCP over HTTP (JSON-RPC 2.0); the bundled scripts set a `User-Agent`, because the server answers 403 to Python's default.
- Python 3.10, standard library only, for the skill scripts; matplotlib, numpy, scipy for the plots.
- OpenStreetMap Nominatim for geocoding (no key); NYC Planning borough boundaries and Census 1:500k county outlines for the base map.

## Contributing

This is a lab notebook for one exploration; issues and PRs are welcome if you find a tool behaviour or a skill result that does not match what is recorded here.
