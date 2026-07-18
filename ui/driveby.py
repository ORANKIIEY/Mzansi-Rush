import pygame
import random
from ui.colors import ACCENT_GOLD, ACCENT_RED


class DriveByAnimation:
    """A car that races across the screen behind the menu."""

    CAR_W = 380
    CAR_H = 160
    SPEED = 11          # px per frame
    Y_POS_RATIO = 0.68  # vertical position as fraction of screen height

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.car_x = -self.CAR_W - 40
        self.car_y = int(screen_h * self.Y_POS_RATIO)
        self.color = (220, 60, 60)
        self.active = False
        self._sparks = []

    def trigger(self, color):
        self.color = color
        self.car_x = -self.CAR_W - 40
        self.active = True
        self._sparks = []

    def update(self):
        if not self.active:
            return
        self.car_x += self.SPEED
        # spawn random spark/particle near rear wheel
        if random.random() < 0.4:
            wx = self.car_x + 60
            wy = self.car_y + self.CAR_H - 18
            self._sparks.append({
                "x": wx, "y": wy,
                "vx": random.uniform(-3, -1),
                "vy": random.uniform(-2, 1),
                "life": random.randint(8, 18),
                "color": random.choice([ACCENT_GOLD, ACCENT_RED, (255, 255, 200)]),
            })
        # update sparks
        for s in self._sparks:
            s["x"] += s["vx"]
            s["y"] += s["vy"]
            s["life"] -= 1
        self._sparks = [s for s in self._sparks if s["life"] > 0]

        if self.car_x > self.screen_w + 40:
            self.active = False

    def draw(self, surface):
        if not self.active:
            return

        cx = self.car_x + self.CAR_W // 2
        cy = self.car_y

        # speed lines (horizontal streaks behind car)
        streak_surf = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        for i in range(18):
            sy = cy - 40 + i * 16
            length = random.randint(60, 200)
            alpha = random.randint(20, 60)
            color_a = (*self.color, alpha)
            x_end = self.car_x + random.randint(-30, 20)
            pygame.draw.line(streak_surf, color_a,
                             (max(0, x_end - length), sy), (max(0, x_end), sy), 2)
        surface.blit(streak_surf, (0, 0))

        # shadow
        shadow = pygame.Surface((self.CAR_W, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        surface.blit(shadow, (self.car_x + 20, cy + self.CAR_H - 14))

        # --- body ---
        x = self.car_x
        y = cy
        w, h = self.CAR_W, self.CAR_H

        body = pygame.Rect(x + 30, y + 48, w - 60, h - 52)
        roof_pts = [
            (x + 90,  y + 48),
            (x + 140, y + 8),
            (x + w - 110, y + 8),
            (x + w - 60, y + 48),
        ]

        pygame.draw.rect(surface, self.color, body, border_radius=12)
        pygame.draw.polygon(surface, self.color, roof_pts)

        highlight = tuple(min(255, c + 70) for c in self.color)
        pygame.draw.rect(surface, highlight, body, 2, border_radius=12)
        pygame.draw.polygon(surface, highlight, roof_pts, 2)

        # windshield
        wind_pts = [
            (roof_pts[0][0] + 12, roof_pts[0][1] + 6),
            (roof_pts[1][0] + 8,  roof_pts[1][1] + 6),
            (roof_pts[2][0] - 8,  roof_pts[2][1] + 6),
            (roof_pts[3][0] - 12, roof_pts[3][1] + 6),
        ]
        wind_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(wind_surf, (100, 190, 255, 140), [
            (p[0] - x, p[1] - y) for p in wind_pts])
        surface.blit(wind_surf, (x, y))

        # headlights
        pygame.draw.ellipse(surface, (255, 240, 150),
                            (x + w - 56, y + 56, 22, 14))
        pygame.draw.ellipse(surface, (255, 255, 200, 80),
                            (x + w - 40, y + 42, 40, 38))

        # wheels
        for wx, wy in [(x + 76, y + h - 20), (x + w - 76, y + h - 20)]:
            pygame.draw.circle(surface, (25, 25, 25), (wx, wy), 32)
            pygame.draw.circle(surface, (55, 55, 65), (wx, wy), 22)
            pygame.draw.circle(surface, (120, 120, 130), (wx, wy), 10)
            # spin effect lines
            for angle_step in range(0, 360, 60):
                import math
                a = math.radians(angle_step + (pygame.time.get_ticks() // 20) % 360)
                lx = wx + int(math.cos(a) * 18)
                ly = wy + int(math.sin(a) * 18)
                pygame.draw.line(surface, (80, 80, 90), (wx, wy), (lx, ly), 2)

        # sparks / particles
        for s in self._sparks:
            alpha = int(255 * s["life"] / 18)
            r = pygame.Rect(int(s["x"]) - 2, int(s["y"]) - 2, 4, 4)
            spark_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            spark_surf.fill((*s["color"], alpha))
            surface.blit(spark_surf, r)
