import pygame
from ui.colors import *
from ui.components import draw_rounded_rect, ToggleSwitch, SliderWidget, Button, NAV_H


DIFFICULTIES = ["easy", "medium", "hard"]


class SettingsScreen:
    def __init__(self, screen_w, screen_h, fonts, game_data):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.fonts = fonts
        self.gd = game_data
        self.settings = game_data["settings"]

        cx = screen_w // 2
        row_h = 72
        start_y = NAV_H + 80

        self.music_toggle   = ToggleSwitch(cx + 120, start_y + 0 * row_h + 10)
        self.sfx_toggle     = ToggleSwitch(cx + 120, start_y + 1 * row_h + 10)
        self.fullscreen_tog = ToggleSwitch(cx + 120, start_y + 2 * row_h + 10)
        self.fps_toggle     = ToggleSwitch(cx + 120, start_y + 3 * row_h + 10)

        sl_x = cx - 160
        self.music_slider = SliderWidget(sl_x, start_y + 0 * row_h + 16, 260)
        self.sfx_slider   = SliderWidget(sl_x, start_y + 1 * row_h + 16, 260)

        diff_y = start_y + 4 * row_h + 6
        f = fonts["btn"]
        btn_w = 110
        self.diff_buttons = [
            Button((cx - 180 + i * (btn_w + 12), diff_y, btn_w, 44), d.upper(), f)
            for i, d in enumerate(DIFFICULTIES)
        ]

        self._start_y = start_y

    def handle_event(self, event):
        s = self.settings
        s["music_enabled"] = self.music_toggle.handle_event(event, s["music_enabled"])
        s["sfx_enabled"]   = self.sfx_toggle.handle_event(event,  s["sfx_enabled"])
        s["fullscreen"]    = self.fullscreen_tog.handle_event(event, s["fullscreen"])
        s["show_fps"]      = self.fps_toggle.handle_event(event,   s["show_fps"])

        if s["music_enabled"]:
            s["music_volume"] = self.music_slider.handle_event(event, s["music_volume"])
        if s["sfx_enabled"]:
            s["sfx_volume"] = self.sfx_slider.handle_event(event, s["sfx_volume"])

        for i, btn in enumerate(self.diff_buttons):
            if btn.handle_event(event):
                s["difficulty"] = DIFFICULTIES[i]

        return None

    def draw(self, surface):
        sw, sh = self.screen_w, self.screen_h
        s = self.settings
        cx = sw // 2
        row_h = 72
        start_y = self._start_y

        panel = pygame.Rect(cx - 320, NAV_H + 14, 640, sh - NAV_H - 80)
        draw_rounded_rect(surface, PANEL_BG, panel, 16)

        labels  = ["Music", "SFX / Sound FX", "Fullscreen", "Show FPS"]
        toggles = [self.music_toggle, self.sfx_toggle, self.fullscreen_tog, self.fps_toggle]
        values  = [s["music_enabled"], s["sfx_enabled"], s["fullscreen"], s["show_fps"]]

        for i, (lbl, tog, val) in enumerate(zip(labels, toggles, values)):
            y = start_y + i * row_h
            lbl_surf = self.fonts["body"].render(lbl, True, TEXT_PRIMARY)
            surface.blit(lbl_surf, (cx - 260, y + 14))
            tog.draw(surface, val)

            if i == 0 and val:
                self.music_slider.draw(surface, s["music_volume"])
                vol_txt = self.fonts["small"].render(f"{s['music_volume']}%", True, TEXT_SECONDARY)
                surface.blit(vol_txt, (cx - 160 + 270, start_y + i * row_h + 12))
            elif i == 1 and val:
                self.sfx_slider.draw(surface, s["sfx_volume"])
                vol_txt = self.fonts["small"].render(f"{s['sfx_volume']}%", True, TEXT_SECONDARY)
                surface.blit(vol_txt, (cx - 160 + 270, start_y + i * row_h + 12))

        sep_y = start_y + 4 * row_h - 8
        pygame.draw.line(surface, CARD_BG, (panel.x + 20, sep_y), (panel.right - 20, sep_y), 2)

        diff_lbl = self.fonts["body"].render("Difficulty", True, TEXT_PRIMARY)
        surface.blit(diff_lbl, (cx - 260, start_y + 4 * row_h + 18))
        for i, (btn, diff) in enumerate(zip(self.diff_buttons, DIFFICULTIES)):
            btn.color = ACCENT_RED if s["difficulty"] == diff else BTN_NORMAL
            btn.draw(surface)
