import json
import sys
import pygame

from ui.colors import *
from ui.lobby import LobbyScreen
from ui.garage import GarageScreen
from ui.settings_screen import SettingsScreen
from ui.components import NavBar

DATA_DIR = "data"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def build_fonts():
    pygame.font.init()
    return {
        "big_title": pygame.font.SysFont("Arial Black", 62, bold=True),
        "title":     pygame.font.SysFont("Arial Black", 38, bold=True),
        "heading":   pygame.font.SysFont("Arial",       28, bold=True),
        "body":      pygame.font.SysFont("Arial",       22),
        "btn":       pygame.font.SysFont("Arial Black", 20, bold=True),
        "small":     pygame.font.SysFont("Arial",       16),
        "coin":      pygame.font.SysFont("Arial Black", 24, bold=True),
    }


def draw_background(surface, screen_w, screen_h):
    surface.fill(DARK_BG)
    for x in range(0, screen_w, 60):
        pygame.draw.line(surface, (28, 28, 45), (x, 0), (x, screen_h))
    for y in range(0, screen_h, 60):
        pygame.draw.line(surface, (28, 28, 45), (0, y), (screen_w, y))


def main():
    pygame.init()
    SW, SH = 1024, 680
    screen = pygame.display.set_mode((SW, SH))
    pygame.display.set_caption("Mzansi Rush")
    clock = pygame.time.Clock()

    player   = load_json(f"{DATA_DIR}/player.json")
    cars_raw = load_json(f"{DATA_DIR}/cars.json")
    settings = load_json(f"{DATA_DIR}/settings.json")

    game_data = {
        "player":   player,
        "cars":     cars_raw["cars"],
        "settings": settings,
    }

    fonts = build_fonts()

    lobby          = LobbyScreen(SW, SH, fonts, game_data)
    garage         = GarageScreen(SW, SH, fonts, game_data)
    settings_screen = SettingsScreen(SW, SH, fonts, game_data)
    navbar         = NavBar(SW, fonts["btn"], fonts["small"], fonts["coin"])

    # Navigation history stack — each entry is a screen name string.
    # The top of the stack is the current screen.
    history = ["lobby"]

    def current():
        return history[-1]

    def navigate_to(screen_name):
        """Push a new screen, avoid duplicate consecutive pushes."""
        if history[-1] != screen_name:
            history.append(screen_name)
        if screen_name == "lobby":
            lobby.on_enter()

    def navigate_back():
        if len(history) > 1:
            history.pop()
        if current() == "lobby":
            lobby.on_enter()

    running = True
    while running:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

            # NavBar handles back button + ESC for all non-lobby screens
            if current() != "lobby":
                nav_result = navbar.handle_event(event, history)
                if nav_result == "back":
                    navigate_back()
                    continue

            if current() == "lobby":
                result = lobby.handle_event(event)
                if result == "garage":
                    navigate_to("garage")
                elif result == "settings":
                    navigate_to("settings")
                elif result == "race":
                    print(f"Starting race with: {game_data['player']['selected_car']}")
                elif result == "quit":
                    running = False

            elif current() == "garage":
                result = garage.handle_event(event)
                if result == "race":
                    print(f"Starting race with: {game_data['player']['selected_car']}")
                    navigate_back()

            elif current() == "settings":
                settings_screen.handle_event(event)

        # update
        if current() == "lobby":
            lobby.update()

        # draw
        draw_background(screen, SW, SH)

        if current() == "lobby":
            lobby.draw(screen)
        elif current() == "garage":
            garage.draw(screen)
        elif current() == "settings":
            settings_screen.draw(screen)

        # NavBar drawn on top of every screen except lobby
        if current() != "lobby":
            navbar.draw(screen, history, game_data["player"]["coins"])

        if game_data["settings"].get("show_fps"):
            fps_surf = fonts["small"].render(f"FPS: {clock.get_fps():.0f}", True, TEXT_SECONDARY)
            screen.blit(fps_surf, (8, SH - 24))

        pygame.display.flip()
        clock.tick(60)

    save_json(f"{DATA_DIR}/player.json",   game_data["player"])
    save_json(f"{DATA_DIR}/settings.json", game_data["settings"])
    cars_raw["cars"] = game_data["cars"]
    save_json(f"{DATA_DIR}/cars.json", cars_raw)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
