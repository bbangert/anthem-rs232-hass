"""Sensor platform for the Anthem AVR RS-232 integration.

Diagnostic sensors: the configured serial port (both generations) and the
detected input signal info (Gen 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_PORT, EntityCategory

from .entity import AnthemMainDeviceEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AnthemCoordinator
    from .data import AnthemConfigEntry


@dataclass(frozen=True, kw_only=True)
class AnthemSensorDescription(SensorEntityDescription):
    """Describes an Anthem sensor entity."""

    value_fn: Callable[[AnthemConfigEntry, Any], Any]
    requires_power: bool = True


def _enum_label(member: Any) -> str | None:
    return member.name.replace("_", " ").title() if member is not None else None


SERIAL_PORT_SENSOR = AnthemSensorDescription(
    key="serial_port",
    name="Serial port",
    icon="mdi:serial-port",
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=lambda entry, state: entry.data[CONF_PORT],  # noqa: ARG005
    requires_power=False,
)

GEN2_SENSORS: tuple[AnthemSensorDescription, ...] = (
    AnthemSensorDescription(
        key="audio_input_format",
        name="Audio input format",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entry, state: (  # noqa: ARG005
            state.main_zone.audio_input_name
            or _enum_label(state.main_zone.audio_input_format)
        ),
    ),
    AnthemSensorDescription(
        key="audio_input_channels",
        name="Audio input channels",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entry, state: (  # noqa: ARG005
            _enum_label(state.main_zone.audio_input_channels)
        ),
    ),
    AnthemSensorDescription(
        key="audio_input_rate",
        name="Audio input rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entry, state: state.main_zone.audio_input_rate,  # noqa: ARG005
    ),
    AnthemSensorDescription(
        key="video_input_resolution",
        name="Video input resolution",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda entry, state: (  # noqa: ARG005
            _enum_label(state.main_zone.video_input_resolution)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AnthemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for the receiver."""
    data = entry.runtime_data
    descriptions: list[AnthemSensorDescription] = [SERIAL_PORT_SENSOR]
    if data.generation != 1:
        descriptions.extend(GEN2_SENSORS)
    async_add_entities(
        AnthemSensor(data.coordinator, entry, description)
        for description in descriptions
    )


class AnthemSensor(AnthemMainDeviceEntity, SensorEntity):
    """A read-only receiver value."""

    entity_description: AnthemSensorDescription

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        description: AnthemSensorDescription,
    ) -> None:
        """Set up the entity from its description."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._entry = entry
        self._requires_receiver_power = description.requires_power
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self._entry, self.coordinator.data)
