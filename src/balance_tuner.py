import json
import os
import sys
import math
from typing import Dict, List, Tuple

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Racetrack, TileDefinition
from src.validator import load_json_file

class Vehicle:
    def __init__(self):
        # Default vehicle specs for simulation
        self.mass = 1200.0  # kg
        self.max_engine_force = 6000.0  # N
        self.drag_coeff = 0.35  # aerodynamic drag
        self.braking_force = 12000.0  # N
        self.base_top_speed = 35.0  # m/s (approx 126 km/h)
        self.handling_grip = 1.0  # handling coefficient

def simulate_lap(track: Racetrack, tile_defs: Dict[str, TileDefinition], vehicle: Vehicle) -> dict:
    """
    Simulates a lap of a vehicle around the checkpoints.
    Uses basic physics: F = m*a, incorporating tile friction and speed limits.
    """
    # 1. Reconstruct path sequence: starting grid -> CP 1 -> CP 2 -> ... -> CP N -> starting grid
    if not track.starting_grid or not track.checkpoints:
        return {}

    path_coords = [(track.starting_grid[0].x, track.starting_grid[0].y)]
    sorted_cps = sorted(track.checkpoints, key=lambda c: c.id)
    for cp in sorted_cps:
        path_coords.append((cp.x, cp.y))
    # Close the loop back to start
    path_coords.append((track.starting_grid[0].x, track.starting_grid[0].y))

    # 2. Interpolate points along the segments to simulate continuous driving
    sim_points = []
    tile_size_meters = 5.0  # Assume each tile is 5x5 meters
    
    for i in range(len(path_coords) - 1):
        x1, y1 = path_coords[i]
        x2, y2 = path_coords[i+1]
        
        # Grid distance
        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        
        # Determine number of steps
        steps = max(int(dist * 4), 1)  # 4 steps per tile coordinate
        for step in range(steps):
            t = step / steps
            px = x1 + dx * t
            py = y1 + dy * t
            sim_points.append((px, py))

    # 3. Perform physics integration
    time_elapsed = 0.0
    velocity = 0.0  # m/s
    top_speed = 0.0
    total_distance = 0.0
    sliding_time = 0.0
    total_damage = 0.0

    # Step duration (assumed 0.05 seconds per step on average, dynamically calculated)
    for i in range(len(sim_points) - 1):
        p1 = sim_points[i]
        p2 = sim_points[i+1]
        
        # Distance between points in meters
        dx_m = (p2[0] - p1[0]) * tile_size_meters
        dy_m = (p2[1] - p1[1]) * tile_size_meters
        step_dist = math.hypot(dx_m, dy_m)
        total_distance += step_dist

        # Look up tile at p1
        gx, gy = int(p1[0]), int(p1[1])
        tile_type = track.get_tile_type_at(gx, gy)
        tile_def = tile_defs.get(tile_type)

        if not tile_def:
            friction = 0.5
            speed_mult = 0.5
            dmg = 0.0
        else:
            friction = tile_def.friction
            speed_mult = tile_def.speed_multiplier
            dmg = tile_def.damage_per_sec

        # Physics simulation:
        # Effective engine force is constrained by friction (wheel slip limits)
        max_tractive_force = vehicle.max_engine_force * friction
        
        # Air resistance
        drag_force = vehicle.drag_coeff * (velocity ** 2)
        
        # Net acceleration force
        net_force = max_tractive_force - drag_force
        acceleration = net_force / vehicle.mass
        
        # Apply speed multiplier to max top speed
        effective_max_speed = vehicle.base_top_speed * speed_mult
        
        # Calculate time step to cover step_dist:
        # d = v*t + 0.5*a*t^2 -> approximate dt = step_dist / avg_velocity
        avg_v = max(velocity, 0.5)
        dt = step_dist / avg_v
        
        # Limit dt to prevent numerical instability
        dt = min(dt, 0.5)
        
        # Update velocity
        velocity += acceleration * dt
        if velocity > effective_max_speed:
            velocity = effective_max_speed  # Cap by tile limits
            
        velocity = max(velocity, 1.0)  # Always keep rolling
        
        # Keep track of top speed
        if velocity > top_speed:
            top_speed = velocity
            
        # Accumulate metrics
        time_elapsed += dt
        
        # Check if sliding (low grip)
        if friction < 0.6:
            sliding_time += dt
            
        # Accumulate damage
        total_damage += dmg * dt

    avg_speed = total_distance / max(time_elapsed, 0.1)

    return {
        "track_length_meters": total_distance,
        "lap_time_seconds": time_elapsed,
        "average_speed_kmh": avg_speed * 3.6,
        "top_speed_kmh": top_speed * 3.6,
        "sliding_percentage": (sliding_time / max(time_elapsed, 0.1)) * 100.0,
        "damage_taken": total_damage
    }

def analyze_track_composition(track: Racetrack, tile_defs: Dict[str, TileDefinition]) -> Dict[str, float]:
    total_cells = track.grid_size.width * track.grid_size.height
    counts = {}
    
    for y in range(track.grid_size.height):
        for x in range(track.grid_size.width):
            tile_type = track.get_tile_type_at(x, y)
            counts[tile_type] = counts.get(tile_type, 0) + 1
            
    percentages = {}
    for name, count in counts.items():
        percentages[name] = (count / total_cells) * 100.0
    return percentages

