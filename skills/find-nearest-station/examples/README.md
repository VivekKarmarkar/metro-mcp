# find-nearest-station — the examples it was proven on

Vivek dictated five places by voice on 2026-09-13 (names garbled by transcription) and knew the right station for each. Every one came out right (skills tests 4.1–4.5 in the metro-mcp project). They are kept here as proof that the method generalises; the code has no knowledge of them.

| dictated | resolved to (Step 2) | command (Step 3) | nearest |
|---|---|---|---|
| "Fontaine Has", Indian chai shop, DUMBO | Fontainhas, 28 Jay St, Brooklyn | `nearest_station.py "28 Jay St, Brooklyn"` | York St (F) 0.17 mi |
| "Aileen's cheesecake" | Eileen's Special Cheesecake, 17 Cleveland Pl, Manhattan | `nearest_station.py "17 Cleveland Pl, Manhattan"` | Spring St (6) 0.05 mi |
| "Punjabi Delhi, East Village" | Punjabi Grocery & Deli, 114 E 1st St, Manhattan | `nearest_station.py "114 E 1st St, Manhattan"` | 2 Av (F) 0.18 mi |
| "Kaatirol company, close to Times Square" | The Kati Roll Company, 49 W 39th St, Manhattan (other branches: 229 E 53rd St, 99 MacDougal St, 22 Maiden Ln) | `nearest_station.py "49 W 39th St, Manhattan"` | 42 St-Bryant Pk (B D F M) 0.10 mi |
| "Sarwana Bhavan on Lexington Avenue" | Saravanaa Bhavan, 81 Lexington Av, Manhattan | `nearest_station.py "81 Lexington Ave, Manhattan"` | 28 St (6) 0.13 mi |

Vivek's note on 4.2: he usually walks to Broadway-Lafayette St / Bleecker St (the bigger station), but Spring St is the nearest.
