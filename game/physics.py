import math


class CarPhysics:
    """Arcade drift physics with separate heading and velocity vectors.

    The car has:
      - angle      : direction it's FACING  (visual + steering)
      - vel_angle  : direction it's actually MOVING
      - speed      : magnitude of movement

    The difference (angle - vel_angle) is the DRIFT ANGLE.
    When grip is high (asphalt + high grip stat), vel_angle snaps quickly
    to match angle → responsive, planted feel.
    When grip is low (dirt/ice/oil + low grip stat), vel_angle lags behind
    → the tail kicks out, car slides sideways = DRIFT.

    Visually the car sprite rotates to `angle`, but it moves along `vel_angle`.
    This naturally produces oversteer, powerslides, and that satisfying
    counter-steer catch.
    """

    # ── base tuning (at speed stat 100) ───────────────────────────────────
    BASE_MAX_SPEED  = 460      # px/sec — roughly 190 km/h at stat 100
    BASE_ACCEL      = 420      # px/sec² — punchy acceleration
    BASE_BRAKE      = 600      # px/sec² — strong brakes
    BASE_FRICTION   = 120      # px/sec² passive drag (coasting)

    # ── steering ──────────────────────────────────────────────────────────
    MAX_ANG_VEL     = 260      # deg/sec ceiling
    ANG_ACCEL       = 720      # deg/sec² while key held
    ANG_FRICTION    = 6.5      # angular decay rate (asphalt)

    # ── drift / grip ──────────────────────────────────────────────────────
    # How fast vel_angle catches up to facing angle (higher = more grip)
    GRIP_SNAP_BASE  = 8.0      # per-second, at grip=100 on asphalt
    GRIP_SNAP_MIN   = 0.6      # minimum snap even on oil with 0 grip

    # Speed-dependent grip loss: faster = harder to hold the line
    SPEED_GRIP_FALLOFF = 0.35  # fraction of grip lost at max speed

    # Counter-steer bonus: steering into the slide recovers faster
    COUNTERSTEER_MULT  = 2.2

    # ── downhill / gravity boost ──────────────────────────────────────────
    GRAVITY_BOOST   = 120      # extra px/sec² on steep downhill tiles

    def __init__(self, x: float, y: float, angle: float = 90.0, stats: dict | None = None):
        self.x            = float(x)
        self.y            = float(y)
        self.angle        = float(angle)   # heading: where the car FACES
        self.vel_angle    = float(angle)   # velocity: where the car MOVES
        self.speed        = 0.0            # px/sec (positive = forward)
        self.angular_vel  = 0.0            # deg/sec (steering rate)

        # ── car stats ─────────────────────────────────────────────────
        s = stats or {}
        spd  = s.get("speed", 50) / 100.0
        grip = s.get("grip",  50) / 100.0

        self.max_speed  = self.BASE_MAX_SPEED * (0.50 + 0.80 * spd)
        self.accel      = self.BASE_ACCEL     * (0.55 + 0.70 * spd)
        self.grip_stat  = grip   # 0.0 → 1.0 — how planted the car is

        # ── drift state (exposed for visual effects) ──────────────────
        self.drift_angle = 0.0   # signed degrees: positive = tail-right

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
                       Low friction = less grip = more slide.
        """
        # ── forward / brake ───────────────────────────────────────────
        speed_cap = self.max_speed * max(speed_mult, 0.0)
        if speed_mult > 1.0:
            speed_cap = self.max_speed * speed_mult   # boost tiles

        if up:
            self.speed = min(speed_cap, self.speed + self.accel * dt)
        elif down:
            self.speed = max(-speed_cap * 0.35,
                             self.speed - self.BASE_BRAKE * dt)
        else:
            # coast drag — more drag on low-friction surfaces (wheelspin)
            drag = self.BASE_FRICTION * (1.0 + (1.0 - surf_friction) * 2.0) * dt
            if self.speed > 0:
                self.speed = max(0.0, self.speed - drag)
            else:
                self.speed = min(0.0, self.speed + drag)

        # Smooth speed cap (don't instantly clamp, ease down)
        if abs(self.speed) > speed_cap:
            self.speed *= max(0.0, 1.0 - 3.5 * dt)

        # ── steering (angular velocity) ───────────────────────────────
        if left:
            self.angular_vel -= self.ANG_ACCEL * dt
        elif right:
            self.angular_vel += self.ANG_ACCEL * dt
        else:
            effective_decay = self.ANG_FRICTION * surf_friction
            self.angular_vel *= max(0.0, 1.0 - effective_decay * dt)
            if abs(self.angular_vel) < 1.5:
                self.angular_vel = 0.0

        self.angular_vel = max(-self.MAX_ANG_VEL,
                               min(self.MAX_ANG_VEL, self.angular_vel))

        # Update facing angle
        self.angle = (self.angle + self.angular_vel * dt) % 360

        # ── DRIFT MODEL: vel_angle catches up to facing angle ─────────
        # Effective grip = car grip stat × surface friction
        # At higher speeds, grip falls off → easier to slide
        speed_ratio = min(1.0, abs(self.speed) / max(1.0, self.max_speed))
        speed_grip_penalty = 1.0 - self.SPEED_GRIP_FALLOFF * speed_ratio

        effective_grip = (
            self.grip_stat
            * surf_friction
            * speed_grip_penalty
        )

        # Snap rate: how fast vel_angle → angle
        snap = self.GRIP_SNAP_MIN + (self.GRIP_SNAP_BASE - self.GRIP_SNAP_MIN) * effective_grip

        # Calculate the angular difference (drift angle)
        diff = (self.angle - self.vel_angle + 180) % 360 - 180  # [-180, 180]

        # Counter-steer bonus: if player steers INTO the slide, snap faster
        if self.angular_vel != 0 and diff != 0:
            # Steering is "into the slide" if angular_vel opposes the drift
            if (self.angular_vel > 0 and diff < 0) or (self.angular_vel < 0 and diff > 0):
                snap *= self.COUNTERSTEER_MULT

        # Apply velocity angle correction
        correction = diff * snap * dt
        # Don't overshoot
        if abs(correction) > abs(diff):
            correction = diff
        self.vel_angle = (self.vel_angle + correction) % 360

        # Store drift angle for visual effects (skid marks, smoke, etc.)
        self.drift_angle = (self.angle - self.vel_angle + 180) % 360 - 180

        # ── Throttle-induced oversteer (power slide) ──────────────────
        # Accelerating hard while turning pushes the tail out on low-grip
        if up and abs(self.angular_vel) > 30 and self.speed > 50:
            power_slide = (
                self.angular_vel * 0.08
                * (1.0 - effective_grip)
                * speed_ratio
                * dt
            )
            self.vel_angle = (self.vel_angle - power_slide) % 360
            self.drift_angle = (self.angle - self.vel_angle + 180) % 360 - 180

        # ── integrate position along VELOCITY angle ───────────────────
        rad = math.radians(self.vel_angle)
        self.x += math.sin(rad) * self.speed * dt
        self.y -= math.cos(rad) * self.speed * dt

    @property
    def kmh(self) -> float:
        """Convert internal px/sec to km/h display value."""
        return abs(self.speed) * 0.32

    @property
    def rpm(self) -> int:
        ratio = abs(self.speed) / max(1.0, self.max_speed)
        return int(900 + ratio * 7100)

    @property
    def is_drifting(self) -> bool:
        """True when the car is sliding significantly."""
        return abs(self.drift_angle) > 8.0 and abs(self.speed) > 60

    @property
    def drift_intensity(self) -> float:
        """0.0 → 1.0 drift intensity for visual effects."""
        if abs(self.speed) < 40:
            return 0.0
        return min(1.0, abs(self.drift_angle) / 45.0)
