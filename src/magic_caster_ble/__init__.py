from __future__ import annotations

__version__ = "1.1.7"


from bleak_retry_connector import get_device

from .const import WAND_FRIENDLY_TO_UUID
from .exceptions import CharacteristicMissingError
from .wand_ble import MagicCasterWandBLE

__all__ = [
    "CharacteristicMissingError",
    "MagicCasterWandBLE",
    "WAND_FRIENDLY_TO_UUID",
    "get_device",
]