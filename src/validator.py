"""Mzansi Rush — map validator.

Usage:
    python3 src/validator.py data/mzansi_asphalt.json
    python3 src/validator.py --all          # validate every track in data/

Checks performed (E=error stops the race, W=warning):
  [E] Schema compliance          (world_schema.json)
  [E] Grid dimensions match grid_size
  [E] No unknown characters in grid
  [E] All palette entries map to known tile types (tile_definitions.json)
  [E] Spawn points on drivable tiles and in-bounds
  [E] Checkpoint IDs sequential from 1
  [E] Checkpoints on drivable tiles and in-bounds
  [E] All checkpoints reachable from spawn[0] via drivable tiles
  [E] Circuit loop: each checkpoint can reach the next, last can reach first
  [W] start_finish_checkpoint_id present and valid
  [W] start_finish_checkpoint_id == 1 (CP1 expected at start)
  [W] CP1 within 8 BFS tiles of spawn[0] (should be right in front of spawn)
  [W] No isolated drivable islands (all drivable tiles in one component)
  [W] No road gaps (non-road tile surrounded by road on 3+ sides)
  [W] No dead-end road tiles (only 1 drivable neighbour)
  [W] No pit lane defined (informational)
  [W] Decoration coordinates in-bounds
  [W] Checkpoint order plausible (BFS distances from spawn non-decreasing
      for first half of CPs, then non-increasing — simple sanity heuristic)
"""

import json
import os
import sys
from collections import deque
from typing import Optional

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

# ── paths ──────────────────────────────────────────────────────────────────
_BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH     = os.path.join(_BASE, "data", "world_schema.json")
TILE_DEFS_PATH  = os.path.join(_BASE, "data", "tile_definitions.json")

DRIVABLE_TYPES = {"asphalt","grass","dirt","mud","ice","oil_slick",
                  "boost","lava","water"}
ROAD_TYPES     = DRIVABLE_TYPES - {"grass"}   # non-border drivable


# ── BFS helpers ────────────────────────────────────────────────────────────

def _bfs_reachable(grid, gw, gh, driv, sx, sy):
    """Return set of (x,y) reachable from (sx,sy) over drivable tiles."""
    if not (0<=sx<gw and 0<=sy<gh and driv[sy][sx]):
        return set()
    vis = {(sx, sy)}
    q   = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0<=nx<gw and 0<=ny<gh and (nx,ny) not in vis and driv[ny][nx]:
                vis.add((nx, ny))
                q.append((nx, ny))
    return vis


def _bfs_dist(grid, gw, gh, driv, sx, sy):
    """Return dict (x,y)->min_distance from (sx,sy) over drivable tiles."""
    if not (0<=sx<gw and 0<=sy<gh and driv[sy][sx]):
        return {}
    dist = {(sx, sy): 0}
    q    = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0<=nx<gw and 0<=ny<gh and (nx,ny) not in dist and driv[ny][nx]:
                dist[(nx, ny)] = dist[(x,y)] + 1
                q.append((nx, ny))
    return dist


def _bfs_path(grid, gw, gh, driv, sx, sy, ex, ey):
    """Return shortest BFS path from (sx,sy)→(ex,ey) or None."""
    if not (0<=sx<gw and 0<=sy<gh and driv[sy][sx]):
        return None
    if not (0<=ex<gw and 0<=ey<gh and driv[ey][ex]):
        return None
    prev = {(sx, sy): None}
    q    = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        if x == ex and y == ey:
            path, cur = [], (ex, ey)
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return path[::-1]
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0<=nx<gw and 0<=ny<gh and (nx,ny) not in prev and driv[ny][nx]:
                prev[(nx, ny)] = (x, y)
                q.append((nx, ny))
    return None


# ── main validation function ───────────────────────────────────────────────

