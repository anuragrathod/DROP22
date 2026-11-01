# Smart Ventilation System: Components List

**Automatic exhaust fan control with air monitoring and mobile connectivity**

|  |  |
| --- | --- |
| **Controller** | ESP32-WROOM-32 development board |
| **Fan supply** | Separate 12 V DC, switched by relay |
| **Interface** | OLED display and local Wi-Fi dashboard |
| **Document type** | Bill of materials and wiring reference |

## Hardware Components

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
| 13 | LM2596 HW-411 adjustable buck converter | 1 | Steps down a higher DC input voltage to a lower regulated DC output. |
