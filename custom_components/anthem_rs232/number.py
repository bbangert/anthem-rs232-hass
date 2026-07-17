"""Number platform for the Anthem AVR RS-232 integration.

Tone controls (bass/treble) plus the per-input processing values (lip sync
delay, Dolby Volume Leveler). The per-input entities target the currently
selected input, matching the receiver's ``xx=00`` command semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS, EntityCategory, UnitOfTime

from .anthem_rs232 import (
    LIP_SYNC_STEP_MS,
    MAX_DOLBY_VOLUME_LEVELER,
    MAX_LIP_SYNC_MS,
    MIN_DOLBY_VOLUME_LEVELER,
    MIN_LIP_SYNC_MS,
    gen1,
)
from .entity import AnthemMainDeviceEntity

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AnthemCoordinator
    from .data import AnthemConfigEntry


@dataclass(frozen=True, kw_only=True)
class AnthemNumberDescription(NumberEntityDescription):
    """Describes an Anthem number entity."""

    value_fn: Callable[[Any], float | None]
    set_fn: Callable[[Any, float], Coroutine[Any, Any, None]]


def _current_input_setting(state: Any, attr: str) -> Any:
    """Read a per-input setting for the currently selected main zone input."""
    index = state.main_zone.input_index
    if index is None:
        return None
    config = state.inputs.get(index)
    return getattr(config, attr) if config is not None else None


GEN2_NUMBERS: tuple[AnthemNumberDescription, ...] = (
    AnthemNumberDescription(
        key="bass",
        name="Bass",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.main_zone.bass,
        set_fn=lambda receiver, value: receiver.main.set_bass(value),
    ),
    AnthemNumberDescription(
        key="treble",
        name="Treble",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.main_zone.treble,
        set_fn=lambda receiver, value: receiver.main.set_treble(value),
    ),
    AnthemNumberDescription(
        key="lip_sync",
        name="Lip sync",
        native_min_value=MIN_LIP_SYNC_MS,
        native_max_value=MAX_LIP_SYNC_MS,
        native_step=LIP_SYNC_STEP_MS,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: _current_input_setting(state, "lip_sync_ms"),
        set_fn=lambda receiver, value: receiver.set_lip_sync(int(value)),
    ),
    AnthemNumberDescription(
        key="dolby_volume_leveler",
        name="Dolby Volume Leveler",
        native_min_value=MIN_DOLBY_VOLUME_LEVELER,
        native_max_value=MAX_DOLBY_VOLUME_LEVELER,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: _current_input_setting(state, "dolby_volume_leveler"),
        set_fn=lambda receiver, value: receiver.set_dolby_volume_leveler(int(value)),
    ),
)

GEN1_NUMBERS: tuple[AnthemNumberDescription, ...] = (
    AnthemNumberDescription(
        key="bass",
        name="Bass",
        native_min_value=gen1.const.TONE_MIN_DB,
        native_max_value=gen1.const.TONE_MAX_DB,
        native_step=gen1.const.TONE_STEP,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.main_zone.bass_master,
        set_fn=lambda receiver, value: receiver.main.set_master_bass(value),
    ),
    AnthemNumberDescription(
        key="treble",
        name="Treble",
        native_min_value=gen1.const.TONE_MIN_DB,
        native_max_value=gen1.const.TONE_MAX_DB,
        native_step=gen1.const.TONE_STEP,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda state: state.main_zone.treble_master,
        set_fn=lambda receiver, value: receiver.main.set_master_treble(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AnthemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for the receiver."""
    data = entry.runtime_data
    descriptions = GEN1_NUMBERS if data.generation == 1 else GEN2_NUMBERS
    async_add_entities(
        AnthemNumber(data.coordinator, entry, description)
        for description in descriptions
    )


class AnthemNumber(AnthemMainDeviceEntity, NumberEntity):
    """A numeric receiver setting."""

    entity_description: AnthemNumberDescription

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        description: AnthemNumberDescription,
    ) -> None:
        """Set up the entity from its description."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the current value from receiver state."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Send the new value to the receiver."""
        await self._send(
            self.entity_description.set_fn(self.coordinator.receiver, value)
        )
