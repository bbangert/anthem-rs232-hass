"""Base entity for the Anthem AVR RS-232 integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AnthemCoordinator


class AnthemEntity(CoordinatorEntity[AnthemCoordinator]):
    """Base class for Anthem entities."""

    _attr_has_entity_name = True
