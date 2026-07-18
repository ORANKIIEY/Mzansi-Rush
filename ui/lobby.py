import pygame
from ui.colors import *
from ui.components import draw_rounded_rect, Button, CoinDisplay
from ui.driveby import DriveByAnimation


class LobbyScreen:
    """Main menu with navigation to Garage, Settings, and Race."""

    def __init__(self, screen_w, screen_h, fonts, game_data):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.fonts = fonts
        self.gd = game_data

        cx = screen_w // 2
        btn_w, btn_h = 280, 64
        gap = 24
        start_y = screen_h // 2 - 60

        f = fonts["btn"]
        self.btn_garage   = Button((cx - btn_w // 2, start_y,                    btn_w, btn_h),
                                   "GARAGE",   f, BTN_NORMAL, BTN_HOVER)
        self.btn_settings = Button((cx - btn_w // 2, start_y + btn_h + gap,      btn_w, btn_h),
                                   "SETTINGS", f, BTN_NORMAL, BTN_HOVER)
        self.btn_race     = Button((cx - btn_w // 2, start_y + (btn_h + gap) * 2, btn_w, btn_h),
                                   "RACE  ▶",  f, ACCENT_RED, (255, 80, 80))
        self.btn_quit     = Button((cx - btn_w // 2, start_y + (btn_h + gap) * 3, btn_w, btn_h),
                                   "QUIT",     f, (60, 30, 30), (100, 40, 40))

        self.coin_display = CoinDisplay(screen_w - 260, 22, fonts["coin"], fonts["small"])

        self.driveby = DriveByAnimation(screen_w, screen_h)
        self._trigger_driveby()

        self._last_selected = game_data["player"]["selected_car"]

    def _trigger_driveby(self):
        sel_id = self.gd["player"]["selected_car"]
        cars = self.gd["cars"]
        car = next((c for c in cars if c["id"] == sel_id), None)
        color = tuple(car["color"]) if car else (220, 60, 60)
        self.driveby.trigger(color)

    def on_enter(self):
        """Call this every time the lobby becomes the active screen."""
        sel = self.gd["player"]["selected_car"]
        if sel != self._last_selected or not self.driveby.active:
            self._last_selected = sel
            self._trigger_driveby()

    def update(self):
        self.driveby.update()

    def handle_event(self, event):
        if self.btn_garage.handle_event(event):
            return "garage"
        if self.btn_settings.handle_event(event):
            return "settings"
        if self.btn_race.handle_event(event):
            return "race"
        if self.btn_quit.handle_event(event):
            return "quit"
        return None

    def draw(self, surface):
        sw, sh = self.screen_w, self.screen_h
        player = self.gd["player"]

        # animated car behind everything
        self.driveby.draw(surface)

        # dark gradient strip so text stays readable over the car
        strip = pygame.Surface((sw, sh), pygame.SRCALPHA)
        strip.fill((10, 10, 20, 140))
        surface.blit(strip, (0, 0))

        # game title
        title = self.fonts["big_title"].render("MZANSI RUSH", True, ACCENT_RED)
        surface.blit(title, title.get_rect(centerx=sw // 2, y=55))

        sub = self.fonts["heading"].render("Street Racing", True, ACCENT_GOLD)
        surface.blit(sub, sub.get_rect(centerx=sw // 2, y=55 + title.get_height() + 4))

        # player info (top-left)
        self._draw_player_card(surface, player)

        # coins (top-right)
        self.coin_display.draw(surface, player["coins"])

        # nav buttons
        self.btn_garage.draw(surface)
        self.btn_settings.draw(surface)
        self.btn_race.draw(surface)
        self.btn_quit.draw(surface)

        # selected car hint
        sel_id = player["selected_car"]
        cars = self.gd["cars"]
        sel_car = next((c for c in cars if c["id"] == sel_id), None)
        if sel_car:
            hint = self.fonts["small"].render(
                f"Selected:  {sel_car['name']}", True, TEXT_SECONDARY)
            surface.blit(hint, hint.get_rect(centerx=sw // 2, y=sh - 36))

    def _draw_player_card(self, surface, player):
        card = pygame.Rect(20, 14, 260, 56)
        draw_rounded_rect(surface, PANEL_BG, card, 12)

        name_surf = self.fonts["body"].render(player["name"], True, TEXT_PRIMARY)
        surface.blit(name_surf, (38, 18))

        lvl_txt = self.fonts["small"].render(
            f"Level {player['level']}  —  "
            f"{player['level_xp']} / {player['level_xp_max']} XP", True, TEXT_SECONDARY)
        surface.blit(lvl_txt, (38, 38))

        bar_w = card.w - 48
        xp_ratio = player["level_xp"] / player["level_xp_max"]
        pygame.draw.rect(surface, STAT_BAR_BG, (38, 56, bar_w, 8), border_radius=4)
        pygame.draw.rect(surface, ACCENT_GOLD,  (38, 56, int(bar_w * xp_ratio), 8),
                         border_radius=4)
