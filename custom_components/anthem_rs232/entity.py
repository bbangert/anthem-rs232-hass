"""Base entity and device info helpers for the Anthem AVR RS-232 integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .anthem_rs232 import CommandError, Gen1CommandError
from .const import DOMAIN, MANUFACTURER
from .coordinator import AnthemCoordinator

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from .data import AnthemConfigEntry


def main_device_info(entry: AnthemConfigEntry, state: Any) -> DeviceInfo:
    """Device info for the receiver chassis (the main zone device).

    ``state`` is the coordinator data for either generation: Gen 2 carries
    ``software_version`` and ``mac_address``, Gen 1 carries ``version``.
    """
    info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=entry.data.get(CONF_MODEL),
        name=entry.title,
        sw_version=(
            getattr(state, "software_version", None) or getattr(state, "version", None)
        ),
    )
    mac = getattr(state, "mac_address", None)
    if mac:
        info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac))}
    return info


class AnthemEntity(CoordinatorEntity[AnthemCoordinator]):
    """Base class for Anthem entities."""

    _attr_has_entity_name = True

    async def _send(self, command: Coroutine[Any, Any, Any]) -> None:
        """Await a receiver command, mapping library errors to HA errors."""
        try:
            await command
        except (
            CommandError,
            Gen1CommandError,
            TimeoutError,
            ConnectionError,
            OSError,
        ) as err:
            raise HomeAssistantError(
                f"Command to Anthem receiver failed: {err}"
            ) from err


class AnthemMainDeviceEntity(AnthemEntity):
    """Base class for entities that live on the main receiver device."""

    def __init__(
        self, coordinator: AnthemCoordinator, entry: AnthemConfigEntry
    ) -> None:
        """Attach to the main receiver device."""
        super().__init__(coordinator)
        self._attr_device_info = main_device_info(entry, coordinator.data)
