import logging
from typing import override

from custom_components.victron_vedirect.domain import VictronVEDirectConfigEntry
from custom_components.victron_vedirect.const import DOMAIN, VEDirectKeys
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.victron_vedirect.vedirect.vedirect_client import ConnectionState, VEDirectClient

_LOGGER = logging.getLogger(__name__)


class VictronVEDirectCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator for push updates from the VEDirect port."""

    data: dict[str, str]

    def __init__(self, hass: HomeAssistant, config_entry: VictronVEDirectConfigEntry, vedirect_client: VEDirectClient) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_interval=None,
            update_method=None,
            always_update=False,
        )

        self._client = vedirect_client
        vedirect_client.async_add_state_listener(self.state_callback)
        vedirect_client.async_add_text_message_listener(self.vedirect_text_message_callback)

    async def async_shutdown(self) -> None:
        """Run shutdown clean up."""
        await super().async_shutdown()

        self._client.async_remove_state_listener(self._state_callback)
        self._client.async_remove_text_message_listener(self._vedirect_text_message_callback)

    @callback
    def _state_callback(self, state: ConnectionState) -> None:
        if state != ConnectionState.CONNECTED:
            self.async_set_update_error(self._client.last_exception if self._client.last_exception else Exception('Unknown error'))

    @callback
    def _vedirect_text_message_callback(self, data: dict[str, str]) -> None:
        self.async_set_updated_data(data)

    def get_value_by_key(self, key: VEDirectKeys) -> str | None:
        """Retrieves the current value for the specified key or None if no value exists."""

        if self.data is None:
            return None
        return self.data.get(key)
