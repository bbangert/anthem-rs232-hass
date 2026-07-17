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
> upstream commit `a08d257`). The only
> requirement Home Assistant installs from PyPI is
> [serialx](https://pypi.org/project/serialx/), the async serial transport.
> Once the library is released on PyPI, the vendored copy will be replaced by
> a pinned requirement.

## Configuration

Add the integration via **Settings → Devices & Services → Add Integration →
Anthem AVR RS-232**. The only input is the serial port:

- a local device such as `/dev/ttyUSB0`, or
- any [serialx](https://github.com/puddly/serialx) URL, e.g.
  `socket://192.168.1.50:4999` (serial-over-TCP bridge) or `esphome://my-node`
  for an ESPHome UART proxy.

The port is probed automatically (Gen 2 @ 115200, then Gen 1 @ 9600 and
19200 baud) to detect the model, protocol generation, and baud rate — no other
settings needed. Wiring is a straight-through DB-9 cable (pin 2 = Tx,
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

State is **push-based**: the integration enables the receiver's serial
auto-reports (`ECH1` on Gen 2, `SST1` on Gen 1), so front-panel, IR, and app
changes appear in Home Assistant immediately. If the serial link drops, the
integration reconnects automatically with backoff.

## License

MIT
