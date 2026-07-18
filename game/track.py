"""Tile-based track engine.

Physics: tile grid (friction / speed_mult / damage / drivable).
Visuals: BFS road-trace → Catmull-Rom smooth centerline → thick-line
         render with red/white curbs, textured background, dashed
         centre line — matching the original polished aesthetic.
"""

import json
import math
import random
from collections import deque

import pygame
from src.models import Racetrack, TileDefinition

TILE_DEFS_PATH = "data/tile_definitions.json"
DEFAULT_TRACK  = "data/mzansi_asphalt.json"

AVAILABLE_TRACKS = [
    ("mzansi_asphalt",   "data/mzansi_asphalt.json"),
    ("kalahari_drift",   "data/kalahari_drift.json"),
    ("drakensberg_ice",  "data/drakensberg_ice.json"),
    ("volcanic_heat",    "data/volcanic_heat.json"),
]

RENDER_SCALE = 2   # rendered tile = JSON tile_size × 2 (gives ~128-px tiles)

_DIR_TO_ANGLE = {"north": 0.0, "east": 90.0, "south": 180.0, "west": 270.0}

# ── dark background palette (replaces raw JSON colors) ──────────────────────
_BG = {
    "wall":      ( 32,  30,  28),
    "grass":     ( 22,  42,  15),
    "dirt":      ( 72,  48,  18),
    "mud":       ( 48,  34,  22),
    "ice":       ( 92, 128, 148),
    "asphalt":   ( 28,  25,  22),   # background under road (nearly black)
    "boost":     ( 28,  25,  22),
    "lava":      (140,  32,   0),
    "water":     ( 18,  72, 148),
    "oil_slick": ( 14,  14,  16),
}

# ── road surface color per tile type ────────────────────────────────────────
_ROAD = {
    "asphalt":   ( 86,  82,  78),
    "boost":     ( 86,  82,  78),
    "dirt":      (105,  70,  28),
    "mud":       ( 72,  52,  32),
    "ice":       (152, 192, 212),
    "water":     ( 34, 112, 200),
    "lava":      (175,  50,   0),
    "oil_slick": ( 24,  24,  26),
}
_ROAD_DEFAULT = ( 86,  82,  78)

# ── curb & marking colours ───────────────────────────────────────────────────
_CURB_R = (200,  38,  38)
_CURB_W = (224, 222, 218)
_DASH   = (210, 185,  38)    # yellow centre dashes
_SF_W   = (240, 240, 240)
_SF_B   = (  8,   8,   8)

# ── decoration colours ───────────────────────────────────────────────────────
_TREE_D  = ( 12,  72,  12)
_TREE_M  = ( 24, 108,  24)
_TIRE    = ( 24,  24,  24)
_BARR_A  = (255, 140,   0)
_BARR_B  = (228, 228, 228)


# ── Catmull-Rom ──────────────────────────────────────────────────────────────

