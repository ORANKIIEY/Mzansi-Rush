import json
import os
import math
from typing import List, Tuple, Dict

def dist_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    
    # Calculate projection
    t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
    t = max(0.0, min(1.0, t))
    
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)

def create_base_grid(width: int, height: int, default_char: str) -> List[List[str]]:
    # Create empty grid
    grid = [[default_char for _ in range(width)] for _ in range(height)]
    # Place wall boundary
    for y in range(height):
        for x in range(width):
            if y == 0 or y == height - 1 or x == 0 or x == width - 1:
                grid[y][x] = "W"
    return grid

def draw_thick_track(grid: List[List[str]], skeleton: List[Tuple[float, float]], road_char: str, road_width: float):
    h = len(grid)
    w = len(grid[0])
    
    # For each grid cell, find if it lies within road_width/2 distance to any skeleton segment
    for y in range(h):
        for x in range(w):
            # Ignore boundaries
            if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                continue
            
            min_d = 999999.0
            for i in range(len(skeleton)):
                p1 = skeleton[i]
                p2 = skeleton[(i + 1) % len(skeleton)]
                d = dist_point_to_segment(x, y, p1[0], p1[1], p2[0], p2[1])
                if d < min_d:
                    min_d = d
            
            if min_d <= (road_width / 2.0):
                grid[y][x] = road_char

def serialize_grid(grid: List[List[str]]) -> List[str]:
    return ["".join(row) for row in grid]

def save_track_file(filepath: str, data: dict):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated track: {filepath}")

def generate_mzansi_asphalt():
    width, height = 40, 30
    grid = create_base_grid(width, height, "G")
    
    # Track nodes
    skeleton = [
        (6, 6),
        (18, 6),
        (20, 12),  # chicane down
        (22, 6),
        (34, 6),
        (34, 24),
        (24, 24),
        (24, 18),  # chicane up
        (16, 18),
        (16, 24),  # chicane down
        (6, 24)
    ]
    
    draw_thick_track(grid, skeleton, "A", 3.6)
    
    # Place Speed Boost (B) pads on top and bottom straights
    boost_locs = [(10, 6), (11, 6), (28, 6), (29, 6), (20, 18), (21, 18)]
    for bx, by in boost_locs:
        grid[by][bx] = "B"
        
    # Place walls inside the center loops to guide the racer
    # Let's add some inner walls in the empty grass regions
    for y in range(9, 15):
        for x in range(23, 27):
            grid[y][x] = "W"
            
    # Checkpoints on asphalt path
    checkpoints = [
        {"id": 1, "x": 6, "y": 15, "name": "Start/Finish Line"},
        {"id": 2, "x": 15, "y": 6, "name": "Sector 1 Chicane Entry"},
        {"id": 3, "x": 28, "y": 6, "name": "Sector 1 Straight"},
        {"id": 4, "x": 34, "y": 15, "name": "Sector 2 East Loop"},
        {"id": 5, "x": 20, "y": 18, "name": "Sector 3 Infield"},
        {"id": 6, "x": 6, "y": 24, "name": "Sector 3 Final Turn"}
    ]
    
    # Spawns just behind start/finish
    starting_grid = [
        {"x": 6, "y": 16, "direction": "north"},
        {"x": 7, "y": 16, "direction": "north"},
        {"x": 6, "y": 17, "direction": "north"},
        {"x": 7, "y": 17, "direction": "north"}
    ]

    data = {
        "name": "Mzansi Asphalt Classic",
        "description": "A high-speed grand prix street circuit with technical chicanes and supercharger boost pads.",
        "creator": "Track Architect",
        "version": "1.0",
        "grid_size": {"width": width, "height": height},
        "laps": 3,
        "difficulty": "medium",
        "tile_size": 32,
        "tile_palette": {
            "W": "wall",
            "G": "grass",
            "A": "asphalt",
            "B": "boost"
        },
        "grid": serialize_grid(grid),
        "checkpoints": checkpoints,
        "starting_grid": starting_grid,
        "decorations": [
            {"type": "tree", "x": 10.5, "y": 10.5},
            {"type": "tree", "x": 11.5, "y": 11.5},
            {"type": "tire_stack", "x": 19.5, "y": 8.5},
            {"type": "tire_stack", "x": 23.5, "y": 25.5}
        ]
    }
    
    save_track_file("data/mzansi_asphalt.json", data)

