DISCONNECT_DELAY = 120


# TODO: Typed? consts?
WAND_FRIENDLY_TO_UUID: dict[
    str, # Service/Characteristic friendly name
    dict[
        str, # Map Service and Channel
        str # to their id
    ]
] = {
    # Standard BLE service
    "Battery_Level_Notify": {
        "Service": "0000180f-0000-1000-8000-00805f9b34fb",
        "Characteristic": "00002a19-0000-1000-8000-00805f9b34fb"
    },
    # Write & Notify (Used to send commands TO the wand)
    "Wand_Command_Channel": {
        "Service": "57420001-587e-48a0-974c-544d6163c577",
        "Characteristic": "57420002-587e-48a0-974c-544d6163c577"
    },
    # Notify only (Receives IMU, Spells, ? from wand)
    "Wand_Activity_Notify": {
        "Service": "57420001-587e-48a0-974c-544d6163c577",
        "Characteristic": "57420003-587e-48a0-974c-544d6163c577"
    },
}

class WandCommandOpCodes:
    SPELL_DETECTED = 0x24
