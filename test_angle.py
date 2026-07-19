import math

pts = [(-9, 8), (9, 8), (0, -10)]
dx, dy = 1, 0  # RIGHT
a = math.atan2(dy, dx) + math.pi/2
cos_a, sin_a = math.cos(a), math.sin(a)

rotated_pts = []
for px, py in pts:
    nx = px * cos_a - py * sin_a
    ny = px * sin_a + py * cos_a
    rotated_pts.append((nx, ny))

print(f"Angle: {a}")
print(f"Rotated points: {rotated_pts}")
