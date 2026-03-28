"""The Victron VE.Direct integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.victron_vedirect.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.victron_vedirect.coordinator import VEDirectClient
from custom_components.victron_vedirect.domain import VictronVEDirectConfigEntry
from custom_components.victron_vedirect.sensor import VictronVEDirectCoordinator
from homeassistant.const import CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.SENSOR]






# TODO Update entry annotation
async def async_setup_entry(
    hass: HomeAssistant, config_entry: VictronVEDirectConfigEntry
) -> bool:
    """Set up Victron VE.Direct from a config entry."""

    #Initialize vedirect client and connect
    client = VEDirectClient(config_entry.data[CONF_PORT])
    await client.async_connect()

    # Initialise the coordinator that manages data updates
    coordinator = VictronVEDirectCoordinator(hass, config_entry, client)

    # TODO add validation here
    # # Perform an initial data load from api.
    # # async_config_entry_first_refresh() is special in that it does not log errors if it fails
    # await coordinator.async_config_entry_first_refresh()

    # # Test to see if api initialised correctly, else raise ConfigNotReady to make HA retry setup
    # # TODO: Change this to match how your api will know if connected or successful update
    # if not coordinator.api.connected:
    #     raise ConfigEntryNotReady

    # Add coordinator to runtime data
    config_entry.runtime_data = {"coordinator":coordinator, "deviceInfo": create_device_info(hass, config_entry)}

    # Setup platforms (based on the list of entity types in PLATFORMS defined above)
    # This calls the async_setup method in each of your entity type files.
    hass.async_create_task(hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS))

    # Return true to denote a successful setup.
    return True

def create_device_info(hass: HomeAssistant, config_entry: VictronVEDirectConfigEntry):
    return DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=config_entry.data[CONF_NAME],
        manufacturer="Victron Energy",
        model=config_entry.data.get(CONF_DEVICE_TYPE)
    )

async def async_unload_entry(hass: HomeAssistant, entry: VictronVEDirectConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
