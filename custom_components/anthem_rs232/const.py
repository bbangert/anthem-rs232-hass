"""Constants for the Anthem AVR RS-232 integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "anthem_rs232"
MANUFACTURER = "Anthem"

CONF_GENERATION = "generation"
CONF_BAUD_RATE = "baud_rate"

RECONNECT_INITIAL_DELAY = 5.0
RECONNECT_MAX_DELAY = 300.0

# A receiver in standby can swallow power-on frames: confirm with a power
# query and resend, up to this many attempts.
POWER_ON_ATTEMPTS = 3
POWER_ON_CONFIRM_DELAY = 1.0

# Seconds to wait after a Gen 2 receiver reports power-on before running the
# full state re-query. (Gen 1 uses the library's DELAY_AFTER_POWER_ON.)
GEN2_POWER_ON_QUERY_DELAY = 1.0
