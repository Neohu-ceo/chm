/**
 * 灵犀 Lingxi — ESP32-C3 Firmware
 *
 * Hardware: ESP32-C3 + 8×WS2812B + CAP1203 Touch + INMP441 Mic + Vibration Motor
 * WiFi → Backend API → LED/Vibration/Mic
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <Wire.h>

// ── Pin Definitions (based on design analysis) ─────────────────
#define LED_PIN         8    // WS2812B data
#define TOUCH_SDA       6    // CAP1203 I2C
#define TOUCH_SCL       7
#define MOTOR_PIN       4    // Vibration motor
#define MIC_I2S_WS      3    // INMP441
#define MIC_I2S_SCK     5
#define MIC_I2S_SD      2
#define LED_COUNT       8    // 2 cheeks + 2 eyes + 4 base

// ── WiFi ───────────────────────────────────────────────────────
const char* WIFI_SSID = "Lingxi_Setup";
const char* WIFI_PASS = "lingxi888";
#define API_HOST "http://192.168.1.100:5500"

// ── Globals ────────────────────────────────────────────────────
Adafruit_NeoPixel leds(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
String device_id = "";
String user_id = "";
bool bonded = false;
String current_emotion = "calm";
float current_intensity = 0.5;
int brightness = 60;
unsigned long last_heartbeat = 0;
unsigned long last_touch = 0;
int touch_count = 0;

// ── LED Mapping (based on design: cheeks + eyes + base) ────────
// LED positions: 0=left cheek, 1=right cheek, 2=left eye, 3=right eye
//                4-7=base ring (bottom glow)

uint32_t hexToColor(String hex) {
    long number = strtol(hex.substring(1).c_str(), NULL, 16);
    return leds.Color((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF);
}

void setEmotionLight(String emotion, float intensity) {
    // Emotion → LED behavior
    struct { uint32_t color; int brightness; int pattern; } config;

    if (emotion == "joy")       config = {leds.Color(255,215,0), 80, 0};    // Warm gold, bright
    else if (emotion == "calm")     config = {leds.Color(135,206,235), 40, 0}; // Soft blue, dim
    else if (emotion == "sadness")  config = {leds.Color(107,123,141), 25, 0};  // Dim purple
    else if (emotion == "excited")  config = {leds.Color(255,107,53), 100, 0};   // Sparkle orange
    else if (emotion == "love")     config = {leds.Color(255,105,180), 70, 0};   // Pink pulse
    else if (emotion == "sleepy")   config = {leds.Color(74,74,106), 15, 0};     // Fading navy
    else config = {leds.Color(255,160,100), 50, 0};

    int b = config.brightness * intensity;
    leds.setBrightness(constrain(b, 10, 100));

    // Cheeks glow
    leds.setPixelColor(0, config.color);
    leds.setPixelColor(1, config.color);
    // Eyes flicker
    leds.setPixelColor(2, config.color);
    leds.setPixelColor(3, config.color);
    // Base ring
    for (int i = 4; i < 8; i++) {
        leds.setPixelColor(i, leds.Color(
            (config.color >> 16) & 0xFF,
            (config.color >> 8) & 0xFF,
            (config.color) & 0xFF
        ));
    }
    leds.show();
}

void breatheEffect() {
    for (int b = 15; b <= 50; b += 3) {
        leds.setBrightness(b); leds.show(); delay(25);
    }
    for (int b = 50; b >= 15; b -= 3) {
        leds.setBrightness(b); leds.show(); delay(25);
    }
}

// ── Touch Detection ────────────────────────────────────────────
bool touched = false;

void checkTouch() {
    // CAP1203 via I2C
    Wire.beginTransmission(0x28);
    Wire.write(0x00); // Touch status register
    Wire.endTransmission();
    Wire.requestFrom(0x28, 1);
    if (Wire.available()) {
        uint8_t status = Wire.read();
        touched = (status > 0);
    }

    if (touched && millis() - last_touch > 1000) {
        last_touch = millis();
        touch_count++;

        // Short tap → poke reaction
        setEmotionLight("excited", 0.9);
        digitalWrite(MOTOR_PIN, HIGH);
        delay(100);
        digitalWrite(MOTOR_PIN, LOW);
        delay(500);
        setEmotionLight(current_emotion, current_intensity);
    }
}

// ── API Communication ──────────────────────────────────────────
void sendChat(String text) {
    if (WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    http.begin(String(API_HOST) + "/api/chat");
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<512> doc;
    doc["user_id"] = user_id;
    doc["text"] = text;

    String body;
    serializeJson(doc, body);
    int code = http.POST(body);

    if (code == 200) {
        StaticJsonDocument<512> resp;
        deserializeJson(resp, http.getString());

        current_emotion = resp["emotion"] | "calm";
        current_intensity = resp["intensity"] | 0.5;

        // Apply hardware effects from backend
        JsonObject hw = resp["hardware"];
        if (hw.containsKey("brightness")) {
            brightness = hw["brightness"];
        }
        setEmotionLight(current_emotion, current_intensity);

        Serial.println("✅ Chat response received");
    }
    http.end();
}

void sendHeartbeat() {
    if (WiFi.status() != WL_CONNECTED) return;
    if (millis() - last_heartbeat < 30000) return;
    last_heartbeat = millis();

    HTTPClient http;
    http.begin(String(API_HOST) + "/api/hardware/heartbeat");
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<128> doc;
    doc["user_id"] = user_id;
    doc["device_id"] = device_id;
    doc["touch_count"] = touch_count;
    doc["emotion"] = current_emotion;

    String body;
    serializeJson(doc, body);
    http.POST(body);
    http.end();
}

void bondDevice() {
    HTTPClient http;
    http.begin(String(API_HOST) + "/api/bond");
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<128> doc;
    doc["device_id"] = device_id;
    doc["name"] = "灵犀";

    String body;
    serializeJson(doc, body);
    int code = http.POST(body);

    if (code == 200) {
        StaticJsonDocument<256> resp;
        deserializeJson(resp, http.getString());
        user_id = resp["user_id"].as<String>();
        bonded = true;
        Serial.println("✅ Device bonded!");
    }
    http.end();
}

// ── Voice Input (INMP441 via I2S) ──────────────────────────────
// TODO: Implement voice activity detection + STT
// For now: long touch (>2s) triggers voice mode

// ── Setup ──────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial.println("\n🪨 灵犀 Lingxi Firmware v1.0");

    // Init LEDs
    leds.begin();
    leds.setBrightness(40);
    leds.clear(); leds.show();

    // Init motor
    pinMode(MOTOR_PIN, OUTPUT);
    digitalWrite(MOTOR_PIN, LOW);

    // Generate device ID
    uint64_t chipid = ESP.getEfuseMac();
    device_id = String((uint32_t)(chipid >> 32), HEX) + String((uint32_t)chipid, HEX);

    // Boot animation — gentle wake up
    for (int b = 0; b <= 60; b += 3) {
        leds.setBrightness(b);
        setEmotionLight("calm", b / 60.0);
        delay(20);
    }
    delay(300);
    setEmotionLight("calm", 0.5);

    // Connect WiFi
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 30) {
        delay(500); Serial.print("."); retries++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✅ WiFi connected");
        bondDevice();
    } else {
        Serial.println("\n⚠️ WiFi failed — standalone mode");
    }

    last_heartbeat = millis();
    last_touch = millis();
    Serial.println("✅ Lingxi ready");
}

// ── Loop ───────────────────────────────────────────────────────
void loop() {
    checkTouch();
    sendHeartbeat();

    // Idle breathing when no interaction
    if (millis() - last_touch > 15000) {
        breatheEffect();
        last_touch = millis() - 10000;
    }

    // Long touch (>2s) — voice mode trigger
    if (touched && millis() - last_touch > 2000) {
        // TODO: Voice recognition
        // For now: send a preset message
        sendChat("我碰了碰你");
        last_touch = millis();
    }

    delay(50);
}
