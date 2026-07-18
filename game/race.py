"""Race screen: tile-based top-down race with inertial tank steering.

Physics are driven by tile_definitions.json properties:
  - speed_multiplier : caps / boosts forward speed
  - friction         : scales angular-velocity decay (low = ice sliding)
  - damage_per_sec   : reduces car health (lava, etc.)
  - drivable=False   : wall tiles → car bounces back + collision_damage
"""

import os
import math
import pygame

from game.physics import CarPhysics
from game.track   import Track, DEFAULT_TRACK
from game.hud     import HUD

_CAR_W = 42
_CAR_H = 68

_SKID_THRESHOLD = 70    # deg/sec
_SKID_MIN_SPEED = 35    # px/sec
_SKID_MAX       = 400

_GOLD  = (215, 180,  30)
_WHITE = (235, 235, 235)
_GREY  = (130, 120, 110)
_RED   = (210,  40,  40)
_GREEN = ( 60, 200,  80)
_BOOST_COL = (255, 215, 0)


class RaceScreen:
    def __init__(self, SW: int, SH: int, fonts: dict, game_data: dict):
        self.SW = SW
        self.SH = SH
        self.fonts = fonts

        # ── select track from settings ────────────────────────────────
        track_key  = game_data["settings"].get("active_track", "mzansi_asphalt")
        track_path = f"data/{track_key}.json"
        if not os.path.exists(track_path):
            track_path = DEFAULT_TRACK

        self.track = Track(track_path)

        # ── car setup ─────────────────────────────────────────────────
        sel_id  = game_data["player"]["selected_car"]
        car_def = next(
            (c for c in game_data["cars"] if c["id"] == sel_id),
            game_data["cars"][0],
        )
        self.car_color = tuple(car_def.get("color", (180, 30, 30)))
        self._sprite   = self._load_sprite(car_def.get("image", ""))

        self.physics = CarPhysics(
            self.track.start_x,
            self.track.start_y,
            self.track.start_angle,
            car_def.get("stats"),
        )

        # ── HUD ───────────────────────────────────────────────────────
        self.hud = HUD(SW, SH, fonts, self.track)

        # ── lap / checkpoint state ────────────────────────────────────
        self._lap      = 1
        self._next_cp  = 0          # index into track.checkpoints (starts at 0 = finish line cp)
        self._cp_done  = 0          # how many checkpoints hit this lap

        # ── timers ────────────────────────────────────────────────────
        self._lap_time   = 0.0
        self._best_lap   = 999.0
        self._total_time = 0.0

        # ── health ────────────────────────────────────────────────────
        self.health      = 100.0
        self._boost_flash = 0.0     # screen flash timer for boost

        # ── camera ────────────────────────────────────────────────────
        self.cam_x = float(self.track.start_x - SW / 2)
        self.cam_y = float(self.track.start_y - SH / 2)
        self._clamp_cam()

        # ── visual extras ─────────────────────────────────────────────
        self._skid_marks: list[tuple[int, int, int]] = []

        # ── state ─────────────────────────────────────────────────────
        self.state      = "countdown"
        self._countdown = 3.0

    # ── public ────────────────────────────────────────────────────────────────

    def handle_event(self, event) -> str | None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == "paused":
                    self.state = "racing"
                elif self.state == "racing":
                    self.state = "paused"
                elif self.state in ("finished", "countdown"):
                    return "lobby"
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.state in ("finished", "paused"):
                    return "lobby"
        return None

    def update(self, dt: float):
        if self.state in ("paused", "finished"):
            return

        if self.state == "countdown":
            self._countdown -= dt
            if self._countdown <= 0:
                self.state = "racing"
            return

        # ── input ─────────────────────────────────────────────────────
        keys  = pygame.key.get_pressed()
        up    = keys[pygame.K_UP]    or keys[pygame.K_w]
        down  = keys[pygame.K_DOWN]  or keys[pygame.K_s]
        left  = keys[pygame.K_LEFT]  or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        # ── save pre-update position for wall collision ────────────────
        prev_x, prev_y = self.physics.x, self.physics.y

        # ── tile physics lookup ───────────────────────────────────────
        tile_def    = self.track.get_tile_def_at(self.physics.x, self.physics.y)
        speed_mult  = tile_def.speed_multiplier if tile_def else 1.0
        surf_fric   = tile_def.friction         if tile_def else 1.0

        self.physics.update(dt, up, down, left, right, speed_mult, surf_fric)

        # ── wall collision ────────────────────────────────────────────
        new_tile = self.track.get_tile_def_at(self.physics.x, self.physics.y)
        if new_tile and not new_tile.drivable:
            self.physics.x = prev_x
            self.physics.y = prev_y
            self.physics.speed *= -0.25
            if new_tile.collision_damage > 0:
                self.health = max(0.0, self.health - new_tile.collision_damage)

        # ── per-tile damage / boost ───────────────────────────────────
        cur_tile = self.track.get_tile_def_at(self.physics.x, self.physics.y)
        if cur_tile:
            if cur_tile.damage_per_sec > 0:
                self.health = max(0.0, self.health - cur_tile.damage_per_sec * dt)
            if cur_tile.speed_multiplier > 1.0:
                self._boost_flash = 0.12

        self._boost_flash = max(0.0, self._boost_flash - dt)

        # ── timers ────────────────────────────────────────────────────
        self._lap_time   += dt
        self._total_time += dt

        # ── checkpoint / lap logic ────────────────────────────────────
        n_cp   = len(self.track.checkpoints)
        cp_idx = self._next_cp % n_cp
        if self.track.checkpoint_reached(self.physics.x, self.physics.y, cp_idx):
            self._cp_done += 1
            self._next_cp  = (self._next_cp + 1) % n_cp

            if self._cp_done >= n_cp:
                self._cp_done = 0
                if self._lap_time < self._best_lap:
                    self._best_lap = self._lap_time
                self._lap_time = 0.0
                if self._lap < self.track.total_laps:
                    self._lap += 1
                else:
                    self.state = "finished"

        # ── skid marks ────────────────────────────────────────────────
        if (abs(self.physics.angular_vel) > _SKID_THRESHOLD
                and self.physics.speed > _SKID_MIN_SPEED):
            self._skid_marks.append(
                (int(self.physics.x), int(self.physics.y), 220)
            )
            if len(self._skid_marks) > _SKID_MAX:
                self._skid_marks.pop(0)

        self._skid_marks = [
            (x, y, max(0, a - 1)) for x, y, a in self._skid_marks if a > 0
        ]

        # ── camera smooth follow ──────────────────────────────────────
        tx = self.physics.x - self.SW / 2
        ty = self.physics.y - self.SH / 2
        self.cam_x += (tx - self.cam_x) * min(1.0, 9 * dt)
        self.cam_y += (ty - self.cam_y) * min(1.0, 9 * dt)
        self._clamp_cam()

    def draw(self, surface):
        # 1. track tiles
        self.track.draw(surface, self.cam_x, self.cam_y)

        # 2. skid marks
        for wx, wy, alpha in self._skid_marks:
            sx = int(wx - self.cam_x)
            sy = int(wy - self.cam_y)
            if 0 <= sx < self.SW and 0 <= sy < self.SH:
                a8 = max(0, int(55 * alpha / 220))
                pygame.draw.circle(surface, (a8, max(0, a8-3), max(0, a8-5)), (sx, sy), 3)

        # 3. car
        sx = int(self.physics.x - self.cam_x)
        sy = int(self.physics.y - self.cam_y)
        self._draw_car(surface, sx, sy)

        # 4. boost flash overlay
        if self._boost_flash > 0:
            fsurf = pygame.Surface((self.SW, self.SH), pygame.SRCALPHA)
            alpha = int(60 * self._boost_flash / 0.12)
            fsurf.fill((*_BOOST_COL, alpha))
            surface.blit(fsurf, (0, 0))

        # 5. HUD
        cur_tile = self.track.get_tile_def_at(self.physics.x, self.physics.y)
        self.hud.draw(
            surface, self.physics,
            self._lap, self.track.total_laps,
            self._lap_time, self._best_lap,
            self._total_time, cur_tile, self.health,
        )

        # 6. overlays
        if self.state == "countdown":
            self._draw_countdown(surface)
        elif self.state == "paused":
            self._draw_pause(surface)
        elif self.state == "finished":
            self._draw_finished(surface)

    # ── private ───────────────────────────────────────────────────────────────

    def _clamp_cam(self):
        self.cam_x = max(0.0, min(self.cam_x, self.track.world_w - self.SW))
        self.cam_y = max(0.0, min(self.cam_y, self.track.world_h - self.SH))

    def _load_sprite(self, path: str):
        if path and os.path.exists(path):
            try:
                raw = pygame.image.load(path)
                try:
                    raw = raw.convert_alpha()
                except pygame.error:
                    pass
                return pygame.transform.smoothscale(raw, (_CAR_W, _CAR_H))
            except Exception:
                pass
        return None

    def _draw_car(self, surface, sx, sy):
        if self._sprite:
            rotated = pygame.transform.rotate(self._sprite, -self.physics.angle)
            rect    = rotated.get_rect(center=(sx, sy))
            shadow  = rotated.copy()
            shadow.fill((0, 0, 0, 100), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow, shadow.get_rect(center=(sx + 4, sy + 5)))
            surface.blit(rotated, rect)
        else:
            self._draw_fallback(surface, sx, sy)

    def _draw_fallback(self, surface, cx, cy):
        rad       = math.radians(self.physics.angle)
        fw, fh    = 18, 30
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        corners   = [(-fw//2,-fh//2),(fw//2,-fh//2),(fw//2,fh//2),(-fw//2,fh//2)]
        poly      = [(cx + x*cos_a - y*sin_a, cy + x*sin_a + y*cos_a) for x, y in corners]
        pygame.draw.polygon(surface, self.car_color, poly)
        pygame.draw.polygon(surface, _WHITE, poly, 2)

    def _draw_countdown(self, surface):
        sw, sh = self.SW, self.SH
        n      = int(self._countdown) + 1
        ov     = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 110))
        surface.blit(ov, (0, 0))

        txt   = str(n) if n <= 3 else "GO!"
        col   = _RED if n > 1 else _GOLD
        surf  = self.fonts["big_title"].render(txt, True, col)
        surface.blit(surf, surf.get_rect(center=(sw//2, sh//2 - 30)))

        # Track name
        name_s = self.fonts["heading"].render(self.track.name, True, _WHITE)
        surface.blit(name_s, name_s.get_rect(centerx=sw//2, y=sh//2 + 40))

        diff_s = self.fonts["small"].render(
            f"Difficulty: {self.track.difficulty.upper()}  ·  {self.track.total_laps} laps",
            True, _GREY)
        surface.blit(diff_s, diff_s.get_rect(centerx=sw//2, y=sh//2 + 78))

        hint = self.fonts["small"].render(
            "W/↑ accelerate  ·  A/D steer  ·  S/↓ brake  ·  ESC pause",
            True, (145, 138, 130))
        surface.blit(hint, hint.get_rect(centerx=sw//2, y=sh - 32))

    def _draw_pause(self, surface):
        sw, sh = self.SW, self.SH
        ov     = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 165))
        surface.blit(ov, (0, 0))

        t = self.fonts["big_title"].render("PAUSED", True, _WHITE)
        surface.blit(t, t.get_rect(center=(sw//2, sh//2 - 40)))

        s = self.fonts["body"].render(
            "SPACE / ENTER — return to lobby   ·   ESC — resume", True, _GREY)
        surface.blit(s, s.get_rect(center=(sw//2, sh//2 + 18)))

    def _draw_finished(self, surface):
        sw, sh = self.SW, self.SH
        ov     = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 175))
        surface.blit(ov, (0, 0))

        t = self.fonts["big_title"].render("RACE COMPLETE!", True, _GOLD)
        surface.blit(t, t.get_rect(center=(sw//2, sh//2 - 60)))

        def fmt(tt):
            m  = int(tt // 60)
            s  = int(tt % 60)
            ms = int((tt % 1) * 100)
            return f"{m:01d}:{s:02d}.{ms:02d}"

        hp_col = _GREEN if self.health > 50 else (_GOLD if self.health > 25 else _RED)
        for i, (text, col) in enumerate([
            (f"Best lap:    {fmt(self._best_lap)}", _WHITE),
            (f"Total time:  {fmt(self._total_time)}", _GREY),
            (f"HP remaining: {int(self.health)}", hp_col),
        ]):
            s = self.fonts["heading"].render(text, True, col)
            surface.blit(s, s.get_rect(center=(sw//2, sh//2 + i * 44)))

        hint = self.fonts["body"].render(
            "SPACE / ENTER — return to lobby", True, (118, 108, 98))
        surface.blit(hint, hint.get_rect(center=(sw//2, sh//2 + 160)))
