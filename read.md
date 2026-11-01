# Smart Ventilation System: Components List

**Automatic exhaust fan control with air monitoring and mobile connectivity**

|  |  |
| --- | --- |
| **Controller** | ESP32-WROOM-32 development board |
| **Fan supply** | Separate 12 V DC, switched by relay |
| **Interface** | OLED display and local Wi-Fi dashboard |
| **Document type** | Bill of materials and wiring reference |

## 1. Hardware Components

| No. | Component | Qty | Purpose |
| --- | --- | --- | --- |
| 1 | ESP32-WROOM-32 development board | 1 | Main controller. Reads sensors, runs the control logic, drives the relay interface, updates the OLED and hosts the Wi-Fi dashboard. |
| 2 | DHT22 / AM2302 temperature and humidity sensor | 1 | Measures ambient temperature and relative humidity. |
| 3 | MQ-series gas sensor module (exact model to be confirmed) | 1 | Provides an analog response to selected gases or vapours for prototype monitoring. |
| 4 | 0.96-inch, 128 × 64 OLED display (SSD1306-compatible; confirm module) | 1 | Shows temperature, humidity, air-status category and fan command/state. |
| 5 | Single-channel 5 V relay module | 1 | Switches the separate 12 V supply to the exhaust fan. |
| 6 | KN2222A NPN transistor | 1 | Interfaces the ESP32 GPIO signal with the relay module's active-low input. |
| 7 | 10 kΩ resistor | 3 | Two form the MQ analog-output voltage divider. One limits transistor base current. |
| 8 | 12 V DC brushless exhaust fan (Honeycomb CLDB0225SH; verify label) | 1 | Moves air when its supply is switched by the relay. |
| 9 | 12 V DC, 1 A power adapter | 1 | Powers the exhaust fan. |
| 10 | USB cable and USB power source | 1 | Powers and programs the ESP32 during development. |
| 11 | Connecting wires / jumper wires | As required | Connects sensors, display, controller, relay driver and power circuits. |
| 12 | Prototype enclosure and mounting materials | As required | Supports the components and houses the demonstration model. |

## 2. Optional / Currently Unused Component

| Component | Qty | Intended function | Current status |
| --- | --- | --- | --- |
| LM2596 HW-411 adjustable buck converter | 1 | Steps down a higher DC input voltage to a lower regulated DC output. | Not connected in the current working prototype. |

## 3. Software and Development Tools

| No. | Tool / Library | Purpose |
| --- | --- | --- |
| 1 | Arduino IDE 2.3.10 | Writing, compiling and uploading the ESP32 firmware. |
| 2 | Espressif ESP32 board package | Adds ESP32 board support to Arduino IDE. |
| 3 | Adafruit DHT sensor library | Reads temperature and humidity from the DHT22. |
| 4 | Adafruit Unified Sensor library | Provides shared sensor interface support. |
| 5 | Adafruit SSD1306 library | Controls the OLED display. |
| 6 | Adafruit GFX library | Provides text and graphics functions for the display. |
| 7 | ESP32 Wi-Fi support | Configures the ESP32 as a local Wi-Fi access point. |
| 8 | WebServer | Hosts the local mobile web dashboard. |
| 9 | Preferences | Stores configuration settings in ESP32 non-volatile memory. |
| 10 | Wire | Provides I²C communication with the OLED display. |

## 4. Electrical Connections

### 4.1 Low-voltage connections

| ESP32 pin / rail | Connected to | Function |
| --- | --- | --- |
| GPIO4 | DHT22 DATA | Digital temperature and humidity data |
| GPIO21 | OLED SDA | I²C data |
| GPIO22 | OLED SCL | I²C clock |
| GPIO34 | MQ voltage-divider junction | Analog sensor input |
| GPIO5 | KN2222A base, through a 10 kΩ resistor | Relay control signal |
| 3V3 | DHT22 and OLED VCC | 3.3 V supply |
| USB-derived 5 V / VIN rail | MQ module and relay module VCC | 5 V module supply (subject to board verification) |
| GND | All low-voltage circuit grounds | Common reference |

### 4.2 Fan power path

1. 12 V adapter positive connects to relay **COM**.
2. Relay **NO** connects to the fan positive wire.
3. Fan negative connects to the 12 V adapter negative.
4. Relay **NC** is unused.

> **Warning:** Never connect the 12 V fan supply directly to ESP32 GPIO pins or the 3.3 V rail. Before powering the circuit, confirm the relay contact rating, transistor pinout, module polarity and actual component labels.

## 5. Verification Checklist

- [ ] Confirm the exact MQ sensor model from the module label before adding model-specific specifications.
- [ ] Confirm the fan voltage and current ratings from its label.
- [ ] Verify the maximum voltage at the MQ divider junction (GPIO34) under operating conditions. The two 10 kΩ resistors reduce the MQ analog output before it reaches the ESP32.
- [ ] Confirm the relay contact rating, transistor pinout and relay module polarity.

## 6. Notes

- The MQ sensor's raw analog reading is a prototype indicator only. It is not a calibrated gas concentration or a certified Air Quality Index.
- The DHT22 and OLED run from 3.3 V. The MQ module and relay module run from the USB-derived 5 V rail.
- The LM2596 converter is listed as available only. It is not part of the current working circuit.

---

*Prepared for the Smart Ventilation System project repository.*
