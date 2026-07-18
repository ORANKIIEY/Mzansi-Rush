"""Tile-based track engine powered by the colleague's JSON data format.

Loads a track JSON (mzansi_asphalt, kalahari_drift, etc.) plus
tile_definitions.json and builds a pre-rendered world surface.
Provides tile-physics lookups (friction, speed_mult, damage, drivable).
"""

import json
import pygame
from src.models import Racetrack, TileDefinition

TILE_DEFS_PATH = "data/tile_definitions.json"
DEFAULT_TRACK  = "data/mzansi_asphalt.json"

# Available track files shown in lobby selector
AVAILABLE_TRACKS = [
    ("mzansi_asphalt",   "data/mzansi_asphalt.json"),
    ("kalahari_drift",   "data/kalahari_drift.json"),
    ("drakensberg_ice",  "data/drakensberg_ice.json"),
    ("volcanic_heat",    "data/volcanic_heat.json"),
]

# Render at 2× the JSON tile_size so the world is large enough for proper camera travel
RENDER_SCALE = 2

# Direction strings from JSON → physics angle (0=up, 90=right, 180=down, 270=left)
_DIR_TO_ANGLE = {"north": 0.0, "east": 90.0, "south": 180.0, "west": 270.0}

# Decoration colours
_TREE_DARK  = ( 15,  80,  15)
_TREE_MID   = ( 28, 120,  28)
_TIRE_COL   = ( 28,  28,  28)
_BARRIER_A  = (255, 140,   0)
_BARRIER_B  = (230, 230, 230)


