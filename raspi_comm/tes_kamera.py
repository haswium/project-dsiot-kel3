import cv2
import time
import base64
import paho.mqtt.client as mqtt

# Konfigurasi Jaringan Pusat Logi-Nexus
MQTT_BROKER = "100.88.25.26"
MQTT_TOPIC = "/kamera/foto"

print("[RASPI] Menghubungkan ke Broker Netbird VPS...")
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_BROKER, 1883, 60)

# Menggunakan Indeks 0 yang sudah TERBUKTI NYALA di perangkatmu!
cap = cv2.VideoCapture(0)

# Set resolusi kamera agak rendah agar pengiriman Base64 super ringan & real-time
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

print("🚀 [SISTEM AKTIF] Kamera menyala ASLI & NYATA!")
print("Mengirim gambar ke VPS secara kontinu setiap 3 detik. Tekan Ctrl+C untuk stop.")

try:
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("⚠️ Gagal menangkap gambar dari webcam, mencoba lagi...")
            time.sleep(1)
            continue
            
        # Kompresi gambar ke format JPG dengan kualitas 50% (Sangat pas untuk efisiensi bandwidth)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        
        # Encode biner gambar ke string teks Base64
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        
        # Tembak data nyata ke VPS
        result = client.publish(MQTT_TOPIC, jpg_as_text)
        
        # PENGUNCI BIAR DATA TIDAK LENYAP DI JALAN
        result.wait_for_publish() 
        
        print(f"📸 [KIRIM NYATA] Sukses melempar foto ke database VPS! Jam: {time.strftime('%H:%M:%S')}")
        
        # Interval kirim secara kontinu
        time.sleep(3)

except KeyboardInterrupt:
    print("\n[RASPI] Menerima sinyal stop dari user...")
finally:
    # --- PROSES CLEANUP AMAN AGAR KAMERA TIDAK MOGOK LAGI ---
    print("[SISTEM] Membersihkan sesi hardware & jaringan...")
    cap.release()       # Lepas kunci hardware kamera
    client.disconnect() # Putus koneksi MQTT secara terhormat
    print("✅ Selesai! Kamera dan jaringan ditutup dengan aman.")
