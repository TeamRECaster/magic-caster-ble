from __future__ import annotations

__version__ = "1.1.7"


from bleak_retry_connector import get_device

from .exceptions import CharacteristicMissingError
from .wand_ble import MagicCasterWandBLE

__all__ = [
    "CharacteristicMissingError",
    "MagicCasterWandBLE",
    "get_device",
]