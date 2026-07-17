"""Custom types for the Anthem AVR RS-232 integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .anthem_rs232 import AnthemReceiver, Gen1Receiver
    from .coordinator import AnthemCoordinator

type AnthemConfigEntry = ConfigEntry[AnthemData]


@dataclass
class AnthemData:
    """Runtime data for an Anthem AVR config entry."""

    coordinator: AnthemCoordinator
    receiver: AnthemReceiver | Gen1Receiver
    generation: int
