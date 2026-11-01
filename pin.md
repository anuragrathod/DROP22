# Smart Ventilation System: Pin Connections

**Wiring reference for the power, sensor, display, relay-driver and fan connections of the prototype**

|  |  |
| --- | --- |
| **Controller** | ESP32-WROOM-32 development board |
| **Power arrangement** | 12 V adapter → LM2596 buck converter (adjusted to 5 V) → USB-C cable → ESP32 |
| **Low-voltage logic** | 3.3 V (DHT22, OLED) and USB-derived 5 V (MQ module, relay module) |
| **Fan supply** | 12 V adapter, switched through relay contacts |

This document describes the prototype wiring. Verify all module labels, board power arrangements and component datasheets before reproducing the circuit.

## 1. ESP32 GPIO Assignment

| ESP32 pin / board label | Connected to | Signal / function |
| --- | --- | --- |
| GPIO4 (D4) | DHT22 DATA | Digital temperature and humidity signal |
| GPIO21 (D21) | OLED SDA | I²C data |
| GPIO22 (D22) | OLED SCL / SCK | I²C clock |
| GPIO34 (D34) | MQ voltage-divider junction | Analog sensor input |
| GPIO5 (D5) | KN2222A base, through a 10 kΩ resistor | Relay-control signal |
| 3V3 | DHT22 VCC and OLED VCC | 3.3 V supply |
| USB-derived 5 V rail | MQ module VCC and relay module VCC | 5 V module supply (verify the actual board and wiring) |
| GND | Low-voltage circuit grounds | Common reference |

## 2. DHT22 Temperature and Humidity Sensor

| DHT22 pin | Connect to |
| --- | --- |
| `+` / VCC | ESP32 3V3 |
| `OUT` / DATA | ESP32 GPIO4 (D4) |
| `-` / GND | Common GND |

**Notes**

- Add a pull-up resistor between DATA and 3V3 if the sensor module does not already include one.
- Do not connect the DATA line to 5 V.

## 3. MQ-Series Sensor Module

| MQ module pin | Connection |
| --- | --- |
| VCC | USB-derived 5 V rail |
| GND | Common GND |
| AO | Top of the voltage-divider resistor |
| DO | Not connected |

### 3.1 Analog voltage divider

Two 10 kΩ resistors scale the MQ analog output down before it reaches the ESP32.

1. Connect MQ `AO` to the first 10 kΩ resistor.
2. Connect the other end of the first resistor to a junction.
3. Connect the junction to ESP32 GPIO34.
4. Connect the second 10 kΩ resistor between the junction and GND.

For equal resistor values:

`V_GPIO34 ≈ V_AO / 2`

> **Important:** Verify the maximum voltage at GPIO34 under actual operating conditions. The ESP32 ADC input must stay within its permitted range. Raw MQ readings are prototype indicators only, not calibrated gas concentrations or certified AQI values.

## 4. OLED Display (I²C)

| OLED pin | Connect to |
| --- | --- |
| VCC | ESP32 3V3 |
| GND | Common GND |
| SDA | ESP32 GPIO21 (D21) |
| SCL / SCK | ESP32 GPIO22 (D22) |

- **Tested I²C address:** `0x3C`
- **Display:** 0.96-inch, 128 × 64 pixels, SSD1306-compatible module (confirm the controller on the actual display)

## 5. KN2222A Transistor and Relay Module

### 5.1 Transistor control connections

| KN2222A terminal | Connection |
| --- | --- |
| Base | ESP32 GPIO5, through a 10 kΩ resistor |
| Collector | Relay module IN |
| Emitter | Common GND |

### 5.2 Relay module connections

| Relay module pin | Connection |
| --- | --- |
| VCC | USB-derived 5 V rail |
| GND | Common GND |
| IN | KN2222A collector |

### 5.3 Switching behaviour

| GPIO5 | Transistor | Relay input | Relay |
| --- | --- | --- | --- |
| HIGH | On | Pulled LOW (active-low) | Activated |
| LOW | Off | Not pulled low | Deactivated |

> **Critical verification:** Confirm the base, collector and emitter arrangement from the datasheet for the exact KN2222A package. Also verify that the relay module input is active-low and compatible with this transistor interface.

## 6. Relay Contacts and 12 V Exhaust Fan

Terminal mapping identified on the tested relay module:

| Terminal marking | Function | Connection |
| --- | --- | --- |
| 2 | COM | 12 V adapter positive |
| 1 | NO | Fan positive |
| 3 | NC | Unused |

### 6.1 Fan power path

1. Connect the 12 V adapter positive to relay COM (terminal 2).
2. Connect relay NO (terminal 1) to the fan positive wire.
3. Connect the fan negative wire to the 12 V adapter negative.
4. Leave relay NC (terminal 3) unused.

When the relay activates, COM connects to NO and the fan is powered. When the relay is inactive, the NO contact is open and the fan supply is disconnected.

Verify the terminal markings and relay contact ratings against the actual module and the fan's rated and startup current.

## 7. Power Supply Connections

### 7.1 ESP32 power path

| From | To | Description |
| --- | --- | --- |
| 12 V DC adapter positive and negative | LM2596 input (`IN+`, `IN-`) | Supplies the buck converter |
| LM2596 output (`OUT+`, `OUT-`) | USB-C cable power input | Provides regulated 5 V to the cable |
| USB-C cable | ESP32 USB-C port | Powers the ESP32 development board |

**Before connecting the USB-C cable to the ESP32**

- Adjust the LM2596 output and verify approximately 5 V with a multimeter.
- Confirm the USB-C cable is wired for the correct polarity and power pins.
- Use a suitable USB-C power connector or breakout, or a correctly assembled cable. Do not assume a bare USB-C cable can safely be connected directly to the buck converter output.
- Check that the converter can supply the ESP32's peak current demand.
- Do not connect a second USB power source at the same time unless the board's power design explicitly supports it.

### 7.2 Sensor and relay power

The current prototype wiring uses the USB-derived 5 V rail for the MQ sensor module and relay module. The DHT22 and OLED use the ESP32 3.3 V output. Confirm the actual wiring and module voltage ratings.

### 7.3 Fan power path

The 12 V adapter also supplies the fan through the relay contacts:

`12 V adapter (+) → Relay COM → Relay NO → Fan (+)`

`Fan (-) → 12 V adapter (-)`

> **Warning:** The fan's 12 V supply must never be connected directly to ESP32 GPIO pins or the 3.3 V rail.

## 8. Power Distribution Summary

| Supply | Loads |
| --- | --- |
| 12 V adapter | LM2596 input, and fan supply through relay contacts |
| LM2596 regulated 5 V output | ESP32, through the USB-C power connection |
| ESP32 3.3 V output | DHT22 and OLED |
| USB-derived 5 V rail | MQ module and relay module, per the current prototype wiring |

The LM2596 is part of the current power arrangement. Its output powers the ESP32 through a USB-C cable.

## 9. Safety Notes

- Disconnect all power sources before changing wiring.
- Never apply 12 V directly to an ESP32 GPIO pin or the 3.3 V rail.
- Verify the buck converter output with a multimeter before connecting it to the USB-C power input.
- Do not connect USB power from a computer and the buck-converter USB-C supply at the same time unless the development board supports this safely.
- Verify the relay contact rating and fan startup current.
- Use insulated connections and a protective grille around the rotating fan.
- This document describes an educational prototype. Verify every connection against the actual component labels and datasheets before reproducing the circuit.
