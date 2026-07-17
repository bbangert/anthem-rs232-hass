"""The Anthem AVR RS-232 integration.

Integrates Anthem receivers and processors connected over RS-232 into Home
Assistant, using the ``anthem-rs232`` library. Supports both the Gen 2
protocol (MRX 310-1120, AVM 60) and the Gen 1 protocol (Statement D1/D2/D2v,
AVM 20-50v, MRX 300/500/700).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_MODEL, CONF_PORT, Platform

from .anthem_rs232 import AnthemReceiver, Gen1Receiver, gen1, models
from .const import CONF_BAUD_RATE, CONF_GENERATION
from .coordinator import AnthemCoordinator
from .data import AnthemData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import AnthemConfigEntry

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def _build_receiver(entry: AnthemConfigEntry) -> AnthemReceiver | Gen1Receiver:
    """Build the right receiver class for the probed protocol generation."""
    port: str = entry.data[CONF_PORT]
    generation: int = entry.data[CONF_GENERATION]
    model_name = (entry.data.get(CONF_MODEL) or "").strip().upper()

    if generation == 1:
        gen1_model = next(
            (m for m in gen1.ALL_MODELS if m.name.upper() == model_name),
            gen1.OTHER,
        )
        return Gen1Receiver(
            port,
            model=gen1_model,
            baud_rate=entry.data.get(CONF_BAUD_RATE),
        )

    gen2_model = next(
        (m for m in models.ALL_MODELS if m.name.upper() == model_name),
        models.OTHER,
    )
    return AnthemReceiver(port, model=gen2_model)


async def async_setup_entry(hass: HomeAssistant, entry: AnthemConfigEntry) -> bool:
    """Set up an Anthem receiver from a config entry."""
    receiver = _build_receiver(entry)
    coordinator = AnthemCoordinator(hass, entry, receiver)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AnthemData(
        coordinator=coordinator,
        receiver=receiver,
        generation=entry.data[CONF_GENERATION],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AnthemConfigEntry) -> bool:
    """Unload a config entry (the coordinator closes the serial connection)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
