"""Config flow for the Victron VE.Direct integration."""

from __future__ import annotations

import logging
from typing import Any

import serial.tools.list_ports
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TYPE, DOMAIN, VictronDeviceType

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    port = data[CONF_PORT]

    try:
        # Placeholder connection test
        ser = serial.Serial(port, 19200, timeout=1)
        ser.write(b"TEST\n")  # Placeholder command
        ser.close()

    except serial.SerialException as err:
        _LOGGER.error("Serial connection failed: %s", err)
        raise CannotConnect from err

    return {"title": f"VE.Direct ({port})"}


def _get_serial_ports() -> list[str]:
    """Return a list of available serial ports."""
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]


class VictronVedirectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VE.Direct."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step when user initializes a integration."""
        errors = {}
        placeholders = {}
        if user_input is not None:
            name = user_input[CONF_NAME]
            device_type = user_input[CONF_DEVICE_TYPE]
            port = user_input[CONF_PORT]

            self._async_abort_entries_match({CONF_PORT: port})
            
            probe_result = True
            # TODO implement probe
            if probe_result:
                return self.async_create_entry(title=name, data={CONF_PORT: port, CONF_DEVICE_TYPE: device_type, CONF_NAME: name})
            errors[CONF_PORT] = "cannot_connect"
            placeholders["error_detail"] = probe_result.name.lower()

        available_ports = await self.hass.async_add_executor_job(_get_serial_ports)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_DEVICE_TYPE): vol.Coerce(VictronDeviceType),
                    vol.Required(CONF_PORT): vol.In(available_ports),
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