def generate_kalahari_drift():
    width, height = 50, 40
    grid = create_base_grid(width, height, "G")
    
    # Large rally drift loop
    skeleton = [
        (8, 8),
        (42, 8),
        (42, 32),
        (25, 32),
        (25, 20),
        (8, 20)
    ]
    
    draw_thick_track(grid, skeleton, "D", 4.8)
    
    # Place Mud (M) hazards on corner entry/apex zones
    mud_zones = [
        (8, 8), (9, 8), (8, 9), (9, 9), (7, 8), (8, 7), # Top-Left Turn
        (41, 8), (42, 8), (41, 9), (42, 9), (43, 7), (43, 8), # Top-Right Turn
        (42, 31), (42, 32), (41, 32), (43, 32), (41, 31), # Bottom-Right Turn
        (24, 20), (25, 20), (26, 20), (25, 19), (25, 21) # Middle Chicane Corner
    ]
    
    for mx, my in mud_zones:
        # Check coordinates and set mud
        if grid[my][mx] == "D":
            grid[my][mx] = "M"
            
    # Checkpoints
    checkpoints = [
        {"id": 1, "x": 15, "y": 20, "name": "Rally Stage Start"},
        {"id": 2, "x": 8, "y": 14, "name": "Kalahari Apex 1"},
        {"id": 3, "x": 25, "y": 8, "name": "Desert Straightaway"},
        {"id": 4, "x": 42, "y": 20, "name": "Salt Flat Turn"},
        {"id": 5, "x": 25, "y": 26, "name": "Ridge Climb"}
    ]
    
    # Spawns facing east on middle straight
    starting_grid = [
        {"x": 12, "y": 20, "direction": "east"},
        {"x": 11, "y": 20, "direction": "east"},
        {"x": 12, "y": 19, "direction": "east"},
        {"x": 11, "y": 19, "direction": "east"}
    ]

    data = {
        "name": "Kalahari Drift",
        "description": "Loose dirt desert tracks featuring thick mud pools that slow down cars and challenge sliding lines.",
        "creator": "Rally Master",
        "version": "1.0",
        "grid_size": {"width": width, "height": height},
        "laps": 2,
        "difficulty": "medium",
        "tile_size": 32,
        "tile_palette": {
            "W": "wall",
            "G": "grass",
            "D": "dirt",
            "M": "mud"
        },
        "grid": serialize_grid(grid),
        "checkpoints": checkpoints,
        "starting_grid": starting_grid,
        "decorations": [
            {"type": "tree", "x": 14.5, "y": 12.5},
            {"type": "tree", "x": 30.5, "y": 15.5},
            {"type": "barrier", "x": 6.5, "y": 7.5}
        ]
    }
    
    save_track_file("data/kalahari_drift.json", data)

def generate_drakensberg_ice():
    width, height = 45, 35
    grid = create_base_grid(width, height, "W") # Base is all rock/wall
    
    # Narrow mountain road layout (width 3)
    skeleton = [
        (6, 6),
        (38, 6),
        (38, 16),
        (16, 16),
        (16, 28),
        (6, 28)
    ]
    
    # Draw mountain pass path with dirt/asphalt
    draw_thick_track(grid, skeleton, "A", 3.0)
    
    # Inject Ice (I) patches on critical hairpins
    ice_zones = [
        # Sector corners
        (38, 6), (37, 6), (38, 7), (37, 7),
        (16, 16), (15, 16), (17, 16), (16, 15), (16, 17),
        (6, 28), (7, 28), (6, 27), (7, 27),
        # Middle of straight segments
        (22, 6), (23, 6), (24, 6),
        (25, 16), (26, 16)
    ]
    for ix, iy in ice_zones:
        if grid[iy][ix] == "A":
            grid[iy][ix] = "I"
            
    # Checkpoints
    checkpoints = [
        {"id": 1, "x": 6, "y": 12, "name": "Pass Start"},
        {"id": 2, "x": 20, "y": 6, "name": "Glacier Run"},
        {"id": 3, "x": 38, "y": 11, "name": "East Precipice"},
        {"id": 4, "x": 22, "y": 16, "name": "Mid-Mountain Slip"},
        {"id": 5, "x": 16, "y": 24, "name": "South Gorge"},
        {"id": 6, "x": 10, "y": 28, "name": "Valley Ascent"}
    ]
    
    # Starting grid
    starting_grid = [
        {"x": 6, "y": 10, "direction": "south"},
        {"x": 6, "y": 9, "direction": "south"},
        {"x": 5, "y": 10, "direction": "south"},
        {"x": 5, "y": 9, "direction": "south"}
    ]

    data = {
        "name": "Drakensberg Ice Pass",
        "description": "Treacherous narrow pass carved into mountain rock. Frozen ice patches cause total steering loss near sheer walls.",
        "creator": "Mountain Engineer",
        "version": "1.0",
        "grid_size": {"width": width, "height": height},
        "laps": 3,
        "difficulty": "hard",
        "tile_size": 32,
        "tile_palette": {
            "W": "wall",
            "A": "asphalt",
            "I": "ice"
        },
        "grid": serialize_grid(grid),
        "checkpoints": checkpoints,
        "starting_grid": starting_grid,
        "decorations": [
            {"type": "barrier", "x": 39.5, "y": 5.5},
            {"type": "barrier", "x": 15.5, "y": 15.5}
        ]
    }
    
    save_track_file("data/drakensberg_ice.json", data)