def _cr(p0, p1, p2, p3, t):
    t2, t3 = t*t, t*t*t
    return (
        0.5*((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2
             + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
        0.5*((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2
             + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3),
    )


def _smooth(pts, spp=10):
    n, out = len(pts), []
    for i in range(n):
        p0, p1 = pts[(i-1)%n], pts[i]
        p2, p3 = pts[(i+1)%n], pts[(i+2)%n]
        for j in range(spp):
            out.append(_cr(p0, p1, p2, p3, j/spp))
    return out


# ── BFS road trace ───────────────────────────────────────────────────────────

def _bfs(drivable, gw, gh, sx, sy, ex, ey):
    if not (0<=sx<gw and 0<=sy<gh and drivable[sy][sx]): return []
    q   = deque()
    q.append((sx, sy, []))
    vis = {(sx, sy)}
    while q:
        x, y, path = q.popleft()
        path = path + [(x, y)]
        if x == ex and y == ey:
            return path
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx, ny = x+dx, y+dy
            if 0<=nx<gw and 0<=ny<gh and drivable[ny][nx] and (nx,ny) not in vis:
                vis.add((nx, ny))
                q.append((nx, ny, path))
    return []


class Track:
    def __init__(self, track_path: str = DEFAULT_TRACK):
        with open(TILE_DEFS_PATH) as f:
            td_raw = json.load(f)
        self.tile_defs: dict[str, TileDefinition] = {
            name: TileDefinition.from_dict(name, d)
            for name, d in td_raw["tiles"].items()
        }

        with open(track_path) as f:
            track_raw = json.load(f)
        self.racetrack: Racetrack = Racetrack.from_dict(track_raw)

        ts         = self.racetrack.tile_size
        self._ts   = ts
        self._rts  = ts * RENDER_SCALE           # rendered tile size (64 px)

        self.world_w = self.racetrack.grid_size.width  * self._rts
        self.world_h = self.racetrack.grid_size.height * self._rts

        spawn            = self.racetrack.starting_grid[0]
        self.start_x     = (spawn.x + 0.5) * self._rts
        self.start_y     = (spawn.y + 0.5) * self._rts
        self.start_angle = _DIR_TO_ANGLE.get(spawn.direction, 90.0)

        self.total_laps  = self.racetrack.laps

        self.checkpoints = [
            ((cp.x + 0.5) * self._rts, (cp.y + 0.5) * self._rts, cp.name)
            for cp in sorted(self.racetrack.checkpoints, key=lambda c: c.id)
        ]
        self.cp_radius_sq = (self._rts * 1.8) ** 2

        self.name       = self.racetrack.name
        self.difficulty = self.racetrack.difficulty

        self._surface = None
        self._built   = False

    # ── physics ───────────────────────────────────────────────────────────────

    def get_tile_def_at(self, wx: float, wy: float) -> TileDefinition | None:
        return self._tile_def(int(wx / self._rts), int(wy / self._rts))

    def is_drivable(self, wx: float, wy: float) -> bool:
        td = self.get_tile_def_at(wx, wy)
        return td.drivable if td else False

    def checkpoint_reached(self, wx: float, wy: float, cp_idx: int) -> bool:
        if cp_idx >= len(self.checkpoints):
            return False
        cx, cy, _ = self.checkpoints[cp_idx]
        return (wx-cx)**2 + (wy-cy)**2 < self.cp_radius_sq

    # ── rendering ─────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float):
        if not self._built:
            self._build_surface()
        sw, sh = surface.get_width(), surface.get_height()
        clip   = pygame.Rect(int(cam_x), int(cam_y), sw, sh)
        clip.clamp_ip(pygame.Rect(0, 0, self.world_w, self.world_h))
        surface.blit(self._surface, (clip.x - int(cam_x), clip.y - int(cam_y)), clip)

    def draw_minimap(self, surface: pygame.Surface, x, y, w, h,
                     car_wx: float, car_wy: float):
        if not self._built:
            self._build_surface()
        mm = pygame.transform.smoothscale(self._surface, (w, h))
        surface.blit(mm, (x, y))
        dx = int(car_wx / self.world_w * w)
        dy = int(car_wy / self.world_h * h)
        pygame.draw.circle(surface, (220, 40, 40), (x+dx, y+dy), 4)
        pygame.draw.circle(surface, (255, 255, 255), (x+dx, y+dy), 4, 1)

    # ── internal ──────────────────────────────────────────────────────────────

    def _tile_def(self, gx, gy) -> TileDefinition | None:
        rt = self.racetrack
        if not (0 <= gx < rt.grid_size.width and 0 <= gy < rt.grid_size.height):
            return self.tile_defs.get("wall")
        char      = rt.get_tile_char_at(gx, gy)
        tile_type = rt.tile_palette.get(char, "wall")
        return self.tile_defs.get(tile_type)

    def _tile_name(self, gx, gy) -> str:
        td = self._tile_def(gx, gy)
        return td.name if td else "wall"

    def _is_driv(self, gx, gy) -> bool:
        td = self._tile_def(gx, gy)
        return td.drivable if td else False

    # ── road trace (BFS through drivable tiles) ───────────────────────────────

    def _trace_road(self):
        rt   = self.racetrack
        gw   = rt.grid_size.width
        gh   = rt.grid_size.height
        rts  = self._rts

        driv = [[self._is_driv(gx, gy) for gx in range(gw)] for gy in range(gh)]

        spawn = rt.starting_grid[0]
        cps   = [(int(cp.x), int(cp.y))
                 for cp in sorted(rt.checkpoints, key=lambda c: c.id)]
        seq   = [(int(spawn.x), int(spawn.y))] + cps + [(int(spawn.x), int(spawn.y))]

        full = [seq[0]]
        for i in range(len(seq)-1):
            seg = _bfs(driv, gw, gh, seq[i][0], seq[i][1], seq[i+1][0], seq[i+1][1])
            if seg:
                full.extend(seg[1:])

        # Convert to world coords, subsample every 2 tiles, smooth
        world = [(p[0]*rts + rts//2, p[1]*rts + rts//2) for p in full[::2]]
        return _smooth(world, spp=10)

    # ── main surface builder ──────────────────────────────────────────────────

    def _build_surface(self):
        rts  = self._rts
        rt   = self.racetrack
        surf = pygame.Surface((self.world_w, self.world_h))

        # ── 1. Background tiles (dark palette + texture) ──────────────
        rng_bg = random.Random(42)
        for gy in range(rt.grid_size.height):
            for gx in range(rt.grid_size.width):
                name   = self._tile_name(gx, gy)
                col    = _BG.get(name, (28, 25, 22))
                rx, ry = gx*rts, gy*rts
                pygame.draw.rect(surf, col, (rx, ry, rts, rts))

                # per-tile texture variation
                t_rng = random.Random(gx*97 + gy*31 + 7)
                if name == "grass":
                    for _ in range(7):
                        dx = t_rng.randint(2, rts-3)
                        dy = t_rng.randint(2, rts-3)
                        r  = t_rng.randint(2, 5)
                        sc = tuple(max(0, c - t_rng.randint(4, 12)) for c in col)
                        pygame.draw.circle(surf, sc, (rx+dx, ry+dy), r)
                elif name == "dirt":
                    for _ in range(5):
                        dx = t_rng.randint(2, rts-3)
                        dy = t_rng.randint(2, rts-3)
                        r  = t_rng.randint(2, 5)
                        sc = tuple(max(0, min(255, c + t_rng.randint(-10, 14))) for c in col)
                        pygame.draw.circle(surf, sc, (rx+dx, ry+dy), r)
                elif name == "lava":
                    for _ in range(3):
                        dx = t_rng.randint(4, rts-5)
                        dy = t_rng.randint(4, rts-5)
                        r  = t_rng.randint(3, 8)
                        gc = (min(255, col[0]+55), min(80, col[1]+20), 0)
                        pygame.draw.circle(surf, gc, (rx+dx, ry+dy), r)
                elif name == "ice":
                    for _ in range(2):
                        dx = t_rng.randint(4, rts-5)
                        dy = t_rng.randint(4, rts-5)
                        pygame.draw.circle(surf, (180, 215, 232),
                                           (rx+dx, ry+dy), t_rng.randint(2, 5))
                elif name == "water":
                    for _ in range(2):
                        yw = ry + t_rng.randint(8, rts-9)
                        pygame.draw.line(surf, (28, 98, 185),
                                        (rx+4, yw), (rx+rts-4, yw+t_rng.randint(-5, 5)), 2)
                elif name in ("asphalt", "boost", "oil_slick"):
                    if t_rng.random() < 0.3:
                        x1 = rx + t_rng.randint(6, rts-6)
                        y1 = ry + t_rng.randint(6, rts-6)
                        x2 = x1 + t_rng.randint(-14, 14)
                        y2 = y1 + t_rng.randint(-14, 14)
                        pygame.draw.line(surf, (20, 18, 15), (x1, y1), (x2, y2), 1)

        # ── 2. Trace smooth visual centerline via BFS ─────────────────
        cl    = self._trace_road()
        n_cl  = len(cl)
        ROAD_W = int(rts * 2.5)    # visual road width (2.5 rendered tiles)
        CURB_W = 16                 # extra width for curb stripe each side

        # ── 3. Curbs (alternating red / white every ~50 px) ──────────
        dist = 0.0
        for i in range(n_cl):
            j  = (i+1) % n_cl
            p1 = (int(cl[i][0]), int(cl[i][1]))
            p2 = (int(cl[j][0]), int(cl[j][1]))
            seg = math.hypot(cl[j][0]-cl[i][0], cl[j][1]-cl[i][1])
            col = _CURB_R if int(dist/48) % 2 == 0 else _CURB_W
            pygame.draw.line(surf, col, p1, p2, ROAD_W + CURB_W*2)
            dist += seg

        # ── 4. Road surface (colour from tile type at each point) ─────
        for i in range(n_cl):
            j   = (i+1) % n_cl
            p1  = (int(cl[i][0]), int(cl[i][1]))
            p2  = (int(cl[j][0]), int(cl[j][1]))
            td  = self._tile_def(int(cl[i][0]/rts), int(cl[i][1]/rts))
            col = _ROAD.get(td.name if td else "asphalt", _ROAD_DEFAULT)
            pygame.draw.line(surf, col, p1, p2, ROAD_W)

        # ── 5. Centre dashes (yellow, every ~65 px gap) ───────────────
        dist = 0.0
        for i in range(n_cl):
            j    = (i+1) % n_cl
            p1   = (int(cl[i][0]), int(cl[i][1]))
            p2   = (int(cl[j][0]), int(cl[j][1]))
            seg  = math.hypot(cl[j][0]-cl[i][0], cl[j][1]-cl[i][1])
            slot = int(dist / 32)   # dash every 32 px, gap every other slot
            if slot % 2 == 0:
                pygame.draw.line(surf, _DASH, p1, p2, 3)
            dist += seg

        # ── 6. Boost pads ─────────────────────────────────────────────
        for gy in range(rt.grid_size.height):
            for gx in range(rt.grid_size.width):
                if self._tile_name(gx, gy) == "boost":
                    rx, ry = gx*rts, gy*rts
                    pad    = pygame.Rect(rx+8, ry+8, rts-16, rts-16)
                    pygame.draw.rect(surf, (178, 142, 10), pad, border_radius=6)
                    pygame.draw.rect(surf, (255, 215, 0),  pad, 3, border_radius=6)
                    # arrow
                    cx2, cy2 = rx+rts//2, ry+rts//2
                    pygame.draw.polygon(surf, (255, 230, 50),
                                        [(cx2-8, cy2+7), (cx2+8, cy2+7), (cx2, cy2-9)])

        # ── 7. Decorations ────────────────────────────────────────────
        for dec in rt.decorations:
            self._draw_decoration(surf, dec.type, dec.x*rts, dec.y*rts, rts)

        # ── 8. Start / finish line ────────────────────────────────────
        if cl:
            # Find actual start point (first checkpoint world coord)
            if self.checkpoints:
                sfx, sfy, _ = self.checkpoints[0]
            else:
                sfx, sfy = cl[0]
            # Cross-track line direction: perpendicular to road at that point
            # Use nearest centerline point's tangent
            nearest_i = min(range(n_cl),
                            key=lambda k: (cl[k][0]-sfx)**2 + (cl[k][1]-sfy)**2)
            ni  = (nearest_i+1) % n_cl
            tdx = cl[ni][0] - cl[nearest_i][0]
            tdy = cl[ni][1] - cl[nearest_i][1]
            td  = math.hypot(tdx, tdy) or 1
            nx, ny = -tdy/td, tdx/td
            hw  = ROAD_W // 2
            p1  = (sfx + nx*hw, sfy + ny*hw)
            p2  = (sfx - nx*hw, sfy - ny*hw)
            blocks = 10
            for k in range(blocks):
                t0, t1 = k/blocks, (k+1)/blocks
                col_k  = _SF_W if k % 2 == 0 else _SF_B
                quad   = [
                    (int(p1[0]+(p2[0]-p1[0])*t0), int(p1[1]+(p2[1]-p1[1])*t0)),
                    (int(p1[0]+(p2[0]-p1[0])*t1), int(p1[1]+(p2[1]-p1[1])*t1)),
                    (int(p1[0]+(p2[0]-p1[0])*t1+tdx/td*18),
                     int(p1[1]+(p2[1]-p1[1])*t1+tdy/td*18)),
                    (int(p1[0]+(p2[0]-p1[0])*t0+tdx/td*18),
                     int(p1[1]+(p2[1]-p1[1])*t0+tdy/td*18)),
                ]
                pygame.draw.polygon(surf, col_k, quad)

        self._surface = surf
        self._built   = True

    def _draw_decoration(self, surf, dec_type, wx, wy, rts):
        r = int(rts * 0.36)
        if dec_type == "tree":
            pygame.draw.circle(surf, _TREE_D, (int(wx), int(wy)), r)
            pygame.draw.circle(surf, _TREE_M, (int(wx), int(wy)), max(1, r-5))
        elif dec_type == "tire_stack":
            pygame.draw.circle(surf, _TIRE,       (int(wx), int(wy)), r)
            pygame.draw.circle(surf, (65, 65, 65), (int(wx), int(wy)), r, 3)
        elif dec_type == "barrier":
            bw  = int(rts * 0.7)
            bh  = int(rts * 0.3)
            br  = pygame.Rect(int(wx-bw//2), int(wy-bh//2), bw, bh)
            pygame.draw.rect(surf, _BARR_A, br, border_radius=4)
            pygame.draw.rect(surf, _BARR_B, br, 2, border_radius=4)
