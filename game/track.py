"""Tile-based track engine.

Physics : tile grid (friction / speed_mult / damage / drivable).
Visuals : hybrid tile-fill + edge-curbs + BFS-only centre-dashes.

  Layer 0  Background tiles  – dark textured colour per tile type
  Layer 1  Road fill          – every drivable tile filled with road colour
  Layer 2  Road texture       – subtle per-tile roughness / cracks
  Layer 3  Curb edges         – 14-px strip drawn at every drivable→non-drivable
                                boundary, alternating red / white every 3 tiles
  Layer 4  Centre dashes      – BFS path Catmull-Rom smoothed, yellow dashes
  Layer 5  Boost pads         – per-tile gold overlay
  Layer 6  Decorations        – trees / tyre stacks / barriers
  Layer 7  Start/finish line  – at spawn[0] position, perpendicular to direction
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

RENDER_SCALE = 2

_DIR_TO_ANGLE = {"north": 0.0, "east": 90.0, "south": 180.0, "west": 270.0}

_DRIVABLE = {"asphalt","grass","dirt","mud","ice","oil_slick","boost","lava","water"}
_ROAD_FILL = {"asphalt","boost","dirt","mud","ice","oil_slick","lava","water"}

# ── dark background palette ──────────────────────────────────────────────────
_BG = {
    "wall":      ( 32,  30,  28),
    "grass":     ( 22,  42,  15),
    "dirt":      ( 72,  48,  18),
    "mud":       ( 48,  34,  22),
    "ice":       ( 92, 128, 148),
    "asphalt":   ( 28,  25,  22),
    "boost":     ( 28,  25,  22),
    "lava":      (140,  32,   0),
    "water":     ( 18,  72, 148),
    "oil_slick": ( 14,  14,  16),
}

# ── road surface colour per tile type ───────────────────────────────────────
_ROAD = {
    "asphalt":   ( 86,  82,  78),
    "boost":     ( 86,  82,  78),
    "dirt":      (108,  74,  30),
    "mud":       ( 72,  52,  32),
    "ice":       (155, 196, 216),
    "water":     ( 34, 112, 200),
    "lava":      (178,  52,   0),
    "oil_slick": ( 22,  22,  24),
}
_ROAD_DEFAULT = (86, 82, 78)

# ── curb colours ─────────────────────────────────────────────────────────────
_CURB_R  = (210,  38,  38)
_CURB_W  = (228, 224, 218)
_DASH    = (212, 188,  40)
_SF_W    = (240, 240, 240)
_SF_B    = (  8,   8,   8)
CURB_PX  = 14     # curb strip width in pixels
CURB_SEG = 3      # tiles per colour alternation

# ── decoration colours ───────────────────────────────────────────────────────
_TREE_D = ( 12,  72,  12)
_TREE_M = ( 24, 108,  24)
_TIRE   = ( 24,  24,  24)
_BARR_A = (255, 140,   0)
_BARR_B = (228, 228, 228)

# ── crowd colours ─────────────────────────────────────────────────────────────
_CROWD_SKINS  = [(210,160,110),(180,120,80),(140,90,50),(100,65,30),(240,200,160),(160,110,70)]
_CROWD_SHIRTS = [(220,40,40),(40,100,200),(40,180,60),(200,160,20),(220,220,220),
                 (180,30,180),(200,100,30),(30,160,200),(240,120,30),(80,200,220)]

# ── prop colours ──────────────────────────────────────────────────────────────
_BARREL_Y = (200, 170,  20)
_BARREL_R = (180,  30,  30)
_CONE_O   = (230, 100,  20)
_CONCRETE = (140, 138, 135)
_CORR     = (120, 115, 110)

# ── SA flag colours ───────────────────────────────────────────────────────────
_SA_GREEN = (  0, 106,  46)
_SA_GOLD  = (255, 185,   0)
_SA_RED   = (222,  56,  49)
_SA_BLUE  = (  0,  33, 105)

# ── sign data ─────────────────────────────────────────────────────────────────
_SIGN_COLS = {
    "sign_spaza":  ((155, 20, 20),  (240, 220, 180)),
    "sign_vuka":   (( 50, 80, 30),  (240, 200,  60)),
    "sign_we_buy": (( 20, 90, 30),  (220, 240, 200)),
    "sign_no_gas": (( 22, 22, 22),  (220, 220, 220)),
}
_SIGN_TEXT = {
    "sign_spaza":  "SPAZA SHOP",
    "sign_vuka":   "VUKA! MOJA",
    "sign_we_buy": "WE BUY CARS",
    "sign_no_gas": "NO GAS\nNO GO!",
}
_BULB_Y = (255, 230, 120)


# ── obstacle collision radii (world px) ──────────────────────────────────────
# Decoration types that physically block the car, mapped to their collision radius
# as a fraction of one rendered tile (rts).  Types absent here pass through freely.
_OBSTACLE_RADIUS: dict[str, float] = {
    "oil_drum":        0.23,
    "oil_drum_red":    0.23,
    "traffic_cone":    0.18,
    "concrete_block":  0.30,
    "corrugated_wall": 0.38,
    "tire_wall":       0.32,
    "tire_stack":      0.30,
    "barrier":         0.30,
}

# ── Catmull-Rom (centre-dashes only) ─────────────────────────────────────────

def _cr(p0, p1, p2, p3, t):
    t2, t3 = t*t, t*t*t
    return (
        .5*((2*p1[0])+(-p0[0]+p2[0])*t+(2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2
            +(-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
        .5*((2*p1[1])+(-p0[1]+p2[1])*t+(2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2
            +(-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3),
    )

def _smooth(pts, spp=10):
    n, out = len(pts), []
    for i in range(n):
        p0,p1 = pts[(i-1)%n], pts[i]
        p2,p3 = pts[(i+1)%n], pts[(i+2)%n]
        for j in range(spp):
            out.append(_cr(p0,p1,p2,p3,j/spp))
    return out


# ── BFS road-centre tracer ────────────────────────────────────────────────────

def _bfs(drivable, gw, gh, sx, sy, ex, ey):
    if not (0<=sx<gw and 0<=sy<gh and drivable[sy][sx]): return []
    q = deque(); q.append((sx,sy,[]))
    vis = {(sx,sy)}
    while q:
        x,y,path = q.popleft()
        path = path+[(x,y)]
        if x==ex and y==ey: return path
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            nx,ny = x+dx,y+dy
            if 0<=nx<gw and 0<=ny<gh and drivable[ny][nx] and (nx,ny) not in vis:
                vis.add((nx,ny)); q.append((nx,ny,path))
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

        ts        = self.racetrack.tile_size
        self._ts  = ts
        self._rts = ts * RENDER_SCALE

        self.world_w = self.racetrack.grid_size.width  * self._rts
        self.world_h = self.racetrack.grid_size.height * self._rts

        spawn              = self.racetrack.starting_grid[0]
        self.start_x       = (spawn.x + 0.5) * self._rts
        self.start_y       = (spawn.y + 0.5) * self._rts
        self.start_angle   = _DIR_TO_ANGLE.get(spawn.direction, 90.0)
        self.total_laps    = self.racetrack.laps

        self.checkpoints = [
            ((cp.x+0.5)*self._rts, (cp.y+0.5)*self._rts, cp.name)
            for cp in sorted(self.racetrack.checkpoints, key=lambda c: c.id)
        ]
        self.cp_radius_sq = (self._rts * 1.8) ** 2
        self.name         = self.racetrack.name
        self.difficulty   = self.racetrack.difficulty

        # obstacles: list of (world_x, world_y, collision_radius_px)
        self.obstacles: list[tuple[float, float, float]] = [
            (dec.x * self._rts, dec.y * self._rts,
             _OBSTACLE_RADIUS[dec.type] * self._rts)
            for dec in self.racetrack.decorations
            if dec.type in _OBSTACLE_RADIUS
        ]

        self._surface = None
        self._built   = False

    # ── physics ───────────────────────────────────────────────────────────────

    def get_tile_def_at(self, wx: float, wy: float) -> TileDefinition | None:
        return self._tile_def(int(wx / self._rts), int(wy / self._rts))

    def is_drivable(self, wx: float, wy: float) -> bool:
        td = self.get_tile_def_at(wx, wy)
        return td.drivable if td else False

    def checkpoint_reached(self, wx: float, wy: float, cp_idx: int) -> bool:
        if cp_idx >= len(self.checkpoints): return False
        cx, cy, _ = self.checkpoints[cp_idx]
        return (wx-cx)**2 + (wy-cy)**2 < self.cp_radius_sq

    # ── rendering ─────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, cam_x: float, cam_y: float):
        if not self._built:
            try:
                self._build_surface()
            except Exception as e:
                print(f"[Track] _build_surface error: {e}")
                self._surface = pygame.Surface((self.world_w, self.world_h))
                self._surface.fill((40, 36, 32))
                self._built = True
        sw, sh = surface.get_width(), surface.get_height()
        clip   = pygame.Rect(int(cam_x), int(cam_y), sw, sh)
        clip.clamp_ip(pygame.Rect(0, 0, self.world_w, self.world_h))
        surface.blit(self._surface, (clip.x - int(cam_x), clip.y - int(cam_y)), clip)

    def draw_minimap(self, surface: pygame.Surface, x, y, w, h,
                     car_wx: float, car_wy: float):
        if not self._built:
            try:
                self._build_surface()
            except Exception:
                self._surface = pygame.Surface((self.world_w, self.world_h))
                self._surface.fill((40, 36, 32))
                self._built = True
        if self._surface is None:
            return
        mm = pygame.transform.smoothscale(self._surface, (w, h))
        surface.blit(mm, (x, y))
        dx = int(car_wx / self.world_w * w)
        dy = int(car_wy / self.world_h * h)
        pygame.draw.circle(surface, (220, 40, 40), (x+dx, y+dy), 4)
        pygame.draw.circle(surface, (255,255,255), (x+dx, y+dy), 4, 1)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _tile_def(self, gx, gy) -> TileDefinition | None:
        rt = self.racetrack
        if not (0<=gx<rt.grid_size.width and 0<=gy<rt.grid_size.height):
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

    def _is_road(self, gx, gy) -> bool:
        return self._tile_name(gx, gy) in _ROAD_FILL

    # ── BFS centre trace ──────────────────────────────────────────────────────

    def _trace_road(self):
        rt  = self.racetrack
        gw  = rt.grid_size.width
        gh  = rt.grid_size.height
        rts = self._rts
        driv = [[self._is_driv(gx,gy) for gx in range(gw)] for gy in range(gh)]

        spawn = rt.starting_grid[0]
        cps   = [(int(cp.x),int(cp.y))
                 for cp in sorted(rt.checkpoints, key=lambda c: c.id)]
        seq   = [(int(spawn.x),int(spawn.y))] + cps + [(int(spawn.x),int(spawn.y))]

        full = [seq[0]]
        for i in range(len(seq)-1):
            seg = _bfs(driv,gw,gh,seq[i][0],seq[i][1],seq[i+1][0],seq[i+1][1])
            if seg: full.extend(seg[1:])

        world = [(p[0]*rts+rts//2, p[1]*rts+rts//2) for p in full[::2]]
        return _smooth(world, spp=10)

    # ── surface builder ───────────────────────────────────────────────────────

    def _build_surface(self):
        rts  = self._rts
        rt   = self.racetrack
        gw   = rt.grid_size.width
        gh   = rt.grid_size.height
        surf = pygame.Surface((self.world_w, self.world_h))

        # ── LAYER 0  background ───────────────────────────────────────────
        t_rng = random.Random(42)
        for gy in range(gh):
            for gx in range(gw):
                name    = self._tile_name(gx, gy)
                col     = _BG.get(name, (28, 25, 22))
                rx, ry  = gx*rts, gy*rts
                pygame.draw.rect(surf, col, (rx, ry, rts, rts))

                r = random.Random(gx*97+gy*31+7)
                if name == "grass":
                    for _ in range(7):
                        sc = tuple(max(0, c-r.randint(4,12)) for c in col)
                        pygame.draw.circle(surf, sc,
                            (rx+r.randint(2,rts-3), ry+r.randint(2,rts-3)),
                            r.randint(2,5))
                elif name == "dirt":
                    for _ in range(5):
                        sc = tuple(max(0,min(255,c+r.randint(-10,14))) for c in col)
                        pygame.draw.circle(surf, sc,
                            (rx+r.randint(2,rts-3), ry+r.randint(2,rts-3)),
                            r.randint(2,5))
                elif name == "lava":
                    for _ in range(3):
                        pygame.draw.circle(surf,
                            (min(255,col[0]+55), min(80,col[1]+20), 0),
                            (rx+r.randint(4,rts-5), ry+r.randint(4,rts-5)),
                            r.randint(3,8))
                elif name == "ice":
                    for _ in range(2):
                        pygame.draw.circle(surf, (180,215,232),
                            (rx+r.randint(4,rts-5), ry+r.randint(4,rts-5)),
                            r.randint(2,5))
                elif name == "water":
                    for _ in range(2):
                        yw = ry+r.randint(8,rts-9)
                        pygame.draw.line(surf, (28,98,185),
                            (rx+4, yw), (rx+rts-4, yw+r.randint(-5,5)), 2)

        # ── LAYER 1  road fill (every drivable non-grass tile) ────────────
        for gy in range(gh):
            for gx in range(gw):
                name = self._tile_name(gx, gy)
                if name not in _ROAD_FILL: continue
                col  = _ROAD.get(name, _ROAD_DEFAULT)
                rx, ry = gx*rts, gy*rts
                pygame.draw.rect(surf, col, (rx, ry, rts, rts))

        # ── LAYER 2  road texture (cracks / roughness on asphalt) ────────
        for gy in range(gh):
            for gx in range(gw):
                name = self._tile_name(gx, gy)
                if name not in ("asphalt", "boost", "oil_slick"): continue
                rx, ry = gx*rts, gy*rts
                r = random.Random(gx*113+gy*41+3)
                # subtle dark cracks
                for _ in range(r.randint(0,3)):
                    x1 = rx+r.randint(4, rts-4)
                    y1 = ry+r.randint(4, rts-4)
                    x2 = x1+r.randint(-16,16)
                    y2 = y1+r.randint(-16,16)
                    pygame.draw.line(surf, (68,64,60), (x1,y1), (x2,y2), 1)
                # dirt spots on dirt/mud roads
                if name in ("dirt","mud"):
                    for _ in range(3):
                        sc = tuple(max(0,min(255,c+r.randint(-12,14)))
                                   for c in _ROAD.get(name,_ROAD_DEFAULT))
                        pygame.draw.circle(surf, sc,
                            (rx+r.randint(4,rts-4), ry+r.randint(4,rts-4)),
                            r.randint(2,6))

        # ── LAYER 3  curb edges ───────────────────────────────────────────
        # Draw 14-px curb strip on each exposed road edge.
        # Colour alternates red/white every CURB_SEG tiles along that axis.
        cpx = CURB_PX
        for gy in range(gh):
            for gx in range(gw):
                if not self._is_road(gx, gy): continue
                rx, ry = gx*rts, gy*rts

                # left edge (curb where road meets non-road: grass counts as non-road)
                if not self._is_road(gx-1, gy):
                    seg = gy // CURB_SEG
                    col = _CURB_R if seg % 2 == 0 else _CURB_W
                    pygame.draw.rect(surf, col, (rx, ry, cpx, rts))

                # right edge
                if not self._is_road(gx+1, gy):
                    seg = gy // CURB_SEG
                    col = _CURB_R if seg % 2 == 0 else _CURB_W
                    pygame.draw.rect(surf, col, (rx+rts-cpx, ry, cpx, rts))

                # top edge
                if not self._is_road(gx, gy-1):
                    seg = gx // CURB_SEG
                    col = _CURB_R if seg % 2 == 0 else _CURB_W
                    pygame.draw.rect(surf, col, (rx, ry, rts, cpx))

                # bottom edge
                if not self._is_road(gx, gy+1):
                    seg = gx // CURB_SEG
                    col = _CURB_R if seg % 2 == 0 else _CURB_W
                    pygame.draw.rect(surf, col, (rx, ry+rts-cpx, rts, cpx))

        # ── LAYER 4  centre-line dashes (BFS + Catmull-Rom) ───────────────
        cl   = self._trace_road()
        n_cl = len(cl)
        dist = 0.0
        for i in range(n_cl):
            j   = (i+1) % n_cl
            p1  = (int(cl[i][0]), int(cl[i][1]))
            p2  = (int(cl[j][0]), int(cl[j][1]))
            seg = math.hypot(cl[j][0]-cl[i][0], cl[j][1]-cl[i][1])
            # only draw on tiles that ARE road (avoid drawing through walls)
            if self._is_road(int(cl[i][0]/rts), int(cl[i][1]/rts)):
                if int(dist/34) % 2 == 0:
                    pygame.draw.line(surf, _DASH, p1, p2, 3)
            dist += seg

        # ── LAYER 5  boost & slow pads ───────────────────────────────────────────
        for gy in range(gh):
            for gx in range(gw):
                tname = self._tile_name(gx, gy)
                if tname not in ("boost", "slow_pad"): continue
                rx, ry = gx*rts, gy*rts
                cx2, cy2 = rx+rts/2, ry+rts/2

                # pad background
                pad = pygame.Rect(rx+10, ry+10, rts-20, rts-20)
                if tname == "boost":
                    pygame.draw.rect(surf, (162, 128,  8), pad, border_radius=6)
                    pygame.draw.rect(surf, (255, 215,  0), pad, 3, border_radius=6)
                    chev_col = (255, 230, 50)
                    pts = [(-9, 8), (9, 8), (0, -10)] # points UP
                else:
                    pygame.draw.rect(surf, (162,  40,  8), pad, border_radius=6)
                    pygame.draw.rect(surf, (255,  80, 50), pad, 3, border_radius=6)
                    chev_col = (255, 120, 80)
                    pts = [(-9, -8), (9, -8), (0, 10)] # points DOWN (backward)

                # find closest cl point to determine road direction
                best_i = 0
                best_d = float('inf')
                for i, p in enumerate(cl):
                    d = (p[0]-cx2)**2 + (p[1]-cy2)**2
                    if d < best_d:
                        best_d = d
                        best_i = i
                
                # get forward direction (look slightly ahead)
                n_idx = (best_i + 3) % n_cl
                dx = cl[n_idx][0] - cl[best_i][0]
                dy = cl[n_idx][1] - cl[best_i][1]
                
                # angle = atan2(dy, dx) + pi/2 (to align UP with forward)
                a = math.atan2(dy, dx) + math.pi/2
                cos_a, sin_a = math.cos(a), math.sin(a)

                # apply rotation
                rotated_pts = []
                for px, py in pts:
                    nx = px * cos_a - py * sin_a
                    ny = px * sin_a + py * cos_a
                    rotated_pts.append((cx2 + nx, cy2 + ny))

                pygame.draw.polygon(surf, chev_col, rotated_pts)

        # ── LAYER 6  ice patches ──────────────────────────────────────────
        for gy in range(gh):
            for gx in range(gw):
                if self._tile_name(gx, gy) != "ice": continue
                rx, ry = gx*rts, gy*rts
                r = random.Random(gx*61+gy*17)
                for _ in range(4):
                    pw, ph = r.randint(8,18), r.randint(6,14)
                    px2 = rx+r.randint(cpx, rts-cpx-pw)
                    py2 = ry+r.randint(cpx, rts-cpx-ph)
                    pygame.draw.ellipse(surf, (190,225,240), (px2,py2,pw,ph))

        # ── LAYER 7  oil slick sheen ──────────────────────────────────────
        for gy in range(gh):
            for gx in range(gw):
                if self._tile_name(gx, gy) != "oil_slick": continue
                rx, ry = gx*rts, gy*rts
                sheen = pygame.Surface((rts,rts), pygame.SRCALPHA)
                sheen.fill((60,0,80,45))
                surf.blit(sheen, (rx, ry))

        # ── LAYER 8  decorations ──────────────────────────────────────────
        for dec in rt.decorations:
            self._draw_decoration(surf, dec.type, dec.x*rts, dec.y*rts, rts)

        # ── LAYER 8.5  Procedural crowd on grass tiles bordering road ───
        _crng = random.Random(1337)
        for gy in range(gh):
            for gx in range(gw):
                if self._tile_name(gx, gy) != "grass":
                    continue
                if not any(self._is_road(gx+dx, gy+dy)
                           for dx, dy in ((-1,0),(1,0),(0,-1),(0,1))):
                    continue
                if _crng.random() < 0.52:
                    continue
                rx, ry = gx*rts, gy*rts
                for _ in range(_crng.randint(2, 4)):
                    px = rx + _crng.randint(8, rts-8)
                    py = ry + _crng.randint(8, rts-8)
                    skin  = _CROWD_SKINS [_crng.randint(0, len(_CROWD_SKINS)-1)]
                    shirt = _CROWD_SHIRTS[_crng.randint(0, len(_CROWD_SHIRTS)-1)]
                    self._draw_crowd_person(surf, px, py, skin, shirt)

        # ── LAYER 9  start / finish line ──────────────────────────────────
        spawn   = rt.starting_grid[0]
        sfgx    = int(spawn.x)
        sfgy    = int(spawn.y)
        sfdir   = spawn.direction
        # Lay tiles perpendicular to travel direction across all road tiles
        if sfdir in ("north", "south"):
            # Travel is vertical → S/F line is horizontal row of tiles
            # Flood-fill along the row from spawn column to avoid crossing
            # into disconnected road sections on the other side of the map.
            fy = sfgy * rts
            road_xs = []
            gx = sfgx
            while gx >= 0 and self._is_road(gx, sfgy):
                road_xs.append(gx); gx -= 1
            gx = sfgx + 1
            while gx < gw and self._is_road(gx, sfgy):
                road_xs.append(gx); gx += 1
            for gx in road_xs:
                # Checkerboard stripe: 2 rows of alternating squares
                sq = rts // 8
                for col_i in range(rts // sq):
                    for row_i in range(2):
                        c = _SF_W if (col_i+row_i) % 2 == 0 else _SF_B
                        pygame.draw.rect(surf, c,
                            (gx*rts + col_i*sq,
                             fy + rts//2 - sq + row_i*sq, sq, sq))
        else:
            # Travel is horizontal → S/F line is vertical column of tiles
            fx = sfgx * rts
            road_ys = []
            gy = sfgy
            while gy >= 0 and self._is_road(sfgx, gy):
                road_ys.append(gy); gy -= 1
            gy = sfgy + 1
            while gy < gh and self._is_road(sfgx, gy):
                road_ys.append(gy); gy += 1
            for gy in road_ys:
                sq = rts // 8
                for row_i in range(rts // sq):
                    for col_i in range(2):
                        c = _SF_W if (row_i+col_i) % 2 == 0 else _SF_B
                        pygame.draw.rect(surf, c,
                            (fx + rts//2 - sq + col_i*sq,
                             gy*rts + row_i*sq, sq, sq))

        self._surface = surf
        self._built   = True

    def _draw_crowd_person(self, surf, cx, cy, skin, shirt):
        pygame.draw.circle(surf, skin,      (cx, cy-9), 5)
        pygame.draw.rect(surf,   shirt,     (cx-4, cy-4, 8, 11))
        pant = (38, 28, 18)
        pygame.draw.rect(surf, pant, (cx-4, cy+7, 3, 9))
        pygame.draw.rect(surf, pant, (cx+1, cy+7, 3, 9))

    def _draw_decoration(self, surf, dec_type, wx, wy, rts):
        r   = int(rts * 0.36)
        ix  = int(wx)
        iy  = int(wy)

        if dec_type == "tree":
            pygame.draw.circle(surf, _TREE_D, (ix, iy), r)
            pygame.draw.circle(surf, _TREE_M, (ix, iy), max(1, r-5))

        elif dec_type == "tire_stack":
            pygame.draw.circle(surf, _TIRE,     (ix, iy), r)
            pygame.draw.circle(surf, (65,65,65),(ix, iy), r, 3)

        elif dec_type == "barrier":
            bw = int(rts*.7); bh = int(rts*.3)
            br = pygame.Rect(ix-bw//2, iy-bh//2, bw, bh)
            pygame.draw.rect(surf, _BARR_A, br, border_radius=4)
            pygame.draw.rect(surf, _BARR_B, br, 2, border_radius=4)

        elif dec_type == "warning_sign":
            bw, bh = int(rts*0.72), int(rts*0.44)
            bx, by = ix - bw//2, iy - bh//2
            stripe  = bw // 5
            for i in range(5):
                c = (215, 30, 30) if i % 2 == 0 else (225, 225, 225)
                pygame.draw.rect(surf, c, (bx + i*stripe, by, stripe, bh))
            pygame.draw.rect(surf, (55, 50, 46), (bx, by, bw, bh), 2)
            pygame.draw.line(surf, (90,80,70), (ix, iy+bh//2), (ix, iy+bh//2+rts//3), 4)

        elif dec_type in ("oil_drum", "oil_drum_red"):
            col = _BARREL_R if dec_type == "oil_drum_red" else _BARREL_Y
            br  = int(rts * 0.21)
            bh2 = int(rts * 0.42)
            pygame.draw.rect(surf, col, (ix-br, iy-bh2//2, br*2, bh2), border_radius=br//2)
            for ri in range(3):
                ry2 = iy - bh2//2 + ri * bh2//3 + bh2//6
                pygame.draw.line(surf, tuple(max(0,c-45) for c in col),
                                 (ix-br+2, ry2), (ix+br-2, ry2), 2)
            pygame.draw.ellipse(surf, tuple(min(255,c+35) for c in col),
                                (ix-br, iy-bh2//2, br*2, br))
            pygame.draw.rect(surf, tuple(max(0,c-30) for c in col),
                             (ix-br, iy-bh2//2, br*2, bh2), 2, border_radius=br//2)

        elif dec_type == "traffic_cone":
            base_w = int(rts * 0.46)
            h      = int(rts * 0.56)
            pygame.draw.polygon(surf, _CONE_O, [
                (ix - base_w//2, iy + h//2),
                (ix + base_w//2, iy + h//2),
                (ix, iy - h//2)
            ])
            mid = iy
            pygame.draw.polygon(surf, (245, 245, 245), [
                (ix - base_w//4, mid+4),
                (ix + base_w//4, mid+4),
                (ix + base_w//8, mid-4),
                (ix - base_w//8, mid-4),
            ])
            pygame.draw.rect(surf, (55,52,50), (ix-base_w//2, iy+h//2-4, base_w, 8), border_radius=2)

        elif dec_type == "concrete_block":
            bw, bh = int(rts*0.66), int(rts*0.36)
            bx, by = ix - bw//2, iy - bh//2
            pygame.draw.rect(surf, _CONCRETE, (bx, by, bw, bh), border_radius=5)
            pygame.draw.rect(surf, (100,98,95), (bx, by, bw, bh), 2, border_radius=5)
            pygame.draw.line(surf, (162,160,157), (bx+4, by+4), (bx+bw-4, by+4), 2)

        elif dec_type == "corrugated_wall":
            bw, bh = int(rts*0.82), int(rts*0.52)
            bx, by = ix - bw//2, iy - bh//2
            pygame.draw.rect(surf, _CORR, (bx, by, bw, bh))
            for ci in range(bw//7 + 1):
                lx = bx + ci*7
                col = (100,96,92) if ci % 2 == 0 else (132,127,122)
                pygame.draw.line(surf, col, (lx, by), (lx, by+bh), 1)
            pygame.draw.rect(surf, (68,64,60), (bx, by, bw, bh), 2)

        elif dec_type == "tire_wall":
            tr = int(rts * 0.19)
            for ti in range(2):
                for tj in range(3):
                    tx = ix - tr*3 + tj*tr*2 + tr
                    ty = iy + (ti-1)*tr*2 + tr
                    pygame.draw.circle(surf, (28,26,24), (tx, ty), tr)
                    pygame.draw.circle(surf, (55,52,50), (tx, ty), tr, 2)
                    pygame.draw.circle(surf, (44,42,40), (tx, ty), max(1, tr-5))

        elif dec_type in _SIGN_TEXT:
            bg_col, txt_col = _SIGN_COLS[dec_type]
            text = _SIGN_TEXT[dec_type]
            bw, bh = int(rts*0.92), int(rts*0.5)
            bx, by = ix - bw//2, iy - bh//2
            pygame.draw.rect(surf, bg_col, (bx, by, bw, bh), border_radius=5)
            light = tuple(min(255, c+55) for c in bg_col)
            pygame.draw.rect(surf, light, (bx, by, bw, bh), 2, border_radius=5)
            try:
                fnt = pygame.font.SysFont("arial", max(8, bh//3), bold=True)
                lines = text.split("\n")
                for li, line in enumerate(lines):
                    ts = fnt.render(line, True, txt_col)
                    if ts.get_width() > bw - 8:
                        ts = pygame.transform.scale(ts, (bw-8, ts.get_height()))
                    ly2 = iy - (len(lines)-1) * (bh//4) // 2 + li * bh//4 - bh//8
                    surf.blit(ts, ts.get_rect(centerx=ix, centery=ly2))
            except Exception:
                pass
            pygame.draw.line(surf, (78,68,58), (ix, iy+bh//2), (ix, iy+bh//2+rts//4), 3)

        elif dec_type == "sa_flag":
            pygame.draw.line(surf, (155,138,95), (ix, iy-int(rts*0.52)), (ix, iy+int(rts*0.52)), 3)
            fw, fh = int(rts*0.58), int(rts*0.40)
            fx, fy = ix + 3, iy - int(rts*0.5)
            pygame.draw.rect(surf, _SA_RED,         (fx, fy,          fw, fh//3))
            pygame.draw.rect(surf, (255,255,255),   (fx, fy+fh//3,    fw, fh//3))
            pygame.draw.rect(surf, _SA_BLUE,        (fx, fy+2*fh//3,  fw, fh//3))
            pygame.draw.polygon(surf, _SA_GREEN,
                [(fx, fy), (fx+fw//3, fy+fh//2), (fx, fy+fh)])
            pygame.draw.polygon(surf, (0,0,0),
                [(fx+2, fy+fh//8), (fx+fw//4, fy+fh//2), (fx+2, fy+7*fh//8)])
            pygame.draw.polygon(surf, _SA_GOLD, [
                (fx+fw//4-2, fy+fh//2-3),
                (fx+fw//3-2, fy+fh//2),
                (fx+fw//4-2, fy+fh//2+3),
            ])
            pygame.draw.rect(surf, (90,80,70), (fx, fy, fw, fh), 1)

        elif dec_type == "string_lights":
            n   = 5
            lx0 = ix - int(rts*0.52)
            lx1 = ix + int(rts*0.52)
            ly  = iy - 10
            pygame.draw.line(surf, (65,55,45), (lx0, ly), (lx1, ly), 2)
            for i in range(n):
                bx = lx0 + i*(lx1-lx0)//(n-1)
                pygame.draw.line(surf, (65,55,45), (bx, ly), (bx, ly+13), 1)
                glow = pygame.Surface((22, 22), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255,230,120,70), (11,11), 11)
                surf.blit(glow, (bx-11, ly+3))
                pygame.draw.circle(surf, _BULB_Y,       (bx, ly+14), 6)
                pygame.draw.circle(surf, (255,255,200),  (bx, ly+14), 3)

        elif dec_type == "crowd":
            rng = random.Random(ix*37+iy*19)
            for _ in range(rng.randint(3, 5)):
                px = ix + rng.randint(-int(rts*0.36), int(rts*0.36))
                py = iy + rng.randint(-int(rts*0.32), int(rts*0.32))
                skin  = _CROWD_SKINS [rng.randint(0, len(_CROWD_SKINS)-1)]
                shirt = _CROWD_SHIRTS[rng.randint(0, len(_CROWD_SHIRTS)-1)]
                self._draw_crowd_person(surf, px, py, skin, shirt)
