"""Race HUD: speedometer arc, lap counter, timer, minimap, health bar,
race info panel, gear/RPM display, checkpoint status strip."""

import pygame
import math

_RED    = (210,  40,  40)
_GOLD   = (215, 180,  30)
_WHITE  = (235, 235, 235)
_GREY   = (130, 120, 110)
_GREEN  = ( 60, 200,  80)
_ORANGE = (230, 140,  30)
_ICE    = (140, 200, 230)
_BOOST  = (255, 215,   0)
_DARK   = ( 18,  16,  14)
_PANEL  = ( 22,  20,  18, 195)
_BORDER = ( 54,  48,  44)

_SA_GREEN = (  0, 150,  60)
_SA_GOLD  = (240, 175,   0)
_SA_RED   = (210,  50,  45)
_SA_BLUE  = ( 20,  50, 140)

# gear bands: speed fraction → gear
_GEAR_BANDS = [0.12, 0.24, 0.38, 0.55, 0.72, 0.88, 1.0]


def _fmt(t):
    m  = int(t // 60)
    s  = int(t % 60)
    ms = int((t % 1) * 100)
    return f"{m:01d}:{s:02d}.{ms:02d}"


class HUD:
    SPEEDO_R  = 72
    SPEEDO_CX = 108

    MM_W, MM_H = 210, 165
    MM_PAD     = 14

    def __init__(self, SW: int, SH: int, fonts: dict, track):
        self.SW    = SW
        self.SH    = SH
        self.fonts = fonts
        self.track = track

        self.SPEEDO_CY = SH - self.SPEEDO_R - 22

        self.mm_x = SW - self.MM_W - self.MM_PAD
        self.mm_y = SH - self.MM_H - self.MM_PAD

    def draw(self, surface, physics, lap, total_laps, lap_time, best_lap,
             total_time, tile_def, health, next_cp=0, total_cp=0):
        self._draw_speedometer(surface, physics.kmh, physics.max_speed * 0.32, tile_def,
                               physics.speed, physics.max_speed, physics.rpm)
        self._draw_health_bar(surface, health)
        self._draw_race_info_panel(surface, lap, total_laps, lap_time, best_lap)
        self._draw_player_info(surface)
        self._draw_minimap(surface, physics.x, physics.y)
        self._draw_checkpoint_status(surface, next_cp, total_cp)
        if tile_def:
            self._draw_tile_alert(surface, tile_def)

    # ── speedometer + gear/RPM ────────────────────────────────────────────────

    def _draw_speedometer(self, surface, kmh, max_kmh, tile_def, speed, max_speed, rpm=5000):
        cx, cy = self.SPEEDO_CX, self.SPEEDO_CY
        R      = self.SPEEDO_R

        # panel background (slightly wider for gear/RPM alongside)
        panel_w = (R + 14) * 2 + 56
        panel_h = (R + 14) * 2 + 14
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill(_PANEL)
        surface.blit(bg, (cx - R - 14, cy - R - 14))

        # arc
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

        if tile_def and tile_def.speed_multiplier > 1.0:
            pygame.draw.circle(surface, _BOOST, (cx, cy), R, 3)

        # KMH number
        kmh_s = self.fonts["title"].render(f"{int(kmh)}", True, _WHITE)
        surface.blit(kmh_s, kmh_s.get_rect(center=(cx, cy - 4)))

        lbl = self.fonts["small"].render("KM/H", True, _GREY)
        surface.blit(lbl, lbl.get_rect(center=(cx, cy + R - 18)))

        for tick in range(9):
            ang = math.radians(start_ang + sweep * tick / 8)
            x1  = cx + math.cos(ang) * (R - 14)
            y1  = cy - math.sin(ang) * (R - 14)
            x2  = cx + math.cos(ang) * (R - 4)
            y2  = cy - math.sin(ang) * (R - 4)
            col = _WHITE if tick % 2 == 0 else (78, 72, 68)
            pygame.draw.line(surface, col, (int(x1), int(y1)), (int(x2), int(y2)), 2)

        # gear + RPM column to the right of arc
        gr_x = cx + R + 6
        gr_y = cy - R

        # gear indicator
        spd_ratio = abs(speed) / max(max_speed, 1)
        gear = 1
        for i, band in enumerate(_GEAR_BANDS):
            if spd_ratio <= band:
                gear = i + 1
                break
        rpm_ratio = max(0.0, min(1.0, (rpm - 900) / 7100.0))

        gear_surf = self.fonts["title"].render(str(gear), True, _GOLD)
        surface.blit(gear_surf, (gr_x + 12, gr_y + 4))
        glbl = self.fonts["small"].render("GEAR", True, _GREY)
        surface.blit(glbl, (gr_x + 4, gr_y + 44))

        # RPM bar (vertical)
        bar_x, bar_y = gr_x + 6, gr_y + 66
        bar_h = R * 2 - 70
        bar_w = 12
        pygame.draw.rect(surface, (45, 40, 38), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_h = int(bar_h * rpm_ratio)
        rpm_r = int(min(255, rpm_ratio * 510))
        rpm_g = int(min(255, (1-rpm_ratio) * 510))
        if fill_h > 0:
            pygame.draw.rect(surface, (rpm_r, rpm_g, 20),
                             (bar_x, bar_y + bar_h - fill_h, bar_w, fill_h), border_radius=3)
        rpm_val = int(1200 + rpm_ratio * 6800)
        rpm_s   = self.fonts["small"].render(f"{rpm_val}", True, _GREY)
        surface.blit(rpm_s, (bar_x - 4, bar_y + bar_h + 2))
        rpm_lbl = self.fonts["small"].render("RPM", True, _GREY)
        surface.blit(rpm_lbl, (bar_x - 2, bar_y + bar_h + 16))

    # ── health bar ────────────────────────────────────────────────────────────

    def _draw_health_bar(self, surface, health):
        cx, cy = self.SPEEDO_CX, self.SPEEDO_CY
        R      = self.SPEEDO_R
        bx     = cx - R - 14
        by     = cy + R + 2
        bw     = (R + 14) * 2 + 56
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
        surface.blit(hp_s, hp_s.get_rect(centerx=cx + 28, y=by + bh + 4))

    # ── race info panel (top-right) ───────────────────────────────────────────

    def _draw_race_info_panel(self, surface, lap, total_laps, lap_time, best_lap):
        w, h = 230, 108
        x    = self.SW - w - 10
        y    = 8

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill(_PANEL)
        surface.blit(bg, (x, y))
        pygame.draw.rect(surface, _BORDER, (x, y, w, h), 1, border_radius=8)

        # header
        hdr = self.fonts["small"].render("RACE INFO", True, _GREY)
        surface.blit(hdr, (x + 8, y + 6))
        pygame.draw.line(surface, _BORDER, (x+8, y+22), (x+w-8, y+22), 1)

        # rows: icon-char + label + value
        rows = [
            ("L", "LAP",  f"{min(lap, total_laps)} / {total_laps}", _GOLD),
            ("T", "TIME", _fmt(lap_time),                           _WHITE),
            ("B", "BEST", _fmt(best_lap) if best_lap < 999 else "--", _GREEN),
        ]
        for i, (icon_char, label, value, col) in enumerate(rows):
            ry = y + 30 + i * 26
            # icon circle
            pygame.draw.circle(surface, _BORDER, (x+18, ry+9), 9)
            ic = self.fonts["small"].render(icon_char, True, col)
            surface.blit(ic, ic.get_rect(center=(x+18, ry+9)))
            # label
            lbl_s = self.fonts["small"].render(label, True, _GREY)
            surface.blit(lbl_s, (x+32, ry+2))
            # value (right-aligned)
            val_s = self.fonts["small"].render(value, True, col)
            surface.blit(val_s, val_s.get_rect(right=x+w-8, y=ry+2))

    # ── player info bar (top-left) ────────────────────────────────────────────

    def _draw_player_info(self, surface):
        w, h = 230, 48
        x, y = 10, 8

        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill(_PANEL)
        surface.blit(bg, (x, y))
        pygame.draw.rect(surface, _BORDER, (x, y, w, h), 1, border_radius=8)

        # SA flag strip
        fw, fh = 38, 24
        fx, fy = x + 10, y + 12
        pygame.draw.rect(surface, _SA_RED,          (fx,           fy, fw, fh//3))
        pygame.draw.rect(surface, (255,255,255),    (fx,    fy+fh//3, fw, fh//3))
        pygame.draw.rect(surface, _SA_BLUE,         (fx, fy+2*fh//3, fw, fh//3))
        pygame.draw.polygon(surface, _SA_GREEN,
            [(fx, fy), (fx+fw//3, fy+fh//2), (fx, fy+fh)])
        pygame.draw.rect(surface, (80,70,60), (fx, fy, fw, fh), 1)

        # position label
        pos_s = self.fonts["coin"].render("P1", True, _GOLD)
        surface.blit(pos_s, pos_s.get_rect(centerx=fx+fw+22, centery=y+h//2))

        # "MZANSI RUSH" text
        nm_s = self.fonts["small"].render("MZANSI RUSH", True, _WHITE)
        surface.blit(nm_s, nm_s.get_rect(left=fx+fw+50, centery=y+h//2))

    # ── checkpoint status strip (bottom-centre) ───────────────────────────────

    def _draw_checkpoint_status(self, surface, next_cp, total_cp):
        if total_cp < 2:
            return
        icon_r  = 11
        spacing = 28
        total_w = total_cp * spacing
        bx      = (self.SW - total_w) // 2
        by      = self.SH - self.MM_H - self.MM_PAD - 38

        bg = pygame.Surface((total_w + 16, 30), pygame.SRCALPHA)
        bg.fill(_PANEL)
        surface.blit(bg, (bx - 8, by - 4))

        for i in range(total_cp):
            cx2 = bx + i * spacing + spacing // 2
            cy2 = by + 11
            if i < next_cp:
                # passed – green tick arrow
                pygame.draw.circle(surface, _GREEN, (cx2, cy2), icon_r, 2)
                pts = [(cx2-5, cy2),(cx2-2, cy2+5),(cx2+6, cy2-5)]
                pygame.draw.lines(surface, _GREEN, False, pts, 2)
            elif i == next_cp:
                # current – gold arrow
                pygame.draw.circle(surface, _GOLD, (cx2, cy2), icon_r, 2)
                pygame.draw.polygon(surface, _GOLD,
                    [(cx2-4, cy2-6),(cx2+6, cy2),(cx2-4, cy2+6),(cx2-1, cy2)])
            else:
                # future – grey X
                pygame.draw.circle(surface, _GREY, (cx2, cy2), icon_r, 1)
                d = 5
                pygame.draw.line(surface, _GREY, (cx2-d, cy2-d), (cx2+d, cy2+d), 2)
                pygame.draw.line(surface, _GREY, (cx2+d, cy2-d), (cx2-d, cy2+d), 2)

    # ── minimap ───────────────────────────────────────────────────────────────

    def _draw_minimap(self, surface, car_x, car_y):
        mx, my = self.mm_x, self.mm_y
        mw, mh = self.MM_W, self.MM_H

        bg = pygame.Surface((mw, mh), pygame.SRCALPHA)
        bg.fill((18, 16, 14, 200))
        surface.blit(bg, (mx, my))
        pygame.draw.rect(surface, _BORDER, (mx, my, mw, mh), 1, border_radius=6)

        self.track.draw_minimap(surface, mx, my, mw, mh, car_x, car_y)
        pygame.draw.rect(surface, _BORDER, (mx, my, mw, mh), 1, border_radius=6)

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
