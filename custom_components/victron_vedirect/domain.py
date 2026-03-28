from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class VictronVEDirectRuntimeData(TypedDict):
    coordinator: DataUpdateCoordinator
    deviceInfo: DeviceInfo


type VictronVEDirectConfigEntry = ConfigEntry[VictronVEDirectRuntimeData]
