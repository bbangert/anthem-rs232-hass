"""Constants for the Anthem AVR RS-232 integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "anthem_rs232"
MANUFACTURER = "Anthem"

CONF_GENERATION = "generation"
CONF_BAUD_RATE = "baud_rate"

# Reconnect/backoff is owned by the vendored serialkit runtime, not this
# integration, so no reconnect-delay constants live here.

# A receiver in standby can swallow power-on frames. Send one power-on;
# if the zone doesn't confirm on within POWER_ON_CONFIRM_DELAY, send
# POWER_ON_BURST_COUNT power-ons back-to-back and confirm once more.
POWER_ON_CONFIRM_DELAY = 1.0
POWER_ON_BURST_COUNT = 3

# Seconds to wait after a Gen 2 receiver reports power-on before running the
# full state re-query. (Gen 1 uses the library's DELAY_AFTER_POWER_ON.)
GEN2_POWER_ON_QUERY_DELAY = 1.0
