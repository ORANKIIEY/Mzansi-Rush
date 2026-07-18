import pygame
import json
import os
import sys
import copy
from typing import Dict, List, Tuple, Optional

# Add parent dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Racetrack, TileDefinition, Checkpoint, SpawnPoint, Decoration, GridSize
from src.validator import validate_track

class Editor:
    def __init__(self, track_file: str):
        pygame.init()
        pygame.font.init()
        self.screen_w = 1280
        self.screen_h = 720
        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h))
        pygame.display.set_caption("Mzansi Rush - Racetrack Grid Editor")
        self.clock = pygame.time.Clock()

        # Load configurations
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.track_file = track_file
        self.schema_path = os.path.join(self.base_dir, "data", "world_schema.json")
        self.tile_defs_path = os.path.join(self.base_dir, "data", "tile_definitions.json")

        self.tile_defs: Dict[str, TileDefinition] = {}
        self.load_tile_definitions()

        # Load or create track
        self.track: Racetrack = None
        self.load_track()

        # Viewport Settings (Camera)
        self.zoom_level = 1.0
        self.min_zoom = 0.15
        self.max_zoom = 4.0
        self.camera_offset = [50.0, 50.0]
        self.panning = False
        self.pan_start = (0, 0)
        self.grid_visible = True

        # Editor Tools State
        self.selected_category = "tiles"  # "tiles", "entities"
        self.selected_tile_type = "asphalt"  # Asphalt default
        self.selected_entity_type = "checkpoint"  # checkpoint, spawn, decoration
        self.selected_direction = "east"  # for spawns
        self.selected_decoration_type = "tree"  # for decorations

        # Undo / Redo History
        self.undo_stack = []
        self.redo_stack = []

        # Validation status
        self.validation_result = {"valid": True, "errors": [], "warnings": []}
        self.run_validation()

        # Font
        self.font_small = pygame.font.SysFont("Outfit", 14)
        self.font_medium = pygame.font.SysFont("Outfit", 18)
        self.font_large = pygame.font.SysFont("Outfit", 22)
        self.font_title = pygame.font.SysFont("Outfit", 26, bold=True)

        # Scrolling in sidebar
        self.sidebar_scroll = 0

    def load_tile_definitions(self):
        try:
            with open(self.tile_defs_path, "r") as f:
                data = json.load(f)
                for name, d in data["tiles"].items():
                    self.tile_defs[name] = TileDefinition.from_dict(name, d)
        except Exception as e:
            print(f"Error loading tile definitions: {e}")
            sys.exit(1)

    def load_track(self):
        if os.path.exists(self.track_file):
            try:
                with open(self.track_file, "r") as f:
                    data = json.load(f)
                    self.track = Racetrack.from_dict(data)
                print(f"Loaded track: {self.track.name}")
            except Exception as e:
                print(f"Failed to load track from {self.track_file}: {e}")
                self.create_default_track()
        else:
            self.create_default_track()

    def create_default_track(self):
        print(f"Creating a new default track at: {self.track_file}")
        # Default 40x30 track filled with grass, walled around borders
        w, h = 40, 30
        grid = []
        for r in range(h):
            if r == 0 or r == h - 1:
                grid.append("W" * w)
            else:
                grid.append("W" + "G" * (w - 2) + "W")

        # Basic palette
        palette = {
            "W": "wall",
            "G": "grass",
            "A": "asphalt",
            "D": "dirt",
            "M": "mud",
            "I": "ice",
            "O": "oil_slick",
            "B": "boost",
            "L": "lava",
            "H": "water"
        }

        # Place a default asphalt starting loop
        for r in range(1, 10):
            row_list = list(grid[r])
            for c in range(1, 15):
                if r == 1 or r == 9 or c == 1 or c == 14:
                    row_list[c] = "A"
            grid[r] = "".join(row_list)

        self.track = Racetrack(
            name="New Racetrack",
            description="Created with the Mzansi Rush Map Editor",
            creator="Designer",
            version="1.0",
            grid_size=GridSize(w, h),
            tile_palette=palette,
            grid=grid,
            checkpoints=[
                Checkpoint(id=1, x=2, y=1, name="Start/Finish"),
                Checkpoint(id=2, x=13, y=5, name="East Turn"),
                Checkpoint(id=3, x=7, y=9, name="South Straight")
            ],
            starting_grid=[
                SpawnPoint(x=2, y=1, direction="east"),
                SpawnPoint(x=3, y=1, direction="east"),
                SpawnPoint(x=4, y=1, direction="east"),
                SpawnPoint(x=5, y=1, direction="east")
            ]
        )

    def save_track(self):
        try:
            # First run validation to alert designer
            self.run_validation()
            with open(self.track_file, "w") as f:
                json.dump(self.track.to_dict(), f, indent=2)
            print(f"Track saved to '{self.track_file}'")
            return True
        except Exception as e:
            print(f"Error saving track: {e}")
            return False

    def run_validation(self):
        self.validation_result = validate_track(
            self.track.to_dict(),
            self.schema_path,
            self.tile_defs_path
        )

    def push_history(self):
        # Save a copy of grid and entities for undoing
        state = {
            "grid": list(self.track.grid),
            "checkpoints": [copy.deepcopy(cp) for cp in self.track.checkpoints],
            "starting_grid": [copy.deepcopy(sp) for sp in self.track.starting_grid],
            "decorations": [copy.deepcopy(dec) for dec in self.track.decorations]
        }
        self.undo_stack.append(state)
        # Cap undo history at 50 states
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return
        current_state = {
            "grid": list(self.track.grid),
            "checkpoints": [copy.deepcopy(cp) for cp in self.track.checkpoints],
            "starting_grid": [copy.deepcopy(sp) for sp in self.track.starting_grid],
            "decorations": [copy.deepcopy(dec) for dec in self.track.decorations]
        }
        self.redo_stack.append(current_state)
        prev = self.undo_stack.pop()
        self.track.grid = prev["grid"]
        self.track.checkpoints = prev["checkpoints"]
        self.track.starting_grid = prev["starting_grid"]
        self.track.decorations = prev["decorations"]
        self.run_validation()

    def redo(self):
        if not self.redo_stack:
            return
        current_state = {
            "grid": list(self.track.grid),
            "checkpoints": [copy.deepcopy(cp) for cp in self.track.checkpoints],
            "starting_grid": [copy.deepcopy(sp) for sp in self.track.starting_grid],
            "decorations": [copy.deepcopy(dec) for dec in self.track.decorations]
        }
        self.undo_stack.append(current_state)
        next_state = self.redo_stack.pop()
        self.track.grid = next_state["grid"]
        self.track.checkpoints = next_state["checkpoints"]
        self.track.starting_grid = next_state["starting_grid"]
        self.track.decorations = next_state["decorations"]
        self.run_validation()

    def world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        sz = self.track.tile_size * self.zoom_level
        sx = int(wx * sz + self.camera_offset[0])
        sy = int(wy * sz + self.camera_offset[1])
        return sx, sy

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        sz = self.track.tile_size * self.zoom_level
        wx = (sx - self.camera_offset[0]) / sz
        wy = (sy - self.camera_offset[1]) / sz
        return wx, wy

    def get_tile_palette_char(self, tile_type: str) -> str:
        for char, t_type in self.track.tile_palette.items():
            if t_type == tile_type:
                return char
        # If not present in palette, find a free uppercase letter and assign it
        used_chars = set(self.track.tile_palette.keys())
        for i in range(65, 91):  # A-Z
            c = chr(i)
            if c not in used_chars:
                self.track.tile_palette[c] = tile_type
                return c
        return "?"

    def edit_tile(self, gx: int, gy: int, char: str):
        if 0 <= gy < self.track.grid_size.height and 0 <= gx < self.track.grid_size.width:
            row_list = list(self.track.grid[gy])
            if row_list[gx] != char:
                self.push_history()
                row_list[gx] = char
                self.track.grid[gy] = "".join(row_list)
                self.run_validation()

    def place_entity(self, gx: int, gy: int):
        if not (0 <= gy < self.track.grid_size.height and 0 <= gx < self.track.grid_size.width):
            return

        self.push_history()

        if self.selected_entity_type == "checkpoint":
            # Remove any checkpoint at this location first
            self.track.checkpoints = [cp for cp in self.track.checkpoints if not (cp.x == gx and cp.y == gy)]
            # Assign the next sequential ID
            next_id = 1
            if self.track.checkpoints:
                next_id = max(cp.id for cp in self.track.checkpoints) + 1
            self.track.checkpoints.append(Checkpoint(id=next_id, x=gx, y=gy, name=f"Sector {next_id}"))

        elif self.selected_entity_type == "spawn":
            # Remove any spawn at this location first
            self.track.starting_grid = [sp for sp in self.track.starting_grid if not (sp.x == gx and sp.y == gy)]
            self.track.starting_grid.append(SpawnPoint(x=gx, y=gy, direction=self.selected_direction))

        elif self.selected_entity_type == "decoration":
            # Remove any decoration at this location first (allowing multiple decorations if off-grid, but we enforce cell-level spacing here)
            self.track.decorations = [dec for dec in self.track.decorations if not (int(dec.x) == gx and int(dec.y) == gy)]
            self.track.decorations.append(Decoration(type=self.selected_decoration_type, x=gx + 0.5, y=gy + 0.5))

        self.run_validation()

    def erase_entity_or_tile(self, gx: int, gy: int):
        if not (0 <= gy < self.track.grid_size.height and 0 <= gx < self.track.grid_size.width):
            return

        self.push_history()
        # Check if an entity is at this cell
        has_entity = False
        
        # Check checkpoints
        prev_cp_count = len(self.track.checkpoints)
        self.track.checkpoints = [cp for cp in self.track.checkpoints if not (cp.x == gx and cp.y == gy)]
        if len(self.track.checkpoints) != prev_cp_count:
            # Reorder checkpoint IDs so they stay sequential 1 to N
            self.track.checkpoints.sort(key=lambda cp: cp.id)
            for idx, cp in enumerate(self.track.checkpoints):
                cp.id = idx + 1
            has_entity = True

        # Check spawns
        prev_sp_count = len(self.track.starting_grid)
        self.track.starting_grid = [sp for sp in self.track.starting_grid if not (sp.x == gx and sp.y == gy)]
        if len(self.track.starting_grid) != prev_sp_count:
            has_entity = True

        # Check decorations
        prev_dec_count = len(self.track.decorations)
        self.track.decorations = [dec for dec in self.track.decorations if not (int(dec.x) == gx and int(dec.y) == gy)]
        if len(self.track.decorations) != prev_dec_count:
            has_entity = True

        # If no entity, reset tile to grass ('G')
        if not has_entity:
            grass_char = self.get_tile_palette_char("grass")
            row_list = list(self.track.grid[gy])
            row_list[gx] = grass_char
            self.track.grid[gy] = "".join(row_list)

        self.run_validation()

    def draw_grid_canvas(self):
        sz = self.track.tile_size * self.zoom_level
        grid_w = self.track.grid_size.width
        grid_h = self.track.grid_size.height

        # Fill background with a very dark background representing off-map space
        pygame.draw.rect(self.screen, (20, 20, 20), (0, 0, 1000, 720))

        # We only render what's in the canvas viewport (x=0 to 1000, y=0 to 720)
        # Iterate over all cells
        for gy in range(grid_h):
            for gx in range(grid_w):
                # Check if visible in screen coordinates
                sx, sy = self.world_to_screen(gx, gy)
                if -sz < sx < 1000 and -sz < sy < 720:
                    tile_type = self.track.get_tile_type_at(gx, gy)
                    tile_def = self.tile_defs.get(tile_type)
                    color = tile_def.color_rgb if tile_def else (128, 128, 128)

                    # Draw tile rectangle
                    pygame.draw.rect(self.screen, color, (sx, sy, int(sz) + 1, int(sz) + 1))

                    # Special tile visual aids
                    if tile_type == "boost":
                        # Draw gold arrow indicating acceleration pad
                        pygame.draw.polygon(self.screen, (255, 255, 255), [
                            (sx + sz * 0.3, sy + sz * 0.7),
                            (sx + sz * 0.7, sy + sz * 0.5),
                            (sx + sz * 0.3, sy + sz * 0.3)
                        ])
                    elif tile_type == "oil_slick":
                        # Draw a dark circle
                        pygame.draw.circle(self.screen, (10, 10, 10), (int(sx + sz/2), int(sy + sz/2)), int(sz * 0.35))
                    elif tile_type == "lava":
                        # Draw heat glow lines
                        pygame.draw.line(self.screen, (255, 140, 0), (sx, sy + sz/2), (sx + sz, sy + sz/2), 2)
                    elif tile_type == "water":
                        # Draw wave indicators
                        pygame.draw.arc(self.screen, (255, 255, 255), (sx + sz*0.1, sy + sz*0.3, sz*0.8, sz*0.4), 0, 3.14, 2)

        # Draw grid lines if zoom is large enough
        if self.grid_visible and sz >= 10:
            for x in range(grid_w + 1):
                sx, sy_start = self.world_to_screen(x, 0)
                _, sy_end = self.world_to_screen(x, grid_h)
                if 0 <= sx <= 1000:
                    pygame.draw.line(self.screen, (40, 40, 40), (sx, sy_start), (sx, sy_end), 1)

            for y in range(grid_h + 1):
                sx_start, sy = self.world_to_screen(0, y)
                sx_end, _ = self.world_to_screen(grid_w, y)
                if 0 <= sy <= 720:
                    pygame.draw.line(self.screen, (40, 40, 40), (sx_start, sy), (sx_end, sy), 1)

        # Draw Checkpoints
        for cp in self.track.checkpoints:
            sx, sy = self.world_to_screen(cp.x, cp.y)
            if -sz < sx < 1000 and -sz < sy < 720:
                # Checkpoint flag circles
                pygame.draw.circle(self.screen, (0, 120, 255), (int(sx + sz/2), int(sy + sz/2)), int(sz * 0.4))
                pygame.draw.circle(self.screen, (255, 255, 255), (int(sx + sz/2), int(sy + sz/2)), int(sz * 0.4), 2)
                # Render ID number
                id_txt = self.font_medium.render(str(cp.id), True, (255, 255, 255))
                self.screen.blit(id_txt, (sx + sz/2 - id_txt.get_width()/2, sy + sz/2 - id_txt.get_height()/2))

        # Draw Starting Spawn Points
        for idx, sp in enumerate(self.track.starting_grid):
            sx, sy = self.world_to_screen(sp.x, sp.y)
            if -sz < sx < 1000 and -sz < sy < 720:
                # Vehicle spawn points draw as green circles with index label
                pygame.draw.circle(self.screen, (34, 177, 76), (int(sx + sz/2), int(sy + sz/2)), int(sz * 0.35))
                # Draw direction pointer line
                cx, cy = sx + sz/2, sy + sz/2
                rad = sz * 0.35
                if sp.direction == "east":
                    pygame.draw.line(self.screen, (255, 255, 255), (cx, cy), (cx + rad, cy), 3)
                elif sp.direction == "west":
                    pygame.draw.line(self.screen, (255, 255, 255), (cx, cy), (cx - rad, cy), 3)
                elif sp.direction == "north":
                    pygame.draw.line(self.screen, (255, 255, 255), (cx, cy), (cx, cy - rad), 3)
                elif sp.direction == "south":
                    pygame.draw.line(self.screen, (255, 255, 255), (cx, cy), (cx, cy + rad), 3)
                
                idx_txt = self.font_small.render(str(idx + 1), True, (255, 255, 255))
                self.screen.blit(idx_txt, (sx + 3, sy + 3))

        # Draw Decorations
        for dec in self.track.decorations:
            sx, sy = self.world_to_screen(dec.x, dec.y)
            if -sz < sx < 1000 and -sz < sy < 720:
                # Render tree vs tire stacks visually
                if dec.type == "tree":
                    # Tree green triangle
                    pygame.draw.polygon(self.screen, (0, 100, 0), [
                        (sx, sy + sz * 0.3),
                        (sx - sz * 0.3, sy + sz * 0.9),
                        (sx + sz * 0.3, sy + sz * 0.9)
                    ])
                    # Trunk
                    pygame.draw.rect(self.screen, (100, 50, 0), (sx - 3, sy + sz*0.9, 6, sz*0.2))
                elif dec.type == "tire_stack":
                    # Stack of circles
                    pygame.draw.circle(self.screen, (40, 40, 40), (int(sx), int(sy)), int(sz * 0.3))
                    pygame.draw.circle(self.screen, (255, 255, 255), (int(sx), int(sy)), int(sz * 0.3), 1)
                    pygame.draw.circle(self.screen, (0, 0, 0), (int(sx), int(sy)), int(sz * 0.12))
                else:
                    # General obstacle cross
                    pygame.draw.line(self.screen, (255, 0, 0), (sx - 5, sy - 5), (sx + 5, sy + 5), 2)
                    pygame.draw.line(self.screen, (255, 0, 0), (sx + 5, sy - 5), (sx - 5, sy + 5), 2)

    def draw_sidebar(self):
        # Sidebar rect
        sidebar_x = 1000
        sidebar_w = 280
        pygame.draw.rect(self.screen, (30, 30, 35), (sidebar_x, 0, sidebar_w, 720))
        # Divider line
        pygame.draw.line(self.screen, (60, 60, 70), (sidebar_x, 0), (sidebar_x, 720), 2)

        # Title Info
        title_y = 15
        track_name_txt = self.font_title.render(self.track.name, True, (255, 255, 255))
        self.screen.blit(track_name_txt, (sidebar_x + 15, title_y))

        meta_txt = self.font_small.render(f"Size: {self.track.grid_size.width}x{self.track.grid_size.height} | Laps: {self.track.laps} | Diff: {self.track.difficulty.upper()}", True, (180, 180, 190))
        self.screen.blit(meta_txt, (sidebar_x + 15, title_y + 35))

        # Mode Buttons (Tiles vs. Entities)
        btn_y = title_y + 65
        btn_h = 32
        btn_w = 115
        
        # Tiles category button
        tiles_btn_color = (70, 80, 150) if self.selected_category == "tiles" else (50, 50, 60)
        pygame.draw.rect(self.screen, tiles_btn_color, (sidebar_x + 15, btn_y, btn_w, btn_h), 0, 5)
        self.screen.blit(self.font_medium.render("Paint Tiles", True, (255, 255, 255)), (sidebar_x + 25, btn_y + 6))

        # Entities category button
        ents_btn_color = (70, 80, 150) if self.selected_category == "entities" else (50, 50, 60)
        pygame.draw.rect(self.screen, ents_btn_color, (sidebar_x + 150, btn_y, btn_w, btn_h), 0, 5)
        self.screen.blit(self.font_medium.render("Place Entities", True, (255, 255, 255)), (sidebar_x + 160, btn_y + 6))

        # List selectable items under selected category
        list_y = btn_y + 45
        
        if self.selected_category == "tiles":
            # Display list of tiles
            self.draw_tile_list(sidebar_x + 15, list_y)
        else:
            # Display entity placement options
            self.draw_entity_list(sidebar_x + 15, list_y)

        # Validation status at the bottom
        hud_y = 520
        pygame.draw.rect(self.screen, (22, 22, 26), (sidebar_x + 10, hud_y, sidebar_w - 20, 180), 0, 5)
        pygame.draw.rect(self.screen, (50, 50, 60), (sidebar_x + 10, hud_y, sidebar_w - 20, 180), 1, 5)

        hud_title_color = (50, 200, 50) if self.validation_result["valid"] else (220, 50, 50)
        hud_status_str = "STATUS: VALID TRACK" if self.validation_result["valid"] else "STATUS: INVALID TRACK"
        hud_title = self.font_medium.render(hud_status_str, True, hud_title_color)
        self.screen.blit(hud_title, (sidebar_x + 20, hud_y + 10))

        # Show errors or instructions
        err_y = hud_y + 35
        if not self.validation_result["valid"] and self.validation_result["errors"]:
            # Display first 5 errors
            for idx, err in enumerate(self.validation_result["errors"][:5]):
                # Wrap text if too long
                err_text = self.font_small.render(f"- {err[:35]}...", True, (240, 100, 100))
                self.screen.blit(err_text, (sidebar_x + 20, err_y))
                err_y += 18
            if len(self.validation_result["errors"]) > 5:
                more_txt = self.font_small.render(f"And {len(self.validation_result['errors']) - 5} more errors...", True, (240, 100, 100))
                self.screen.blit(more_txt, (sidebar_x + 20, err_y))
        else:
            # Check warnings
            warn_y = err_y
            if self.validation_result["warnings"]:
                for idx, warn in enumerate(self.validation_result["warnings"][:3]):
                    warn_text = self.font_small.render(f"- {warn[:35]}...", True, (220, 180, 50))
                    self.screen.blit(warn_text, (sidebar_x + 20, warn_y))
                    warn_y += 18
            else:
                ok_txt = self.font_small.render("All pathfinding & integrity checks passed!", True, (150, 220, 150))
                self.screen.blit(ok_txt, (sidebar_x + 20, warn_y))
                controls_y = warn_y + 30
                self.screen.blit(self.font_small.render("Controls: [L-Click] Draw/Place | [R-Click] Erase", True, (180, 180, 180)), (sidebar_x + 20, controls_y))
                self.screen.blit(self.font_small.render("Keys: Ctrl+S Save | Ctrl+Z Undo | Ctrl+Y Redo", True, (180, 180, 180)), (sidebar_x + 20, controls_y + 18))
                self.screen.blit(self.font_small.render("Drag Right-Mouse or WASD to Pan | Scroll Zoom", True, (180, 180, 180)), (sidebar_x + 20, controls_y + 36))

    def draw_tile_list(self, x: int, start_y: int):
        y = start_y
        sorted_tile_names = sorted(list(self.tile_defs.keys()))
        for name in sorted_tile_names:
            tile_def = self.tile_defs[name]
            
            # Draw selection highlight background
            is_selected = (name == self.selected_tile_type)
            bg_color = (60, 60, 80) if is_selected else (40, 40, 45)
            pygame.draw.rect(self.screen, bg_color, (x, y, 250, 36), 0, 4)
            if is_selected:
                pygame.draw.rect(self.screen, (100, 120, 220), (x, y, 250, 36), 1, 4)

            # Draw representative color swatch
            pygame.draw.rect(self.screen, tile_def.color_rgb, (x + 10, y + 8, 20, 20), 0, 2)
            pygame.draw.rect(self.screen, (255, 255, 255), (x + 10, y + 8, 20, 20), 1, 2)

            # Draw Label
            char = self.get_tile_palette_char(name)
            name_text = f"{name.capitalize()} ({char})"
            lbl = self.font_medium.render(name_text, True, (255, 255, 255))
            self.screen.blit(lbl, (x + 40, y + 8))

            # Hover/Click check
            mouse_pos = pygame.mouse.get_pos()
            if x <= mouse_pos[0] <= x + 250 and y <= mouse_pos[1] <= y + 36:
                if pygame.mouse.get_pressed()[0]:
                    self.selected_tile_type = name

            y += 40

    def draw_entity_list(self, x: int, start_y: int):
        y = start_y

        entities = [
            ("checkpoint", "Place Checkpoint (Flag)"),
            ("spawn", f"Place Spawn Point ({self.selected_direction.upper()})"),
            ("decoration", f"Place Dec: {self.selected_decoration_type.capitalize()}")
        ]

        for ent_id, label in entities:
            is_selected = (ent_id == self.selected_entity_type)
            bg_color = (60, 60, 80) if is_selected else (40, 40, 45)
            pygame.draw.rect(self.screen, bg_color, (x, y, 250, 36), 0, 4)
            if is_selected:
                pygame.draw.rect(self.screen, (100, 120, 220), (x, y, 250, 36), 1, 4)

            # Icon color
            icon_color = (0, 120, 255) if ent_id == "checkpoint" else ((34, 177, 76) if ent_id == "spawn" else (0, 100, 0))
            pygame.draw.circle(self.screen, icon_color, (x + 20, y + 18), 8)

            # Label
            lbl = self.font_medium.render(label, True, (255, 255, 255))
            self.screen.blit(lbl, (x + 40, y + 8))

            # Select
            mouse_pos = pygame.mouse.get_pos()
            if x <= mouse_pos[0] <= x + 250 and y <= mouse_pos[1] <= y + 36:
                if pygame.mouse.get_pressed()[0]:
                    self.selected_entity_type = ent_id

            y += 40

        # Sub-options based on entity selection
        sub_y = y + 10
        if self.selected_entity_type == "spawn":
            pygame.draw.rect(self.screen, (45, 45, 50), (x, sub_y, 250, 90), 0, 4)
            lbl = self.font_small.render("Select Spawn direction:", True, (180, 180, 180))
            self.screen.blit(lbl, (x + 10, sub_y + 10))
            dirs = ["north", "east", "south", "west"]
            dir_x = x + 10
            for d in dirs:
                is_sel = (d == self.selected_direction)
                d_color = (100, 120, 220) if is_sel else (70, 70, 75)
                pygame.draw.rect(self.screen, d_color, (dir_x, sub_y + 35, 52, 28), 0, 3)
                txt = self.font_small.render(d[:5].capitalize(), True, (255, 255, 255))
                self.screen.blit(txt, (dir_x + 6, sub_y + 40))

                mouse_pos = pygame.mouse.get_pos()
                if dir_x <= mouse_pos[0] <= dir_x + 52 and sub_y + 35 <= mouse_pos[1] <= sub_y + 63:
                    if pygame.mouse.get_pressed()[0]:
                        self.selected_direction = d
                
                dir_x += 58

        elif self.selected_entity_type == "decoration":
            pygame.draw.rect(self.screen, (45, 45, 50), (x, sub_y, 250, 90), 0, 4)
            lbl = self.font_small.render("Select Decoration type:", True, (180, 180, 180))
            self.screen.blit(lbl, (x + 10, sub_y + 10))
            decs = ["tree", "tire_stack", "barrier"]
            dec_x = x + 10
            for d in decs:
                is_sel = (d == self.selected_decoration_type)
                d_color = (100, 120, 220) if is_sel else (70, 70, 75)
                # Trim width slightly to fit
                w_btn = 72
                pygame.draw.rect(self.screen, d_color, (dec_x, sub_y + 35, w_btn, 28), 0, 3)
                txt = self.font_small.render(d.replace("_", " ").capitalize(), True, (255, 255, 255))
                self.screen.blit(txt, (dec_x + 5, sub_y + 40))

                mouse_pos = pygame.mouse.get_pos()
                if dec_x <= mouse_pos[0] <= dec_x + w_btn and sub_y + 35 <= mouse_pos[1] <= sub_y + 63:
                    if pygame.mouse.get_pressed()[0]:
                        self.selected_decoration_type = d
                
                dec_x += w_btn + 6

    def handle_keyboard_panning(self, keys):
        pan_speed = 8.0 / self.zoom_level
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.camera_offset[1] += pan_speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.camera_offset[1] -= pan_speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.camera_offset[0] += pan_speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.camera_offset[0] -= pan_speed

    def run(self):
        running = True
        while running:
            # Handle Keyboard hold movements
            keys = pygame.key.get_pressed()
            self.handle_keyboard_panning(keys)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                # Camera Zoom centering on mouse cursor
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4:  # Scroll Up -> Zoom In
                        mx, my = pygame.mouse.get_pos()
                        if mx < 1000:
                            wx, wy = self.screen_to_world(mx, my)
                            self.zoom_level = min(self.max_zoom, self.zoom_level * 1.1)
                            self.camera_offset[0] = mx - wx * (self.track.tile_size * self.zoom_level)
                            self.camera_offset[1] = my - wy * (self.track.tile_size * self.zoom_level)
                    elif event.button == 5:  # Scroll Down -> Zoom Out
                        mx, my = pygame.mouse.get_pos()
                        if mx < 1000:
                            wx, wy = self.screen_to_world(mx, my)
                            self.zoom_level = max(self.min_zoom, self.zoom_level / 1.1)
                            self.camera_offset[0] = mx - wx * (self.track.tile_size * self.zoom_level)
                            self.camera_offset[1] = my - wy * (self.track.tile_size * self.zoom_level)

                    # Panning start
                    elif event.button == 3:  # Right Click drag to pan
                        self.panning = True
                        self.pan_start = pygame.mouse.get_pos()
                    
                    # Painting start
                    elif event.button == 1:  # Left Click
                        mx, my = pygame.mouse.get_pos()
                        # If inside grid canvas
                        if mx < 1000:
                            gx, gy = self.screen_to_world(mx, my)
                            gx, gy = int(gx), int(gy)
                            if self.selected_category == "tiles":
                                char = self.get_tile_palette_char(self.selected_tile_type)
                                self.edit_tile(gx, gy, char)
                            else:
                                self.place_entity(gx, gy)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 3:
                        self.panning = False

                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    # Draw paint continuous drag for tiles
                    if pygame.mouse.get_pressed()[0] and mx < 1000:
                        gx, gy = self.screen_to_world(mx, my)
                        gx, gy = int(gx), int(gy)
                        if self.selected_category == "tiles":
                            char = self.get_tile_palette_char(self.selected_tile_type)
                            self.edit_tile(gx, gy, char)
                    
                    # Erase continuous drag
                    elif pygame.mouse.get_pressed()[2] and mx < 1000 and not self.panning:
                        gx, gy = self.screen_to_world(mx, my)
                        gx, gy = int(gx), int(gy)
                        self.erase_entity_or_tile(gx, gy)

                    # Panning calculation
                    if self.panning:
                        dx = mx - self.pan_start[0]
                        dy = my - self.pan_start[1]
                        self.camera_offset[0] += dx
                        self.camera_offset[1] += dy
                        self.pan_start = event.pos

                # Shortcuts
                elif event.type == pygame.KEYDOWN:
                    # Check modifier keys
                    ctrl_held = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL] or keys[pygame.K_LMETA] or keys[pygame.K_RMETA]
                    
                    if ctrl_held:
                        if event.key == pygame.K_s:
                            self.save_track()
                        elif event.key == pygame.K_z:
                            self.undo()
                        elif event.key == pygame.K_y:
                            self.redo()
                        elif event.key == pygame.K_v:
                            self.run_validation()
                    else:
                        if event.key == pygame.K_g:
                            self.grid_visible = not self.grid_visible

            # Rendering
            self.screen.fill((10, 10, 12))
            self.draw_grid_canvas()
            self.draw_sidebar()
            
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

if __name__ == "__main__":
    track_path = os.path.join("data", "sample_base.json")
    if len(sys.argv) > 1:
        track_path = sys.argv[1]
    
    # Ensure full absolute path
    if not os.path.isabs(track_path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        track_path = os.path.join(base, track_path)

    # Launch editor
    editor = Editor(track_path)
    editor.run()
