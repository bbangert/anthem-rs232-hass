"""Media player platform for the Anthem AVR RS-232 integration.

One media player entity per receiver zone (main zone + Zone 2). The entity
classes are split by protocol generation because the two generations expose
different input models: Gen 2 uses numeric input indexes with names queried
from the receiver, Gen 1 uses single-character source codes mapped through the
model's source table.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from serialkit import SerialKitError

from .anthem_rs232 import (
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    AudioListeningMode,
    gen1,
)
from .const import (
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    POWER_ON_BURST_COUNT,
    POWER_ON_CONFIRM_DELAY,
)
from .entity import AnthemEntity, main_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .anthem_rs232 import AnthemReceiver, Gen1Receiver
    from .coordinator import AnthemCoordinator
    from .data import AnthemConfigEntry

BASE_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

MAIN_ZONE = "main_zone"
ZONE_2 = "zone_2"

# Minimum zone count (per the model definition) for a Zone 2 entity.
MIN_ZONES_FOR_ZONE_2 = 2


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: AnthemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media player entities for each receiver zone."""
    data = entry.runtime_data
    coordinator = data.coordinator

    entities: list[MediaPlayerEntity]
    if data.generation == 1:
        entities = [AnthemGen1Zone(coordinator, entry, MAIN_ZONE)]
        gen1_receiver: Gen1Receiver = data.receiver
        if (
            gen1_receiver.model is None
            or gen1_receiver.model.zones >= MIN_ZONES_FOR_ZONE_2
        ):
            entities.append(AnthemGen1Zone(coordinator, entry, ZONE_2))
    else:
        entities = [AnthemGen2MainZone(coordinator, entry)]
        gen2_receiver: AnthemReceiver = data.receiver
        if (
            gen2_receiver.model is None
            or gen2_receiver.model.zones >= MIN_ZONES_FOR_ZONE_2
        ):
            entities.append(AnthemGen2Zone(coordinator, entry, ZONE_2))

    async_add_entities(entities)


def _sound_mode_name(mode: AudioListeningMode) -> str:
    """Return a human-readable name for an audio listening mode."""
    return mode.name.replace("_", " ").title()


class AnthemZone(AnthemEntity, MediaPlayerEntity):
    """A single zone of an Anthem receiver, either generation."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = BASE_FEATURES
    _attr_name = None
    # Serial state can be stale (a receiver in standby swallows frames);
    # the receiver has discrete power commands, so present separate
    # on/off controls instead of a state-guessing toggle.
    _attr_assumed_state = True

    _min_db: float
    _max_db: float
    _player: Any

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        zone_key: str,
    ) -> None:
        """Set up the unique id and the per-zone device."""
        super().__init__(coordinator)
        self._zone_key = zone_key
        model: str | None = entry.data.get(CONF_MODEL)
        main_device = (DOMAIN, entry.entry_id)
        if zone_key == MAIN_ZONE:
            self._attr_unique_id = f"{entry.entry_id}_main"
            self._attr_device_info = main_device_info(entry, coordinator.data)
        else:
            self._attr_unique_id = f"{entry.entry_id}_{zone_key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{zone_key}")},
                manufacturer=MANUFACTURER,
                model=model,
                name=f"{entry.title} Zone 2",
                via_device=main_device,
            )

    @property
    def _zone(self) -> Any:
        """Return the state dataclass for this zone (generation-specific)."""
        return getattr(self.coordinator.data, self._zone_key)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return on/off from the zone power state."""
        power = self._zone.power
        if power is None:
            return None
        return MediaPlayerState.ON if power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Map the zone volume in dB onto 0..1."""
        db = self._zone.volume
        if db is None:
            return None
        level = (db - self._min_db) / (self._max_db - self._min_db)
        return max(0.0, min(1.0, level))

    @property
    def is_volume_muted(self) -> bool | None:
        """Return the zone mute state."""
        return self._zone.mute

    def _level_to_db(self, volume: float) -> float:
        return self._min_db + volume * (self._max_db - self._min_db)

    async def async_turn_on(self) -> None:
        """Turn the zone on, bursting if the receiver stays in standby.

        A receiver in standby can swallow power-on frames without any
        error (the command is fire-and-forget on the wire). Send one
        power-on and confirm the zone reports on with a power query —
        one of the few queries Anthem answers even in standby. If it
        doesn't confirm within the delay, send a burst of power-ons
        back-to-back and confirm once more.
        """
        await self._send(self._player.power_on())
        await asyncio.sleep(POWER_ON_CONFIRM_DELAY)
        if await self._power_on_confirmed():
            return
        LOGGER.debug(
            "Zone power-on not confirmed within %.0f s; sending burst of %d",
            POWER_ON_CONFIRM_DELAY,
            POWER_ON_BURST_COUNT,
        )
        for _ in range(POWER_ON_BURST_COUNT):
            await self._send(self._player.power_on())
        await asyncio.sleep(POWER_ON_CONFIRM_DELAY)
        if await self._power_on_confirmed():
            return
        raise HomeAssistantError(
            "Receiver did not confirm power on after the power-on burst"
        )

    async def _power_on_confirmed(self) -> bool:
        """Return True if the zone reports powered on."""
        try:
            return bool(await self._player.query_power())
        except (SerialKitError, ConnectionError, OSError):
            return False

    async def async_turn_off(self) -> None:
        """Turn the zone off."""
        await self._send(self._player.power_off())

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the zone volume (the receiver rounds to its volume grid)."""
        await self._send(self._player.set_volume(self._level_to_db(volume)))

    async def async_volume_up(self) -> None:
        """Step the zone volume up."""
        await self._send(self._player.volume_up())

    async def async_volume_down(self) -> None:
        """Step the zone volume down."""
        await self._send(self._player.volume_down())

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the zone."""
        await self._send(self._player.mute_on() if mute else self._player.mute_off())


class AnthemGen2Zone(AnthemZone):
    """A zone of a Gen 2 receiver (MRX 310-1120, AVM 60)."""

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        zone_key: str,
    ) -> None:
        """Bind the zone player and volume range."""
        super().__init__(coordinator, entry, zone_key)
        receiver: AnthemReceiver = coordinator.receiver
        self._player = receiver.main if zone_key == MAIN_ZONE else receiver.zone_2
        model = receiver.model
        self._min_db = model.min_volume_db if model else MIN_VOLUME_DB
        self._max_db = model.max_volume_db if model else MAX_VOLUME_DB

    def _input_names(self) -> dict[int, str]:
        """Return input index -> display name, from the receiver's config."""
        return {
            index: cfg.long_name or cfg.short_name or f"Input {index}"
            for index, cfg in sorted(self.coordinator.data.inputs.items())
        }

    @property
    def source_list(self) -> list[str] | None:
        """Return the configured input names."""
        return list(self._input_names().values()) or None

    @property
    def source(self) -> str | None:
        """Return the name of the active input."""
        index = self._zone.input_index
        if index is None:
            return None
        return self._input_names().get(index, f"Input {index}")

    async def async_select_source(self, source: str) -> None:
        """Select an input by name."""
        for index, name in self._input_names().items():
            if name == source:
                await self._send(self._player.select_input(index))
                return
        raise HomeAssistantError(f"Unknown source: {source}")