class Track:
    def __init__(self, track_path: str = DEFAULT_TRACK):
        # ── tile definitions ──────────────────────────────────────────
        with open(TILE_DEFS_PATH) as f:
            td_raw = json.load(f)
        self.tile_defs: dict[str, TileDefinition] = {
            name: TileDefinition.from_dict(name, d)
            for name, d in td_raw["tiles"].items()
        }

        # ── track layout ──────────────────────────────────────────────
        with open(track_path) as f:
            track_raw = json.load(f)
        self.racetrack: Racetrack = Racetrack.from_dict(track_raw)

        ts = self.racetrack.tile_size        # JSON tile size (usually 32)
        self._ts   = ts
        self._rts  = ts * RENDER_SCALE       # rendered tile size (64)

        self.world_w = self.racetrack.grid_size.width  * self._rts
        self.world_h = self.racetrack.grid_size.height * self._rts

        # ── start position / heading ──────────────────────────────────
        spawn = self.racetrack.starting_grid[0]
        self.start_x     = (spawn.x + 0.5) * self._rts
        self.start_y     = (spawn.y + 0.5) * self._rts
        self.start_angle = _DIR_TO_ANGLE.get(spawn.direction, 90.0)

        # ── laps from JSON ────────────────────────────────────────────
        self.total_laps = self.racetrack.laps

        # ── checkpoints (world coords, sorted by id) ──────────────────
        self.checkpoints = [
            ((cp.x + 0.5) * self._rts, (cp.y + 0.5) * self._rts, cp.name)
            for cp in sorted(self.racetrack.checkpoints, key=lambda c: c.id)
        ]
        self.cp_radius_sq = (self._rts * 1.8) ** 2

        # ── track meta ────────────────────────────────────────────────
        self.name        = self.racetrack.name
        self.difficulty  = self.racetrack.difficulty

        self._surface = None
        self._built   = False

    # ── tile physics lookups ──────────────────────────────────────────────────

    def get_tile_def_at(self, wx: float, wy: float) -> TileDefinition | None:
        gx = int(wx / self._rts)
        gy = int(wy / self._rts)
        return self._tile_def(gx, gy)

    def is_drivable(self, wx: float, wy: float) -> bool:
        td = self.get_tile_def_at(wx, wy)
        return td.drivable if td else False

    # ── checkpoint ────────────────────────────────────────────────────────────

    def checkpoint_reached(self, wx: float, wy: float, cp_idx: int) -> bool:
        if cp_idx >= len(self.checkpoints):
            return False
        cx, cy, _ = self.checkpoints[cp_idx]
        return (wx - cx) ** 2 + (wy - cy) ** 2 < self.cp_radius_sq

    # ── rendering ─────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float):
        if not self._built:
            self._build_surface()
        sw, sh = surface.get_width(), surface.get_height()
        clip = pygame.Rect(int(cam_x), int(cam_y), sw, sh)
        clip.clamp_ip(pygame.Rect(0, 0, self.world_w, self.world_h))
        surface.blit(self._surface, (clip.x - int(cam_x), clip.y - int(cam_y)), clip)

    def draw_minimap(self, surface: pygame.Surface, x: int, y: int, w: int, h: int,
                     car_wx: float, car_wy: float):
        if not self._built:
            self._build_surface()
        mm = pygame.transform.smoothscale(self._surface, (w, h))
        surface.blit(mm, (x, y))
        # Car dot
        dx = int(car_wx / self.world_w * w)
        dy = int(car_wy / self.world_h * h)
        pygame.draw.circle(surface, (220, 40, 40), (x + dx, y + dy), 4)
        pygame.draw.circle(surface, (255, 255, 255), (x + dx, y + dy), 4, 1)

    # ── internals ─────────────────────────────────────────────────────────────

    def _tile_def(self, gx: int, gy: int) -> TileDefinition | None:
        rt = self.racetrack
        if not (0 <= gx < rt.grid_size.width and 0 <= gy < rt.grid_size.height):
            return self.tile_defs.get("wall")
        char      = rt.get_tile_char_at(gx, gy)
        tile_type = rt.tile_palette.get(char, "wall")
        return self.tile_defs.get(tile_type)

    def _build_surface(self):
        rts  = self._rts
        rt   = self.racetrack
        surf = pygame.Surface((self.world_w, self.world_h))

        for gy in range(rt.grid_size.height):
            for gx in range(rt.grid_size.width):
                td  = self._tile_def(gx, gy)
                col = tuple(td.color_rgb) if td else (50, 50, 50)
                rx, ry = gx * rts, gy * rts
                pygame.draw.rect(surf, col, (rx, ry, rts, rts))
                # Grid shadow (darkened edge)
                edge = tuple(max(0, c - 18) for c in col)
                pygame.draw.rect(surf, edge, (rx, ry, rts, rts), 1)

        # Draw decorations
        for dec in rt.decorations:
            self._draw_decoration(surf, dec.type, dec.x * rts, dec.y * rts, rts)

        # Start / finish marker
        if self.checkpoints:
            cx, cy, _ = self.checkpoints[0]
            pygame.draw.line(surf, (255, 255, 255),
                             (int(cx - rts), int(cy)), (int(cx + rts), int(cy)), 4)
            pygame.draw.line(surf, (255, 255, 255),
                             (int(cx), int(cy - rts)), (int(cx), int(cy + rts)), 4)
            # Checker blocks
            for k in range(6):
                col_k = (255, 255, 255) if k % 2 == 0 else (10, 10, 10)
                pygame.draw.rect(surf, col_k,
                                 (int(cx - rts + k * rts // 3), int(cy - 6),
                                  rts // 3, 12))

        self._surface = surf
        self._built   = True

    def _draw_decoration(self, surf: pygame.Surface, dec_type: str,
                          wx: float, wy: float, rts: int):
        r = int(rts * 0.38)
        if dec_type == "tree":
            pygame.draw.circle(surf, _TREE_DARK, (int(wx), int(wy)), r)
            pygame.draw.circle(surf, _TREE_MID,  (int(wx), int(wy)), max(1, r - 4))
        elif dec_type == "tire_stack":
            pygame.draw.circle(surf, _TIRE_COL, (int(wx), int(wy)), r)
            pygame.draw.circle(surf, (70, 70, 70), (int(wx), int(wy)), r, 3)
        elif dec_type == "barrier":
            bw, bh = int(rts * 0.72), int(rts * 0.32)
            br = pygame.Rect(int(wx - bw//2), int(wy - bh//2), bw, bh)
            pygame.draw.rect(surf, _BARRIER_A, br, border_radius=4)
            pygame.draw.rect(surf, _BARRIER_B, br, 2, border_radius=4)
