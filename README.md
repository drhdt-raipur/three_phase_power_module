# 3-Phase PWM Controller - Arduino UNO R4 WiFi + Python GUI

[![Arduino](https://img.shields.io/badge/Board-Arduino%20UNO%20R4%20WiFi-00979D?logo=arduino&logoColor=white)](https://store.arduino.cc/products/uno-r4-wifi)
[![MCU](https://img.shields.io/badge/MCU-Renesas%20RA4M1%20%4048%20MHz-blue)](https://www.renesas.com/en/products/microcontrollers-microprocessors/ra-cortex-m-mcus/ra4m1-32-bit-microcontrollers-48mhz-up-256kb-flash-lowest-pin-count)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Generate **three independent, phase-shifted PWM signals** at up to 200 kHz from a single Arduino UNO R4 WiFi board — controlled live from a Python GUI over USB serial. Built on the RA4M1's dedicated General PWM Timer (GPT) hardware channels, the signals run entirely in silicon with **zero CPU overhead**.

```
D3  ──►  Channel A   0°   ┐
D6  ──►  Channel B  120°  ├─  20 kHz · 50% duty · adjustable via GUI
D9  ──►  Channel C  240°  ┘
```

---

## Table of Contents

- [Features](#features)
- [Demo](#demo)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
  - [1. Flash the Arduino](#1-flash-the-arduino)
  - [2. Run the Python GUI](#2-run-the-python-gui)
- [Pin Mapping](#pin-mapping)
- [Serial Protocol](#serial-protocol)
  - [Commands](#commands)
  - [JSON Status Response](#json-status-response)
- [Firmware Architecture](#firmware-architecture)
  - [PWM Library](#pwm-library)
  - [Phase Generation — Staggered Start Method](#phase-generation--staggered-start-method)
  - [Duty Cycle — Live Register Update](#duty-cycle--live-register-update)
  - [Standalone Operation](#standalone-operation)
- [Python GUI Architecture](#python-gui-architecture)
  - [SerialWorker — Communication Layer](#serialworker--communication-layer)
  - [PhaseDiagram — Visualisation Canvas](#phasediagram--visualisation-canvas)
  - [WaveformView — Waveform Preview Canvas](#waveformview--waveform-preview-canvas)
  - [State Synchronisation on Connect](#state-synchronisation-on-connect)
- [RA4M1 Hardware Reference](#ra4m1-hardware-reference)
  - [GPT Timer Registers](#gpt-timer-registers)
  - [GTIOR Output Mode Table](#gtior-output-mode-table)
  - [Pin Function Select (PmnPFS)](#pin-function-select-pmnpfs)
- [Key Design Decisions](#key-design-decisions)
- [Applications](#applications)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Feature | Detail |
|---|---|
| **Output frequency** | 100 Hz – 200 kHz (default 20 kHz) |
| **Duty cycle** | 0.1 % – 99.9 % (default 50 %) |
| **Phase offset** | 0° – 359° per channel, 1° resolution |
| **CPU load** | 0 % in `loop()` — pure hardware GPT timers |
| **Standalone** | Runs without USB / GUI — signals live on power-up |
| **Live duty update** | `pulse_perc()` — no timer restart, no glitch |
| **GUI sync** | JSON status on connect — sliders always show real hardware state |
| **Presets** | 3-phase 120°, 3-phase 90°, in-phase, half-bridge |
| **Serial protocol** | Plain ASCII, newline-terminated, 115200 baud |
| **Python dependency** | `pyserial` only — everything else is stdlib |

---

## Demo

```
Board powers up  →  D3 / D6 / D9 immediately output 20 kHz PWM
Open GUI         →  sliders auto-sync to hardware state via GET STATUS
Move slider      →  SET FREQ / SET DUTY / SET PHASE_B / SET PHASE_C sent
Close GUI        →  PWM keeps running at last settings
```

> **Tip:** You can verify the output with any logic analyser or oscilloscope.
> At 20 kHz and 50 % duty, each channel has a 25 µs HIGH pulse in a 50 µs period.

---

## Hardware Requirements

| Item | Notes |
|---|---|
| Arduino UNO R4 WiFi | The firmware uses the RA4M1 `pwm.h` library — **not** compatible with UNO R3 or R4 Minima without modification |
| USB-A to USB-C cable | For programming and serial communication |
| Oscilloscope / Logic analyser | To verify waveforms on D3, D6, D9 (optional but recommended) |

---

## Software Requirements

### Arduino Side

- **Arduino IDE 2.x** or Arduino CLI
- **Arduino UNO R4 Board Package** (`arduino:renesas_uno` ≥ 1.1.0)
  - Install via `Tools → Board → Board Manager → search "UNO R4"`
- No additional libraries required — `pwm.h` is included in the R4 board package

### Python Side

- **Python 3.8+**
- **pyserial**

```bash
pip install pyserial
```

> All other modules (`tkinter`, `threading`, `json`, `math`, `time`) are Python standard library.

---

## Repository Structure

```
3phase-pwm-controller/
│
├── firmware/
│   └── pwm_final/
│       └── pwm_final.ino          # Arduino firmware — flash this to the board
│
├── gui/
│   └── pwm_gui.py                 # Python GUI — run this on your PC
│
├── docs/
│   └── PROJECT_DOCUMENT.pptx      # Project Documentation
│
└── README.md
```

---

## Quick Start

### 1. Flash the Arduino

1. Open `firmware/pwm_final/pwm_final.ino` in Arduino IDE 2.x
2. Select **Tools → Board → Arduino UNO R4 WiFi**
3. Select the correct COM port under **Tools → Port**
4. Click **Upload** (Ctrl+U)
5. The board will reset and immediately begin outputting PWM on **D3**, **D6**, and **D9**

> You do **not** need to open the Serial Monitor. PWM starts on power-up.

### 2. Run the Python GUI

```bash
# Clone the repository
git clone https://github.com/<your-username>/3phase-pwm-controller.git
cd 3phase-pwm-controller

# Install the only dependency
pip install pyserial

# Launch the GUI
python gui/pwm_gui.py
```

1. Select the Arduino's COM port from the dropdown
2. Click **Connect**
3. The GUI sends `GET STATUS` after 600 ms and syncs all sliders to the hardware
4. Adjust frequency, duty cycle, or phase — changes are sent immediately on **SEND**
5. Use presets for common configurations

---

## Pin Mapping

Verified against RA4M1 Hardware Manual **Tables 19.10 and 19.11** (Rev. 1.10, Sep 2023).

| Arduino Pin | RA4M1 Port | PSEL Value | GPT Signal | GPT Channel | Output |
|---|---|---|---|---|---|
| **D3** | P402 | `00011b` | GTIOC6B | GPT ch 6 | B |
| **D6** | P405 | `00011b` | GTIOC1A | GPT ch 1 | A |
| **D9** | P303 | `00011b` | GTIOC7B | GPT ch 7 | B |

> **Why these pins?** Each must map to a **different GPT channel number**. Using two pins on the same channel would allow only one to be active at a time. D3, D6, and D9 map to GPT6, GPT1, and GPT7 — three completely independent timers.

---

## Serial Protocol

Communication uses **115200 baud, 8N1, newline-terminated ASCII** over the USB serial port.

### Commands

| Command | Example | Action | Constraints |
|---|---|---|---|
| `SET FREQ <hz>` | `SET FREQ 20000` | Change frequency, restart timers | 100 – 200000 |
| `SET DUTY <pct>` | `SET DUTY 50` | Update duty cycle live (no restart) | 0.1 – 99.9 |
| `SET PHASE_B <deg>` | `SET PHASE_B 120` | Set Channel B phase, restart | 0 – 359.9 |
| `SET PHASE_C <deg>` | `SET PHASE_C 240` | Set Channel C phase, restart | 0 – 359.9 |
| `GET STATUS` | `GET STATUS` | Request full JSON status | — |
| `START` | `START` | Re-apply settings and start timers | — |
| `STOP` | `STOP` | Stop all timers, pins go LOW | — |

Every command replies with a plain `OK ...` confirmation followed immediately by a full JSON status object.

**Error responses** begin with `ERR`:
```
ERR freq 100-200000 Hz
ERR duty 0.1-99.9 %
ERR phase_b 0-359.9 degrees
ERR unknown: <command>
```

### JSON Status Response

Sent after every command and in response to `GET STATUS`:

```json
{
  "freq": 20000.0,
  "duty": 50.0,
  "phase_b": 120.0,
  "phase_c": 240.0,
  "running": true
}
```

| Field | Type | Description |
|---|---|---|
| `freq` | float | Current output frequency in Hz |
| `duty` | float | Current duty cycle in percent |
| `phase_b` | float | Channel B phase offset in degrees |
| `phase_c` | float | Channel C phase offset in degrees |
| `running` | bool | `true` if timers are active, `false` if stopped |

---

## Firmware Architecture

### PWM Library

The firmware uses the `pwm.h` library included in the Arduino UNO R4 board package. This library wraps the RA4M1 GPT hardware timers and provides a clean two-method interface:

```cpp
PwmOut pwm(D3);
pwm.begin(freq_hz, duty_percent);   // start timer
pwm.pulse_perc(new_duty);           // update duty live
pwm.end();                          // stop timer
```

Three independent `PwmOut` objects are declared globally — one per output pin — each claiming a separate GPT channel from the RA4M1's eight available channels.

### Phase Generation — Staggered Start Method

The RA4M1 GPT channels are free-running independent counters with no hardware synchronisation bus. Phase offsets are achieved by **staggering the start time** of each channel:

```
period_us = 1,000,000 / freq_hz        (e.g. 50 µs at 20 kHz)

Phase B delay = period_us × phase_b / 360
Phase C delay = period_us × phase_c / 360
```

**Execution sequence:**

```cpp
void start_pwm() {
    float period_us = 1000000.0f / g_freq;

    pwmA.begin(g_freq, g_duty);                          // t = 0     → 0°

    uint32_t delay_b = (uint32_t)(period_us * g_phase_b / 360.0f);
    if (delay_b > 0) delayMicroseconds(delay_b);
    pwmB.begin(g_freq, g_duty);                          // t = 16.7µ → 120°

    uint32_t delay_c = (uint32_t)(period_us * g_phase_c / 360.0f);
    if (delay_c > delay_b) delayMicroseconds(delay_c - delay_b);
    pwmC.begin(g_freq, g_duty);                          // t = 33.3µ → 240°
}
```

Once started, all three timers free-run at the same frequency and the phase relationship remains stable indefinitely.

**Phase accuracy:** `delayMicroseconds()` on the RA4M1 at 48 MHz has approximately 1–2 clock cycle jitter (~0.04 µs). At 20 kHz this is **< 0.3° of phase error** — well within tolerance for motor drive and power electronics applications.

**Timing diagram at 20 kHz, 50% duty:**

```
CH A (D3)  ▔▔▔▔▔▔▏_____▔▔▔▔▔▔▏_____
CH B (D6)  ___▔▔▔▔▔▔▏_____▔▔▔▔▔▔▏__
CH C (D9)  ______▔▔▔▔▔▔▏_____▔▔▔▔▔▔
           0    16.7  25   33.3  50 µs
                 ↑          ↑
              120° delay  240° delay
```

### Duty Cycle — Live Register Update

Changing duty cycle does **not** require stopping and restarting the timers. The `pulse_perc()` method writes directly to the GPT compare-match register while the counter is running:

```cpp
// In the SET DUTY handler — no restart, no phase disturbance
if (g_running) {
    pwmA.pulse_perc(g_duty);
    pwmB.pulse_perc(g_duty);
    pwmC.pulse_perc(g_duty);
}
```

Frequency and phase changes **do** require a `stop → start` cycle because they alter the fundamental period and the timing delays between channel starts.

### Standalone Operation

The critical design decision that enables standalone operation is the **removal of `while (!Serial)`** from `setup()`:

```cpp
void setup() {
    Serial.begin(115200);
    // NO while (!Serial) — that would block PWM until USB connects

    start_pwm();    // PWM is live here — GUI not needed

    delay(100);
    Serial.println(F("# UNO R4 3-Phase PWM ready"));
    send_status();
}
```

The board can be powered from any 5 V supply. PWM starts immediately. Serial communication is available whenever a USB cable is connected, but it is not a dependency.

---

## Python GUI Architecture

The GUI (`pwm_gui.py`) is structured in three separated layers:

```
┌─────────────────────────────────────────────────┐
│  App (tk.Tk)  —  Control Layer                  │
│  Owns tk.DoubleVar state, dispatches commands,  │
│  parses JSON, syncs sliders                     │
├─────────────────────────────────────────────────┤
│  PhaseDiagram  │  WaveformView                  │
│  Visualisation Layer (tk.Canvas subclasses)     │
├─────────────────────────────────────────────────┤
│  SerialWorker  —  Communication Layer           │
│  pyserial + daemon thread + threading.Lock      │
└─────────────────────────────────────────────────┘
```

### SerialWorker — Communication Layer

Handles all serial I/O without blocking the GUI:

```python
class SerialWorker:
    def connect(self, port, baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self._running = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    def send(self, cmd: str):
        with self._lock:                          # thread-safe write
            self.ser.write((cmd + '\n').encode())

    def _read_loop(self):
        while self._running:
            line = self.ser.readline().decode(errors='replace').strip()
            if line:
                self.on_message(line)             # fires on background thread
```

Key decisions:
- **Daemon thread** — killed automatically when the main program exits, releasing the COM port
- **`threading.Lock`** — prevents write corruption if multiple UI events fire close together
- **`self.after(0, callback)`** — used in `App._on_serial_msg()` to safely hand data back to the Tkinter main thread

### PhaseDiagram — Visualisation Canvas

Draws three phasor arrows on a unit circle using polar-to-Cartesian conversion:

```python
rad = math.radians(-deg + 90)      # rotate CCW from 12-o'clock
ex  = cx + r * math.cos(rad)
ey  = cy - r * math.sin(rad)       # y-axis inverted in screen coordinates
```

The `-deg + 90` formula maps 0° to the top of the circle and increases clockwise, matching conventional phasor diagram convention.

### WaveformView — Waveform Preview Canvas

Renders 2 cycles of all three channels simultaneously. The core logic for any channel:

```python
duty_frac  = self._duty / 100.0
phase_frac = phase_deg / 360.0

for s in range(steps + 1):
    t          = s / steps * n_cycles        # time in cycles (0 → 2)
    t_in_cycle = (t - phase_frac) % 1.0     # shift + wrap to [0, 1)
    high       = t_in_cycle < duty_frac      # HIGH if within duty window
```

The `% 1.0` modulo operation correctly handles all phase values including those that would wrap around the cycle boundary mid-canvas.

### State Synchronisation on Connect

```python
def _toggle_connect(self):
    self.worker.connect(port)
    # Wait 600 ms for Arduino boot, then request state
    self.after(600, lambda: self.worker.send('GET STATUS'))

def _apply_status(self, d):
    if 'freq'    in d: self.s_freq.set(d['freq'])
    if 'duty'    in d: self.s_duty.set(d['duty'])
    if 'phase_b' in d: self.s_phase_b.set(d['phase_b'])
    if 'phase_c' in d: self.s_phase_c.set(d['phase_c'])
```

The 600 ms delay accounts for the Arduino's USB enumeration and boot time. After syncing, the GUI always shows what the hardware is **actually doing**, not stale startup defaults.

---

## RA4M1 Hardware Reference

### GPT Timer Registers

For users who want to understand or extend the low-level hardware behaviour:

| Register | Offset | Purpose |
|---|---|---|
| `GTCR` | `0x2C` | Start/stop counter, set mode (saw-wave), set clock divider |
| `GTPR` | `0x64` | Period. Counter wraps at `GTPR + 1`. `freq = 48 MHz / (GTPR + 1)` |
| `GTCCRA` | `0x4C` | Compare match A. Used by GTIOCA output pins |
| `GTCCRB` | `0x50` | Compare match B. Used by GTIOCB output pins |
| `GTCNT` | `0x48` | Current counter value. Pre-loading before start sets phase offset |
| `GTIOR` | `0x34` | Output control. Selects initial level, compare match action, overflow action |
| `GTUDDTYC` | `0x30` | Count direction and duty force control |
| `GTWP` | `0x00` | Write protection. Unlock with `PRKEY = 0xA5`, lock with `WP = 1` |

GPT base address: `0x40078000`, stride between channels: `0x100`

### GTIOR Output Mode Table

From Table 22.5 of the RA4M1 Hardware Manual (p. 423). The pattern used in this project:

| GTIOA[4:0] | b4 (Initial) | b3,b2 (Cycle end) | b1,b0 (Compare match) | Behaviour |
|---|---|---|---|---|
| `0b10110` (0x16) | HIGH | LOW at overflow | HIGH at compare match | Non-inverted PWM |

GTIOR register values:
- **GTIOCA** (D6, GPT ch1): `(1 << 8) | 0x16` = `0x00000116`
- **GTIOCB** (D3, D9, GPT ch6/7): `(1 << 24) | (0x16 << 16)` = `0x01160000`

### Pin Function Select (PmnPFS)

PFS base address: `0x40040800`. Register for port P, pin N: `base + (P × 0x20 + N) × 4`

| PmnPFS Bits | Field | Value Used |
|---|---|---|
| b28:b24 | `PSEL[4:0]` | `0x03` (= `00011b`) → GTIOC peripheral |
| b16 | `PMR` | `1` → peripheral mode (not GPIO) |
| b2 | `PDR` | `1` → output direction |

Write protection must be lifted before writing PFS:
```cpp
PMISC_PWPR = 0x00;   // clear B0WI
PMISC_PWPR = 0x40;   // set PFSWE
// ... write PFS registers ...
PMISC_PWPR = 0x00;   // clear PFSWE
PMISC_PWPR = 0x80;   // set B0WI (lock)
```

---

## Key Design Decisions

### 1. Hardware-First, Zero CPU Overhead

PWM signals are generated by dedicated GPT hardware timers. `loop()` contains nothing but serial command parsing. The PWM waveforms are completely unaffected by anything the CPU does.

### 2. GUI-Optional Standalone Operation

Removing `while (!Serial)` from `setup()` is the single most important decision for deployability. The board works powered from a bench supply, a USB charger, or a battery — no PC, no IDE, no serial monitor required.

### 3. Verified Pin-to-Channel Mapping

Every pin assignment was cross-referenced against the RA4M1 Hardware Manual port function tables. Two pins on the same GPT channel share a counter and cannot produce independent waveforms. D3 → GPT6, D6 → GPT1, D9 → GPT7 are confirmed to be three distinct channels.

### 4. Glitch-Free Duty Cycle Updates

`pulse_perc()` writes to the running GPT compare-match register. The counter continues without interruption, so duty cycle changes appear on the next cycle with no phase skip or glitch. Only frequency and phase changes, which require re-timing the startup delays, need a full stop/start.

### 5. Thread-Safe Non-Blocking Serial

Running serial reads on a daemon background thread prevents the Tkinter event loop from stalling. The `threading.Lock` on writes prevents output corruption. All data returned to the GUI goes through `self.after()` to respect Tkinter's single-thread model.

### 6. Bidirectional State Synchronisation

The JSON-on-every-command design means the GUI is always authoritative about the real hardware state. There is no possibility of the sliders showing a value that differs from what the hardware is actually running — even after a board reset or power cycle.

---

## Applications

- **3-phase motor drives** — Gate drive signals for inverter bridges driving BLDC and induction motors
- **Interleaved DC-DC converters** — Phase-shifted switching reduces input/output ripple current
- **Multi-phase battery chargers** — Phase-distributed charging for li-ion packs in EV and storage applications
- **Class D audio amplifiers** — Ultra-low-jitter gate drive at frequencies above 20 kHz
- **Lab signal generator** — Configurable multi-channel PWM source for testing and characterising power electronics
- **Educational demonstrations** — Live, visual exploration of phase relationships, duty cycles, and switching behaviour

---

## Troubleshooting

### No waveform on D3 / D6 / D9

| Check | Action |
|---|---|
| Board package version | Ensure `arduino:renesas_uno` ≥ 1.1.0 is installed |
| Correct board selected | Must be **Arduino UNO R4 WiFi**, not R4 Minima |
| Upload successful | Check Arduino IDE output for errors |
| `pwm.h` found | The library is bundled with the R4 board package — no separate install needed |
| Scope/analyser settings | Set timebase to 20–50 µs/div to see 20 kHz waveforms clearly |

### GUI cannot connect

| Check | Action |
|---|---|
| COM port in use | Close Arduino IDE Serial Monitor before opening the GUI |
| Wrong port selected | Use **⟳ Refresh** button and reselect the port |
| pyserial installed | Run `pip install pyserial` |
| Baud rate mismatch | Both sides are fixed at 115200 — no configuration needed |

### GUI sliders do not sync after connect

The GUI sends `GET STATUS` 600 ms after connecting. If the board has not finished booting by then (e.g., slow USB enumeration), the status may be missed. Click **▶ SEND ALL** to force a full resync.

### Phase offset looks wrong on scope

- The staggered start introduces a one-time delay during `start_pwm()`. After that, all timers free-run. If you trigger your scope on Channel A and measure Channel B rising edge, you should see the delay match `period × phase_b / 360`.
- At very high frequencies (> 100 kHz), `delayMicroseconds` resolution limits phase accuracy. Consider using direct GPT register pre-loading (`GTCNT` pre-load) for sub-microsecond precision at high frequencies.

### Frequency or phase change causes a brief output gap

This is expected behaviour. Frequency and phase changes call `stop_pwm()` followed by `start_pwm()`. The gap duration is equal to the time needed to restart three timers in sequence — typically a few tens of microseconds. For duty cycle changes, no gap occurs.

---

## Contributing

Contributions are welcome. Please follow these guidelines:

1. **Fork** the repository and create a feature branch: `git checkout -b feature/my-improvement`
2. **Test** on actual hardware before submitting a pull request
3. **Document** any new serial commands in this README and in the firmware's startup message
4. **Keep the GUI backward compatible** — existing commands should continue to work
5. Submit a **pull request** with a clear description of the change and why it is needed

### Ideas for Contribution

- Dead-time insertion between complementary channels (for H-bridge gate drive)
- 6-channel version using D3, D5, D6, D9, D10, D11 (see `pwm_6ch.ino` in the repo)
- GTCNT pre-load method for high-frequency phase precision (> 100 kHz)
- Auto-detect baud rate in the GUI
- Save/load settings to a JSON config file from the GUI
- Dark/light theme toggle in the GUI

---

## License

This project is released under the **MIT License**. See [LICENSE](LICENSE) for full terms.

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## References

- [RA4M1 Group User's Manual: Hardware](https://www.renesas.com/en/document/mah/ra4m1-group-users-manual-hardware) — Rev. 1.10, R01UH0887EJ0110 (Sep 2023)
  - Table 19.10 — PORT3 pin function select (P303 → GTIOC7B)
  - Table 19.11 — PORT4 pin function select (P402 → GTIOC6B, P405 → GTIOC1A)
  - Table 22.5 — GTIOR GTIOA/GTIOB pin function select
  - Section 22.2.14 — General PWM Timer I/O Control Register (GTIOR)
- [Arduino UNO R4 WiFi Cheat Sheet](https://docs.arduino.cc/tutorials/uno-r4-wifi/cheat-sheet/)
- [Arduino UNO R4 Board Package](https://github.com/arduino/ArduinoCore-renesas)
- [pyserial Documentation](https://pyserial.readthedocs.io/)

---

*Built with the Arduino UNO R4 WiFi · Renesas RA4M1 · Python 3 · Tkinter · pyserial*
