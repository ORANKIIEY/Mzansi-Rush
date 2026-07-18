import json
import os
import sys
from typing import Dict, List, Tuple, Set, Optional
import jsonschema

class TrackValidationError(Exception):
    """Custom exception representing validation errors."""
    pass

def load_json_file(file_path: str) -> dict:
    with open(file_path, "r") as f:
        return json.load(f)

def find_bfs_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    grid_w: int,
    grid_h: int,
    drivable_grid: List[List[bool]]
) -> Optional[List[Tuple[int, int]]]:
    """Finds a path between start and end using BFS, returns path list or None."""
    if not (0 <= start[0] < grid_w and 0 <= start[1] < grid_h):
        return None
    if not (0 <= end[0] < grid_w and 0 <= end[1] < grid_h):
        return None
    if not drivable_grid[start[1]][start[0]] or not drivable_grid[end[1]][end[0]]:
        return None

    queue = [[start]]
    visited = {start}

    while queue:
        path = queue.pop(0)
        current = path[-1]

        if current == end:
            return path

        x, y = current
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < grid_w and 0 <= ny < grid_h:
                if drivable_grid[ny][nx] and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    new_path = list(path)
                    new_path.append((nx, ny))
                    queue.append(new_path)
    return None

def validate_track(
    track_data: dict,
    schema_path: str,
    tile_defs_path: str
) -> dict:
    """
    Validates a racetrack dictionary.
    Returns:
        dict: {"valid": bool, "errors": list, "warnings": list}
    """
    result = {"valid": True, "errors": [], "warnings": []}

    # 1. Structural Schema Validation
    try:
        schema = load_json_file(schema_path)
    except Exception as e:
        result["errors"].append(f"Failed to load schema from '{schema_path}': {str(e)}")
        result["valid"] = False
        return result

    try:
        jsonschema.validate(instance=track_data, schema=schema)
    except jsonschema.ValidationError as ve:
        result["errors"].append(f"Schema validation failed: {ve.message} at {list(ve.absolute_path)}")
        result["valid"] = False
        return result
    except Exception as e:
        result["errors"].append(f"JSON validation error: {str(e)}")
        result["valid"] = False
        return result

    # 2. Tile Definitions Validation
    try:
        tile_defs_data = load_json_file(tile_defs_path)
        tile_defs = tile_defs_data.get("tiles", {})
    except Exception as e:
        result["errors"].append(f"Failed to load tile definitions from '{tile_defs_path}': {str(e)}")
        result["valid"] = False
        return result

    grid_size = track_data["grid_size"]
    grid_w = grid_size["width"]
    grid_h = grid_size["height"]
    grid = track_data["grid"]
    palette = track_data["tile_palette"]
    checkpoints = track_data["checkpoints"]
    starting_grid = track_data["starting_grid"]

    # 3. Grid Row & Column size consistency
    if len(grid) != grid_h:
        result["errors"].append(f"Grid height mismatch: metadata claims {grid_h}, but grid array has {len(grid)} rows.")
    for idx, row in enumerate(grid):
        if len(row) != grid_w:
            result["errors"].append(f"Grid width mismatch at row {idx}: metadata claims {grid_w}, but row has {len(row)} characters.")

    # 4. Palette and Tile validation
    unknown_chars = set()
    invalid_palette_targets = set()
    for char, tile_type in palette.items():
        if tile_type not in tile_defs:
            invalid_palette_targets.add((char, tile_type))

    if invalid_palette_targets:
        for char, tile_type in invalid_palette_targets:
            result["errors"].append(f"Palette mapping error: character '{char}' maps to '{tile_type}' which is undefined in tile_definitions.json")

    # Check grid characters
    for y, row in enumerate(grid):
        for x, char in enumerate(row):
            if char not in palette:
                unknown_chars.add(char)

    if unknown_chars:
        for char in unknown_chars:
            result["errors"].append(f"Grid layout contains undefined character: '{char}'")

    if result["errors"]:
        result["valid"] = False
        return result

    # Build matrix of drivable tiles for pathfinding
    drivable_grid = [[True for _ in range(grid_w)] for _ in range(grid_h)]
    for y, row in enumerate(grid):
        for x, char in enumerate(row):
            tile_type = palette[char]
            is_drivable = tile_defs[tile_type]["drivable"]
            drivable_grid[y][x] = is_drivable

    # 5. Starting Grid Checks
    if len(starting_grid) < 4:
        result["warnings"].append(f"Starting grid has only {len(starting_grid)} spawns. Standard grid should support at least 4 cars.")

    for idx, spawn in enumerate(starting_grid):
        sx, sy = spawn["x"], spawn["y"]
        if not (0 <= sx < grid_w and 0 <= sy < grid_h):
            result["errors"].append(f"Spawn point {idx} is out of bounds: ({sx}, {sy})")
            continue
        char = grid[sy][sx]
        tile_type = palette[char]
        if not tile_defs[tile_type]["drivable"]:
            result["errors"].append(f"Spawn point {idx} at ({sx}, {sy}) is placed on non-drivable tile: '{tile_type}' ({char})")

    # 6. Checkpoint Checks
    cp_ids = [cp["id"] for cp in checkpoints]
    cp_ids_sorted = sorted(cp_ids)

    # Check that they start from 1 and are sequential
    expected_ids = list(range(1, len(checkpoints) + 1))
    if cp_ids_sorted != expected_ids:
        result["errors"].append(f"Checkpoint IDs must be sequential integers starting from 1. Got IDs: {cp_ids_sorted}")

    # Check bounds and drivability of checkpoints
    checkpoints_sorted = sorted(checkpoints, key=lambda c: c["id"])
    cp_coords = []
    for cp in checkpoints_sorted:
        cx, cy = cp["x"], cp["y"]
        c_id = cp["id"]
        if not (0 <= cx < grid_w and 0 <= cy < grid_h):
            result["errors"].append(f"Checkpoint {c_id} is out of bounds: ({cx}, {cy})")
            continue
        char = grid[cy][cx]
        tile_type = palette[char]
        if not tile_defs[tile_type]["drivable"]:
            result["errors"].append(f"Checkpoint {c_id} at ({cx}, {cy}) is placed on non-drivable tile: '{tile_type}' ({char})")
        cp_coords.append((cx, cy, c_id))

    if result["errors"]:
        result["valid"] = False
        return result

    # 7. Routing Validation (Pathfinding)
    if len(starting_grid) > 0 and len(cp_coords) > 0:
        first_spawn = (starting_grid[0]["x"], starting_grid[0]["y"])
        first_cp = (cp_coords[0][0], cp_coords[0][1])
        path = find_bfs_path(first_spawn, first_cp, grid_w, grid_h, drivable_grid)
        if not path:
            result["errors"].append(f"Connectivity check failed: Starting grid spawn 0 at {first_spawn} cannot reach Checkpoint 1 at {first_cp} (blocked by walls/obstacles).")

    for i in range(len(cp_coords)):
        curr_cp = cp_coords[i]
        next_cp = cp_coords[(i + 1) % len(cp_coords)]  # Loop back to checkpoint 1
        curr_pos = (curr_cp[0], curr_cp[1])
        next_pos = (next_cp[0], next_cp[1])

        path = find_bfs_path(curr_pos, next_pos, grid_w, grid_h, drivable_grid)
        if not path:
            result["errors"].append(
                f"Connectivity check failed: Checkpoint {curr_cp[2]} at {curr_pos} cannot reach "
                f"Checkpoint {next_cp[2]} at {next_pos} (blocked by walls/obstacles)."
            )

    if result["errors"]:
        result["valid"] = False

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 validator.py <path_to_world.json>")
        sys.exit(1)

    track_file = sys.argv[1]
    # Locate paths relative to this file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_p = os.path.join(base_dir, "data", "world_schema.json")
    tile_defs_p = os.path.join(base_dir, "data", "tile_definitions.json")

    if not os.path.exists(track_file):
        print(f"Error: File not found: {track_file}")
        sys.exit(1)

    try:
        track_dict = load_json_file(track_file)
        res = validate_track(track_dict, schema_p, tile_defs_p)

        if res["valid"]:
            print(f" SUCCESS: '{track_file}' is valid.")
            if res["warnings"]:
                print("Warnings:")
                for w in res["warnings"]:
                    print(f"  - {w}")
            sys.exit(0)
        else:
            print(f" FAILURE: '{track_file}' has validation errors:")
            for err in res["errors"]:
                print(f"  [ERROR] {err}")
            for w in res["warnings"]:
                print(f"  [WARNING] {w}")
            sys.exit(1)
    except Exception as exc:
        print(f"Unexpected execution error: {str(exc)}")
        sys.exit(1)
