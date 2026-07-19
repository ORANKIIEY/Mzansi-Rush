import pygame
pygame.init()
pygame.display.set_mode((100, 100))
from game.track import Track
import math

t = Track("data/mzansi_asphalt.json")
cl = t._trace_road()
rts = t._rts
n_cl = len(cl)

def test_pad(gx, gy):
    rx, ry = gx*rts, gy*rts
    cx2, cy2 = rx+rts/2, ry+rts/2
    best_i = 0
    best_d = float('inf')
    for i, p in enumerate(cl):
        d = (p[0]-cx2)**2 + (p[1]-cy2)**2
        if d < best_d:
            best_d = d
            best_i = i

    n_idx = (best_i + 3) % n_cl
    dx = cl[n_idx][0] - cl[best_i][0]
    dy = cl[n_idx][1] - cl[best_i][1]
    
    a = math.atan2(dy, dx) + math.pi/2
    
    # Let's simulate the yellow pad tip: (0, -10)
    cos_a, sin_a = math.cos(a), math.sin(a)
    tip_nx = 0 * cos_a - (-10) * sin_a
    tip_ny = 0 * sin_a + (-10) * cos_a
    
    # Is tip_nx positive? (pointing right)
    print(f"Tile ({gx}, {gy}): dx={dx:.2f}, dy={dy:.2f}, angle={math.degrees(a):.1f}, tip_nx={tip_nx:.2f}, tip_ny={tip_ny:.2f}")

print("Testing top stretch:")
test_pad(11, 6)
test_pad(12, 6)
test_pad(13, 6)

test_pad(29, 6)
test_pad(30, 6)
test_pad(31, 6)

print("Testing bottom stretch:")
test_pad(11, 18)
test_pad(12, 18)
test_pad(13, 18)
