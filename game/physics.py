import math


class CarPhysics:
    """Inertial tank-steering with tile-surface physics.

    Tap left/right  → brief angular_vel burst → small heading change.
    Hold left/right → angular_vel builds (angular acceleration).
    Release         → angular_vel decays proportional to surface friction:
                      ice / oil = slow decay (car keeps sliding),
                      asphalt   = fast decay (responsive steering).
    """

    BASE_MAX_SPEED  = 300     # px/sec at speed stat 100
    BASE_ACCEL      = 360
    BASE_BRAKE      = 500
    BASE_FRICTION   = 110     # passive drag (no throttle key)

    MAX_ANG_VEL     = 210     # deg/sec ceiling
    ANG_ACCEL       = 620     # deg/sec² build-up rate while key held
    ANG_FRICTION    = 5.8     # per-second decay on full-grip (asphalt) surface

    def __init__(self, x: float, y: float, angle: float = 90.0, stats: dict | None = None):
        self.x            = float(x)
        self.y            = float(y)
        self.angle        = float(angle)   # degrees; 0=up 90=right 180=down 270=left
        self.speed        = 0.0            # px/sec (positive = forward)
        self.angular_vel  = 0.0            # deg/sec

        spd = (stats or {}).get("speed", 50) / 100.0
        self.max_speed = self.BASE_MAX_SPEED * (0.45 + 0.85 * spd)
        self.accel     = self.BASE_ACCEL    * (0.50 + 0.75 * spd)

    def update(
        self,
        dt: float,
        up: bool,
        down: bool,
        left: bool,
        right: bool,
        speed_mult: float = 1.0,
        surf_friction: float = 1.0,
    ):
        """
        speed_mult:    tile speed multiplier (1.0=asphalt, 0.6=grass, 1.5=boost).
        surf_friction: tile friction coefficient (1.0=asphalt, 0.15=ice, 0.05=oil).
                       Low friction = angular velocity decays slower (realistic sliding).
        """
        # ── forward / brake ───────────────────────────────────────────
        speed_cap = self.max_speed * max(speed_mult, 0.0)
        if speed_mult > 1.0:               # boost tile — allow exceeding base max_speed
            speed_cap = self.max_speed * speed_mult

        if up:
            self.speed = min(speed_cap, self.speed + self.accel * dt)
        elif down:
            self.speed = max(-speed_cap * 0.38,
                             self.speed - self.BASE_BRAKE * dt)
        else:
            drag = self.BASE_FRICTION * (1.0 + (1.0 - surf_friction) * 2.5) * dt
            if self.speed > 0:
                self.speed = max(0.0, self.speed - drag)
            else:
                self.speed = min(0.0, self.speed + drag)

        # Clamp to current tile's speed cap (smooth, not instant)
        if abs(self.speed) > speed_cap:
            self.speed *= max(0.0, 1.0 - 3.0 * dt)

        # ── angular velocity ──────────────────────────────────────────
        if left:
            self.angular_vel -= self.ANG_ACCEL * dt
        elif right:
            self.angular_vel += self.ANG_ACCEL * dt
        else:
            # Decay scaled by surface grip: ice barely decays, asphalt decays fast
            effective_decay = self.ANG_FRICTION * surf_friction
            self.angular_vel *= max(0.0, 1.0 - effective_decay * dt)
            if abs(self.angular_vel) < 1.5:
                self.angular_vel = 0.0

        self.angular_vel = max(-self.MAX_ANG_VEL,
                               min(self.MAX_ANG_VEL, self.angular_vel))

        # ── integrate ─────────────────────────────────────────────────
        self.angle = (self.angle + self.angular_vel * dt) % 360
        rad = math.radians(self.angle)
        self.x += math.sin(rad) * self.speed * dt
        self.y -= math.cos(rad) * self.speed * dt

    @property
    def kmh(self) -> float:
        return abs(self.speed) * 0.32

    @property
    def rpm(self) -> int:
        ratio = abs(self.speed) / max(1.0, self.max_speed)
        return int(900 + ratio * 7100)
