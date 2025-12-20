from dataclasses import dataclass


@dataclass(frozen=True)
class WandBLEState:
    version_num: int = 0.1
    last_cast_spell: str = ""
    battery_level: int = 0
