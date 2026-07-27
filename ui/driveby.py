import pygame
import random
from ui.colors import ACCENT_GOLD, ACCENT_RED

_sprite_cache: dict = {}


def _load_rotated_sprite(path, target_h):
    """Load sprite, rotate 90° so top-down car faces right, scale to target height."""
    key = (path, target_h)
    if key in _sprite_cache:
        return _sprite_cache[key]
    raw = pygame.image.load(path)
    try:
        img = raw.convert_alpha()
    except pygame.error:
        img = raw
    # top-down cars face up (portrait) → rotate -90° so they face right (landscape)
    img = pygame.transform.rotate(img, -90)
    iw, ih = img.get_size()
    scale = target_h / ih
    img = pygame.transform.smoothscale(img, (int(iw * scale), target_h))
    _sprite_cache[key] = img
    return img


class DriveByAnimation:
    """A car that races across the screen behind the menu."""

    CAR_H  = 110         # sprite height in px
    SPEED  = 11          # px per frame
    Y_POS_RATIO = 0.70   # vertical position as fraction of screen height

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.car_y    = int(screen_h * self.Y_POS_RATIO)
        self.color    = (220, 60, 60)
        self.image_path = None
        self._sprite  = None
        self._car_w   = 260         # updated when sprite loads
        self.car_x    = -self._car_w - 40
        self.active   = False
        self._sparks  = []

    def trigger(self, color, image_path=None):
        self.color      = color
        self.image_path = image_path
        self._sprite    = None          # will load on first draw
        self.car_x      = -(self._car_w + 40)
        self.active     = True
        self._sparks    = []

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

        # lazy-load sprite
        import os
        if self._sprite is None and self.image_path and os.path.exists(self.image_path):
            self._sprite = _load_rotated_sprite(self.image_path, self.CAR_H)
            self._car_w  = self._sprite.get_width()

        car_w = self._car_w
        cy    = self.car_y
        cx    = self.car_x + car_w // 2

        # speed lines behind the car
        streak_surf = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
        for i in range(18):
            sy     = cy - 30 + i * 14
            length = random.randint(60, 200)
            alpha  = random.randint(20, 60)
            x_end  = self.car_x + random.randint(-30, 20)
            pygame.draw.line(streak_surf, (*self.color, alpha),
                             (max(0, x_end - length), sy), (max(0, x_end), sy), 2)
        surface.blit(streak_surf, (0, 0))

        # drop shadow
        shadow = pygame.Surface((car_w, 20), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 90), shadow.get_rect())
        surface.blit(shadow, (self.car_x, cy + self.CAR_H - 10))

        if self._sprite:
            surface.blit(self._sprite, (self.car_x, cy - self.CAR_H // 2))
        else:
            # fallback geometric car
            x, y, w, h = self.car_x, cy, car_w, self.CAR_H
            body = pygame.Rect(x + 20, y + 30, w - 40, h - 40)
            pygame.draw.rect(surface, self.color, body, border_radius=12)
            highlight = tuple(min(255, c + 70) for c in self.color)
            pygame.draw.rect(surface, highlight, body, 2, border_radius=12)

        # sparks / particles
        for s in self._sparks:
            alpha = int(255 * s["life"] / 18)
            r = pygame.Rect(int(s["x"]) - 2, int(s["y"]) - 2, 4, 4)
            spark_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            spark_surf.fill((*s["color"], alpha))
            surface.blit(spark_surf, r)
