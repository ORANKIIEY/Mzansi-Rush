




"""Race HUD: speedometer arc, lap counter, timer, minimap, health bar."""

import pygame
import math

_RED   = (210,  40,  40)
_GOLD  = (215, 180,  30)
_WHITE = (235, 235, 235)
_GREY  = (130, 120, 110)
_GREEN = ( 60, 200,  80)
_ORANGE= (230, 140,  30)
_ICE   = (140, 200, 230)
_BOOST = (255, 215,   0)


class HUD:
    SPEEDO_R  = 72
    SPEEDO_CX = 104

    MM_W, MM_H = 210, 165
    MM_PAD     = 14

    def __init__(self, SW: int, SH: int, fonts: dict, track):
        self.SW    = SW
        self.SH    = SH
        self.fonts = fonts
        self.track = track

        self.SPEEDO_CY = SH - self.SPEEDO_R - 18

        self.mm_x = SW - self.MM_W - self.MM_PAD
        self.mm_y = SH - self.MM_H - self.MM_PAD

    def draw(self, surface, physics, lap, total_laps, lap_time, best_lap,
             total_time, tile_def, health):
        self._draw_speedometer(surface, physics.kmh, physics.max_speed * 0.32, tile_def)
        self._draw_health_bar(surface, health)
        self._draw_lap_panel(surface, lap, total_laps, lap_time, best_lap)
        self._draw_minimap(surface, physics.x, physics.y)
        if tile_def:
            self._draw_tile_alert(surface, tile_def)

    # ── speedometer ───────────────────────────────────────────────────────────

    def _draw_speedometer(self, surface, kmh, max_kmh, tile_def):
        cx, cy = self.SPEEDO_CX, self.SPEEDO_CY
        R      = self.SPEEDO_R

        bg = pygame.Surface(((R+14)*2, (R+14)*2 + 12), pygame.SRCALPHA)
        bg.fill((18, 16, 14, 190))
        surface.blit(bg, (cx - R - 14, cy - R - 14))

        start_ang = 210
        sweep     = -240
        ratio     = min(1.0, kmh / max(max_kmh, 1))

        pygame.draw.arc(surface, (58, 52, 48),
                        (cx-R, cy-R, R*2, R*2),
                        math.radians(start_ang + sweep),
                        math.radians(start_ang), 10)
        if ratio > 0:
            r = int(min(255, ratio * 510))
            g = int(min(255, (1-ratio) * 510))
            pygame.draw.arc(surface, (r, g, 20),
                            (cx-R, cy-R, R*2, R*2),
                            math.radians(start_ang + sweep * ratio),
                            math.radians(start_ang), 10)

        pygame.draw.circle(surface, (48, 43, 40), (cx, cy), R, 2)

        # Boost tint ring
        if tile_def and tile_def.speed_multiplier > 1.0:
            pygame.draw.circle(surface, _BOOST, (cx, cy), R, 3)

        # KMH number
        kmh_s = self.fonts["title"].render(f"{int(kmh)}", True, _WHITE)
        surface.blit(kmh_s, kmh_s.get_rect(center=(cx, cy - 2)))

        lbl = self.fonts["small"].render("KMH", True, _GREY)
        surface.blit(lbl, lbl.get_rect(center=(cx, cy + R - 18)))

        for tick in range(9):
            ang = math.radians(start_ang + sweep * tick / 8)
            x1  = cx + math.cos(ang) * (R - 14)
            y1  = cy - math.sin(ang) * (R - 14)
            x2  = cx + math.cos(ang) * (R - 4)
            y2  = cy - math.sin(ang) * (R - 4)
            col = _WHITE if tick % 2 == 0 else (78, 72, 68)
            pygame.draw.line(surface, col, (int(x1), int(y1)), (int(x2), int(y2)), 2)

    # ── health bar ────────────────────────────────────────────────────────────

    def _draw_health_bar(self, surface, health):
        cx, cy = self.SPEEDO_CX, self.SPEEDO_CY
        R      = self.SPEEDO_R
        bx     = cx - R - 14
        by     = cy + R + 2
        bw     = (R + 14) * 2
        bh     = 10

        bg = pygame.Surface((bw, bh + 4), pygame.SRCALPHA)
        bg.fill((18, 16, 14, 180))
        surface.blit(bg, (bx, by))

        ratio = max(0.0, min(1.0, health / 100.0))
        col   = _GREEN if ratio > 0.5 else (_ORANGE if ratio > 0.25 else _RED)
        if bw > 4:
            pygame.draw.rect(surface, (45, 40, 38), (bx+2, by+2, bw-4, bh), border_radius=3)
            pygame.draw.rect(surface, col, (bx+2, by+2, int((bw-4)*ratio), bh), border_radius=3)

        hp_s = self.fonts["small"].render(f"HP {int(health)}", True, col)
        surface.blit(hp_s, hp_s.get_rect(centerx=cx, y=by + bh + 4))

    # ── lap / timer panel ─────────────────────────────────────────────────────

    def _draw_lap_panel(self, surface, lap, total_laps, lap_time, best_lap):
        sw   = self.SW
        w, h = 280, 88
        x    = (sw - w) // 2
        y    = 8

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((18, 16, 14, 190))
        surface.blit(bg, (x, y))
        pygame.draw.rect(surface, (54, 48, 44), (x, y, w, h), 1, border_radius=8)

        lap_s = self.fonts["coin"].render(f"LAP  {min(lap, total_laps)} / {total_laps}", True, _GOLD)
        surface.blit(lap_s, lap_s.get_rect(centerx=x + w//2, y=y+8))

        def fmt(t):
            m  = int(t // 60)
            s  = int(t % 60)
            ms = int((t % 1) * 100)
            return f"{m:01d}:{s:02d}.{ms:02d}"

        lt_s = self.fonts["body"].render(fmt(lap_time), True, _WHITE)
        surface.blit(lt_s, lt_s.get_rect(centerx=x + w//2, y=y+36))

        if best_lap < 999:
            bl_s = self.fonts["small"].render(f"BEST  {fmt(best_lap)}", True, _GREY)
            surface.blit(bl_s, bl_s.get_rect(right=x+w-6, y=y+66))

    # ── minimap ───────────────────────────────────────────────────────────────

    def _draw_minimap(self, surface, car_x, car_y):
        mx, my  = self.mm_x, self.mm_y
        mw, mh  = self.MM_W, self.MM_H

        bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
        bg.fill((18, 16, 14, 200))
        surface.blit(bg, (mx, my))
        pygame.draw.rect(surface, (54, 48, 44), (mx, my, mw, mh), 1, border_radius=6)

        self.track.draw_minimap(surface, mx, my, mw, mh, car_x, car_y)
        pygame.draw.rect(surface, (54, 48, 44), (mx, my, mw, mh), 1, border_radius=6)

    # ── tile surface alert (bottom strip) ────────────────────────────────────

    def _draw_tile_alert(self, surface, tile_def):
        if not tile_def.hazard and tile_def.speed_multiplier == 1.0:
            return

        if tile_def.speed_multiplier > 1.0:
            msg = "BOOST!"
            col = (255, 215, 0, 130)
            txt_col = (255, 240, 100)
        elif not tile_def.drivable:
            return
        elif tile_def.damage_per_sec > 0:
            msg = f"{tile_def.name.upper()}  —  {tile_def.description[:38]}"
            col = (180, 20, 20, 110)
            txt_col = (255, 180, 180)
        elif tile_def.friction < 0.3:
            msg = f"SLIPPERY {tile_def.name.upper()}!"
            col = (30, 80, 160, 100)
            txt_col = (150, 200, 255)
        else:
            return

        sw = self.SW
        strip = pygame.Surface((sw, 32), pygame.SRCALPHA)
        strip.fill(col)
        surface.blit(strip, (0, self.SH - self.MM_H - self.MM_PAD - 42))
        txt = self.fonts["small"].render(msg, True, txt_col)
        surface.blit(txt, txt.get_rect(
            centerx=sw//2, y=self.SH - self.MM_H - self.MM_PAD - 36))
