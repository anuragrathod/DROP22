/*
  Smart Ventilation System
  ESP32 + DHT22 + MQ analog gas sensor + SSD1306 OLED + relay driver
  + Wi-Fi access-point dashboard.

  Hardware pin assignment:
    DHT22 DATA       -> GPIO4
    OLED SDA         -> GPIO21
    OLED SCL         -> GPIO22
    MQ sensor AO     -> GPIO34 (through a voltage divider!)
    Relay transistor -> GPIO5 (through 10k base resistor)

  Power notes:
    12V adapter -> LM2596 buck converter adjusted to 5.0V
                -> suitable USB-C cable/input -> ESP32 USB-C port
    Fan is powered separately from the 12V adapter through relay COM/NO.
    Never connect 12V to an ESP32 GPIO, 3V3, or 5V pin.
    All low-voltage circuit grounds must be common.
    Check the actual KN2222A pinout and relay-driver wiring before powering.

  Libraries:
    - Adafruit GFX Library
    - Adafruit SSD1306
    - DHT sensor library by Adafruit
    - Adafruit Unified Sensor
    ESP32 board package by Espressif Systems.

  IMPORTANT:
    MQ raw ADC thresholds below are prototype starting values, NOT ppm/AQI.
    Calibrate the sensor in the actual enclosure/environment before relying
    on it. This prototype is not a certified life-safety or gas-alarm device.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

// ------------------------- Pin configuration -------------------------

#define DHT_PIN       4
#define DHT_TYPE      DHT22
#define MQ_PIN        34
#define FAN_DRIVER_PIN 5

#define OLED_SDA      21
#define OLED_SCL      22
#define OLED_WIDTH    128
#define OLED_HEIGHT   64
#define OLED_RESET    -1
#define OLED_ADDRESS  0x3C

// ------------------------- Wi-Fi access point -------------------------

// Change this password before sharing/publishing the project.
const char* AP_SSID = "SmartVentilation";
const char* AP_PASSWORD = "Vent12345"; // Minimum 8 characters

// ------------------------- Sensor/control settings --------------------

const unsigned long SENSOR_INTERVAL_MS = 2000;
const float TEMP_HYSTERESIS_C = 2.0f;
const int AIR_HYSTERESIS = 200;

// Provisional defaults. Adjust from the dashboard after calibration.
float tempLimitC = 35.0f;
int airLimitRaw = 1800;

DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);
WebServer server(80);
Preferences preferences;

float temperatureC = NAN;
float humidity = NAN;
int gasRaw = 0;

bool dhtValid = false;
bool tempAlarm = false;
bool gasAlarm = false;
bool fanOn = false;
bool autoMode = true;
bool oledAvailable = false;

unsigned long lastSensorRead = 0;
unsigned long lastDisplayUpdate = 0;

// ------------------------- Utility functions -------------------------

String jsonBool(bool value) {
  return value ? "true" : "false";
}

String airStatus() {
  // These are relative prototype categories based on raw ADC counts only.
  if (gasRaw < (airLimitRaw / 2)) return "GOOD";
  if (gasRaw < airLimitRaw) return "AVERAGE";
  return "POOR";
}

void applyFanOutput() {
  // GPIO HIGH drives the NPN transistor. The transistor pulls the
  // relay module IN low, energizing an active-low relay input.
  digitalWrite(FAN_DRIVER_PIN, fanOn ? HIGH : LOW);
}

void updateAutomaticControl() {
  if (!autoMode) {
    applyFanOutput();
    return;
  }

  // Fail-safe prototype behavior: if temperature/humidity sensor data
  // is invalid, request ventilation rather than silently switching off.
  if (!dhtValid) {
    tempAlarm = true;
  } else {
    if (!tempAlarm && temperatureC >= tempLimitC) {
      tempAlarm = true;
    } else if (tempAlarm && temperatureC <= (tempLimitC - TEMP_HYSTERESIS_C)) {
      tempAlarm = false;
    }
  }

  if (!gasAlarm && gasRaw >= airLimitRaw) {
    gasAlarm = true;
  } else if (gasAlarm && gasRaw <= (airLimitRaw - AIR_HYSTERESIS)) {
    gasAlarm = false;
  }

  fanOn = tempAlarm || gasAlarm;
  applyFanOutput();
}

void readSensors() {
  float newTemp = dht.readTemperature();
  float newHumidity = dht.readHumidity();

  if (isnan(newTemp) || isnan(newHumidity)) {
    dhtValid = false;
  } else {
    temperatureC = newTemp;
    humidity = newHumidity;
    dhtValid = true;
  }

  // GPIO34 is ADC1 and can be used while Wi-Fi is active.
  gasRaw = analogRead(MQ_PIN);

  updateAutomaticControl();
}

void updateOLED() {
  if (!oledAvailable) return;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("SMART VENTILATION");
  display.drawLine(0, 11, 127, 11, SSD1306_WHITE);

  display.setCursor(0, 15);
  display.print("Temp: ");
  if (dhtValid) {
    display.print(temperatureC, 1);
    display.print(" C");
  } else {
    display.print("Sensor error");
  }

  display.setCursor(0, 27);
  display.print("Humidity: ");
  if (dhtValid) {
    display.print(humidity, 1);
    display.print("%");
  } else {
    display.print("--");
  }

  display.setCursor(0, 39);
  display.print("Gas raw: ");
  display.print(gasRaw);

  display.setCursor(0, 51);
  display.print("Fan:");
  display.print(fanOn ? " ON " : " OFF");
  display.print(autoMode ? " AUTO" : " MANUAL");

  display.display();
}

String dashboardPage() {
  String page = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Ventilation</title>
<style>
body{font-family:Arial,sans-serif;background:#f2f5f8;color:#17212b;margin:0;padding:18px}
main{max-width:520px;margin:auto}
h2{margin-top:0}
.card{background:white;border-radius:14px;padding:16px;margin:12px 0;box-shadow:0 2px 9px #0001}
.value{font-size:25px;font-weight:bold}
.small{color:#64748b;font-size:13px}
button{border:0;border-radius:9px;padding:12px 16px;margin:5px 4px 5px 0;font-weight:bold;background:#164e8a;color:white}
button.secondary{background:#475569}
input[type=range]{width:100%}
input[type=number]{width:90px;padding:8px}
.status{font-weight:bold}
</style>
</head>
<body><main>
<h2>Smart Ventilation System</h2>
<div class="small">ESP32 live monitoring and fan control</div>
<div class="card">
  <div>Temperature</div><div class="value" id="temp">--</div>
  <div class="small">Humidity: <span id="hum">--</span></div>
</div>
<div class="card">
  <div>Gas sensor raw reading</div><div class="value" id="gas">--</div>
  <div>Air status: <span class="status" id="air">--</span></div>
  <div class="small">Raw ADC count only; not ppm or a certified air-quality value.</div>
</div>
<div class="card">
  <div>Fan: <span class="value" id="fan">--</span></div>
  <div>Control mode: <span id="mode">--</span></div>
  <button onclick="setMode('auto')">AUTO MODE</button>
  <button class="secondary" onclick="setMode('manual')">MANUAL MODE</button>
  <button onclick="manualFan('on')">FAN ON</button>
  <button class="secondary" onclick="manualFan('off')">FAN OFF</button>
</div>
<div class="card">
  <h3>Automatic thresholds</h3>
  <label>Temperature limit: <b><span id="tempLabel">35.0</span> C</b></label>
  <input id="tempLimit" type="range" min="20" max="50" step="0.5" value="35"
         oninput="tempLabel.textContent=Number(this.value).toFixed(1)">
  <br><br>
  <label>Gas raw limit: <b><span id="airLabel">1800</span></b></label>
  <input id="airLimit" type="range" min="100" max="4095" step="10" value="1800"
         oninput="airLabel.textContent=this.value">
  <br><button onclick="saveSettings()">SAVE THRESHOLDS</button>
  <div class="small" id="message"></div>
</div>
<div class="small">Connect to Wi-Fi: SmartVentilation · Open http://192.168.4.1</div>
</main>
<script>
async function refresh(){
 try{
  const r=await fetch('/data'); const d=await r.json();
  document.getElementById('temp').textContent=d.dhtValid?d.temperature.toFixed(1)+' C':'Sensor error';
  document.getElementById('hum').textContent=d.dhtValid?d.humidity.toFixed(1)+'%':'--';
  document.getElementById('gas').textContent=d.gasRaw;
  document.getElementById('air').textContent=d.airStatus;
  document.getElementById('fan').textContent=d.fanOn?'ON':'OFF';
  document.getElementById('mode').textContent=d.autoMode?'AUTO':'MANUAL';
  document.getElementById('tempLimit').value=d.tempLimit;
  document.getElementById('tempLabel').textContent=Number(d.tempLimit).toFixed(1);
  document.getElementById('airLimit').value=d.airLimit;
  document.getElementById('airLabel').textContent=d.airLimit;
 }catch(e){}
}
async function sendConfig(q){
 const r=await fetch('/config?'+q);
 const d=await r.text();
 document.getElementById('message').textContent=d;
 refresh();
}
function setMode(m){sendConfig('mode='+m);}
function manualFan(s){sendConfig('fan='+s);}
function saveSettings(){
 sendConfig('temp='+encodeURIComponent(tempLimit.value)+'&air='+encodeURIComponent(airLimit.value));
}
refresh(); setInterval(refresh,2000);
</script>
</body></html>
)rawliteral";
  return page;
}

// ------------------------- Web server handlers -----------------------

void handleRoot() {
  server.send(200, "text/html", dashboardPage());
}

void handleData() {
  String json = "{";
  json += "\"temperature\":" + String(dhtValid ? temperatureC : 0.0f, 1) + ",";
  json += "\"humidity\":" + String(dhtValid ? humidity : 0.0f, 1) + ",";
  json += "\"dhtValid\":" + jsonBool(dhtValid) + ",";
  json += "\"gasRaw\":" + String(gasRaw) + ",";
  json += "\"airStatus\":\"" + airStatus() + "\",";
  json += "\"fanOn\":" + jsonBool(fanOn) + ",";
  json += "\"autoMode\":" + jsonBool(autoMode) + ",";
  json += "\"tempLimit\":" + String(tempLimitC, 1) + ",";
  json += "\"airLimit\":" + String(airLimitRaw);
  json += "}";
  server.send(200, "application/json", json);
}

void handleConfig() {
  bool changed = false;

  if (server.hasArg("mode")) {
    String mode = server.arg("mode");
    if (mode == "auto") {
      autoMode = true;
      changed = true;
    } else if (mode == "manual") {
      autoMode = false;
      changed = true;
    }
  }

  if (server.hasArg("fan") && !autoMode) {
    String command = server.arg("fan");
    if (command == "on") {
      fanOn = true;
      changed = true;
    } else if (command == "off") {
      fanOn = false;
      changed = true;
    }
  }

  if (server.hasArg("temp")) {
    float value = server.arg("temp").toFloat();
    if (value >= 20.0f && value <= 50.0f) {
      tempLimitC = value;
      changed = true;
    }
  }

  if (server.hasArg("air")) {
    int value = server.arg("air").toInt();
    if (value >= 100 && value <= 4095) {
      airLimitRaw = value;
      changed = true;
    }
  }

  if (autoMode) {
    updateAutomaticControl();
  } else {
    applyFanOutput();
  }

  if (changed) {
    preferences.putFloat("tempLimit", tempLimitC);
    preferences.putInt("airLimit", airLimitRaw);
    preferences.putBool("autoMode", autoMode);
  }

  server.send(200, "text/plain", "Settings updated.");
}

// ------------------------- Setup and main loop ------------------------

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(FAN_DRIVER_PIN, OUTPUT);
  fanOn = false;
  applyFanOutput();

  analogReadResolution(12);
  analogSetPinAttenuation(MQ_PIN, ADC_11db);

  dht.begin();

  Wire.begin(OLED_SDA, OLED_SCL);
  oledAvailable = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);
  if (oledAvailable) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("Smart Ventilation");
    display.println("Starting...");
    display.display();
  } else {
    Serial.println("OLED not detected. Check wiring/address.");
  }

  preferences.begin("smartvent", false);
  tempLimitC = preferences.getFloat("tempLimit", 35.0f);
  airLimitRaw = preferences.getInt("airLimit", 1800);
  autoMode = preferences.getBool("autoMode", true);

  WiFi.mode(WIFI_AP);
  bool apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD);
  Serial.println();
  Serial.println("Smart Ventilation System");
  Serial.print("Access point: ");
  Serial.println(apStarted ? "Started" : "Failed");
  Serial.print("SSID: ");
  Serial.println(AP_SSID);
  Serial.print("Dashboard: http://");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, handleRoot);
  server.on("/data", HTTP_GET, handleData);
  server.on("/config", HTTP_GET, handleConfig);
  server.begin();

  readSensors();
  updateOLED();
}

void loop() {
  server.handleClient();

  unsigned long now = millis();

  if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = now;
    readSensors();

    Serial.print("Temperature: ");
    if (dhtValid) Serial.print(temperatureC);
    else Serial.print("DHT error");
    Serial.print(" C | Humidity: ");
    if (dhtValid) Serial.print(humidity);
    else Serial.print("--");
    Serial.print(" % | MQ raw: ");
    Serial.print(gasRaw);
    Serial.print(" | Fan: ");
    Serial.println(fanOn ? "ON" : "OFF");
  }

  if (now - lastDisplayUpdate >= 1000) {
    lastDisplayUpdate = now;
    updateOLED();
  }
}
