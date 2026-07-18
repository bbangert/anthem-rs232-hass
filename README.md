# Anthem AVR RS-232 for Home Assistant

A [HACS](https://hacs.xyz) custom integration for Anthem receivers and
processors controlled over **RS-232**, built on the
[anthem-rs232](https://github.com/home-assistant-libs/anthem-rs232) library.

Unlike the core `anthemav` integration (which uses the IP control interface),
this integration talks to the serial port — including older units that have no
network control at all.

## Supported hardware

| Model(s)                   | Series      | Protocol |
|----------------------------|-------------|----------|
| Statement D1               | d1          | Gen 1    |
| Statement D2, D2v          | d2 / d2v    | Gen 1    |
| AVM 20, AVM 30, AVM 40     | avm20–avm40 | Gen 1    |
| AVM 50, AVM 50v            | avm50       | Gen 1    |
| MRX 300, MRX 500, MRX 700  | mrx         | Gen 1    |
| MRX 310, MRX 510, MRX 710  | mrx1        | Gen 2    |
| MRX 520, MRX 720, MRX 1120 | mrx2        | Gen 2    |
| AVM 60                     | avm60       | Gen 2    |

Not supported: STR amplifiers, Gen 4 (MRX 540/740/1140, AVM 70/90 — different
protocol), and the IP-only MRX SLM.

## Installation

### HACS (recommended)

1. In HACS, add `https://github.com/bbangert/anthem-rs232-hass` as a
   **custom repository** (category: *Integration*).
2. Install **Anthem AVR RS-232** and restart Home Assistant.

### Manual

Copy `custom_components/anthem_rs232/` into your Home Assistant
`config/custom_components/` directory and restart.

> [!NOTE]
> The [anthem-rs232](https://github.com/home-assistant-libs/anthem-rs232)
> library has no PyPI release yet, so its package is **vendored** into the
> integration (`custom_components/anthem_rs232/anthem_rs232/`, currently at
> upstream commit `2a499b9`). The only
> requirement Home Assistant installs from PyPI is
> [serialx](https://pypi.org/project/serialx/), the async serial transport.
> Once the library is released on PyPI, the vendored copy will be replaced by
> a pinned requirement.

## Configuration

Add the integration via **Settings → Devices & Services → Add Integration →
Anthem AVR RS-232**. The only input is the serial port, picked from a
dropdown that lists the host's local serial ports (e.g. `/dev/ttyUSB0`)
together with any ESPHome serial proxy ports (requires Home Assistant
2026.7 or later).

The selected port is probed automatically (Gen 2 @ 115200, then Gen 1 @ 9600
and 19200 baud) to detect the model, protocol generation, and baud rate — no
other settings needed. Wiring is a straight-through DB-9 cable (pin 2 = Tx,
3 = Rx, 5 = GND).

## Entities

One `media_player` per zone (main zone, plus Zone 2 where the model has one):

- **Power** on/off per zone
- **Volume** set/step/mute (mapped onto the receiver's dB range)
- **Source selection** — Gen 2 input names are read from the receiver
  (`ISN?`/`ILN?`); Gen 1 uses the model's source table plus any RS-232 renames
- **Sound mode** (Gen 2 main zone) — Anthem audio listening modes
  (AnthemLogic, Dolby Surround, DTS Neo, …)
- Detected signal info (audio format/channels, video resolution) as state
  attributes on the Gen 2 main zone

Plus, on the receiver device:

| Platform | Entities |
|---|---|
| `number` | Bass, Treble; **Lip sync** (0–150 ms) and **Dolby Volume Leveler** (0–9) for the current input (Gen 2) |
| `switch` | Anthem Room Correction, **Dolby Volume** for the current input (Gen 2); 12 V triggers (both generations) |
| `select` | Front panel brightness, Dolby dynamic range, speaker profile with names read from the receiver (Gen 2) |
| `sensor` | Serial port (diagnostic, both generations); audio input format/channels/rate and video input resolution (Gen 2, diagnostic) |

Settings entities appear in the device page's *Configuration* and
*Diagnostic* sections. Trigger switches only take effect when the trigger is
set to RS-232/IP control on the receiver. The device also reports the
receiver's software version and (Gen 2) MAC address.

While the receiver is in **standby**, the settings and signal entities show
as unavailable (Anthem only answers identification and power commands in
standby); the media players and the serial port sensor stay available. When
the receiver powers on — from Home Assistant, the front panel, or the IR
remote — the integration re-queries the full state so every entity
repopulates (after the wake-up settle time on Gen 1 units).

State is **push-based**: the integration enables the receiver's serial
auto-reports (`ECH1` on Gen 2, `SST1` on Gen 1), so front-panel, IR, and app
changes appear in Home Assistant immediately. If the serial link drops, the
integration reconnects automatically with backoff.

## License

MIT
