"""DataUpdateCoordinator wrapping an Anthem receiver serial connection.

Reconnect is owned by the vendored serialkit runtime, not this coordinator: on
a dropped link the library fails in-flight work, notifies subscribers with
``None``, backs off, reopens, re-runs the connect handshake, and notifies
again. The coordinator reflects those notifications into HA and re-queries the
full state once a reconnect delivers a fresh snapshot.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from serialkit import ConnectionLostError, SerialKitError

from .anthem_rs232 import AnthemReceiver, gen1
from .const import (
    DOMAIN,
    GEN2_POWER_ON_QUERY_DELAY,
    LOGGER,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .anthem_rs232 import Gen1Receiver, Gen1ReceiverState, ReceiverState
    from .data import AnthemConfigEntry

type AnthemState = ReceiverState | Gen1ReceiverState


def receiver_power_is_on(state: AnthemState) -> bool:
    """Return True when any zone of the receiver is powered on."""
    power = getattr(state, "power", None)  # Gen 2 chassis aggregate
    if power is not None:
        return power
    zone_2 = getattr(state, "zone_2", None)
    return bool(state.main_zone.power or (zone_2 is not None and zone_2.power))


def receiver_power_known_off(state: AnthemState) -> bool:
    """Return True when the receiver definitively reports standby.

    Distinct from ``not receiver_power_is_on``: unknown power (all zones
    ``None``) is not "known off", so a receiver whose power state hasn't
    been read yet still gets the full state query.
    """
    power = getattr(state, "power", None)  # Gen 2 chassis aggregate
    if power is not None:
        return not power
    zone_2 = getattr(state, "zone_2", None)
    zones = [state.main_zone.power, zone_2.power if zone_2 is not None else None]
    known = [z for z in zones if z is not None]
    return bool(known) and not any(known)


class AnthemCoordinator(DataUpdateCoordinator[AnthemState]):
    """Push-based coordinator: state arrives via the receiver's auto-reports.

    The library keeps its own state current from unsolicited serial frames and
    notifies subscribers on every change, so there is no polling interval. The
    subscriber callback receives ``None`` when the serial connection drops;
    serialkit reconnects on its own and the coordinator re-queries the full
    state when the fresh snapshot arrives.
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
        self._refresh_task: asyncio.Task | None = None
        self._last_power: bool | None = None
        # Gen 1 units document a settle time before accepting commands
        # after power-on; Gen 2 only needs a moment.
        self._power_on_query_delay = (
            GEN2_POWER_ON_QUERY_DELAY
            if isinstance(receiver, AnthemReceiver)
            else gen1.DELAY_AFTER_POWER_ON
        )

    async def _async_setup(self) -> None:
        """Connect to the receiver and subscribe to state changes."""
        try:
            await self.receiver.connect()
            await self._refresh_full_state()
        except (SerialKitError, ConnectionError, OSError) as err:
            raise UpdateFailed(f"Cannot connect to Anthem receiver: {err}") from err
        self._last_power = receiver_power_is_on(self.receiver.state)
        self._unsubscribe = self.receiver.subscribe(self._handle_state)

    async def _refresh_full_state(self) -> None:
        """Run query_state + extras, unless the receiver is in standby.

        In standby only identification and power commands are answered
        (and some firmwares answer everything else with noise or bare
        terminators), so the full round is 30+ queries each eating a
        timeout. Skip it; the power-on refresh repopulates on wake.
        """
        if receiver_power_known_off(self.receiver.state):
            LOGGER.debug(
                "Receiver is in standby; deferring the full state query until power-on"
            )
            return
        await self.receiver.query_state()
        await self._query_extras()

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
            except SerialKitError:
                continue

    async def async_shutdown(self) -> None:
        """Unsubscribe and close the serial connection (serialkit stops)."""
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            self._refresh_task = None
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await self.receiver.disconnect()
        await super().async_shutdown()

    @callback
    def _handle_state(self, state: AnthemState | None) -> None:
        """Handle a state notification from the library's read loop.

        ``None`` means the serial link dropped; serialkit reconnects on its
        own, so we only surface the outage. When the fresh snapshot arrives
        after a reconnect we re-query the full state (serialkit's on_connect
        only identifies + enables auto-reports).
        """
        if state is None:
            LOGGER.warning(
                "Connection to Anthem receiver lost; serialkit will reconnect"
            )
            self.async_set_update_error(
                ConnectionLostError("Connection to receiver lost")
            )
            return
        reconnected = not self.last_update_success
        power = receiver_power_is_on(state)
        turned_on = power and self._last_power is False
        self._last_power = power
        if reconnected:
            # serialkit reopened the link; repopulate the full state.
            self._schedule_state_refresh(delay=0.0)
        elif turned_on:
            # Most settings can't be queried in standby, so re-query the full
            # state once the unit is awake -- whether we powered it on or the
            # front panel / IR remote did.
            self._schedule_state_refresh(delay=self._power_on_query_delay)
        self.async_set_updated_data(state)

    @callback
    def _schedule_state_refresh(self, *, delay: float) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        self._refresh_task = self.config_entry.async_create_background_task(
            self.hass,
            self._refresh_after(delay),
            name=f"{DOMAIN} state refresh",
        )

    async def _refresh_after(self, delay: float) -> None:
        """Re-query the full state (after an optional settle delay)."""
        if delay:
            await asyncio.sleep(delay)
        try:
            await self._refresh_full_state()
        except (SerialKitError, ConnectionError, OSError) as err:
            LOGGER.debug("State refresh failed: %s", err)
            return
        self.async_set_updated_data(self.receiver.state)
