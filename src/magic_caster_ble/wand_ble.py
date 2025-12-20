import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.backends.service import (
    BleakError,
    BleakGATTCharacteristic,
    BleakGATTServiceCollection,
)
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .const import DISCONNECT_DELAY, WAND_FRIENDLY_TO_UUID, WandCommandOpCodes
from .exceptions import CharacteristicMissingError
from .models import WandBLEState

_LOGGER = logging.getLogger(__name__)

class MagicCasterWandBLE:
    def __init__(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData | None = None
    ) -> None:
        """Init the wand BLE device"""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data

        self._state = WandBLEState()

        # self._operation_lock = asyncio.Lock()
        self._connect_lock: asyncio.Lock = asyncio.Lock()

        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._expected_disconnect = False

        self._characteristics: dict[str, BleakGATTCharacteristic | None] = {
            "Wand_Activity_Notify": None,
        }
        self._client: BleakClientWithServiceCache | None = None


        self._callbacks: list[Callable[[WandBLEState], None]] = []

        self._startup_event = asyncio.Event()

    # --- BLE device & ad data things ---
    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Set the ble device."""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data
    
    @property
    def address(self) -> str:
        """Return the address."""
        return self._ble_device.address

    # TODO: Make this read/write (Handle 2)
    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._ble_device.name or self._ble_device.address

    
    # TODO: Read only (Handle 4)
    # @property
    # def variant(self) -> str:
    #     """Determine the appearance of the device."""
    #     return self._ble_device.name or self._ble_device.address

    @property
    def rssi(self) -> int | None:
        """Get the rssi of the device."""
        if self._advertisement_data:
            return self._advertisement_data.rssi
        return None

    # --- Application state ---
    @property
    def state(self) -> WandBLEState:
        """Return the state."""
        return self._state
    
    @property
    def last_cast_spell(self) -> tuple[int, int, int]:
        """Return the last cast spell."""
        return self._state.last_cast_spell
    
    @property
    def battery_level(self) -> int:
        """Return the last cast spell."""
        return self._state.battery_level

    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            characteristics = self._characteristics
            client = self._client

            self._expected_disconnect = True
            self._client = None
            # TODO: Type these?
            self._characteristics = {
                "Wand_Activity_Notify": None,
            }

            # Undo IMU command!!
            self._disable_IMU()
            
            if client and client.is_connected:
                for key, characteristic in characteristics.items():
                    if characteristic:
                        try:
                            await client.stop_notify(characteristic)
                        except BleakError:
                            _LOGGER.debug(
                                "%s: Failed to stop notifications", self.name,
                                exc_info=True
                            )
                await client.disconnect()

    async def stop(self) -> None:
        """Stop lsitening for wand updates"""
        _LOGGER.debug("%s: Stop", self.name)
        await self._execute_disconnect()

    def _resolve_characteristics(self, services: BleakGATTServiceCollection) -> bool:
        """Resolve characteristics."""
        for key, _ in self._characteristics.items():
            _LOGGER.debug("Gathering characteristics. Searching for: %s", key)
            char = services.get_characteristic(WAND_FRIENDLY_TO_UUID[key]["Characteristic"])  # noqa: E501
            if char:
                _LOGGER.debug("Found char: %s", char)
                self._characteristics[key] = char
            else:
                _LOGGER.debug("Unable to find characteristic: %s", key)
                # Characteristic missing – keep it as None so we can detect it later
                self._characteristics[key] = None

        # Return True only when every characteristic has been found.
        return all(value is not None for value in self._characteristics.values())
    
    async def update(self) -> None:
        """Update the wand state."""
        await self._ensure_connected()
        _LOGGER.debug("%s: Updating", self.name)
        # TODO: Send queued commands here?

    def _fire_callbacks(self) -> None:
        """Fire the callbacks."""
        for callback in self._callbacks:
            callback(self._state)
    
    def register_callback(
        self, callback: Callable[[WandBLEState], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when the state changes."""

        def unregister_callback() -> None:
            self._callbacks.remove(callback)

        self._callbacks.append(callback)
        return unregister_callback

    def parse_header(self, data: bytearray) -> bytearray:
        # First 4 (0-3) bytes are header
        return data[:4]
    
    def parse_opcode(self, data: bytearray) -> int:
        # return data[3]
        # little endian, our byte ius at start
        return data[0]
        
    def parse_spell(self, data: bytearray) -> str | None:
        if len(data) < 6: # 4 header (0-3) + 1 len + 1 name byte at least
            return None

        spell_length = data[4]
        spell_bytes = data[4 : 4 + spell_length]

        spell_name = None
        try:
            spell_name = spell_bytes.decode('ascii').strip()
        except UnicodeDecodeError as ex:
            _LOGGER.debug("Spell decode failed: ", ex)
            return None
        
        return spell_name
    
    def _enable_IMU(self):
        """Stubbed - not for public release"""
        _LOGGER.debug("enable_IMU called!!")
        return
    
    def _disable_IMU(self):
        """Stubbed - not for public release"""
        _LOGGER.debug("disable_IMU called!!")
        return

    
    def _battery_notification_handler(self, _sender: str, data: bytearray) -> None:
        """Handle notification responses on the battery channel."""
        if not data:
            return
        
        _LOGGER.debug(
            "Battery reply received: %s",
            data.hex(),
        )
        battery = int.from_bytes(data, byteorder="little")
        self._state = replace(self._state, battery_level=battery)
        _LOGGER.debug("Battery reply received: %s%%", battery)


    def _activity_notification_handler(self, _sender: str, data: bytearray) -> None:
        """Handle notification responses on the activity channel."""
        if not data or len(data) < 4:
            return
        
        header = self.parse_header(data)
        opcode = self.parse_opcode(data)
        match opcode:
            case WandCommandOpCodes.SPELL_DETECTED:
                spell_name = self.parse_spell(data)
                if spell_name:
                    self._state = replace(self._state, last_cast_spell=spell_name)
            case _:
                _LOGGER.debug("Unknown opcode encountered :((((((")
        header_int = int.from_bytes(header, byteorder='little')
        _LOGGER.debug("Header 0x%08X, len=%d", header_int, len(header))
        _LOGGER.debug("Opcode 0x%X", opcode)
        _LOGGER.debug("Full packet: 0x%s, len=%d", data.hex(), len(data))

        self._fire_callbacks()
        
        # TODO: Switch statement

        # TODO: Parse IMU (Motion) data
        
        # TODO: Box ignores (spell - down motion) / (spell - up motion)
            # unless light active on respective device
        # TODO: Wand ignores (spell - swirl motion) unless (spell - triangle light motion) active on any device
            # or (spell - swirl motion) on box

    
    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        if self._expected_disconnect:
            _LOGGER.debug(
                "%s: Disconnected from device; RSSI: %s", self.name, self.rssi
            )
            return
        _LOGGER.warning(
            "%s: Device unexpectedly disconnected; RSSI: %s",
            self.name,
            self.rssi,
        )

    async def _execute_timed_disconnect(self) -> None:
        """Execute timed disconnection."""
        _LOGGER.debug(
            "%s: Disconnecting after timeout of %s",
            self.name,
            DISCONNECT_DELAY,
        )
        await self._execute_disconnect()

    def _disconnect(self) -> None:
        """Disconnect from device."""
        self._disconnect_timer = None
        asyncio.create_task(self._execute_timed_disconnect())
    
    def _reset_disconnect_timer(self) -> None:
        """Reset disconnect timer."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        self._expected_disconnect = False
        # TODO: Should we have a connect/disconnect cycle? Does this contribute to lag?
        self._disconnect_timer = asyncio.get_running_loop().call_later(
            DISCONNECT_DELAY, self._disconnect
        )
    
    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        if self._connect_lock.locked():
            _LOGGER.debug(
                "%s: Connection already in progress, waiting for it to complete; RSSI: %s",  # noqa: E501
                self.name,
                self.rssi,
            )
        if self._client and self._client.is_connected:
            self._reset_disconnect_timer()
            return
        async with self._connect_lock:
            # Check again while holding the lock
            if self._client and self._client.is_connected:
                self._reset_disconnect_timer()
                return
            _LOGGER.debug("%s: Connecting; RSSI: %s", self.name, self.rssi)
            for attempt in range(2):
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    self._ble_device,
                    self.name,
                    self._disconnected,
                    use_services_cache=True,
                    ble_device_callback=lambda: self._ble_device,
                )
                _LOGGER.debug("%s: Connected; RSSI: %s", self.name, self.rssi)
                if self._resolve_characteristics(client.services):
                    # Supported characteristics found
                    break
                else:
                    if attempt == 0:
                        # Try to handle services failing to load
                        await client.clear_cache()
                        await client.disconnect()
                        continue
                    await client.disconnect()
                    raise CharacteristicMissingError(
                        "Failed to find supported characteristics, device may not be supported"  # noqa: E501
                    )

            self._client = client
            self._reset_disconnect_timer()

            if not self._client:
                print("Device not found.")
                return False
        
            try:
                if not self._client.is_connected:
                    print(f"Unable to connect to {self.name} :(")
                    return False

                _LOGGER.debug(
                    "%s: Subscribe to notifications; RSSI: %s", self.name, self.rssi
                )

                # for k,v in self._characteristics.items():
                #     _LOGGER.debug("Characteristic: %s = %s", k, v)

                # Subscribe to the wand activity channel
                await self._client.start_notify(
                    self._characteristics["Wand_Activity_Notify"],
                    self._activity_notification_handler
                )

                # TODO: grab thise once on first start? -- otherwise doesn't update until Wand performs action
                await self._client.start_notify(
                    WAND_FRIENDLY_TO_UUID["Battery_Level_Notify"]["Characteristic"],
                    self._battery_notification_handler
                )

                # START IMU
                self._enable_IMU()
                
                # TODO: Does the wand need a keep alive?
                    # Noticed a possible connection drift to the wand box at one point
                    # - maybe nothing?


                _LOGGER.debug(f"Connected to {self.name}!")

                # We're started!
                self._startup_event.set()
                return True
            
            except BleakError as e:
                _LOGGER.debug(f"Connection error: {e}")
                return False
