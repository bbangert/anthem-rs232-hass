"""Switch platform for the Anthem AVR RS-232 integration.

Anthem Room Correction and Dolby Volume (Gen 2), plus the receiver's 12 V
trigger outputs (both generations). Trigger switches only take effect when
the trigger is under RS-232/IP control on the receiver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from .entity import AnthemMainDeviceEntity

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AnthemCoordinator
    from .data import AnthemConfigEntry


@dataclass(frozen=True, kw_only=True)
class AnthemSwitchDescription(SwitchEntityDescription):
    """Describes an Anthem switch entity."""

    is_on_fn: Callable[[Any], bool | None]
    set_fn: Callable[[Any, bool], Coroutine[Any, Any, None]]


def _current_input_dolby_volume(state: Any) -> bool | None:
    index = state.main_zone.input_index
    if index is None:
        return None
    config = state.inputs.get(index)
    return config.dolby_volume if config is not None else None


ARC_SWITCH = AnthemSwitchDescription(
    key="arc",
    name="Anthem Room Correction",
    entity_category=EntityCategory.CONFIG,
    is_on_fn=lambda state: state.main_zone.arc_enabled,
    set_fn=lambda receiver, on: (
        receiver.main.arc_on() if on else receiver.main.arc_off()
    ),
)

DOLBY_VOLUME_SWITCH = AnthemSwitchDescription(
    key="dolby_volume",
    name="Dolby Volume",
    entity_category=EntityCategory.CONFIG,
    is_on_fn=_current_input_dolby_volume,
    set_fn=lambda receiver, on: receiver.set_dolby_volume(on),
)


def _trigger_description(trigger: int) -> AnthemSwitchDescription:
    return AnthemSwitchDescription(
        key=f"trigger_{trigger}",
        name=f"Trigger {trigger}",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda state, trigger=trigger: (
            state.triggers[trigger].on if trigger in state.triggers else None
        ),
        set_fn=lambda receiver, on, trigger=trigger: receiver.set_trigger(trigger, on),
    )


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AnthemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for the receiver."""
    data = entry.runtime_data
    descriptions: list[AnthemSwitchDescription] = []
    if data.generation != 1:
        model = data.receiver.model
        if model is None or model.arc:
            descriptions.append(ARC_SWITCH)
        descriptions.append(DOLBY_VOLUME_SWITCH)
    descriptions.extend(
        _trigger_description(trigger)
        for trigger in sorted(data.coordinator.data.triggers)
    )
    async_add_entities(
        AnthemSwitch(data.coordinator, entry, description)
        for description in descriptions
    )


class AnthemSwitch(AnthemMainDeviceEntity, SwitchEntity):
    """An on/off receiver setting."""

    entity_description: AnthemSwitchDescription

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        description: AnthemSwitchDescription,
    ) -> None:
        """Set up the entity from its description."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the current state from receiver state."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the setting on."""
        await self._send(
            self.entity_description.set_fn(self.coordinator.receiver, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the setting off."""
        await self._send(
            self.entity_description.set_fn(self.coordinator.receiver, False)
        )
