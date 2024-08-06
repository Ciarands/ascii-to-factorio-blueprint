from .vector2 import Vector2
from typing import Set, List, Dict, Tuple

class Icon:
    name: str
    index: int

    def __init__(self, name: str, index: int) -> None:
        self.name = name
        self.index = index

    @property
    def as_dict(self) -> Dict:
        return {
            "signal": {
                "type": "item",
                "name": self.name
            },
            "index": self.index
        }

class Tile:
    name: str
    position: Vector2

    def __init__(self, name: str, position: Vector2) -> None:
        self.name = name
        self.position = position

    @property
    def as_dict(self) -> Dict:
        return {
            "name": self.name,
            "position": self.position.as_dict
        }
    
class Entity:
    name: str
    index: int
    position: Vector2

    def __init__(self, name: str, index: int, position: Vector2) -> None:
        self.name = name
        self.index = index
        self.position = position

    @property
    def as_dict(self) -> Dict:
        return {
            "entity_number": self.index,
            "name": self.name,
            "position": self.position.as_dict
        }


class Blueprint:
    item: str = "blueprint"
    version: int = 281479274299391

    def __init__(self, **kwargs) -> None:
        self.label = kwargs.pop("label", "unknown")
        self.used_positions: Set[Vector2] = set()
        self.entities: List[Dict] = []
        self.tiles: List[Dict] = []
        self.icons: List[Dict] = []

    @property
    def entity_index(self) -> int:
        return len(self.entities) + 1

    @property
    def tile_index(self) -> int:
        return len(self.tiles) + 1

    @property
    def icon_index(self) -> int:
        return len(self.icons) + 1

    @property
    def as_dict(self) -> Dict:
        return {
            "blueprint": {
                "icons": [Icon(name="stone-brick", index=1).as_dict], # TODO: Fix!
                "entities": self.entities,
                "tiles": self.tiles,
                "item": self.item,
                "label": self.label,
                "version": self.version
            },
        }

    def add_data(self, name: str, pos: Vector2) -> None:
        if pos in self.used_positions:
            return

        self.used_positions.add(pos)

        tile = Tile(
            name=name, 
            position=pos
        )

        # TODO: 
        # icon = Icon(
        #     name=name,
        #     index=self.icon_index
        # )
        # if icon.name not in self.seen_icons:
        #     self.icons.append(icon.as_dict)
        #     self.seen_icons.append(icon.name)

        self.tiles.append(tile.as_dict)

    def __repr__(self): 
        return f"Blueprint(version={self.version}, label='{self.label}', icon_index={self.icon_index}, tile_index={self.tile_index})"