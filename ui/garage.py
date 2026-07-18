import pygame
from ui.colors import *
from ui.components import (draw_rounded_rect, draw_stat_bar, ArrowButton,
                            Button, NAV_H)


class CarPreview:
    """Draws a placeholder car shape using the car's color."""

    def __init__(self, cx, cy, w=320, h=140):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h

    def draw(self, surface, color):
        x = self.cx - self.w // 2
        y = self.cy - self.h // 2

        body_rect = pygame.Rect(x + 30, y + 40, self.w - 60, self.h - 50)
        roof_pts = [
            (x + 80,  y + 40),
            (x + 120, y + 5),
            (x + self.w - 100, y + 5),
            (x + self.w - 60, y + 40),
        ]

        shadow = pygame.Surface((self.w, 20), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
        surface.blit(shadow, (x, self.cy + self.h // 2 - 15))

        pygame.draw.rect(surface, color, body_rect, border_radius=10)
        pygame.draw.polygon(surface, color, roof_pts)
        outline_color = tuple(min(255, c + 60) for c in color)
        pygame.draw.rect(surface, outline_color, body_rect, 2, border_radius=10)
        pygame.draw.polygon(surface, outline_color, roof_pts, 2)

        # windshield
        wind_pts = [(p[0] + 4, p[1] + 4) for p in roof_pts]
        wind_pts[0] = (roof_pts[0][0] + 10, roof_pts[0][1] + 5)
        wind_pts[3] = (roof_pts[3][0] - 10, roof_pts[3][1] + 5)
        pygame.draw.polygon(surface, (100, 180, 255, 180), wind_pts)

        # wheels
        for wx, wy in [(x + 65, y + self.h - 20), (x + self.w - 65, y + self.h - 20)]:
            pygame.draw.circle(surface, (30, 30, 30), (wx, wy), 28)
            pygame.draw.circle(surface, (70, 70, 70), (wx, wy), 18)
            pygame.draw.circle(surface, (130, 130, 130), (wx, wy), 8)


class GarageScreen:
    def __init__(self, screen_w, screen_h, fonts, game_data):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.fonts = fonts
        self.gd = game_data

        cars = self.gd["cars"]
        owned = self.gd["player"]["owned_cars"]
        sel_id = self.gd["player"]["selected_car"]
        self.car_index = next((i for i, c in enumerate(cars) if c["id"] == sel_id), 0)

        top = NAV_H + 16
        preview_cx = int(screen_w * 0.38)
        preview_cy = NAV_H + int((screen_h - NAV_H) * 0.48)
        self.preview = CarPreview(preview_cx, preview_cy)

        arr_y = preview_cy
        self.left_arrow  = ArrowButton(preview_cx - 190, arr_y, 28, "left")
        self.right_arrow = ArrowButton(preview_cx + 190, arr_y, 28, "right")

        btn_y = screen_h - 68
        btn_h = 46
        f = fonts["btn"]
        self.btn_upgrade = Button((60,  btn_y, 160, btn_h), "UPGRADE",  f, BTN_NORMAL, BTN_HOVER)
        self.btn_buy     = Button((240, btn_y, 160, btn_h), "BUY CAR",  f, ACCENT_RED, (255, 80, 80))
        self.btn_select  = Button((240, btn_y, 160, btn_h), "SELECT",   f, ACCENT_RED, (255, 80, 80))
        self.btn_race    = Button((screen_w - 180, btn_y, 140, btn_h), "RACE ▶",
                                  f, ACCENT_RED, (255, 80, 80))
        self._top = top

        self.message = ""
        self.message_timer = 0

    # ------------------------------------------------------------------ helpers
    def _current_car(self):
        return self.gd["cars"][self.car_index]

    def _is_owned(self):
        return self._current_car()["id"] in self.gd["player"]["owned_cars"]

    def _is_selected(self):
        return self._current_car()["id"] == self.gd["player"]["selected_car"]

    def _stat_with_upgrade(self, car, stat):
        base = car["stats"][stat]
        lvl  = car["upgrades"][stat]["level"]
        return min(100, base + (lvl - 1) * 5)

    # ------------------------------------------------------------------ events
    def handle_event(self, event):
        cars = self.gd["cars"]

        if self.left_arrow.handle_event(event):
            self.car_index = (self.car_index - 1) % len(cars)
        if self.right_arrow.handle_event(event):
            self.car_index = (self.car_index + 1) % len(cars)

        car = self._current_car()
        owned = self._is_owned()

        if self.btn_upgrade.handle_event(event) and owned:
            self._try_upgrade(car)

        if not owned:
            if self.btn_buy.handle_event(event):
                self._try_buy(car)
        else:
            if self.btn_select.handle_event(event):
                self.gd["player"]["selected_car"] = car["id"]
                self._flash(f"{car['name']} selected!")

        if self.btn_race.handle_event(event) and self._is_owned():
            self.gd["player"]["selected_car"] = car["id"]
            return "race"

        return None

    def _try_buy(self, car):
        price = car["price"]
        if self.gd["player"]["coins"] >= price:
            self.gd["player"]["coins"] -= price
            self.gd["player"]["owned_cars"].append(car["id"])
            self._flash(f"{car['name']} purchased!")
        else:
            self._flash("Not enough coins!")

    def _try_upgrade(self, car):
        upgradeable = False
        for stat, upg in car["upgrades"].items():
            if upg["level"] < upg["max_level"]:
                cost = upg["cost_per_level"]
                if self.gd["player"]["coins"] >= cost:
                    self.gd["player"]["coins"] -= cost
                    upg["level"] += 1
                    self._flash(f"{stat.capitalize()} upgraded!")
                    upgradeable = True
                    break
                else:
                    self._flash("Not enough coins!")
                    return
        if not upgradeable:
            self._flash("All upgrades maxed!")

    def _flash(self, msg):
        self.message = msg
        self.message_timer = 120

    # ------------------------------------------------------------------ draw
    def draw(self, surface):
        sw, sh = self.screen_w, self.screen_h
        car = self._current_car()
        owned = self._is_owned()
        top = self._top

        # car preview panel
        panel = pygame.Rect(40, top, int(sw * 0.62), sh - top - 80)
        draw_rounded_rect(surface, PANEL_BG, panel, 16)

        self.preview.draw(surface, car["color"])
        self.left_arrow.draw(surface)
        self.right_arrow.draw(surface)

        # car name
        name_surf = self.fonts["heading"].render(car["name"], True, TEXT_PRIMARY)
        surface.blit(name_surf, name_surf.get_rect(centerx=self.preview.cx, y=panel.y + 14))

        # locked overlay
        if not owned:
            lock_surf = pygame.Surface((panel.w, panel.h - 80), pygame.SRCALPHA)
            lock_surf.fill((0, 0, 0, 100))
            surface.blit(lock_surf, (panel.x, panel.y + 80))
            lock_txt = self.fonts["heading"].render(
                f"LOCKED  —  {car['price']:,} coins", True, ACCENT_GOLD)
            surface.blit(lock_txt, lock_txt.get_rect(center=(panel.centerx, panel.centery + 20)))

        # --- right panel: stats ---
        rp_x = int(sw * 0.65)
        rp = pygame.Rect(rp_x, top, sw - rp_x - 20, sh - top - 80)
        draw_rounded_rect(surface, PANEL_BG, rp, 16)

        car_name_r = self.fonts["heading"].render(car["name"], True, TEXT_PRIMARY)
        surface.blit(car_name_r, (rp.x + 20, rp.y + 18))

        stats_order = [("speed", "SPEED"), ("weight", "WEIGHT"),
                       ("grip", "GRIP"), ("turbo", "TURBO")]
        bar_x = rp.x + 20
        bar_w = rp.w - 40
        for i, (key, label) in enumerate(stats_order):
            val = self._stat_with_upgrade(car, key)
            by = rp.y + 80 + i * 80
            lbl = self.fonts["small"].render(
                f"{label}  (lvl {car['upgrades'][key]['level']}/{car['upgrades'][key]['max_level']})",
                True, TEXT_SECONDARY)
            surface.blit(lbl, (bar_x, by - 20))
            draw_stat_bar(surface, "", val, 100, bar_x, by, bar_w, 22,
                          highlight=(val > 75))

        # bottom buttons
        if owned:
            self.btn_upgrade.draw(surface)
            if not self._is_selected():
                self.btn_select.draw(surface)
            else:
                selected_lbl = self.fonts["btn"].render("✓ SELECTED", True, ACCENT_GOLD)
                surface.blit(selected_lbl, (240, self.screen_h - 56))
        else:
            self.btn_buy.draw(surface)

        self.btn_race.enabled = owned
        self.btn_race.draw(surface)

        # flash message
        if self.message_timer > 0:
            self.message_timer -= 1
            alpha = min(255, self.message_timer * 6)
            msg_s = self.fonts["heading"].render(self.message, True, ACCENT_GOLD)
            msg_s.set_alpha(alpha)
            surface.blit(msg_s, msg_s.get_rect(centerx=sw // 2, y=sh - 130))
