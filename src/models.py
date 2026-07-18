import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional

@dataclass
class TileDefinition:
    name: str
    friction: float
    drivable: bool
    hazard: bool
    speed_multiplier: float
    damage_per_sec: float
    collision_damage: float
    color_rgb: Tuple[int, int, int]
    description: str

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "TileDefinition":
        return cls(
            name=name,
            friction=float(d.get("friction", 1.0)),
            drivable=bool(d.get("drivable", True)),
            hazard=bool(d.get("hazard", False)),
            speed_multiplier=float(d.get("speed_multiplier", 1.0)),
            damage_per_sec=float(d.get("damage_per_sec", 0.0)),
            collision_damage=float(d.get("collision_damage", 0.0)),
            color_rgb=tuple(d.get("color_rgb", [127, 127, 127])),
            description=d.get("description", "")
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["color_rgb"] = list(self.color_rgb)
        d.pop("name")
        return d


@dataclass
class GridSize:
    width: int
    height: int

    @classmethod
    def from_dict(cls, d: dict) -> "GridSize":
        return cls(width=d["width"], height=d["height"])

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Checkpoint:
    id: int
    x: int
    y: int
    name: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        return cls(
            id=d["id"],
            x=d["x"],
            y=d["y"],
            name=d.get("name", f"Checkpoint {d['id']}")
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpawnPoint:
    x: int
    y: int
    direction: str  # "north", "south", "east", "west"

    @classmethod
    def from_dict(cls, d: dict) -> "SpawnPoint":
        return cls(
            x=d["x"],
            y=d["y"],
            direction=d.get("direction", "east")
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decoration:
    type: str
    x: float
    y: float

    @classmethod
    def from_dict(cls, d: dict) -> "Decoration":
        return cls(
            type=d["type"],
            x=float(d["x"]),
            y=float(d["y"])
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Racetrack:
    name: str
    description: str
    creator: str
    version: str
    grid_size: GridSize
    tile_palette: Dict[str, str]
    grid: List[str]
    checkpoints: List[Checkpoint]
    starting_grid: List[SpawnPoint]
    laps: int = 3
    difficulty: str = "medium"
    tile_size: int = 32
    decorations: List[Decoration] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Racetrack":
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            creator=d.get("creator", "Unknown"),
            version=d.get("version", "1.0"),
            grid_size=GridSize.from_dict(d["grid_size"]),
            laps=d.get("laps", 3),
            difficulty=d.get("difficulty", "medium"),
            tile_size=d.get("tile_size", 32),
            tile_palette=dict(d["tile_palette"]),
            grid=list(d["grid"]),
            checkpoints=[Checkpoint.from_dict(cp) for cp in d.get("checkpoints", [])],
            starting_grid=[SpawnPoint.from_dict(sp) for sp in d.get("starting_grid", [])],
            decorations=[Decoration.from_dict(dec) for dec in d.get("decorations", [])]
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "creator": self.creator,
            "version": self.version,
            "grid_size": self.grid_size.to_dict(),
            "laps": self.laps,
            "difficulty": self.difficulty,
            "tile_size": self.tile_size,
            "tile_palette": self.tile_palette,
            "grid": self.grid,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "starting_grid": [sp.to_dict() for sp in self.starting_grid],
            "decorations": [dec.to_dict() for dec in self.decorations]
        }

    def get_tile_char_at(self, x: int, y: int) -> str:
        if 0 <= y < len(self.grid) and 0 <= x < len(self.grid[y]):
            return self.grid[y][x]
        return ""

    def get_tile_type_at(self, x: int, y: int) -> str:
        char = self.get_tile_char_at(x, y)
        return self.tile_palette.get(char, "wall")  # Default to wall if not found

    def get_tile_definition_at(self, x: int, y: int, tile_defs: Dict[str, TileDefinition]) -> Optional[TileDefinition]:
        tile_type = self.get_tile_type_at(x, y)
        return tile_defs.get(tile_type)
