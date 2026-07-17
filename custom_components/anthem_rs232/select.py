"""Select platform for the Anthem AVR RS-232 integration (Gen 2 only).

Front panel brightness, Dolby dynamic range, and the speaker profile
(with profile names read from the receiver where the model supports them).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .anthem_rs232 import DolbyDynamicRange, FrontPanelBrightness
from .entity import AnthemMainDeviceEntity

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import AnthemCoordinator
    from .data import AnthemConfigEntry

SPEAKER_PROFILE_COUNT = 4


@dataclass(frozen=True, kw_only=True)
class AnthemSelectDescription(SelectEntityDescription):
    """Describes an Anthem select entity."""

    options_fn: Callable[[Any], list[str]]
    current_fn: Callable[[Any], str | None]
    select_fn: Callable[[Any, Any, str], Coroutine[Any, Any, None]]


def _enum_label(member: Any) -> str:
    return member.name.replace("_", " ").title()


def _profile_label(state: Any, profile: int) -> str:
    return state.speaker_profile_names.get(profile) or f"Profile {profile}"


def _select_profile(receiver: Any, state: Any, option: str) -> Any:
    for profile in range(1, SPEAKER_PROFILE_COUNT + 1):
        if _profile_label(state, profile) == option:
            return receiver.set_speaker_profile(profile)
    raise HomeAssistantError(f"Unknown speaker profile: {option}")


BRIGHTNESS_SELECT = AnthemSelectDescription(
    key="front_panel_brightness",
    name="Front panel brightness",
    entity_category=EntityCategory.CONFIG,
    options_fn=lambda state: [_enum_label(m) for m in FrontPanelBrightness],  # noqa: ARG005
    current_fn=lambda state: (
        _enum_label(state.front_panel_brightness)
        if state.front_panel_brightness is not None
        else None
    ),
    select_fn=lambda receiver, state, option: (  # noqa: ARG005
        receiver.set_front_panel_brightness(
            FrontPanelBrightness[option.replace(" ", "_").upper()]
        )
    ),
)

DYNAMIC_RANGE_SELECT = AnthemSelectDescription(
    key="dolby_dynamic_range",
    name="Dolby dynamic range",
    entity_category=EntityCategory.CONFIG,
    options_fn=lambda state: [_enum_label(m) for m in DolbyDynamicRange],  # noqa: ARG005
    current_fn=lambda state: (
        _enum_label(state.main_zone.dolby_dynamic_range)
        if state.main_zone.dolby_dynamic_range is not None
        else None
    ),
    select_fn=lambda receiver, state, option: (  # noqa: ARG005
        receiver.main.set_dolby_dynamic_range(
            DolbyDynamicRange[option.replace(" ", "_").upper()]
        )
    ),
)

SPEAKER_PROFILE_SELECT = AnthemSelectDescription(
    key="speaker_profile",
    name="Speaker profile",
    entity_category=EntityCategory.CONFIG,
    options_fn=lambda state: [
        _profile_label(state, profile)
        for profile in range(1, SPEAKER_PROFILE_COUNT + 1)
    ],
    current_fn=lambda state: (
        _profile_label(state, state.speaker_profile)
        if state.speaker_profile is not None
        else None
    ),
    select_fn=_select_profile,
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AnthemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for the receiver (Gen 2 only)."""
    data = entry.runtime_data
    if data.generation == 1:
        return
    descriptions = [BRIGHTNESS_SELECT, DYNAMIC_RANGE_SELECT]
    model = data.receiver.model
    # The x10 series doesn't implement speaker profiles (SSP/SPN).
    if model is None or "SSP" not in model.unsupported_startup_queries:
        descriptions.append(SPEAKER_PROFILE_SELECT)
    async_add_entities(
        AnthemSelect(data.coordinator, entry, description)
        for description in descriptions
    )


class AnthemSelect(AnthemMainDeviceEntity, SelectEntity):
    """A multi-choice receiver setting."""

    entity_description: AnthemSelectDescription

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        description: AnthemSelectDescription,
    ) -> None:
        """Set up the entity from its description."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def options(self) -> list[str]:
        """Return the selectable options."""
        return self.entity_description.options_fn(self.coordinator.data)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self.entity_description.current_fn(self.coordinator.data)

    async def async_select_option(self, option: str) -> None:
        """Send the selected option to the receiver."""
        await self._send(
            self.entity_description.select_fn(
                self.coordinator.receiver, self.coordinator.data, option
            )
        )
