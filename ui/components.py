import pygame
from ui.colors import *


def draw_rounded_rect(surface, color, rect, radius=12, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surface, border_color, rect, border, border_radius=radius)


def draw_stat_bar(surface, label, value, max_value=100, x=0, y=0, w=200, h=22,
                  font=None, highlight=False):
    bar_color = STAT_BAR_HI if highlight else STAT_BAR_FG
    if font:
        lbl = font.render(label, True, TEXT_SECONDARY)
        surface.blit(lbl, (x, y - 18))
    pygame.draw.rect(surface, STAT_BAR_BG, (x, y, w, h), border_radius=6)
    fill_w = int(w * (value / max_value))
    if fill_w > 0:
        pygame.draw.rect(surface, bar_color, (x, y, fill_w, h), border_radius=6)
    pygame.draw.rect(surface, WHITE, (x, y, w, h), 1, border_radius=6)


class Button:
    def __init__(self, rect, text, font, color=BTN_NORMAL, hover_color=BTN_HOVER,
                 text_color=TEXT_PRIMARY, radius=10, icon=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.radius = radius
        self.icon = icon
        self._hovered = False
        self.enabled = True

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface):
        color = self.hover_color if self._hovered else self.color
        if not self.enabled:
            color = BTN_NORMAL
        draw_rounded_rect(surface, color, self.rect, self.radius)
        text_surf = self.font.render(self.text, True,
                                     self.text_color if self.enabled else TEXT_DISABLED)
        tr = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, tr)


