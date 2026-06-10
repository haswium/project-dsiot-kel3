import paho.mqtt.client as mqtt
import time

def on_connect(client, userdata, flags, reason_code, properties):
    print(" [SUKSES] Terhubung ke Broker VPS Lokal!")
    # Subscribe ke semua topik sekaligus
    client.subscribe([("/hrv", 0), ("/status_cam", 0), ("/is_tired", 0)])
    print(" Menunggu aliran data dari Raspi dan Laptop...\n" + "="*50)

def on_message(client, userdata, msg):
    waktu = time.strftime('%H:%M:%S')
    topik = msg.topic.ljust(15)
    data = msg.payload.decode('utf-8')
    print(f"[{waktu}] {topik} {data}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

# Pakai 127.0.0.1 karena skrip ini berjalan di dalam VPS itu sendiri
client.connect("127.0.0.1", 1883, 60) 
client.loop_forever()
