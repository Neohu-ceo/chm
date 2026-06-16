/**
 * 戳戳 ChuoChuo — ESP32-C3 Firmware
 *
 * Hardware: ESP32-C3 + 8×8 LED Matrix (WS2812) + Touch Sensor + Vibration Motor
 * Build:   PlatformIO (platform: espressif32, board: esp32-c3-devkitm-1)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

// ── Configuration ──────────────────────────────────────────────
#define LED_PIN         8
#define TOUCH_PIN       2
#define MOTOR_PIN       4
#define LED_COUNT       64
#define LED_BRIGHTNESS  40

#define WIFI_SSID       "ChuoChuo_Setup"
#define WIFI_PASS       "chuochuo123"
#define API_HOST        "http://192.168.1.100:5002"

// ── Globals ────────────────────────────────────────────────────
Adafruit_NeoPixel leds(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
String device_id = "";
String device_secret = "";
String current_emotion = "happy";
unsigned long last_interaction = 0;
int poke_count = 0;
bool paired = false;

// ── Emotion Patterns (8×8 bitmap) ──────────────────────────────
struct Emotion {
    const char* name;
    const uint32_t colors[64];
};

// Pre-defined emotion RGB colors for LED matrix
const uint32_t C_BLACK  = 0x000000;
const uint32_t C_ORANGE = 0xFF6B35;
const uint32_t C_PINK   = 0xE8879A;
const uint32_t C_BLUE   = 0x5B9BD5;
const uint32_t C_GREEN  = 0x6BAF6B;

Emotion emotions[] = {
    {"happy", {
        C_BLACK,C_BLACK,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_BLACK,C_BLACK,
        C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,
        C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,
        C_ORANGE,C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,C_ORANGE,
        C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,
        C_BLACK,C_ORANGE,C_BLACK,C_ORANGE,C_ORANGE,C_BLACK,C_ORANGE,C_BLACK,
        C_BLACK,C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_ORANGE,C_ORANGE,C_BLACK,C_BLACK,C_BLACK,
    }},
    {"sleepy", {
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_BLACK,
        C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_BLUE,C_BLUE,C_BLUE,C_BLACK,C_BLACK,
        C_BLACK,C_BLACK,C_BLUE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
    }},
    {"angry", {
        C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_ORANGE,C_BLACK,
        C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,
        C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,C_BLACK,
        C_BLACK,C_BLACK,C_ORANGE,C_BLACK,C_BLACK,C_ORANGE,C_BLACK,C_BLACK,
    }},
};

const int NUM_EMOTIONS = sizeof(emotions) / sizeof(Emotion);

// ── LED Display ────────────────────────────────────────────────

void showEmotion(const char* name) {
    for (int i = 0; i < NUM_EMOTIONS; i++) {
        if (strcmp(emotions[i].name, name) == 0) {
            for (int j = 0; j < LED_COUNT; j++) {
                leds.setPixelColor(j, emotions[i].colors[j]);
            }
            leds.setBrightness(LED_BRIGHTNESS);
            leds.show();
            current_emotion = name;
            return;
        }
    }
}

void breatheEffect() {
    // Soft breathing animation when idle
    for (int b = 20; b <= 60; b += 2) {
        leds.setBrightness(b);
        leds.show();
        delay(30);
    }
    for (int b = 60; b >= 20; b -= 2) {
        leds.setBrightness(b);
        leds.show();
        delay(30);
    }
}

void pokeReaction() {
    // Flash bright on poke
    leds.setBrightness(150);
    leds.show();
    delay(50);
    leds.setBrightness(LED_BRIGHTNESS);
    leds.show();
    digitalWrite(MOTOR_PIN, HIGH);
    delay(80);
    digitalWrite(MOTOR_PIN, LOW);
}

// ── API Communication ──────────────────────────────────────────

void syncInteraction(const char* type, int intensity) {
    if (!paired || WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    http.begin(String(API_HOST) + "/api/interactions");
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<256> doc;
    doc["device_id"] = device_id;
    doc["secret"] = device_secret;
    doc["type"] = type;
    doc["intensity"] = intensity;
    doc["emotion_before"] = current_emotion;

    String body;
    serializeJson(doc, body);
    int code = http.POST(body);
    http.end();

    if (code == 200) {
        Serial.println("✅ Interaction synced");
    }
}

void checkForUpdates() {
    // OTA update check — placeholder
    // In production: GET /api/devices/{id}/update with firmware version check
}

// ── BLE Pairing ────────────────────────────────────────────────

BLEServer* bleServer = nullptr;
BLECharacteristic* pairChar = nullptr;

class PairCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* ch) {
        String data = ch->getValue().c_str();
        StaticJsonDocument<128> doc;
        deserializeJson(doc, data);
        if (doc.containsKey("device_id")) {
            device_id = doc["device_id"].as<String>();
            device_secret = doc["secret"].as<String>();
            paired = true;
            Serial.println("✅ Device paired via BLE");
            showEmotion("happy");
            delay(1000);
        }
    }
};

void setupBLE() {
    BLEDevice::init("戳戳-ChuoChuo");
    bleServer = BLEDevice::createServer();
    BLEService* svc = bleServer->createService("0000ff00-0000-1000-8000-00805f9b34fb");
    pairChar = svc->createCharacteristic(
        "0000ff01-0000-1000-8000-00805f9b34fb",
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE
    );
    pairChar->setCallbacks(new PairCallback());
    svc->start();
    bleServer->getAdvertising()->start();
    Serial.println("📡 BLE advertising as '戳戳-ChuoChuo'");
}

// ── Main ───────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    Serial.println("\n🖐️ 戳戳 ChuoChuo Firmware v1.0.0");

    // Init hardware
    leds.begin();
    leds.setBrightness(LED_BRIGHTNESS);
    leds.clear();
    leds.show();

    pinMode(MOTOR_PIN, OUTPUT);
    digitalWrite(MOTOR_PIN, LOW);

    // Show boot animation
    showEmotion("happy");
    delay(500);
    showEmotion("sleepy");
    delay(300);
    showEmotion("happy");
    delay(200);

    // Setup BLE for pairing
    setupBLE();

    // Connect WiFi
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int wifi_retries = 0;
    while (WiFi.status() != WL_CONNECTED && wifi_retries < 20) {
        delay(500);
        Serial.print(".");
        wifi_retries++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✅ WiFi connected");
    } else {
        Serial.println("\n⚠️ WiFi failed — BLE only mode");
    }

    last_interaction = millis();
    Serial.println("✅ Firmware ready");
}

void loop() {
    unsigned long now = millis();

    // Touch sensor
    int touch_val = touchRead(TOUCH_PIN);
    if (touch_val < 30) {  // Touched
        if (now - last_interaction > 500) {
            poke_count++;
            pokeReaction();
            syncInteraction("poke", min(poke_count, 10));
            last_interaction = now;
            Serial.printf("👆 Poke #%d (touch=%d)\n", poke_count, touch_val);
            poke_count = 0;
        }
    }

    // Idle breathing when no interaction for 10s
    if (now - last_interaction > 10000) {
        breatheEffect();
        last_interaction = now - 5000;  // Don't breathe too fast
    }

    // Periodic sync
    static unsigned long last_sync = 0;
    if (now - last_sync > 60000) {  // Every 60s
        checkForUpdates();
        last_sync = now;
    }

    delay(50);
}
