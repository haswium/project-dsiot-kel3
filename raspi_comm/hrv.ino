#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"

// --- 1. SETTING NETWORK & SERVER ---
const char* ssid = "BarunKontrak";
const char* password = "abangputih123";
const char* mqtt_server = "103.94.191.134";
const char* mqtt_topic = "dsiot/kel3/fatigue";

WiFiClient espClient;
PubSubClient client(espClient);
MAX30105 particleSensor;

// --- 2. VARIABEL BEAT AVERAGING ---
const byte RATE_SIZE = 5; 
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;
float beatsPerMinute;
int beatAvg = 0;

// --- 3. VARIABEL BIOMETRIK HRV ---
unsigned long lastBeatTime = 0;
long rrInterval = 0;
long lastRRInterval = 0;
float sumRRDiffSq = 0;
int beatCount = 0;
float rmssd = 0;

bool wifiActive = false;
unsigned long lastPrintTime = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("\n--- MODE FINETUNING LOW POWER START ---");

  // Alokasikan pin I2C secara manual
  Wire.begin(21, 22);
  Wire.setClock(100000);

  if (!particleSensor.begin(Wire, I2C_SPEED_STANDARD)) {
    Serial.println("Sensor tidak ditemukan! Periksa hardware.");
    while (1);
  }

  // Setingan konfigurasinya disamakan dengan mode hemat daya yang tadi berhasil tembus 50k
  byte ledBrightness = 0x1F; 
  byte sampleAverage = 4; 
  byte ledMode = 2; 
  int sampleRate = 100; 
  int pulseWidth = 411; 
  int adcRange = 4096; 

  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
}

void loop() {
  long irValue = particleSensor.getIR();

  // Jika jari terdeteksi secara fisik
  if (irValue > 30000) {
    // Fungsi ini dipanggil terus-menerus tanpa delay agar pendeteksian tidak kelewat
    if (checkForBeat(irValue) == true) {
      long delta = millis() - lastBeat;
      lastBeat = millis();
      beatsPerMinute = 60 / (delta / 1000.0);

      if (beatsPerMinute < 255 && beatsPerMinute > 40) {
        rates[rateSpot++] = (byte)beatsPerMinute;
        rateSpot %= RATE_SIZE;
        
        beatAvg = 0;
        for (byte x = 0; x < RATE_SIZE; x++) {
          beatAvg += rates[x];
        }
        beatAvg /= RATE_SIZE;

        unsigned long currentBeatTime = millis();
        if (lastBeatTime > 0) {
          rrInterval = currentBeatTime - lastBeatTime;
          if (lastRRInterval > 0) {
            long diff = rrInterval - lastRRInterval;
            sumRRDiffSq += pow(diff, 2);
            beatCount++;
            rmssd = sqrt(sumRRDiffSq / beatCount);

            // Print langsung setiap ada detak jantung baru yang valid
            Serial.print("IR: "); Serial.print(irValue);
            Serial.print(" | BPM: "); Serial.print(beatAvg);
            Serial.print(" | RMSSD: "); Serial.println(rmssd);

            // Aktifkan pemancar Wi-Fi secara halus hanya jika pembacaan detak internal sudah stabil
            if (!wifiActive && beatCount >= 3) {
              Serial.println("\nMengaktifkan Transmisi Data ke VPS...");
              WiFi.begin(ssid, password);
              client.setServer(mqtt_server, 1883);
              wifiActive = true;
            }

            // Kirim paket data ke broker MQTT di Cloud VPS
            if (wifiActive && WiFi.status() == WL_CONNECTED) {
              if (!client.connected()) {
                String clientId = "ESP32_Kel3_" + String(random(0, 0xFFFF), HEX);
                client.connect(clientId.c_str());
              }
              if (client.connected()) {
                String payload = "{\"bpm\":" + String(beatAvg) + ",\"rmssd\":" + String(rmssd) + "}";
                client.publish(mqtt_topic, payload.c_str());
              }
            }
          }
          lastRRInterval = rrInterval;
        }
        lastBeatTime = currentBeatTime;
      }
    }
  } else {
    // Pengganti delay() menggunakan non-blocking timer agar loop tidak macet
    if (millis() - lastPrintTime > 1000) {
      Serial.print("IR: "); Serial.print(irValue);
      Serial.println(" | Tempelkan jari secara stabil...");
      lastPrintTime = millis();
    }
    // Bersihkan kalkulasi lama jika jari sempat diangkat
    beatCount = 0;
    sumRRDiffSq = 0;
    lastBeatTime = 0;
  }

  // Jalankan background services MQTT
  if (wifiActive && WiFi.status() == WL_CONNECTED) {
    client.loop();
  }
}
