#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"

MAX30105 particleSensor;

// Variabel untuk HRV (RMSSD)
unsigned long lastBeatTime = 0;
long rrInterval = 0;
long lastRRInterval = 0;
float sumRRDiffSq = 0;
int beatCount = 0;
float rmssd = 0;

// Variabel untuk BPM
const byte RATE_SIZE = 10; 
byte rates[RATE_SIZE];
byte rateSpot = 0;
float beatsPerMinute;
int beatAvg;

void setup() {
  Serial.begin(115200);
  Serial.println("--- DSIOT KELOMPOK 3: ADVANCE HRV SYSTEM ---");

  // Inisialisasi I2C (SDA: 21, SCL: 22)
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("FATAL ERROR: Sensor MAX30102 tidak terdeteksi!");
    Serial.println("Cek Solderan I2C di GPIO 21 & 22");
    while (1);
  }

  // Setting Sensor Optimal untuk Deteksi Kelelahan
  byte ledBrightness = 60; // 0=Off to 255=50mA
  byte sampleAverage = 4;   // 1, 2, 4, 8, 16, 32
  byte ledMode = 2;         // 1 = Red only, 2 = Red + IR
  int sampleRate = 100;     // 50, 100, 200, 400, 800
  int pulseWidth = 411;     // 69, 118, 215, 411
  int adcRange = 4096;      // 2048, 4096, 8192, 16384

  particleSensor.setup(ledBrightness, sampleAverage, ledMode, sampleRate, pulseWidth, adcRange);
}

void loop() {
  long irValue = particleSensor.getIR();

  // Jika jari terdeteksi (IR > 50000)
  if (irValue > 50000) {
    if (checkForBeat(irValue) == true) {
      unsigned long currentBeatTime = millis();
      
      // 1. Hitung BPM
      beatsPerMinute = 60 / ((currentBeatTime - lastBeatTime) / 1000.0);
      
      if (beatsPerMinute < 255 && beatsPerMinute > 20) {
        rates[rateSpot++] = (byte)beatsPerMinute;
        rateSpot %= RATE_SIZE;
        beatAvg = 0;
        for (byte x = 0; x < RATE_SIZE; x++) beatAvg += rates[x];
        beatAvg /= RATE_SIZE;

        // 2. Hitung HRV (RMSSD) - Fitur Penting buat AI
        if (lastBeatTime > 0) {
          rrInterval = currentBeatTime - lastBeatTime;
          if (lastRRInterval > 0) {
            long diff = rrInterval - lastRRInterval;
            sumRRDiffSq += pow(diff, 2);
            beatCount++;
            rmssd = sqrt(sumRRDiffSq / beatCount);
          }
          lastRRInterval = rrInterval;
        }
        lastBeatTime = currentBeatTime;

        // 3. Print Data untuk Serial Plotter & MQTT
        Serial.print("BPM:"); Serial.print(beatAvg);
        Serial.print(",RR_ms:"); Serial.print(rrInterval);
        Serial.print(",RMSSD:"); Serial.print(rmssd);
        Serial.println();
      }
    }
  } else {
    // Reset data jika jari dilepas
    Serial.println("STATUS: Tempelkan Jari!");
    beatCount = 0;
    sumRRDiffSq = 0;
    lastBeatTime = 0;
  }
}
