"""Config flow for the Anthem AVR RS-232 integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_MODEL, CONF_PORT
from homeassistant.helpers import selector

from .anthem_rs232 import probe
from .const import CONF_BAUD_RATE, CONF_GENERATION, DOMAIN, LOGGER

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
        ),
    },
)


class AnthemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the serial port, then probe it for an Anthem receiver.

    The probe detects the protocol generation (Gen 1 vs Gen 2), the baud rate,
    and the model name, so the user only ever has to supply the port.
    """

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            self._async_abort_entries_match({CONF_PORT: port})
            try:
                result = await probe(port)
            except (OSError, ValueError) as err:
                LOGGER.error("Error probing %s: %s", port, err)
                errors["base"] = "cannot_connect"
            else:
                if result is None:
                    errors["base"] = "no_receiver"
                else:
                    return self.async_create_entry(
                        title=result.model_name,
                        data={
                            CONF_PORT: port,
                            CONF_GENERATION: result.generation,
                            CONF_MODEL: result.model_name,
                            CONF_BAUD_RATE: result.baud_rate,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )
