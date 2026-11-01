# Smart Ventilation System: Pin Connections

**Wiring reference for the sensor, display, relay-driver and fan connections of the prototype**

|  |  |
| --- | --- |
| **Controller** | ESP32-WROOM-32 development board |
| **Low-voltage logic** | 3.3 V (DHT22, OLED) and USB-derived 5 V (MQ module, relay module) |
| **Fan supply** | Separate 12 V adapter, switched through relay contacts |
| **Document type** | Pinout and wiring reference |

## 1. ESP32 GPIO Assignment

| ESP32 pin / board label | Connected to | Signal / function |
| --- | --- | --- |
| GPIO4 (D4) | DHT22 DATA | Digital temperature and humidity signal |
| GPIO21 (D21) | OLED SDA | I²C data |
| GPIO22 (D22) | OLED SCL / SCK | I²C clock |
| GPIO34 (D34) | MQ voltage-divider junction | Analog sensor input |
| GPIO5 (D5) | KN2222A base, through a 10 kΩ resistor | Relay-control signal |
| 3V3 | DHT22 VCC and OLED VCC | 3.3 V supply |
| USB-derived 5 V / VIN rail | MQ module VCC and relay module VCC | 5 V module supply (verify the board's VIN behaviour) |
| GND | Sensor, OLED, transistor and relay grounds | Common low-voltage reference |

## 2. DHT22 Temperature and Humidity Sensor

| DHT22 pin | Connect to ESP32 |
| --- | --- |
| `+` / VCC | 3V3 |
| `OUT` / DATA | GPIO4 (D4) |
| `-` / GND | GND |

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

> **Important:** Measure or otherwise verify the maximum voltage at GPIO34 under actual operating conditions. The ESP32 ADC input must stay within its permitted range. Raw MQ readings are prototype indicators only, not calibrated gas concentrations or certified AQI values.

## 4. OLED Display (I²C)

| OLED pin | Connect to ESP32 |
| --- | --- |
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO21 (D21) |
| SCL / SCK | GPIO22 (D22) |

- **Tested I²C address:** `0x3C`
- **Display:** 0.96-inch, 128 × 64 pixels, SSD1306-compatible module (confirm the controller on the actual display)

## 5. KN2222A Transistor and Relay Module

### 5.1 Transistor control connections

| KN2222A terminal | Connection |
| --- | --- |
| Base | GPIO5, through a 10 kΩ resistor |
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

> **Critical verification:** Confirm the base, collector and emitter arrangement from the datasheet for the exact KN2222A package, since pinouts can differ between manufacturers and packages. Also verify that the relay module input is active-low and that its input circuit is compatible with this transistor arrangement.

## 6. Relay Contact and 12 V Fan Connections

Tested relay screw-terminal mapping:

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

Verify the relay contact ratings against the fan's rated and startup current, and confirm the terminal markings on the actual relay module before applying power.

## 7. Power Distribution Summary

| Supply | Loads in the current prototype |
| --- | --- |
| ESP32 USB power | ESP32 development board |
| ESP32 3.3 V output | DHT22 and OLED |
| USB-derived 5 V rail | MQ sensor module and relay module |
| Separate 12 V adapter | Exhaust fan, through relay contacts |

The LM2596 HW-411 buck converter is currently unused and is not part of this wiring configuration.

## 8. Pre-Power Checklist

- [ ] Confirm ESP32 GPIO labels and board pinout.
- [ ] Confirm DHT22 VCC, DATA and GND connections.
- [ ] Confirm OLED SDA and SCL connections and I²C address.
- [ ] Confirm the MQ voltage-divider junction is connected to GPIO34.
- [ ] Verify the maximum voltage at GPIO34 is within the ESP32 ADC input limits.
- [ ] Confirm the KN2222A base, collector and emitter pinout from its datasheet.
- [ ] Confirm relay module polarity and active-low input behaviour.
- [ ] Verify COM, NO and NC terminal markings on the actual relay.
- [ ] Confirm the fan's voltage and current ratings.
- [ ] Check that the 12 V fan supply is not connected to any ESP32 GPIO or 3.3 V pin.
- [ ] Check wiring for shorts, loose connections and exposed conductors before powering the system.

## 9. Safety Notes

- Disconnect all power sources before changing wiring.
- Never apply 12 V directly to an ESP32 GPIO pin or the 3.3 V rail.
- Do not assume every ESP32 development board exposes VIN the same way. Check the board documentation and measure the rail before using it.
- Keep the fan's 12 V power path separate from the ESP32 logic supply. Use the required common ground for the low-voltage transistor/relay control circuit.
- Use insulated connections and a protective grille around the rotating fan.
- This pinout documents an educational prototype. Verify all component labels and datasheets before reproducing the circuit.

---

*Prepared for the Smart Ventilation System GitHub repository.*
