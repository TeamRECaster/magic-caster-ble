import asyncio
import logging

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from magic_caster_ble import MagicCasterWandBLE

_LOGGER = logging.getLogger("magic_caster_ble")

TARGET_NAME = "MCW-"

async def run() -> None:
    scanner = BleakScanner()
    future: asyncio.Future[BLEDevice] = asyncio.Future()

    def on_detected(device: BLEDevice, adv: AdvertisementData) -> None:
        if future.done():
            return
        _LOGGER.info("Detected: %s", device)
        if device.name and TARGET_NAME in device.name:
            _LOGGER.info("Found device: %s, %s", device.name, device.address)
            future.set_result(device)

    scanner._backend.register_detection_callback(on_detected)
    await scanner.start()

    device = await future
    wand = MagicCasterWandBLE(device)
    _LOGGER.info("Wand name tested: %s", wand.name)

    await wand.update()

    # TODO: Check some data
    _LOGGER.info("Last cast spell: %s", wand.last_cast_spell)
    _LOGGER.info("Battery: %s", wand.battery_level)

    await asyncio.sleep(5)

    # TODO: Check again
    _LOGGER.info("Last cast spell: %s", wand.last_cast_spell)
    _LOGGER.info("Battery: %s", wand.battery_level)

    await scanner.stop()


logging.basicConfig(level=logging.DEBUG)
logging.getLogger("bleak").setLevel(logging.INFO)
logging.getLogger("magic_caster_ble").setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)

asyncio.run(run())