class AnthemGen2MainZone(AnthemGen2Zone):
    """The main zone of a Gen 2 receiver, with audio listening modes."""

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
    ) -> None:
        """Add sound mode support on top of the base zone."""
        super().__init__(coordinator, entry, MAIN_ZONE)
        self._attr_supported_features = (
            BASE_FEATURES | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        )
        receiver: AnthemReceiver = coordinator.receiver
        modes: frozenset[AudioListeningMode] = frozenset(AudioListeningMode)
        if receiver.model is not None and receiver.model.audio_listening_modes:
            modes = receiver.model.audio_listening_modes
        self._sound_modes = {
            _sound_mode_name(mode): mode
            for mode in sorted(modes, key=lambda mode: mode.value)
        }
        self._attr_sound_mode_list = list(self._sound_modes)

    @property
    def sound_mode(self) -> str | None:
        """Return the active audio listening mode."""
        mode = self.coordinator.data.main_zone.audio_listening_mode
        return _sound_mode_name(mode) if mode is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the detected input signal formats."""
        main = self.coordinator.data.main_zone
        attrs: dict[str, Any] = {}
        if main.audio_input_format is not None:
            attrs["audio_input_format"] = main.audio_input_format.name.lower()
        if main.audio_input_channels is not None:
            attrs["audio_input_channels"] = main.audio_input_channels.name.lower()
        if main.video_input_resolution is not None:
            attrs["video_input_resolution"] = main.video_input_resolution.name.lower()
        return attrs

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Set the audio listening mode by name."""
        mode = self._sound_modes.get(sound_mode)
        if mode is None:
            raise HomeAssistantError(f"Unknown sound mode: {sound_mode}")
        await self._send(self._player.set_audio_listening_mode(mode))


class AnthemGen1Zone(AnthemZone):
    """A zone of a Gen 1 receiver (Statement, AVM 20-50v, MRX 300-700)."""

    def __init__(
        self,
        coordinator: AnthemCoordinator,
        entry: AnthemConfigEntry,
        zone_key: str,
    ) -> None:
        """Bind the zone player and volume range."""
        super().__init__(coordinator, entry, zone_key)
        receiver: Gen1Receiver = coordinator.receiver
        if zone_key == MAIN_ZONE:
            self._player = receiver.main
            self._min_db = gen1.MIN_MAIN_VOLUME_DB
            self._max_db = gen1.MAX_MAIN_VOLUME_DB
        else:
            self._player = receiver.zone_2
            self._min_db = gen1.MIN_ZONE2_VOLUME_DB
            self._max_db = gen1.MAX_ZONE2_VOLUME_DB

    def _source_names(self) -> dict[str, str]:
        """Return source code -> display name, with RS-232 renames applied."""
        receiver: Gen1Receiver = self.coordinator.receiver
        names = dict(receiver.model.source_map) if receiver.model else {}
        names.update(self.coordinator.data.source_names)
        return names

    @property
    def source_list(self) -> list[str] | None:
        """Return the known source names."""
        return list(self._source_names().values()) or None

    @property
    def source(self) -> str | None:
        """Return the name of the active source."""
        code = self._zone.source
        if code is None:
            return None
        return self._source_names().get(code, f"Source {code}")

    async def async_select_source(self, source: str) -> None:
        """Select a source by name."""
        for code, name in self._source_names().items():
            if name == source:
                await self._send(self._player.select_source(code))
                return
        raise HomeAssistantError(f"Unknown source: {source}")