def generate_volcanic_heat():
    width, height = 50, 35
    grid = create_base_grid(width, height, "L") # Outer lava field
    
    # Core circuit skeleton
    skeleton = [
        (8, 8),
        (42, 8),
        (42, 26),
        (8, 26)
    ]
    
    # Draw road of Asphalt
    draw_thick_track(grid, skeleton, "A", 3.8)
    
    # Place some Grass shoulders inside/outside of the loop to shield from lava
    for y in range(len(grid)):
        for x in range(len(grid[0])):
            if grid[y][x] == "L":
                # If close to road, make it grass
                min_d = 99999
                for i in range(len(skeleton)):
                    p1 = skeleton[i]
                    p2 = skeleton[(i + 1) % len(skeleton)]
                    d = dist_point_to_segment(x, y, p1[0], p1[1], p2[0], p2[1])
                    if d < min_d:
                        min_d = d
                if min_d <= 4.0:
                    grid[y][x] = "G"
                    
    # Re-apply walls on grid border
    for y in range(height):
        for x in range(width):
            if y == 0 or y == height - 1 or x == 0 or x == width - 1:
                grid[y][x] = "W"

    # Inject oil slick slicks (O) and water cooling pools (H)
    # Water pools are placed inside the road as cooling lines
    water_zones = [(24, 8), (25, 8), (26, 8), (24, 26), (25, 26), (26, 26)]
    for wx, wy in water_zones:
        grid[wy][wx] = "H"
        
    oil_zones = [(15, 8), (35, 8), (15, 26), (35, 26)]
    for ox, oy in oil_zones:
        grid[oy][ox] = "O"

    boost_zones = [(8, 16), (8, 17), (42, 16), (42, 17)]
    for bx, by in boost_zones:
        grid[by][bx] = "B"
        
    # Checkpoints
    checkpoints = [
        {"id": 1, "x": 20, "y": 8, "name": "Thermal Start"},
        {"id": 2, "x": 42, "y": 8, "name": "Northeast Bend"},
        {"id": 3, "x": 42, "y": 18, "name": "East Booster"},
        {"id": 4, "x": 30, "y": 26, "name": "Ash Straight"},
        {"id": 5, "x": 8, "y": 26, "name": "Southwest Bend"},
        {"id": 6, "x": 8, "y": 13, "name": "West Booster"}
    ]
    
    # Spawn points
    starting_grid = [
        {"x": 12, "y": 8, "direction": "east"},
        {"x": 11, "y": 8, "direction": "east"},
        {"x": 10, "y": 8, "direction": "east"},
        {"x": 9, "y": 8, "direction": "east"}
    ]

    data = {
        "name": "Volcanic Heat Run",
        "description": "An extreme race circuit surrounded by active lava. Run through cooling water pools to offset engine heat, but avoid slick oil spills.",
        "creator": "Magma Core Designer",
        "version": "1.0",
        "grid_size": {"width": width, "height": height},
        "laps": 3,
        "difficulty": "extreme",
        "tile_size": 32,
        "tile_palette": {
            "W": "wall",
            "G": "grass",
            "A": "asphalt",
            "O": "oil_slick",
            "B": "boost",
            "L": "lava",
            "H": "water"
        },
        "grid": serialize_grid(grid),
        "checkpoints": checkpoints,
        "starting_grid": starting_grid,
        "decorations": [
            {"type": "tire_stack", "x": 7.5, "y": 7.5},
            {"type": "tire_stack", "x": 43.5, "y": 26.5}
        ]
    }
    
    save_track_file("data/volcanic_heat.json", data)

if __name__ == "__main__":
    generate_mzansi_asphalt()
    generate_kalahari_drift()
    generate_drakensberg_ice()
    generate_volcanic_heat()
