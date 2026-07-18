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
        if not self._built: self._build_surface()
        sw, sh = surface.get_width(), surface.get_height()
        clip   = pygame.Rect(int(cam_x), int(cam_y), sw, sh)
        clip.clamp_ip(pygame.Rect(0, 0, self.world_w, self.world_h))
        surface.blit(self._surface, (clip.x - int(cam_x), clip.y - int(cam_y)), clip)

    def draw_minimap(self, surface: pygame.Surface, x, y, w, h,
                     car_wx: float, car_wy: float):
        if not self._built: self._build_surface()
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

        # ── LAYER 5  boost pads ───────────────────────────────────────────
        for gy in range(gh):
            for gx in range(gw):
                if self._tile_name(gx, gy) != "boost": continue
                rx, ry = gx*rts, gy*rts
                pad = pygame.Rect(rx+10, ry+10, rts-20, rts-20)
                pygame.draw.rect(surf, (162, 128,  8), pad, border_radius=6)
                pygame.draw.rect(surf, (255, 215,  0), pad, 3, border_radius=6)
                cx2, cy2 = rx+rts//2, ry+rts//2
                pygame.draw.polygon(surf, (255,230,50),
                    [(cx2-9,cy2+8),(cx2+9,cy2+8),(cx2,cy2-10)])

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

    def _draw_decoration(self, surf, dec_type, wx, wy, rts):
        r = int(rts * 0.36)
        if dec_type == "tree":
            pygame.draw.circle(surf, _TREE_D, (int(wx), int(wy)), r)
            pygame.draw.circle(surf, _TREE_M, (int(wx), int(wy)), max(1,r-5))
        elif dec_type == "tire_stack":
            pygame.draw.circle(surf, _TIRE,       (int(wx), int(wy)), r)
            pygame.draw.circle(surf, (65,65,65),  (int(wx), int(wy)), r, 3)
        elif dec_type == "barrier":
            bw = int(rts*.7); bh = int(rts*.3)
            br = pygame.Rect(int(wx-bw//2), int(wy-bh//2), bw, bh)
            pygame.draw.rect(surf, _BARR_A, br, border_radius=4)
            pygame.draw.rect(surf, _BARR_B, br, 2, border_radius=4)
