"""DataUpdateCoordinator wrapping an Anthem receiver serial connection."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .anthem_rs232 import AnthemReceiver, CommandError
from .const import DOMAIN, LOGGER, RECONNECT_INITIAL_DELAY, RECONNECT_MAX_DELAY

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .anthem_rs232 import Gen1Receiver, Gen1ReceiverState, ReceiverState
    from .data import AnthemConfigEntry

type AnthemState = ReceiverState | Gen1ReceiverState


class AnthemCoordinator(DataUpdateCoordinator[AnthemState]):
    """Push-based coordinator: state arrives via the receiver's auto-reports.

    The library keeps its own state current from unsolicited serial frames and
    notifies subscribers on every change, so there is no polling interval. The
    subscriber callback receives ``None`` when the serial connection drops, at
    which point a background task reconnects with exponential backoff.
    """

    config_entry: AnthemConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AnthemConfigEntry,
        receiver: AnthemReceiver | Gen1Receiver,
    ) -> None:
        """Initialize the coordinator around an unconnected receiver."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=None,
        )
        self.receiver = receiver
        self._unsubscribe: Callable[[], None] | None = None
        self._reconnect_task: asyncio.Task | None = None

    async def _async_setup(self) -> None:
        """Connect to the receiver and subscribe to state changes."""
        try:
            await self.receiver.connect()
            await self.receiver.query_state()
        except (ConnectionError, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Cannot connect to Anthem receiver: {err}") from err
        await self._query_extras()
        self._unsubscribe = self.receiver.subscribe(self._handle_state)

    async def _async_update_data(self) -> AnthemState:
        """Return the current state snapshot (first refresh only; push after)."""
        return self.receiver.state

    async def _query_extras(self) -> None:
        """Best-effort queries for values query_state() doesn't cover.

        The per-input processing settings (lip sync, Dolby Volume) are not
        part of the library's startup query round; populate them for the
        currently selected input. Receivers that don't implement them just
        error, which is fine.
        """
        receiver = self.receiver
        if not isinstance(receiver, AnthemReceiver):
            return
        for query in (
            receiver.query_lip_sync,
            receiver.query_dolby_volume,
            receiver.query_dolby_volume_leveler,
        ):
            try:
                await query()
            except CommandError, TimeoutError:
                continue

    async def async_shutdown(self) -> None:
        """Stop reconnecting and close the serial connection."""
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await self.receiver.disconnect()
        await super().async_shutdown()

    @callback
    def _handle_state(self, state: AnthemState | None) -> None:
        """Handle a state notification from the library's read loop."""
        if state is None:
            LOGGER.warning("Connection to Anthem receiver lost; will reconnect")
            self.async_set_update_error(ConnectionError("Connection to receiver lost"))
            self._schedule_reconnect()
            return
        self.async_set_updated_data(state)

    @callback
    def _schedule_reconnect(self) -> None:
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = self.config_entry.async_create_background_task(
            self.hass,
            self._reconnect(),
            name=f"{DOMAIN} reconnect",
        )

    async def _reconnect(self) -> None:
        delay = RECONNECT_INITIAL_DELAY
        while True:
            await asyncio.sleep(delay)
            try:
                await self.receiver.connect()
                await self.receiver.query_state()
            except (ConnectionError, TimeoutError, OSError) as err:
                LOGGER.debug("Reconnect failed (%s); retrying in %.0f s", err, delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY)
                continue
            LOGGER.info("Reconnected to Anthem receiver")
            await self._query_extras()
            self.async_set_updated_data(self.receiver.state)
            return
