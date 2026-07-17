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
