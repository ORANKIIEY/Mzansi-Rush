import os
import pygame
from ui.colors import *
from ui.components import draw_rounded_rect, ArrowButton, Button, NAV_H

STATS_ORDER = [
    ("speed",  "SPEED"),
    ("weight", "WEIGHT"),
    ("grip",   "GRIP"),
    ("turbo",  "TURBO"),
]

_sprite_cache: dict = {}


TIER_COLORS = {
    "starter": (120, 120, 120),
    "economy": (80,  160, 80),
    "mid":     (60,  140, 220),
    "premium": (180, 100, 220),
    "exotic":  (255, 165, 0),
}


def _fmt_coins(n):
    if n >= 1_000_000:
        return f"R{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"R{n//1_000}K"
    return f"R{n}"


def _draw_fallback_car(surface, cx, cy, color, w=260, h=120):
    x, y = cx - w // 2, cy - h // 2
    body = pygame.Rect(x + 20, y + 30, w - 40, h - 40)
    pygame.draw.rect(surface, color, body, border_radius=10)
    outline = tuple(min(255, c + 60) for c in color)
    pygame.draw.rect(surface, outline, body, 2, border_radius=10)
    for wx, wy in [(x + 50, y + h - 16), (x + w - 50, y + h - 16)]:
        pygame.draw.circle(surface, (30, 30, 30), (wx, wy), 22)
        pygame.draw.circle(surface, (80, 80, 80), (wx, wy), 12)


def _load_sprite(path, fit_w, fit_h):
    """Load and scale a car sprite to fit within fit_w × fit_h, keep aspect ratio."""
    if path in _sprite_cache:
        return _sprite_cache[path]
    raw = pygame.image.load(path)
    try:
        img = raw.convert_alpha()
    except pygame.error:
        img = raw
    iw, ih = img.get_size()
    scale = min(fit_w / iw, fit_h / ih)
    img = pygame.transform.smoothscale(img, (int(iw * scale), int(ih * scale)))
    _sprite_cache[path] = img
    return img


class GarageScreen:
    ROW_H     = 68   # px per stat row
    ROW_START = 58   # y offset inside right panel where rows begin

    def __init__(self, screen_w, screen_h, fonts, game_data):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.fonts    = fonts
        self.gd       = game_data

        sel_id = self.gd["player"]["selected_car"]
        self.car_index = next(
            (i for i, c in enumerate(self.gd["cars"]) if c["id"] == sel_id), 0)

        self.selected_stat = None   # which stat row the player has clicked
        self._stat_rects   = {}     # populated each draw() call
        self._hovered_stat = None

        top = NAV_H + 16
        self._top = top

        preview_cx = int(screen_w * 0.38)
        preview_cy = NAV_H + int((screen_h - NAV_H) * 0.48)
        self._preview_cx  = preview_cx
        self._preview_cy  = preview_cy
        self._sprite_fit  = (240, 320)   # max sprite size inside the panel
        self.left_arrow   = ArrowButton(preview_cx - 200, preview_cy, 28, "left")
        self.right_arrow  = ArrowButton(preview_cx + 200, preview_cy, 28, "right")

        # right panel geometry (mirrored from draw so handle_event can use it)
        rp_x   = int(screen_w * 0.65)
        rp_w   = screen_w - rp_x - 20
        rp_h   = screen_h - top - 80
        self._rp = pygame.Rect(rp_x, top, rp_w, rp_h)

        btn_y = screen_h - 68
        btn_h = 46
        f = fonts["btn"]
        self.btn_buy     = Button((240, btn_y, 160, btn_h), "BUY CAR", f, ACCENT_RED, (255, 80, 80))
        self.btn_select  = Button((240, btn_y, 160, btn_h), "SELECT",  f, ACCENT_RED, (255, 80, 80))
        self.btn_race    = Button((screen_w - 180, btn_y, 140, btn_h), "RACE ▶",
                                  f, ACCENT_RED, (255, 80, 80))

        # upgrade confirm button lives in the preview zone; rect set in draw()
        self._upgrade_btn_rect = pygame.Rect(0, 0, 0, 0)
        self._upgrade_btn_hover = False

        self.message = ""
        self.message_timer = 0

    # ── helpers ────────────────────────────────────────────────────────────────

    def _current_car(self):
        return self.gd["cars"][self.car_index]

    def _is_owned(self):
        return self._current_car()["id"] in self.gd["player"]["owned_cars"]

    def _is_selected(self):
        return self._current_car()["id"] == self.gd["player"]["selected_car"]

    def _stat_value(self, car, stat):
        base = car["stats"][stat]
        lvl  = car["upgrades"][stat]["level"]
        return min(100, base + (lvl - 1) * 5)

    def _upgrade_info(self, car, stat):
        """Returns (can_upgrade, cost, current_level, max_level, is_maxed)."""
        upg     = car["upgrades"][stat]
        lvl     = upg["level"]
        max_lvl = upg["max_level"]
        cost    = upg["cost_per_level"]
        return lvl < max_lvl, cost, lvl, max_lvl, lvl >= max_lvl

    def _flash(self, msg):
        self.message       = msg
        self.message_timer = 120

    # ── events ─────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        cars = self.gd["cars"]

        # car carousel arrows
        if self.left_arrow.handle_event(event):
            self.car_index = (self.car_index - 1) % len(cars)
            self.selected_stat = None
        if self.right_arrow.handle_event(event):
            self.car_index = (self.car_index + 1) % len(cars)
            self.selected_stat = None

        car   = self._current_car()
        owned = self._is_owned()

        # stat row hover + click
        if event.type == pygame.MOUSEMOTION:
            self._hovered_stat = next(
                (k for k, r in self._stat_rects.items() if r.collidepoint(event.pos)), None)
            self._upgrade_btn_hover = self._upgrade_btn_rect.collidepoint(event.pos)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # click a stat row to select it
            for key, rect in self._stat_rects.items():
                if rect.collidepoint(event.pos):
                    self.selected_stat = key if self.selected_stat != key else None
                    break

            # click the upgrade confirm button
            if (self._upgrade_btn_rect.collidepoint(event.pos)
                    and owned and self.selected_stat):
                self._try_upgrade_stat(car, self.selected_stat)

        # buy / select / race
        if not owned:
            if self.btn_buy.handle_event(event):
                self._try_buy(car)
        else:
            if self.btn_select.handle_event(event):
                self.gd["player"]["selected_car"] = car["id"]
                self._flash(f"{car['name']} selected!")

        if self.btn_race.handle_event(event) and owned:
            self.gd["player"]["selected_car"] = car["id"]
            return "race"

        return None

    def _try_buy(self, car):
        if self.gd["player"]["coins"] >= car["price"]:
            self.gd["player"]["coins"] -= car["price"]
            self.gd["player"]["owned_cars"].append(car["id"])
            self._flash(f"{car['name']} purchased!")
        else:
            self._flash("Not enough coins!")

    def _try_upgrade_stat(self, car, stat):
        can, cost, lvl, max_lvl, is_maxed = self._upgrade_info(car, stat)
        if is_maxed:
            self._flash(f"{stat.capitalize()} is already maxed!")
            return
        if self.gd["player"]["coins"] < cost:
            self._flash(f"Need {cost - self.gd['player']['coins']:,} more coins!")
            return
        self.gd["player"]["coins"]      -= cost
        car["upgrades"][stat]["level"]  += 1
        self._flash(f"{stat.capitalize()} upgraded to level {lvl + 1}!")

    # ── draw ───────────────────────────────────────────────────────────────────

    def draw(self, surface):
        sw, sh = self.screen_w, self.screen_h
        car    = self._current_car()
        owned  = self._is_owned()
        top    = self._top

        # ── left panel: car preview ──────────────────────────────────────────
        panel = pygame.Rect(40, top, int(sw * 0.62), sh - top - 80)
        draw_rounded_rect(surface, PANEL_BG, panel, 16)

        # car sprite
        img_path = car.get("image", "")
        if img_path and os.path.exists(img_path):
            sprite = _load_sprite(img_path, *self._sprite_fit)
            sw_s, sh_s = sprite.get_size()
            blit_x = self._preview_cx - sw_s // 2
            blit_y = self._preview_cy - sh_s // 2
            # glow ring behind sprite when car is selected
            if self._is_selected():
                glow = pygame.Surface((sw_s + 30, sh_s + 30), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (*ACCENT_GOLD, 40), glow.get_rect())
                surface.blit(glow, (blit_x - 15, blit_y - 15))
            # drop shadow
            shadow = pygame.Surface((sw_s, 20), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 80), shadow.get_rect())
            surface.blit(shadow, (blit_x, blit_y + sh_s - 10))
            surface.blit(sprite, (blit_x, blit_y))
        else:
            # fallback geometric shape
            _draw_fallback_car(surface, self._preview_cx, self._preview_cy, car["color"])

        self.left_arrow.draw(surface)
        self.right_arrow.draw(surface)

        name_surf = self.fonts["heading"].render(car["name"], True, TEXT_PRIMARY)
        surface.blit(name_surf, name_surf.get_rect(centerx=self._preview_cx, y=panel.y + 14))

        if not owned:
            lock_surf = pygame.Surface((panel.w, panel.h - 80), pygame.SRCALPHA)
            lock_surf.fill((0, 0, 0, 110))
            surface.blit(lock_surf, (panel.x, panel.y + 80))
            lock_txt = self.fonts["heading"].render(
                f"LOCKED  —  {_fmt_coins(car['price'])}", True, ACCENT_GOLD)
            surface.blit(lock_txt, lock_txt.get_rect(
                center=(panel.centerx, panel.centery + 20)))

        # ── right panel ──────────────────────────────────────────────────────
        rp = self._rp
        draw_rounded_rect(surface, PANEL_BG, rp, 16)

        name_r = self.fonts["heading"].render(car["name"], True, TEXT_PRIMARY)
        surface.blit(name_r, (rp.x + 20, rp.y + 14))

        # tier badge
        tier      = car.get("tier", "")
        tier_col  = TIER_COLORS.get(tier, TEXT_DISABLED)
        tier_surf = self.fonts["small"].render(tier.upper(), True, tier_col)
        tier_rect = tier_surf.get_rect(right=rp.right - 14, y=rp.y + 18)
        pygame.draw.rect(surface, (*tier_col, 40),
                         tier_rect.inflate(12, 6), border_radius=6)
        surface.blit(tier_surf, tier_rect)

        bar_x = rp.x + 20
        bar_w = rp.w - 40
        coins = self.gd["player"]["coins"]

        self._stat_rects = {}

        for i, (key, label) in enumerate(STATS_ORDER):
            row_y    = rp.y + self.ROW_START + i * self.ROW_H
            val      = self._stat_value(car, key)
            upg      = car["upgrades"][key]
            lvl, max_lvl = upg["level"], upg["max_level"]
            can, cost, _, _, is_maxed = self._upgrade_info(car, key)

            is_sel  = self.selected_stat == key
            is_hov  = self._hovered_stat == key and not is_sel

            # hit rect for the entire row
            row_rect = pygame.Rect(rp.x + 6, row_y - 4, rp.w - 12, self.ROW_H - 6)
            self._stat_rects[key] = row_rect

            # row background highlight
            if is_sel:
                hl = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                hl.fill((255, 195, 0, 28))
                surface.blit(hl, row_rect.topleft)
                pygame.draw.rect(surface, ACCENT_GOLD, row_rect, 1, border_radius=8)
                # gold left accent bar
                pygame.draw.rect(surface, ACCENT_GOLD,
                                 (row_rect.x, row_rect.y, 4, row_rect.h), border_radius=4)
            elif is_hov and owned:
                hl = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 12))
                surface.blit(hl, row_rect.topleft)

            # label line: "SPEED  (lvl 2/5)"
            lbl_str  = f"{label}  (lvl {lvl}/{max_lvl})"
            lbl_col  = ACCENT_GOLD if is_sel else TEXT_SECONDARY
            lbl_surf = self.fonts["small"].render(lbl_str, True, lbl_col)
            surface.blit(lbl_surf, (bar_x, row_y))

            # MAX badge or upgrade cost hint on the right of the label
            if owned:
                if is_maxed:
                    badge = self.fonts["small"].render("MAX", True, ACCENT_GOLD)
                    surface.blit(badge, (rp.right - 16 - badge.get_width(), row_y))
                else:
                    can_afford = coins >= cost
                    cost_col   = TEXT_SECONDARY if can_afford else (180, 60, 60)
                    cost_surf  = self.fonts["small"].render(_fmt_coins(cost), True, cost_col)
                    surface.blit(cost_surf, (rp.right - 16 - cost_surf.get_width(), row_y))

            # stat bar
            bar_col = STAT_BAR_HI if val > 75 else STAT_BAR_FG
            if is_sel:
                bar_col = ACCENT_GOLD
            by = row_y + 22
            pygame.draw.rect(surface, STAT_BAR_BG, (bar_x, by, bar_w, 20), border_radius=6)
            if val:
                pygame.draw.rect(surface, bar_col, (bar_x, by, int(bar_w * val / 100), 20),
                                 border_radius=6)
            pygame.draw.rect(surface, WHITE, (bar_x, by, bar_w, 20), 1, border_radius=6)

            # next-level preview tick on the bar (ghost marker)
            if owned and not is_maxed and is_sel:
                next_val = min(100, val + 5)
                tick_x   = bar_x + int(bar_w * next_val / 100)
                pygame.draw.rect(surface, WHITE, (tick_x - 2, by, 3, 20))
                nxt_surf = self.fonts["small"].render(f"+5", True, WHITE)
                surface.blit(nxt_surf, (tick_x + 4, by + 2))

        # ── upgrade preview zone (bottom of right panel) ─────────────────────
        sep_y = rp.y + self.ROW_START + 4 * self.ROW_H + 4
        pygame.draw.line(surface, CARD_BG, (rp.x + 14, sep_y), (rp.right - 14, sep_y), 2)

        zone_y = sep_y + 12
        zone_h = rp.bottom - zone_y - 8
        self._draw_upgrade_preview(surface, car, owned, rp, zone_y, zone_h, coins)

        # ── bottom buttons ────────────────────────────────────────────────────
        if not owned:
            self.btn_buy.draw(surface)
        else:
            if not self._is_selected():
                self.btn_select.draw(surface)
            else:
                sel_lbl = self.fonts["btn"].render("✓ SELECTED", True, ACCENT_GOLD)
                surface.blit(sel_lbl, (240, sh - 56))

        self.btn_race.enabled = owned
        self.btn_race.draw(surface)

        # flash message
        if self.message_timer > 0:
            self.message_timer -= 1
            alpha   = min(255, self.message_timer * 6)
            msg_s   = self.fonts["heading"].render(self.message, True, ACCENT_GOLD)
            msg_s.set_alpha(alpha)
            surface.blit(msg_s, msg_s.get_rect(centerx=sw // 2, y=sh - 130))

    def _draw_upgrade_preview(self, surface, car, owned, rp, zone_y, zone_h, coins):
        f_small = self.fonts["small"]
        f_btn   = self.fonts["btn"]
        f_body  = self.fonts["body"]

        if not owned or not self.selected_stat:
            hint = f_small.render(
                "Tap a stat to select it for upgrade" if owned else "Buy this car to upgrade",
                True, TEXT_DISABLED)
            surface.blit(hint, hint.get_rect(centerx=rp.centerx, y=zone_y + 8))
            self._upgrade_btn_rect = pygame.Rect(0, 0, 0, 0)
            return

        stat = self.selected_stat
        can, cost, lvl, max_lvl, is_maxed = self._upgrade_info(car, stat)
        stat_label = dict(STATS_ORDER)[stat]
        cur_val    = self._stat_value(car, stat)
        next_val   = min(100, cur_val + 5)

        if is_maxed:
            msg = f_body.render(f"{stat_label}  —  MAX LEVEL", True, ACCENT_GOLD)
            surface.blit(msg, msg.get_rect(centerx=rp.centerx, y=zone_y + 8))
            self._upgrade_btn_rect = pygame.Rect(0, 0, 0, 0)
            return

        # level progression
        lvl_str  = f"{stat_label}:  Lv {lvl}  →  Lv {lvl + 1}    (+5)"
        lvl_surf = f_body.render(lvl_str, True, TEXT_PRIMARY)
        surface.blit(lvl_surf, (rp.x + 16, zone_y + 4))

        # coin cost line
        can_afford = coins >= cost
        short      = cost - coins
        if can_afford:
            cost_str = f"Cost:  {_fmt_coins(cost)}"
            cost_col = ACCENT_GOLD
        else:
            cost_str = f"Need  {_fmt_coins(short)}  more"
            cost_col = (220, 60, 60)
        cost_surf = f_small.render(cost_str, True, cost_col)
        surface.blit(cost_surf, (rp.x + 16, zone_y + 30))

        # upgrade button
        btn_w = rp.w - 32
        btn_h = 38
        btn_x = rp.x + 16
        btn_y = zone_y + 54
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        self._upgrade_btn_rect = btn_rect

        if can_afford:
            btn_col = BTN_HOVER if self._upgrade_btn_hover else ACCENT_RED
            txt_col = WHITE
        else:
            btn_col = (45, 35, 35)
            txt_col = TEXT_DISABLED

        pygame.draw.rect(surface, btn_col, btn_rect, border_radius=10)
        btn_lbl = f_btn.render(
            f"UPGRADE {stat_label}  —  {_fmt_coins(cost)}", True, txt_col)
        surface.blit(btn_lbl, btn_lbl.get_rect(center=btn_rect.center))
