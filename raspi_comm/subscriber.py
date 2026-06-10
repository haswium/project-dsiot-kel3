import mysql.connector
import paho.mqtt.client as mqtt
import json

DB_CONFIG = {
    "host": "localhost",
    "user": "kelompok3",
    "password": "**kelompok3",
    "database": "dsiot_kelompok3"
}

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[VPS] Terhubung ke Broker Netbird!")
    client.subscribe("ido/kelompok3/tes")    # Jalur data HRV
    client.subscribe("/kamera/foto") # Jalur data foto dari Raspi
    print("[VPS] Standby mendengarkan topik '/tes_coba' dan '/kamera/foto'...")

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    print(f"Data masuk dari HiveMQ: {payload}")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        # JALUR 1: Jika data yang masuk adalah angka (HRV)
        if msg.topic == "ido/kelompok3/tes":
            print(f"\n[DATA SENSOR MASUK] Menerima JSON: {payload}")
            data = json.loads(payload)
            bpm_val = data.get('bpm', 0)
            rmssd_val = data.get('rmssd', 0)
            query = "INSERT INTO log_sensor (nilai_sensor) VALUES (%s)"
            cursor.execute(query, (bpm_val,))
            conn.commit()
            print("[DB SUCCESS] Angka sensor berhasil disimpan ke tabel log_sensor!")

        # JALUR 2: Jika data yang masuk adalah FOTO Base64
        elif msg.topic == "/kamera/foto":
            print(f"\n[DATA FOTO MASUK] Menerima foto Base64 ({foto_string[:50]}...)")
            query = "INSERT INTO log_foto (foto_base64) VALUES (%s)"
            cursor.execute(query, (payload,))
            conn.commit()
            print("[DB SUCCESS] String foto berhasil disimpan ke tabel log_foto!")

    except Exception as e:
        print(f"[ERROR VPS] Gagal memproses data MQTT: {e}")
    finally:
        cursor.close()
        conn.close()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

print("[SYSTEM VPS] Menghidupkan mesin subscriber...")
client.connect("broker.hivemq.com", 1883, 60)
client.loop_forever()
