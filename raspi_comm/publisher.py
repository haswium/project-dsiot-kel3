import paho.mqtt.client as mqtt
import random
import time

# --- KONFIGURASI ---
#vps aiot 100.88.25.26
#laptop rahmat 100.88.34.107

MQTT_BROKER = "100.88.34.107" 
MQTT_TOPIC = "/tes_coba"

# Menggunakan API Version 2 agar tidak kena Warning
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

try:
    # Hubungkan ke broker
    client.connect(MQTT_BROKER, 1883, 60)
    print(f"Berhasil terhubung ke Broker: {MQTT_BROKER}")
    
    while True:
        angka_random = round(random.uniform(20.0, 35.0), 2)
        
        # Kirim data
        result = client.publish(MQTT_TOPIC, str(angka_random))
        
        # Cek apakah terkirim
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Sent: {angka_random} to {MQTT_TOPIC}")
        else:
            print("Gagal mengirim pesan")
            
        time.sleep(5)
        
except Exception as e:
    print(f"Waduh, Error: {e}")
    print("Tips: Pastikan Netbird sudah 'up' dan IP VPS sudah benar.")
