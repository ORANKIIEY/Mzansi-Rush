# 🇿🇦 Mzansi Rush — SA Street Racing

A top-down 2D street racing game built with **Pygame**, full of South African flavour.

## 🚀 Quick Start

```bash
pip install -r requirements.txt
python main.py
```

## 🚗 Choose Your Ride

| Car | Style | Vibes |
|---|---|---|
| **Gusheshe** | BMW 325is | Speed demon — fastest, less grip |
| **Citi Golf** | VW legend | Balanced all-rounder |
| **Hilux** | Tough bakkie | Slow but grippy |
| **Quantum** | Taxi king! | Fast, loose handling |

## 🕹️ Controls

| Action | Key |
|---|---|
| Steer left | `←` / `A` |
| Steer right | `→` / `D` |
| Nudge forward | `↑` / `W` |
| Nudge back | `↓` / `S` |
| Start / Restart | `Space` / `Enter` |
| Pause | `Esc` |

Touch / swipe also supported on touchscreen devices.

## 🏁 Gameplay

- Dodge **potholes** and **rival cars** across 3 lanes
- **Overtake rivals** for bonus points (+100 each) with SA slang callouts
- Speed ramps up over time — survive as long as you can
- 3 lives — crash and you lose one. Hit 0 and it's **"EISH!"**
- High score saved automatically

## 🎨 Mzansi Spice

- 🟢🟡🔴 SA flag colour palette throughout
- SA-iconic car names (Gusheshe, Citi Golf, Hilux, Quantum)
- Potholes as obstacles 😂
- Overtake callouts: *SHARP! • LEKKER! • SHAP SHAP! • HEITA! • AYOBA!*
- "EISH!" game-over screen — *"Your ride is totalled, boet!"*

## 🛠️ Tech

- **Python 3** + **Pygame** — zero other dependencies
- Procedural sound effects (Web Audio–style beeps via `pygame.mixer`)
- Pre-rendered car sprites for smooth 60 FPS
- Particle effects, screen shake, headlight beams