def validate_track(track_data: dict,
                   schema_path: str  = SCHEMA_PATH,
                   tile_defs_path: str = TILE_DEFS_PATH) -> dict:
    """
    Validate a racetrack dict.  Returns:
        {"valid": bool, "errors": [str], "warnings": [str]}
    Errors are show-stoppers; warnings are correctness/quality issues.
    """
    errors:   list[str] = []
    warnings: list[str] = []

    def E(msg): errors.append(msg)
    def W(msg): warnings.append(msg)

    # ── 1. Schema ──────────────────────────────────────────────────────────
    if _HAS_JSONSCHEMA:
        try:
            schema = json.load(open(schema_path))
            jsonschema.validate(instance=track_data, schema=schema)
        except FileNotFoundError:
            W(f"Schema file not found: {schema_path} — skipping schema check")
        except jsonschema.ValidationError as ve:
            E(f"Schema: {ve.message} at {list(ve.absolute_path)}")
            return {"valid": False, "errors": errors, "warnings": warnings}
        except Exception as ex:
            W(f"Schema check failed unexpectedly: {ex}")
    else:
        W("jsonschema not installed — schema validation skipped (pip install jsonschema)")

    # ── 2. Load tile definitions ───────────────────────────────────────────
    try:
        tile_defs = json.load(open(tile_defs_path))["tiles"]
    except Exception as ex:
        E(f"Cannot load tile_definitions.json: {ex}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    known_tile_types = set(tile_defs.keys())

    # ── 3. Basic fields ────────────────────────────────────────────────────
    grid        = track_data.get("grid", [])
    palette     = track_data.get("tile_palette", {})
    gs          = track_data.get("grid_size", {})
    gw          = gs.get("width", 0)
    gh          = gs.get("height", 0)
    checkpoints = track_data.get("checkpoints", [])
    spawns      = track_data.get("starting_grid", [])

    # ── 4. Grid dimensions ────────────────────────────────────────────────
    if len(grid) != gh:
        E(f"Grid height mismatch: claimed {gh} but have {len(grid)} rows")
    bad_rows = [(i, len(r)) for i, r in enumerate(grid) if len(r) != gw]
    for ri, rl in bad_rows:
        E(f"Row {ri} width {rl} != {gw}")

    # ── 5. Palette & chars ────────────────────────────────────────────────
    for char, ttype in palette.items():
        if ttype not in known_tile_types:
            E(f"Palette '{char}'→'{ttype}' is not in tile_definitions.json "
              f"(known: {sorted(known_tile_types)})")

    all_chars = {c for row in grid for c in row}
    for c in all_chars - set(palette):
        E(f"Grid contains undefined char '{c}' (not in tile_palette)")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ── build drivability matrix ──────────────────────────────────────────
    def ttype_at(gx, gy) -> str:
        if not (0<=gx<gw and 0<=gy<gh): return "wall"
        c = grid[gy][gx] if gx < len(grid[gy]) else " "
        return palette.get(c, "wall")

    driv = [[ttype_at(gx, gy) in DRIVABLE_TYPES
             for gx in range(gw)] for gy in range(gh)]

    # ── 6. Spawn checks ───────────────────────────────────────────────────
    if not spawns:
        E("No starting_grid entries found")
    for idx, sp in enumerate(spawns):
        sx, sy = sp.get("x", -1), sp.get("y", -1)
        if not (0<=sx<gw and 0<=sy<gh):
            E(f"Spawn[{idx}] ({sx},{sy}) out of bounds ({gw}x{gh})")
        elif not driv[sy][sx]:
            E(f"Spawn[{idx}] ({sx},{sy}) on non-drivable tile '{ttype_at(sx,sy)}'")

    if not spawns or errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    sp0x, sp0y = spawns[0]["x"], spawns[0]["y"]
    from_spawn  = _bfs_dist(None, gw, gh, driv, sp0x, sp0y)
    total_driv  = sum(driv[gy][gx] for gy in range(gh) for gx in range(gw))

    # ── 7. Checkpoint checks ──────────────────────────────────────────────
    cp_ids = [cp["id"] for cp in checkpoints]
    if sorted(cp_ids) != list(range(1, len(cp_ids)+1)):
        E(f"Checkpoint IDs must be 1..N sequential. Got {sorted(cp_ids)}")

    cps = sorted(checkpoints, key=lambda c: c["id"])
    valid_cps = []
    for cp in cps:
        cx, cy, cid = cp["x"], cp["y"], cp["id"]
        if not (0<=cx<gw and 0<=cy<gh):
            E(f"CP{cid} ({cx},{cy}) out of bounds")
            continue
        tt = ttype_at(cx, cy)
        if tt not in DRIVABLE_TYPES:
            E(f"CP{cid} ({cx},{cy}) on non-drivable tile '{tt}'")
            continue
        if (cx, cy) not in from_spawn:
            E(f"CP{cid} ({cx},{cy}) not reachable from spawn[0]")
            continue
        valid_cps.append((cx, cy, cid))

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ── 8. Circuit loop check ─────────────────────────────────────────────
    # Each CP must be able to reach the next; last CP must reach first CP
    for i, (cx, cy, cid) in enumerate(valid_cps):
        nx, ny, nid = valid_cps[(i+1) % len(valid_cps)]
        if _bfs_path(None, gw, gh, driv, cx, cy, nx, ny) is None:
            E(f"No path CP{cid} ({cx},{cy}) → CP{nid} ({nx},{ny}) — circuit broken")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ── 9. start_finish_checkpoint_id ────────────────────────────────────
    sf_id = track_data.get("start_finish_checkpoint_id")
    if sf_id is None:
        W("'start_finish_checkpoint_id' missing — add this to mark which "
          "checkpoint is the start/finish line")
    else:
        if sf_id not in cp_ids:
            E(f"start_finish_checkpoint_id={sf_id} does not match any checkpoint id")
        if sf_id != 1:
            W(f"start_finish_checkpoint_id={sf_id} is not CP1. "
              "Convention: CP1 is the start/finish line")

    # ── 10. CP1 proximity to spawn ────────────────────────────────────────
    cp1x, cp1y = valid_cps[0][0], valid_cps[0][1]
    cp1_dist   = from_spawn.get((cp1x, cp1y), 9999)
    if cp1_dist > 8:
        W(f"CP1 ({cp1x},{cp1y}) is {cp1_dist} BFS tiles from spawn[0] — "
          f"normally the start line should be immediately in front of spawn (≤8 tiles)")

    # ── 11. No isolated drivable islands ──────────────────────────────────
    reachable = _bfs_reachable(None, gw, gh, driv, sp0x, sp0y)
    isolated  = total_driv - len(reachable)
    if isolated > 0:
        W(f"{isolated} drivable tile(s) unreachable from spawn[0] — "
          f"possible isolated road island")

    # ── 12. Road gaps (non-road tile surrounded by road on 3+ sides) ─────
    gaps = []
    for gy in range(gh):
        for gx in range(gw):
            tt = ttype_at(gx, gy)
            if tt in ("grass", "wall"):
                rn = sum(1 for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))
                         if ttype_at(gx+dx, gy+dy) in ROAD_TYPES)
                if rn >= 3:
                    gaps.append((gx, gy, tt))
    for gx, gy, tt in gaps:
        W(f"Road gap at ({gx},{gy}): '{tt}' surrounded by road on 3+ sides")

    # ── 13. Dead-end road tiles ───────────────────────────────────────────
    dead_ends = []
    for gy in range(gh):
        for gx in range(gw):
            if driv[gy][gx]:
                nb = sum(1 for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))
                         if 0<=gx+dx<gw and 0<=gy+dy<gh and driv[gy+dy][gx+dx])
                if nb == 1:
                    dead_ends.append((gx, gy))
    if dead_ends:
        W(f"{len(dead_ends)} dead-end road tile(s) (only 1 drivable neighbour): "
          f"{dead_ends[:4]}{'…' if len(dead_ends)>4 else ''}")

    # ── 14. Pit lane presence ──────────────────────────────────────────────
    has_pit = "pit" in str(track_data).lower()
    if not has_pit:
        W("No pit lane or pit-related area detected. "
          "Consider adding a pit lane connected to the start straight.")

    # ── 15. Decoration bounds ─────────────────────────────────────────────
    for dec in track_data.get("decorations", []):
        dx, dy = dec.get("x", 0), dec.get("y", 0)
        if not (0 <= dx < gw and 0 <= dy < gh):
            W(f"Decoration '{dec.get('type')}' at ({dx},{dy}) is outside grid bounds")

    # ── 16. Checkpoint ordering heuristic ────────────────────────────────
    # Distances from spawn should rise then fall (out-and-back or loop).
    # Flag if two CONSECUTIVE CPs both get CLOSER to spawn before the peak.
    dists = [from_spawn.get((cx,cy), 9999) for cx,cy,_ in valid_cps]
    if len(dists) >= 4:
        peak_idx = dists.index(max(dists))
        # Check increasing portion doesn't have drops
        for i in range(1, peak_idx):
            if dists[i] < dists[i-1] - 5:   # allow small BFS noise (±5)
                W(f"CP{i} (dist={dists[i]}) is much closer to spawn than "
                  f"CP{i-1} (dist={dists[i-1]}) before the halfway peak — "
                  f"checkpoint order may not match driving direction")
        # Check decreasing portion doesn't have rises
        for i in range(peak_idx+2, len(dists)):
            if dists[i] > dists[i-1] + 5:
                W(f"CP{i} (dist={dists[i]}) is much farther from spawn than "
                  f"CP{i-1} (dist={dists[i-1]}) on the return leg — "
                  f"checkpoint order may not match driving direction")

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors, "warnings": warnings}


# ── CLI ────────────────────────────────────────────────────────────────────

def _run_one(path: str, verbose: bool = True) -> bool:
    if not os.path.exists(path):
        print(f"  ERROR: file not found: {path}")
        return False
    try:
        data = json.load(open(path))
    except json.JSONDecodeError as ex:
        print(f"  ERROR: invalid JSON — {ex}")
        return False

    res = validate_track(data)
    ok  = res["valid"]
    tag = "✓ PASS" if ok else "✗ FAIL"
    print(f"{tag}  {path}")
    for e in res["errors"]:
        print(f"       [ERROR]   {e}")
    for w in res["warnings"]:
        print(f"       [WARNING] {w}")
    return ok


if __name__ == "__main__":
    import glob

    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] == "--all":
        paths = sorted(glob.glob(os.path.join(_BASE, "data", "*.json")))
        paths = [p for p in paths
                 if not any(x in os.path.basename(p)
                            for x in ("tile_definitions", "world_schema",
                                      "settings", "player", "cars", "sample"))]
    else:
        paths = args

    all_ok = True
    for p in paths:
        if not _run_one(p):
            all_ok = False

    sys.exit(0 if all_ok else 1)
