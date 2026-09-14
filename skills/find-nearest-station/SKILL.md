---
name: find-nearest-station
description: "I'm around here — what's the nearest subway station?" For any place in New York City — a restaurant, shop, landmark, street address, or coordinates, even a garbled name from voice — resolve it to a street address and report the nearest subway stations with distance, walking time and lines. Use whenever the user names a NYC place and wants to know which station to walk to, "nearest train to X", "how do I get to the subway from here", or types /find-nearest-station. Single skill: the model resolves the place (training knowledge + web search), the bundled code geocodes the address and makes one metro MCP get_all_stations call. Place required (ask once, then null). NYC only.
---

# find-nearest-station — single

Single skill: it invokes no other skill. The model turns the place into a street address; the bundled code turns the address into coordinates (Nominatim) and makes **one** metro MCP tool call, `get_all_stations`, at run time — the station set is never bundled.

```
place (as said)  →  street address (you: training knowledge, web search when unsure)
scripts/nearest_station.py "<address>"   →  Nominatim geocode → get_all_stations → nearest N by distance
```

## Arguments

`<place>` — anything that names a spot in NYC: a business ("Eileen's cheesecake"), a landmark ("Brooklyn Museum"), a street address ("49 W 39th St"), or coordinates ("40.7484,-73.9857"). Voice transcripts garble names; treat the text as a lossy proxy and use the user's hints (borough, neighborhood, cuisine).

## Workflow

### Step 1 — the place
- Given → go on.
- Not given → ask once: *"Where are you (or where are you going)?"* Still none → output `null` and stop.

### Step 2 — resolve it to a street address (you)
- Already an address or coordinates → use as is.
- A name → find the business or landmark and its street address with number, street and borough. Use training knowledge; when unsure, or the name looks garbled, **WebSearch** it with the user's hints. Never invent an address or coordinates.
- Several branches in NYC → pick the one matching the hints (e.g. "near Times Square"); name the others in one line.
- Say in one line what you resolved the place to: `"Aileen's cheesecake" → Eileen's Special Cheesecake, 17 Cleveland Pl, Manhattan`.

### Step 3 — one run of the bundled code
```bash
python3 ~/.claude/skills/find-nearest-station/scripts/nearest_station.py "<street address, borough>"    # or "lat,lon"
```
- Print its output verbatim in a code block (resolved point, then one line per station: distance, walk time, name, lines, ids).
- Exit 2 with "could not geocode" → go back to Step 2 and give it a fuller street address (number + street + borough), once. Still failing → say so and stop.
- Exit 2 with a tool error → say so and stop. Do not call the metro tools in-session as a fallback.

### Step 4 — close
End with the nearest station's name on its own line so the user can run `/get-train-board <station>` on it. Nothing else — no route advice.

## Null rule
No place after one ask → `null`, no tool call.

## Files
- `scripts/nearest_station.py` — the bundled code (stdlib only). Nominatim for geocoding (bounded to the NYC area; one request), the metro server for stations (JSON-RPC over HTTP, URL from `~/.claude.json`, User-Agent set because the server 403s python-urllib's default). Straight-line distance; a note when the nearest station is over a mile away.
- `examples/README.md` — the five dictated test cases this skill was built and proven on (metro-mcp project, skills tests 4.1–4.5). Proof of generality, not a lookup table: nothing in the code knows these places.
- Spec: metro-mcp project, `metro_mcp_nyc_subway_tools_skills_blueprint.md` entry 4.
