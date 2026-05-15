import paho.mqtt.client as mqtt
import cv2
import base64
import time

# --- KONFIGURASI ---
MQTT_BROKER = "100.88.0.45"  # Ganti dengan IP Netbird VPS kamu
MQTT_TOPIC = "/kamera/foto"

# Setup MQTT Client
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect(MQTT_BROKER, 1883, 60)

# Buka Kamera (0 biasanya /dev/video0, ubah ke 2 jika kameramu di /dev/video2)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Kamera tidak terdeteksi!")
    exit()

# Ambil satu frame gambar
ret, frame = cap.read()

if ret:
    # Resize gambar agar tidak terlalu berat (opsional, tapi disarankan untuk MQTT)
    frame = cv2.resize(frame, (640, 480))
    
    # Encode gambar menjadi format JPG (kompresi)
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    
    # Ubah data biner menjadi teks (Base64) agar aman dikirim lewat MQTT
    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
    
    # Kirim ke VPS
    client.publish(MQTT_TOPIC, jpg_as_text)
    print("✅ Foto berhasil dikirim ke VPS via MQTT!")
else:
    print("❌ Gagal mengambil gambar dari kamera.")

# Tutup kamera
cap.release()