class ArrowButton:
    def __init__(self, cx, cy, size, direction):
        self.cx = cx
        self.cy = cy
        self.size = size
        self.direction = direction  # "left" or "right"
        self.rect = pygame.Rect(cx - size, cy - size, size * 2, size * 2)
        self._hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface):
        s = self.size
        color = ACCENT_GOLD if self._hovered else ACCENT_RED
        if self.direction == "left":
            pts = [(self.cx + s // 2, self.cy - s),
                   (self.cx - s // 2, self.cy),
                   (self.cx + s // 2, self.cy + s)]
        else:
            pts = [(self.cx - s // 2, self.cy - s),
                   (self.cx + s // 2, self.cy),
                   (self.cx - s // 2, self.cy + s)]
        pygame.draw.polygon(surface, color, pts)


class CoinDisplay:
    def __init__(self, x, y, font_large, font_small):
        self.x = x
        self.y = y
        self.font_large = font_large
        self.font_small = font_small

    def draw(self, surface, coins):
        radius = 16
        coin_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(coin_surf, COIN_GOLD, (radius, radius), radius)
        pygame.draw.circle(coin_surf, (200, 160, 0), (radius, radius), radius, 2)
        c_lbl = self.font_small.render("$", True, BLACK)
        coin_surf.blit(c_lbl, c_lbl.get_rect(center=(radius, radius)))
        surface.blit(coin_surf, (self.x, self.y - radius))
        txt = self.font_large.render(f"{coins:,}", True, COIN_GOLD)
        surface.blit(txt, (self.x + radius * 2 + 8, self.y - txt.get_height() // 2))


class ToggleSwitch:
    def __init__(self, x, y, w=56, h=28):
        self.rect = pygame.Rect(x, y, w, h)
        self.w = w
        self.h = h
        self._hovered = False

    def handle_event(self, event, value):
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return not value
        return value

    def draw(self, surface, value):
        track_color = ACCENT_RED if value else STAT_BAR_BG
        pygame.draw.rect(surface, track_color, self.rect, border_radius=self.h // 2)
        knob_x = self.rect.x + (self.w - self.h + 4) if value else self.rect.x + 4
        pygame.draw.circle(surface, WHITE, (knob_x + (self.h - 8) // 2,
                                            self.rect.centery), self.h // 2 - 4)


SCREEN_LABELS = {
    "lobby":    "LOBBY",
    "garage":   "GARAGE",
    "settings": "SETTINGS",
    "race":     "RACE",
}

NAV_H = 68  # height reserved for the nav bar


class NavBar:
    """Fixed top bar: back button (left) · breadcrumb (center) · coins (right)."""

    def __init__(self, screen_w, font_btn, font_small, font_coin):
        self.screen_w  = screen_w
        self.font_btn  = font_btn
        self.font_small = font_small
        self.font_coin = font_coin
        self._back_hovered = False
        self._back_rect    = pygame.Rect(0, 0, 0, 0)

    # call this every frame before draw() so it matches current history
    def handle_event(self, event, history):
        """Returns 'back' if back button clicked, else None."""
        if len(history) <= 1:
            return None
        if event.type == pygame.MOUSEMOTION:
            self._back_hovered = self._back_rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._back_rect.collidepoint(event.pos):
                return "back"
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if len(history) > 1:
                return "back"
        return None

    def draw(self, surface, history, coins):
        sw = self.screen_w

        # bar background
        bar = pygame.Rect(0, 0, sw, NAV_H)
        pygame.draw.rect(surface, PANEL_BG, bar)
        pygame.draw.line(surface, ACCENT_RED, (0, NAV_H - 1), (sw, NAV_H - 1), 2)

        # ── back button (left) ──────────────────────────────────────────
        if len(history) > 1:
            dest_label = SCREEN_LABELS.get(history[-2], history[-2])
            btn_text   = f"  ←  {dest_label}  "
            btn_surf   = self.font_btn.render(btn_text, True, TEXT_PRIMARY)
            btn_w      = btn_surf.get_width() + 12
            btn_h      = 38
            btn_x, btn_y = 14, (NAV_H - btn_h) // 2
            self._back_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            color = BTN_HOVER if self._back_hovered else BTN_NORMAL
            pygame.draw.rect(surface, color, self._back_rect, border_radius=10)
            # left arrow accent stripe
            pygame.draw.rect(surface, ACCENT_RED,
                             pygame.Rect(btn_x, btn_y, 4, btn_h), border_radius=10)
            surface.blit(btn_surf, (btn_x + 6, btn_y + (btn_h - btn_surf.get_height()) // 2))
        else:
            self._back_rect = pygame.Rect(0, 0, 0, 0)

        # ── breadcrumb (center) ─────────────────────────────────────────
        crumb_parts = [SCREEN_LABELS.get(s, s) for s in history]
        crumb_str   = "  ›  ".join(crumb_parts)
        crumb_surf  = self.font_small.render(crumb_str, True, TEXT_SECONDARY)
        # highlight the last (current) segment in white
        current_lbl  = crumb_parts[-1]
        cur_surf     = self.font_small.render(current_lbl, True, TEXT_PRIMARY)
        # draw full crumb then overwrite last word with white
        cx = sw // 2 - crumb_surf.get_width() // 2
        cy = (NAV_H - crumb_surf.get_height()) // 2
        surface.blit(crumb_surf, (cx, cy))
        # find x-offset of last segment inside crumb string and overdraw
        prefix     = crumb_str[: crumb_str.rfind(current_lbl)]
        prefix_w   = self.font_small.size(prefix)[0]
        surface.blit(cur_surf, (cx + prefix_w, cy))

        # ── coins (right) ───────────────────────────────────────────────
        r = 14
        coin_x = sw - 180
        coin_y = NAV_H // 2
        coin_circle = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(coin_circle, COIN_GOLD, (r, r), r)
        pygame.draw.circle(coin_circle, (200, 160, 0), (r, r), r, 2)
        dol = self.font_small.render("$", True, BLACK)
        coin_circle.blit(dol, dol.get_rect(center=(r, r)))
        surface.blit(coin_circle, (coin_x, coin_y - r))
        coins_surf = self.font_coin.render(f"{coins:,}", True, COIN_GOLD)
        surface.blit(coins_surf, (coin_x + r * 2 + 6,
                                   coin_y - coins_surf.get_height() // 2))


class SliderWidget:
    def __init__(self, x, y, w=200, h=20, min_val=0, max_val=100):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.dragging = False

    def handle_event(self, event, value):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
        if event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        if event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = max(0, min(event.pos[0] - self.rect.x, self.rect.w))
            value = self.min_val + int((rel_x / self.rect.w) * (self.max_val - self.min_val))
        return value

    def draw(self, surface, value):
        pygame.draw.rect(surface, STAT_BAR_BG, self.rect, border_radius=8)
        ratio = (value - self.min_val) / (self.max_val - self.min_val)
        fill_w = int(self.rect.w * ratio)
        if fill_w:
            pygame.draw.rect(surface, ACCENT_RED,
                             (self.rect.x, self.rect.y, fill_w, self.rect.h), border_radius=8)
        knob_x = self.rect.x + fill_w
        pygame.draw.circle(surface, WHITE, (knob_x, self.rect.centery), self.rect.h // 2 + 2)
        pygame.draw.circle(surface, ACCENT_RED, (knob_x, self.rect.centery), self.rect.h // 2)