def generate_balance_report(track_path: str, schema_path: str, tile_defs_path: str):
    try:
        track_data = load_json_file(track_path)
        track = Racetrack.from_dict(track_data)
        
        # Load tiles
        tile_defs_data = load_json_file(tile_defs_path)
        tile_defs = {}
        for name, d in tile_defs_data["tiles"].items():
            tile_defs[name] = TileDefinition.from_dict(name, d)
            
    except Exception as e:
        print(f"Error loading track or definitions: {e}")
        return

    # Run simulation
    vehicle = Vehicle()
    sim = simulate_lap(track, tile_defs, vehicle)
    comp = analyze_track_composition(track, tile_defs)

    if not sim:
        print(f"Error: Unable to simulate lap on '{track.name}'. Ensure starting spawn and checkpoints are placed.")
        return

    # Determine balanced difficulty rating
    # Factors: hazard presence, sliding ratio, layout complexity (number of turns)
    hazard_ratio = sum(comp.get(name, 0.0) for name, t in tile_defs.items() if t.hazard)
    sliding_pct = sim["sliding_percentage"]
    damage = sim["damage_taken"]
    
    difficulty_score = 0
    if hazard_ratio > 3.0: difficulty_score += 1
    if hazard_ratio > 10.0: difficulty_score += 1
    if sliding_pct > 25.0: difficulty_score += 1
    if sliding_pct > 50.0: difficulty_score += 1
    if damage > 20.0: difficulty_score += 1
    if damage > 60.0: difficulty_score += 1
    
    difficulty_labels = ["Easy", "Medium", "Hard", "Extreme"]
    diff_idx = min(difficulty_score, len(difficulty_labels) - 1)
    calculated_difficulty = difficulty_labels[diff_idx]

    print("=" * 60)
    print(f" GAME BALANCE & SIMULATION REPORT: {track.name}")
    print("=" * 60)
    print(f"Description: {track.description}")
    print(f"Creator:     {track.creator} | Version: {track.version}")
    print(f"Grid Size:   {track.grid_size.width}x{track.grid_size.height} | Configured Laps: {track.laps}")
    print("-" * 60)
    print(" TRACK TILE COMPOSITION ANALYSIS:")
    for tile_name, pct in sorted(comp.items(), key=lambda x: x[1], reverse=True):
        desc = tile_defs[tile_name].description[:40] if tile_name in tile_defs else ""
        print(f"  - {tile_name.capitalize():<12}: {pct:>5.1f}%   ({desc})")
    print("-" * 60)
    print(" LAP PHYSICS SIMULATION RESULTS (1 LAP):")
    print(f"  - Simulated Path Distance : {sim['track_length_meters']:.1f} meters")
    print(f"  - Estimated Lap Time      : {sim['lap_time_seconds']:.2f} seconds")
    print(f"  - Average Speed           : {sim['average_speed_kmh']:.1f} km/h")
    print(f"  - Top Speed Reached       : {sim['top_speed_kmh']:.1f} km/h")
    print(f"  - Sliding / Drift Ratio   : {sim['sliding_percentage']:.1f}% of lap time")
    print(f"  - Total Hazard Damage     : {sim['damage_taken']:.1f} HP (Vehicle Max: 100 HP)")
    print(f"  - Calculated Difficulty   : {calculated_difficulty} (Configured: {track.difficulty.capitalize()})")
    print("-" * 60)
    print(" BALANCING & TUNING RECOMMENDATIONS:")
    
    recommendations = []
    
    # 1. Speed Balance
    if sim["average_speed_kmh"] < 40.0:
        recommendations.append(
            " [SLOW SPEED] Average speed is very low. Consider replacing mud/water slow patches with asphalt, or adding speed boost pads."
        )
    elif sim["average_speed_kmh"] > 100.0:
        recommendations.append(
            " [VERY FAST] Racetrack is highly dominated by high speeds. Add dirt curves or oil hazard spots to force braking zones."
        )
        
    # 2. Damage Balance
    if damage > 80.0:
        recommendations.append(
            " [EXTREME HAZARD] Lava damage threatens vehicle survival in a single lap. Reduce lava tile density or insert water cooling pools."
        )
    elif damage > 0.0 and damage < 5.0:
        recommendations.append(
            " [LOW HAZARD RISK] Hazard zones are present but negligible. Increase damage coefficient or path density to elevate risk reward dynamics."
        )

    # 3. Drifting / Control Balance
    if sliding_pct > 60.0:
        recommendations.append(
            " [DRIFT SPECIALIST] The car slides for over 60% of the track. Classify as 'Drift Circuit'. Adjust grass/ice friction upwards if too slippery."
        )
    elif sliding_pct < 5.0 and track.difficulty != "easy":
        recommendations.append(
            " [LINEAR GRIP] Very low sliding detected. Add dirt or oil patches to encourage drifting mechanics similar to top-down racing style."
        )

    if not recommendations:
        recommendations.append(" [OPTIMAL BALANCE] Track metrics fall within comfortable gameplay balance parameters. Ready for deployment!")

    for rec in recommendations:
        print(rec)
    print("=" * 60)
    print()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_p = os.path.join(base_dir, "data", "world_schema.json")
    tile_defs_p = os.path.join(base_dir, "data", "tile_definitions.json")

    tracks = [
        "mzansi_asphalt.json",
        "kalahari_drift.json",
        "drakensberg_ice.json",
        "volcanic_heat.json"
    ]

    for t_file in tracks:
        path = os.path.join(base_dir, "data", t_file)
        if os.path.exists(path):
            generate_balance_report(path, schema_p, tile_defs_p)
        else:
            print(f"Skipping report: Track file not found at '{path}'")
