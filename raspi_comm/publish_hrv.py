import paho.mqtt.client as mqtt
import time

# ================= KONFIGURASI =================

# 1. BROKER SUMBER (Tempat ESP mengirim data)
BROKER_ESP = "broker.hivemq.com" 
PORT_ESP = 1883
TOPIC_ESP = "kelompok3/hrv"

# 2. BROKER TUJUAN 1 (IP Netbird Laptop Mamat)
BROKER_LAPTOP = "100.88.34.107" 
PORT_LAPTOP = 1883
TOPIC_LAPTOP = "/hrv"

# 3. BROKER TUJUAN 2 (IP VPS Netbird)
BROKER_VPS = "100.88.25.26" # <-- Aku betulkan ke IP VPS kamu
PORT_VPS = 1883
TOPIC_VPS = "/hrv"

# ===============================================

# Inisialisasi 3 Klien MQTT secara terpisah
client_esp = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Raspi_Receiver")
client_laptop = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Raspi_Forwarder_Laptop")
client_vps = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Raspi_Forwarder_VPS")

# --- KUMPULAN FUNGSI CALLBACK ---

def on_connect_esp(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[SUKSES] Terhubung ke Broker ESP ({BROKER_ESP})")
        # Begitu konek, langsung subscribe ke topik HRV
        client.subscribe(TOPIC_ESP)
        print(f" Mendengarkan topik: {TOPIC_ESP} dari ESP...")
    else:
        print(f"[GAGAL] Konek ke Broker ESP. Kode: {reason_code}")

def on_message_esp(client, userdata, msg):
    # Ekstrak data yang diterima dari ESP
    payload = msg.payload.decode('utf-8')
    print(f"[TERIMA] Dari ESP -> Topik: {msg.topic} | Data HRV: {payload}")
    
    # Langsung lempar (publish) data tersebut ke Broker Laptop & VPS
    client_laptop.publish(TOPIC_LAPTOP, payload)
    client_vps.publish(TOPIC_VPS, payload)
    
    print(f"[KIRIM] Di-forward ke Laptop & VPS -> Topik: {TOPIC_LAPTOP} | Data: {payload}")
    print("-" * 50)

# Pasang fungsi callback ke klien ESP
client_esp.on_connect = on_connect_esp
client_esp.on_message = on_message_esp

# --- EKSEKUSI KONEKSI ---

print("Memulai Sistem Jembatan (Bridge) MQTT Raspi...")

# 1. Konek ke Broker Laptop & VPS (dijalankan di latar belakang)
print("Menghubungkan ke Broker Laptop dan VPS Target...")
try:
    # Eksekusi Laptop
    client_laptop.connect(BROKER_LAPTOP, PORT_LAPTOP, 60)
    client_laptop.loop_start() 
    
    # Eksekusi VPS
    client_vps.connect(BROKER_VPS, PORT_VPS, 60)
    client_vps.loop_start()
    
    print("✅ [SUKSES] Terhubung ke Broker Laptop & VPS (Netbird)")
except Exception as e:
    print(f"⚠️ [ERROR] Tidak bisa konek ke Broker Target: {e}")

# 2. Konek ke Broker ESP (dijalankan di loop utama agar terus mendengarkan)
print(f"Menghubungkan ke Broker ESP ({BROKER_ESP})...")
try:
    client_esp.connect(BROKER_ESP, PORT_ESP, 60)
    # loop_forever() akan membuat skrip ini terus berjalan (standby)
    client_esp.loop_forever() 
except KeyboardInterrupt:
    print("\n🛑 Sistem dihentikan oleh user (Ctrl+C).")
except Exception as e:
    print(f"⚠️ [ERROR] Konek ke ESP gagal: {e}")
finally:
    client_esp.disconnect()
    client_laptop.disconnect()
    client_vps.disconnect()
    print("Koneksi ditutup. Selamat istirahat!")
