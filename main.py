#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║   MZANSI RUSH  —  SA Street Racing  🇿🇦          ║
║   A top-down 2D racer with full Mzansi flavour  ║
╚══════════════════════════════════════════════════╝
"""

import pygame
import sys
import os
import json
import math
import random
import struct

# ═══════════════════════════════════════════════════════════
#  INIT
# ═══════════════════════════════════════════════════════════
pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# ═══════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════
WIDTH, HEIGHT = 480, 820
ROAD_W = 300
ROAD_L = (WIDTH - ROAD_W) // 2
ROAD_R = ROAD_L + ROAD_W
LANES  = 3
LANE_W = ROAD_W // LANES
LANE_X = [ROAD_L + LANE_W * i + LANE_W // 2 for i in range(LANES)]
CAR_W, CAR_H = 46, 78
SPRITE_PAD = 14
SPR_W, SPR_H = CAR_W + SPRITE_PAD * 2, CAR_H + SPRITE_PAD * 2
POT_MAX_R = 18
FPS = 60

# ── SA palette ───────────────────────────────────────────
SA_GREEN  = (0, 122, 77)
SA_GOLD   = (255, 184, 28)
SA_RED    = (222, 56, 49)
SA_BLUE   = (0, 35, 149)
SA_WHITE  = (255, 255, 255)
SA_BLACK  = (0, 0, 0)

COL_BG       = (8, 8, 22)
COL_VELD     = (38, 90, 34)
COL_SHOULDER = (80, 71, 58)
COL_TARMAC   = (46, 46, 46)
COL_DASH     = (255, 255, 255)
COL_HUD_BG   = (0, 0, 0, 184)

# ── Car roster ───────────────────────────────────────────
CARS = [
    {"name": "GUSHESHE",  "desc": "325is - Speed demon",  "body": (178, 34, 34),  "roof": (139, 26, 26),  "accent": (231, 76, 60),  "spd": 1.20, "grip": 0.90},
    {"name": "CITI GOLF", "desc": "VW Street legend",      "body": (26, 109, 170), "roof": (20, 83, 127),  "accent": (52, 152, 219), "spd": 1.00, "grip": 1.10},
    {"name": "HILUX",     "desc": "Tough bakkie",           "body": (107, 123, 141),"roof": (87, 103, 120), "accent": (149, 165, 166),"spd": 0.85, "grip": 1.05},
    {"name": "QUANTUM",   "desc": "Taxi king!",             "body": (212, 168, 0),  "roof": (176, 143, 0),  "accent": (241, 196, 15), "spd": 1.10, "grip": 0.80},
]

RIVAL_PALETTES = [
    ((192, 57, 43),  (155, 44, 44)),
    ((36, 113, 163), (26, 82, 118)),
    ((112, 123, 124),(85, 85, 85)),
    ((142, 68, 173), (108, 52, 131)),
    ((240, 240, 240),(204, 204, 204)),
    ((212, 168, 13), (183, 145, 11)),
]

OVERTAKE_MSGS = ["SHARP!", "LEKKER!", "SHAP SHAP!", "HEITA!", "EAZY!", "GRAND!", "NICE ONE!", "AYOBA!"]

# ═══════════════════════════════════════════════════════════
#  DISPLAY
# ═══════════════════════════════════════════════════════════
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Mzansi Rush — SA Street Racing 🇿🇦")

# window icon (tiny SA-coloured car)
_icon = pygame.Surface((32, 32), pygame.SRCALPHA)
pygame.draw.rect(_icon, SA_RED, (8, 2, 16, 28), border_radius=5)
pygame.draw.rect(_icon, (130, 200, 255, 140), (10, 6, 12, 8), border_radius=2)
pygame.display.set_icon(_icon)

clock = pygame.time.Clock()

# ═══════════════════════════════════════════════════════════
#  FONTS
# ═══════════════════════════════════════════════════════════
def _load_font(size, bold=False):
    for name in ["ubuntu", "segoeui", "helvetica", "arial", "dejavusans", "liberationsans"]:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)

FONT_TITLE = _load_font(74, bold=True)
FONT_BIG   = _load_font(38, bold=True)
FONT_MED   = _load_font(20, bold=True)
FONT_SM    = _load_font(15)
FONT_XS    = _load_font(12)
FONT_HUD_L = _load_font(13, bold=True)
FONT_HUD_V = _load_font(17, bold=True)
FONT_FLOAT = _load_font(16, bold=True)
FONT_OVER  = _load_font(78, bold=True)
FONT_STAT_L = _load_font(13, bold=True)
FONT_STAT_V = _load_font(19, bold=True)


def draw_text(surf, text, font, colour, x, y, align="left", alpha=255):
    """Render text and blit with optional alignment and alpha."""
    ts = font.render(text, True, colour)
    if alpha < 255:
        ts.set_alpha(alpha)
    r = ts.get_rect()
    if align == "center":
        r.centerx, r.top = x, y
    elif align == "right":
        r.right, r.top = x, y
    else:
        r.left, r.top = x, y
    surf.blit(ts, r)
    return r

# ═══════════════════════════════════════════════════════════
#  SOUND GENERATION
# ═══════════════════════════════════════════════════════════
def _make_beep(freq, duration, volume=0.25):
    sr = 22050
    n = int(sr * duration)
    samples = []
    for i in range(n):
        t = i / sr
        env = max(0.0, 1.0 - t / duration)
        v = int(32767 * volume * env * math.sin(2 * math.pi * freq * t))
        samples.append(max(-32768, min(32767, v)))
    raw = struct.pack(f"<{n}h", *samples)
    return pygame.mixer.Sound(buffer=raw)

SND_SELECT = _make_beep(600, 0.08, 0.18)
SND_START1 = _make_beep(440, 0.10, 0.15)
SND_START2 = _make_beep(660, 0.10, 0.15)
SND_START3 = _make_beep(880, 0.14, 0.18)
SND_PASS1  = _make_beep(880, 0.11, 0.16)
SND_PASS2  = _make_beep(1100, 0.08, 0.16)
SND_CRASH1 = _make_beep(90, 0.30, 0.30)
SND_CRASH2 = _make_beep(70, 0.38, 0.20)

def sfx_select():
    SND_SELECT.play()
def sfx_start():
    SND_START1.play(); pygame.time.set_timer(pygame.USEREVENT + 1, 100, 1)
def sfx_pass():
    SND_PASS1.play(); pygame.time.set_timer(pygame.USEREVENT + 2, 80, 1)
def sfx_crash():
    SND_CRASH1.play(); SND_CRASH2.play()

# ═══════════════════════════════════════════════════════════
#  SPRITE FACTORY
# ═══════════════════════════════════════════════════════════
def create_car_sprite(body, roof, accent, hero=False):
    """Pre-render a top-down car surface with transparency."""
    w, h = CAR_W, CAR_H
    p = SPRITE_PAD
    surf = pygame.Surface((SPR_W, SPR_H), pygame.SRCALPHA)
    cx, cy = p + w // 2, p + h // 2

    # shadow
    pygame.draw.rect(surf, (0, 0, 0, 50),
                     (cx - w // 2 + 4, cy - h // 2 + 4, w, h), border_radius=9)

    # wheels
    wc = (17, 17, 17)
    ww, wh = 8, 20
    for (wx, wy) in [
        (cx - w // 2 - 2, cy - h // 2 + 10),
        (cx + w // 2 - 6, cy - h // 2 + 10),
        (cx - w // 2 - 2, cy + h // 2 - 30),
        (cx + w // 2 - 6, cy + h // 2 - 30),
    ]:
        pygame.draw.rect(surf, wc, (wx, wy, ww, wh), border_radius=3)

    # body
    pygame.draw.rect(surf, body, (cx - w // 2, cy - h // 2, w, h), border_radius=9)
    pygame.draw.rect(surf, (*[min(255, c + 25) for c in body], 35),
                     (cx - w // 2, cy - h // 2, w, h), width=1, border_radius=9)

    # roof
    pygame.draw.rect(surf, roof,
                     (cx - w // 2 + 5, cy - h // 2 + 18, w - 10, h - 36), border_radius=5)

    # windshield
    pygame.draw.rect(surf, (130, 200, 255, 100),
                     (cx - w // 2 + 6, cy - h // 2 + 12, w - 12, 18), border_radius=4)
    pygame.draw.rect(surf, (255, 255, 255, 35),
                     (cx - w // 2 + 6, cy - h // 2 + 12, w - 12, 18), width=1, border_radius=4)

    # rear window
    pygame.draw.rect(surf, (130, 200, 255, 70),
                     (cx - w // 2 + 8, cy + h // 2 - 27, w - 16, 14), border_radius=3)

    # headlights + glow
    hl = (255, 255, 200) if hero else (255, 238, 136)
    for lx in (cx - w // 2 + 9, cx + w // 2 - 9):
        pygame.draw.circle(surf, (*hl, 35), (lx, cy - h // 2 + 4), 9)
        pygame.draw.ellipse(surf, hl, (lx - 5, cy - h // 2 + 1, 10, 6))

    # taillights + glow
    for lx in (cx - w // 2 + 9, cx + w // 2 - 9):
        pygame.draw.circle(surf, (255, 30, 30, 40), (lx, cy + h // 2 - 4), 9)
        pygame.draw.ellipse(surf, (255, 34, 34), (lx - 5, cy + h // 2 - 7, 10, 6))

    # hero accent stripes
    if hero:
        stripe = pygame.Surface((w - 6, 3), pygame.SRCALPHA)
        stripe.fill((*accent, 85))
        surf.blit(stripe, (cx - w // 2 + 3, cy - h // 2 + 36))
        surf.blit(stripe, (cx - w // 2 + 3, cy + h // 2 - 38))

    return surf


def create_beam():
    """Headlight cone projected ahead of the player car."""
    bw, bh = 110, 130
    surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
    for row in range(bh):
        dist = bh - row
        t = dist / bh
        a = int(16 * (1 - t))
        spread = int(8 + 46 * t)
        if a > 0:
            pygame.draw.line(surf, (255, 255, 210, a),
                             (bw // 2 - spread, row), (bw // 2 + spread, row))
    return surf


def create_tree():
    surf = pygame.Surface((30, 28), pygame.SRCALPHA)
    pygame.draw.rect(surf, (58, 37, 16), (12, 16, 6, 11))
    pygame.draw.circle(surf, (23, 107, 23), (15, 10), 13)
    pygame.draw.circle(surf, (42, 138, 42), (12, 7), 7)
    return surf


# ── Build sprites ────────────────────────────────────────
player_sprites = [create_car_sprite(c["body"], c["roof"], c["accent"], hero=True) for c in CARS]
rival_sprites  = [create_car_sprite(b, r, (150, 150, 150)) for b, r in RIVAL_PALETTES]
beam_sprite    = create_beam()
tree_sprite    = create_tree()

# ═══════════════════════════════════════════════════════════
#  PARTICLES & FLOATING TEXT
# ═══════════════════════════════════════════════════════════
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "sz", "col", "life", "max_life")

    def __init__(self, x, y, vx, vy, sz, col, life):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.sz, self.col, self.life, self.max_life = sz, col, life, life

    def tick(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 40 * dt
        self.life -= dt

    def draw(self, surf):
        a = max(0.0, self.life / self.max_life)
        r = max(1, int(self.sz * a))
        ps = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(ps, (*self.col, int(255 * a)), (r, r), r)
        surf.blit(ps, (int(self.x) - r, int(self.y) - r))


class FloatingText:
    __slots__ = ("x", "y", "text", "col", "life")

    def __init__(self, x, y, text, col):
        self.x, self.y, self.text, self.col = x, y, text, col
        self.life = 1.2

    def tick(self, dt):
        self.y -= 65 * dt
        self.life -= dt

    def draw(self, surf):
        a = max(0, min(255, int(255 * self.life / 1.2)))
        draw_text(surf, self.text, FONT_FLOAT, self.col, int(self.x), int(self.y), "center", a)


particles = []
floats = []

def spawn_exhaust(x, y):
    for _ in range(2):
        particles.append(Particle(
            x + random.uniform(-4, 4), y,
            random.uniform(-12, 12), random.uniform(30, 70),
            random.uniform(3, 5), (120, 120, 120), random.uniform(0.2, 0.45)
        ))

def spawn_sparks(x, y):
    for i in range(14):
        c = SA_GOLD if i % 2 else SA_RED
        particles.append(Particle(
            x, y,
            random.uniform(-130, 130), random.uniform(-130, 130),
            random.uniform(2, 4), c, random.uniform(0.3, 0.7)
        ))

# ═══════════════════════════════════════════════════════════
#  HIGH SCORE
# ═══════════════════════════════════════════════════════════
SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.json")

def load_hs():
    try:
        with open(SCORE_FILE) as f:
            return json.load(f).get("hs", 0)
    except Exception:
        return 0

def save_hs(val):
    try:
        with open(SCORE_FILE, "w") as f:
            json.dump({"hs": val}, f)
    except Exception:
        pass

high_score = load_hs()

# ═══════════════════════════════════════════════════════════
#  GAME STATE
# ═══════════════════════════════════════════════════════════
state    = "MENU"
sel_car  = 0

# gameplay vars (set in start_game)
player      = {}
rivals      = []
potholes    = []
road_off    = 0.0
scroll_spd  = 0.0
dist        = 0.0
score       = 0
overtakes   = 0
lives       = 3
g_time      = 0.0
spawn_t     = 0.0
pot_t       = 0.0
difficulty  = 1.0
shake       = 0.0
paused      = False

# menu background particles
menu_parts = []


def start_game():
    global state, player, rivals, potholes, particles, floats
    global road_off, scroll_spd, dist, score, overtakes, lives
    global g_time, spawn_t, pot_t, difficulty, shake, paused

    player = {
        "x": float(LANE_X[1]), "y": float(HEIGHT - 160),
        "lane": 1, "tx": float(LANE_X[1]),
        "inv": 0.0, "car_idx": sel_car,
    }
    rivals = []
    potholes = []
    particles = []
    floats = []
    road_off = 0.0
    scroll_spd = 160.0
    dist = 0.0
    score = 0
    overtakes = 0
    lives = 3
    g_time = 0.0
    spawn_t = 0.0
    pot_t = 0.0
    difficulty = 1.0
    shake = 0.0
    paused = False
    state = "PLAY"
    sfx_start()


def hit(cx, cy):
    global lives, state, high_score, shake
    lives -= 1
    sfx_crash()
    spawn_sparks(cx, cy)
    shake = 16.0
    player["inv"] = 2.0
    if lives <= 0:
        state = "OVER"
        if score > high_score:
            high_score = score
            save_hs(high_score)


def change_lane(direction):
    nl = player["lane"] + direction
    if 0 <= nl < LANES and abs(player["x"] - player["tx"]) < 10:
        player["lane"] = nl
        player["tx"] = float(LANE_X[nl])

# ═══════════════════════════════════════════════════════════
#  UPDATE
# ═══════════════════════════════════════════════════════════
def update(dt):
    global road_off, scroll_spd, dist, score, overtakes
    global g_time, spawn_t, pot_t, difficulty, shake

    if state != "PLAY" or paused:
        return

    g_time += dt
    difficulty = 1 + g_time * 0.018
    car = CARS[sel_car]
    scroll_spd = min(620, (160 + g_time * 3.2) * car["spd"])
    road_off = (road_off + scroll_spd * dt) % 52

    dist += scroll_spd * dt * 0.05

    # ── player movement ──────────────────────────────────
    ms = 420 * car["grip"]
    dx = player["tx"] - player["x"]
    if abs(dx) > 1:
        player["x"] += math.copysign(min(ms * dt, abs(dx)), dx)
    else:
        player["x"] = player["tx"]

    keys = pygame.key.get_pressed()
    if keys[pygame.K_UP] or keys[pygame.K_w]:
        player["y"] = max(90, player["y"] - 160 * dt)
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:
        player["y"] = min(HEIGHT - 90, player["y"] + 160 * dt)
    player["y"] += (HEIGHT - 160 - player["y"]) * dt * 0.6

    if player["inv"] > 0:
        player["inv"] -= dt

    # exhaust
    if random.random() < dt * 28:
        spawn_exhaust(player["x"], player["y"] + CAR_H // 2)

    # ── spawn rivals ─────────────────────────────────────
    spawn_t -= dt
    if spawn_t <= 0:
        ln = random.randint(0, LANES - 1)
        rivals.append({
            "x": float(LANE_X[ln]), "y": float(-CAR_H - 20),
            "lane": ln,
            "spd": scroll_spd * random.uniform(0.28, 0.55),
            "sprite": random.choice(rival_sprites),
            "passed": False,
            "swerve": random.random() < 0.12 * difficulty,
            "swerve_t": random.uniform(1.2, 3.0),
        })
        spawn_t = max(0.38, random.uniform(0.7, 1.8) / difficulty)

    # ── update rivals ────────────────────────────────────
    for r in rivals[:]:
        r["y"] += (scroll_spd - r["spd"]) * dt

        if r["swerve"]:
            r["swerve_t"] -= dt
            if r["swerve_t"] <= 0:
                nl = r["lane"] + random.choice([-1, 1])
                if 0 <= nl < LANES:
                    r["lane"] = nl
                r["swerve_t"] = random.uniform(1.5, 3.0)
            target_x = LANE_X[r["lane"]]
            r["x"] += (target_x - r["x"]) * dt * 3.5

        if not r["passed"] and r["y"] > player["y"] + CAR_H * 0.6:
            r["passed"] = True
            overtakes += 1
            sfx_pass()
            msg = random.choice(OVERTAKE_MSGS)
            floats.append(FloatingText(player["x"], player["y"] - CAR_H // 2 - 12,
                                       f"+100 {msg}", SA_GOLD))
            spawn_sparks(player["x"], player["y"] - CAR_H // 2)

        if r["y"] > HEIGHT + 120:
            rivals.remove(r)
            continue

        if player["inv"] <= 0:
            if abs(r["x"] - player["x"]) < CAR_W * 0.78 and \
               abs(r["y"] - player["y"]) < CAR_H * 0.78:
                hit(r["x"], r["y"])

    # ── spawn potholes ───────────────────────────────────
    pot_t -= dt
    if pot_t <= 0:
        ln = random.randint(0, LANES - 1)
        potholes.append({
            "x": LANE_X[ln] + random.uniform(-12, 12),
            "y": float(-POT_MAX_R * 2),
            "r": random.uniform(10, POT_MAX_R),
        })
        pot_t = max(0.45, random.uniform(1.2, 3.5) / (difficulty * 0.7))

    for p in potholes[:]:
        p["y"] += scroll_spd * dt
        if p["y"] > HEIGHT + 40:
            potholes.remove(p)
            continue
        if player["inv"] <= 0:
            if abs(p["x"] - player["x"]) < (CAR_W / 2 + p["r"] * 0.55) and \
               abs(p["y"] - player["y"]) < (CAR_H / 2 + p["r"] * 0.55):
                hit(p["x"], p["y"])
                if p in potholes:
                    potholes.remove(p)

    # ── particles & floats ───────────────────────────────
    for pt in particles[:]:
        pt.tick(dt)
        if pt.life <= 0:
            particles.remove(pt)
    for ft in floats[:]:
        ft.tick(dt)
        if ft.life <= 0:
            floats.remove(ft)

    score = int(dist) * 10 + overtakes * 100

    if shake > 0:
        shake *= 0.88
        if shake < 0.4:
            shake = 0

# ═══════════════════════════════════════════════════════════
#  DRAWING — ROAD & SCENERY
# ═══════════════════════════════════════════════════════════
def draw_road():
    screen.fill(COL_VELD)

    # shoulder
    pygame.draw.rect(screen, COL_SHOULDER, (ROAD_L - 14, 0, ROAD_W + 28, HEIGHT))

    # tarmac
    pygame.draw.rect(screen, COL_TARMAC, (ROAD_L, 0, ROAD_W, HEIGHT))

    # lane dashes
    dash, gap = 28, 24
    period = dash + gap
    for lane_i in range(1, LANES):
        lx = ROAD_L + LANE_W * lane_i - 1
        y = -period + int(road_off % period)
        while y < HEIGHT:
            top = max(0, y)
            bot = min(HEIGHT, y + dash)
            if bot > top:
                pygame.draw.rect(screen, COL_DASH, (lx, top, 2, bot - top))
            y += period

    # edge lines
    pygame.draw.rect(screen, SA_GOLD, (ROAD_L - 1, 0, 3, HEIGHT))
    pygame.draw.rect(screen, SA_GOLD, (ROAD_R - 2, 0, 3, HEIGHT))

    # road posts
    ps = 130
    y = -ps + int(road_off % ps)
    while y < HEIGHT + ps:
        # left
        pygame.draw.rect(screen, (204, 204, 204), (ROAD_L - 9, y, 4, 12))
        pygame.draw.rect(screen, SA_RED, (ROAD_L - 9, y, 4, 4))
        # right
        pygame.draw.rect(screen, (204, 204, 204), (ROAD_R + 5, y, 4, 12))
        pygame.draw.rect(screen, SA_RED, (ROAD_R + 5, y, 4, 4))
        y += ps


def draw_scenery():
    ts = 160
    y = -ts + int(road_off % ts)
    while y < HEIGHT + ts:
        tx1 = 15 + int(math.sin(y * 0.012) * 12)
        tx2 = WIDTH - 15 + int(math.cos(y * 0.012) * 12)
        screen.blit(tree_sprite, (tx1 - 15, y - 14))
        screen.blit(tree_sprite, (tx2 - 15, y + 56))
        y += ts


def draw_pothole(x, y, r):
    ri = int(r)
    pygame.draw.circle(screen, (24, 24, 24), (int(x), int(y)), ri + 3)
    pygame.draw.circle(screen, (12, 12, 12), (int(x), int(y)), ri)
    pygame.draw.arc(screen, (255, 255, 255, 15), (int(x) - ri - 2, int(y) - ri - 2,
                    (ri + 2) * 2, (ri + 2) * 2), -0.8, 1.2, 1)

# ═══════════════════════════════════════════════════════════
#  DRAWING — HUD
# ═══════════════════════════════════════════════════════════
def draw_hud():
    hud = pygame.Surface((WIDTH - 20, 55), pygame.SRCALPHA)
    hud.fill((0, 0, 0, 184))
    pygame.draw.rect(hud, (255, 184, 28, 60), (0, 0, WIDTH - 20, 55), width=1, border_radius=10)
    screen.blit(hud, (10, 10))

    cols = [
        ("SCORE",    f"{score:,}",                         25),
        ("DISTANCE", f"{int(dist)}m",                      145),
        ("SPEED",    f"{int(scroll_spd * 0.8)} km/h",     275),
    ]
    for lbl, val, x in cols:
        draw_text(screen, lbl, FONT_HUD_L, SA_GOLD, x, 18)
        draw_text(screen, val, FONT_HUD_V, SA_WHITE, x, 35)

    draw_text(screen, "LIVES", FONT_HUD_L, SA_GOLD, 398, 18)
    for i in range(lives):
        hx = 405 + i * 20
        hy = 42
        pts = []
        for a in range(0, 360, 10):
            rad = math.radians(a)
            r = 7 * (1 - 0.3 * abs(math.sin(rad)))
            pts.append((hx + int(r * math.sin(rad)), hy - int(r * math.cos(rad))))
        if len(pts) >= 3:
            pygame.draw.polygon(screen, SA_RED, pts)

# ═══════════════════════════════════════════════════════════
#  DRAWING — MENU
# ═══════════════════════════════════════════════════════════
def draw_menu():
    screen.fill(COL_BG)

    # bg particles
    while len(menu_parts) < 50:
        menu_parts.append({
            "x": random.uniform(0, WIDTH), "y": random.uniform(0, HEIGHT),
            "vx": random.uniform(-8, 8), "vy": random.uniform(-18, -4),
            "sz": random.uniform(1, 2.8),
            "col": random.choice([SA_GOLD, SA_GREEN, SA_RED]),
            "a": random.randint(20, 90),
        })
    for p in menu_parts:
        p["x"] += p["vx"] * (1 / 60)
        p["y"] += p["vy"] * (1 / 60)
        if p["y"] < -10:
            p["y"] = HEIGHT + 10
            p["x"] = random.uniform(0, WIDTH)
        ps = pygame.Surface((int(p["sz"] * 2 + 1), int(p["sz"] * 2 + 1)), pygame.SRCALPHA)
        pygame.draw.circle(ps, (*p["col"], p["a"]), (int(p["sz"]), int(p["sz"])), int(p["sz"]))
        screen.blit(ps, (int(p["x"] - p["sz"]), int(p["y"] - p["sz"])))

    # flag stripes top
    sh = 5
    pygame.draw.rect(screen, SA_GREEN, (0, 0, WIDTH, sh))
    pygame.draw.rect(screen, SA_GOLD, (0, sh, WIDTH, sh))
    pygame.draw.rect(screen, SA_RED, (0, sh * 2, WIDTH, sh))

    # title
    draw_text(screen, "MZANSI", FONT_TITLE, SA_GREEN, WIDTH // 2, 70, "center")
    draw_text(screen, "RUSH", FONT_TITLE, SA_GOLD, WIDTH // 2, 140, "center")
    draw_text(screen, "SA STREET RACING", FONT_SM, (153, 153, 153), WIDTH // 2, 220, "center")

    # car select label
    draw_text(screen, "CHOOSE YOUR RIDE", FONT_MED, SA_GOLD, WIDTH // 2, 270, "center")

    # cars
    gap = (WIDTH - 80) // 4
    for i, c in enumerate(CARS):
        cx = 40 + gap * i + gap // 2
        cy = 370
        sel = i == sel_car

        if sel:
            hl = pygame.Surface((92, 145), pygame.SRCALPHA)
            hl.fill((255, 184, 28, 30))
            pygame.draw.rect(hl, SA_GOLD, (0, 0, 92, 145), width=2, border_radius=10)
            screen.blit(hl, (cx - 46, cy - 68))

        spr = player_sprites[i]
        # scale down for menu display
        menu_spr = pygame.transform.smoothscale(spr, (int(SPR_W * 0.52), int(SPR_H * 0.52)))
        screen.blit(menu_spr, (cx - menu_spr.get_width() // 2, cy - menu_spr.get_height() // 2))

        col_name = SA_GOLD if sel else (102, 102, 102)
        col_desc = (187, 187, 187) if sel else (68, 68, 68)
        fn = FONT_HUD_L if sel else FONT_XS
        draw_text(screen, c["name"], fn, col_name, cx, cy + 46, "center")
        draw_text(screen, c["desc"], FONT_XS, col_desc, cx, cy + 62, "center")

    # stat bars
    s = CARS[sel_car]
    by = 468
    bar_bg = pygame.Surface((280, 60), pygame.SRCALPHA)
    bar_bg.fill((255, 255, 255, 10))
    screen.blit(bar_bg, (WIDTH // 2 - 140, by))

    # speed bar
    draw_text(screen, "SPEED", FONT_XS, (102, 102, 102), WIDTH // 2 - 120, by + 7)
    pygame.draw.rect(screen, (42, 42, 42), (WIDTH // 2 - 45, by + 8, 155, 10), border_radius=5)
    pygame.draw.rect(screen, SA_RED, (WIDTH // 2 - 45, by + 8, int(155 * s["spd"] / 1.3), 10), border_radius=5)

    # grip bar
    draw_text(screen, "GRIP", FONT_XS, (102, 102, 102), WIDTH // 2 - 120, by + 33)
    pygame.draw.rect(screen, (42, 42, 42), (WIDTH // 2 - 45, by + 34, 155, 10), border_radius=5)
    pygame.draw.rect(screen, SA_GREEN, (WIDTH // 2 - 45, by + 34, int(155 * s["grip"] / 1.2), 10), border_radius=5)

    # controls
    draw_text(screen, "← →  to select car", FONT_XS, (68, 68, 68), WIDTH // 2, 580, "center")

    # start prompt (flash)
    fl = math.sin(pygame.time.get_ticks() * 0.005) * 0.3 + 0.7
    draw_text(screen, "PRESS SPACE TO RACE", FONT_MED, SA_GOLD,
              WIDTH // 2, 630, "center", int(255 * fl))
    draw_text(screen, "or tap the screen", FONT_XS, (51, 51, 51), WIDTH // 2, 658, "center")

    if high_score > 0:
        draw_text(screen, f"HIGH SCORE: {high_score:,}", FONT_SM, SA_GOLD,
                  WIDTH // 2, 710, "center")

    # bottom stripes
    pygame.draw.rect(screen, SA_RED, (0, HEIGHT - sh * 3, WIDTH, sh))
    pygame.draw.rect(screen, SA_GOLD, (0, HEIGHT - sh * 2, WIDTH, sh))
    pygame.draw.rect(screen, SA_GREEN, (0, HEIGHT - sh, WIDTH, sh))

    draw_text(screen, "WASD / ARROWS to drive  ·  Dodge potholes & rivals!",
              FONT_XS, (42, 42, 42), WIDTH // 2, HEIGHT - 26, "center")

# ═══════════════════════════════════════════════════════════
#  DRAWING — GAME OVER
# ═══════════════════════════════════════════════════════════
def draw_game_over():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 5, 16, 184))
    screen.blit(overlay, (0, 0))

    draw_text(screen, "EISH!", FONT_OVER, SA_RED, WIDTH // 2, 130, "center")
    draw_text(screen, "Your ride is totalled, boet!", FONT_SM, (153, 153, 153),
              WIDTH // 2, 222, "center")

    # stats box
    box = pygame.Surface((310, 210), pygame.SRCALPHA)
    box.fill((0, 0, 0, 128))
    pygame.draw.rect(box, (255, 184, 28, 45), (0, 0, 310, 210), width=1, border_radius=12)
    screen.blit(box, (WIDTH // 2 - 155, 260))

    rows = [
        ("FINAL SCORE", f"{score:,}", SA_GOLD),
        ("DISTANCE",    f"{int(dist)}m", SA_WHITE),
        ("RIVALS PASSED", str(overtakes), SA_WHITE),
        ("TOP SPEED",   f"{int(scroll_spd * 0.8)} km/h", SA_WHITE),
    ]
    for i, (lbl, val, col) in enumerate(rows):
        ry = 290 + i * 42
        draw_text(screen, lbl, FONT_STAT_L, (119, 119, 119), WIDTH // 2 - 125, ry)
        draw_text(screen, val, FONT_STAT_V, col, WIDTH // 2 + 125, ry, "right")

    if score >= high_score and score > 0:
        p = math.sin(pygame.time.get_ticks() * 0.008) * 0.2 + 0.8
        draw_text(screen, "NEW HIGH SCORE!", FONT_MED, SA_GOLD,
                  WIDTH // 2, 508, "center", int(255 * p))

    fl = math.sin(pygame.time.get_ticks() * 0.005) * 0.3 + 0.7
    draw_text(screen, "PRESS SPACE TO RACE AGAIN", FONT_MED, SA_GREEN,
              WIDTH // 2, 570, "center", int(255 * fl))
    draw_text(screen, "or tap the screen", FONT_XS, (51, 51, 51),
              WIDTH // 2, 598, "center")

# ═══════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════
running = True
touch_x0 = 0

while running:
    dt = clock.tick(FPS) / 1000.0
    if dt > 0.1:
        dt = 0.1

    # ── events ───────────────────────────────────────────
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

        # delayed sound triggers
        elif ev.type == pygame.USEREVENT + 1:
            SND_START2.play()
            pygame.time.set_timer(pygame.USEREVENT + 3, 100, 1)
        elif ev.type == pygame.USEREVENT + 3:
            SND_START3.play()
        elif ev.type == pygame.USEREVENT + 2:
            SND_PASS2.play()

        elif ev.type == pygame.KEYDOWN:
            if state == "MENU":
                if ev.key in (pygame.K_LEFT, pygame.K_a):
                    sel_car = (sel_car - 1) % len(CARS)
                    sfx_select()
                elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                    sel_car = (sel_car + 1) % len(CARS)
                    sfx_select()
                elif ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    start_game()

            elif state == "PLAY":
                if ev.key in (pygame.K_LEFT, pygame.K_a):
                    change_lane(-1)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                    change_lane(1)
                elif ev.key == pygame.K_ESCAPE:
                    paused = not paused

            elif state == "OVER":
                if ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    state = "MENU"

        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if state == "MENU":
                mx, my = ev.pos
                gap = (WIDTH - 80) // 4
                for i in range(len(CARS)):
                    cx = 40 + gap * i + gap // 2
                    if cx - 46 < mx < cx + 46 and 302 < my < 447:
                        sel_car = i
                        sfx_select()
                        break
                else:
                    start_game()
            elif state == "OVER":
                state = "MENU"

        # touch support (for touchscreen)
        elif ev.type == pygame.FINGERDOWN:
            touch_x0 = ev.x * WIDTH
            if state == "MENU":
                start_game()
            elif state == "OVER":
                state = "MENU"

        elif ev.type == pygame.FINGERMOTION:
            if state == "PLAY":
                dx = ev.x * WIDTH - touch_x0
                if abs(dx) > 28:
                    change_lane(1 if dx > 0 else -1)
                    touch_x0 = ev.x * WIDTH

    # ── update ───────────────────────────────────────────
    update(dt)

    # ── render ───────────────────────────────────────────
    if state == "MENU":
        draw_menu()
    else:
        # apply screen shake offset
        ox = int(random.uniform(-shake, shake)) if shake > 0 else 0
        oy = int(random.uniform(-shake, shake)) if shake > 0 else 0

        draw_road()
        draw_scenery()

        for p in potholes:
            draw_pothole(p["x"] + ox, p["y"] + oy, p["r"])

        for r in rivals:
            spr = r["sprite"]
            screen.blit(spr, (int(r["x"] + ox) - SPR_W // 2,
                              int(r["y"] + oy) - SPR_H // 2))

        # player beam
        screen.blit(beam_sprite, (int(player["x"] + ox) - beam_sprite.get_width() // 2,
                                  int(player["y"] + oy) - CAR_H // 2 - beam_sprite.get_height()))

        # player car (blink when invulnerable)
        show_player = player["inv"] <= 0 or int(player["inv"] * 10) % 2 == 0
        if show_player:
            spr = player_sprites[player["car_idx"]]
            screen.blit(spr, (int(player["x"] + ox) - SPR_W // 2,
                              int(player["y"] + oy) - SPR_H // 2))

        for pt in particles:
            pt.draw(screen)
        for ft in floats:
            ft.draw(screen)

        # crash flash overlay
        if shake > 2:
            flash_s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash_s.fill((222, 56, 49, int(min(shake * 4, 60))))
            screen.blit(flash_s, (0, 0))

        draw_hud()

        # pause overlay
        if paused:
            po = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            po.fill((0, 0, 0, 150))
            screen.blit(po, (0, 0))
            draw_text(screen, "PAUSED", FONT_BIG, SA_GOLD, WIDTH // 2, HEIGHT // 2 - 30, "center")
            draw_text(screen, "Press ESC to resume", FONT_SM, (153, 153, 153),
                      WIDTH // 2, HEIGHT // 2 + 15, "center")

        if state == "OVER":
            draw_game_over()

    pygame.display.flip()

pygame.quit()
sys.exit()
