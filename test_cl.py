import pygame
pygame.init()
pygame.display.set_mode((100, 100))

from game.track import Track

t = Track("data/mzansi_asphalt.json")
cl = t._trace_road()
rts = t._rts

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

    n_cl = len(cl)
    n_idx = (best_i + 3) % n_cl
    dx = cl[n_idx][0] - cl[best_i][0]
    dy = cl[n_idx][1] - cl[best_i][1]
    
    import math
    a = math.atan2(dy, dx) + math.pi/2
    print(f"Tile ({gx}, {gy}): dx={dx:.2f}, dy={dy:.2f}, angle={math.degrees(a):.1f}")

test_pad(11, 6) # where the first B is
test_pad(12, 6) # where S is
