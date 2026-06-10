from flask import Flask, Response, render_template, jsonify
import paho.mqtt.client as mqtt
import json
import cv2

app = Flask(__name__)

# --- VARIABEL GLOBAL PENYIMPAN DATA TERBARU ---
latest_data = {
    "bpm": 0,
    "cam_status": "Menunggu...",
    "final_status": "Menunggu..."
}

# --- SETUP MQTT UNTUK FLASK ---
def on_message(client, userdata, msg):
    global latest_data
    topik = msg.topic
    payload = msg.payload.decode('utf-8')
    
    if topik == "/hrv":
        try:
            data = json.loads(payload)
            latest_data["bpm"] = data.get("bpm", 0)
        except: 
            pass
    elif topik == "/status_cam":
        latest_data["cam_status"] = payload
    elif topik == "/is_tired":
        latest_data["final_status"] = payload

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message

try:
    print("Menghubungkan Flask ke MQTT VPS...")
    mqtt_client.connect("100.88.25.26", 1883, 60) # Konek ke VPS
    mqtt_client.subscribe([("/hrv", 0), ("/status_cam", 0), ("/is_tired", 0)])
    mqtt_client.loop_start() # Jalan di background tanpa mengganggu kamera
except Exception as e:
    print(f"Gagal konek MQTT di Flask: {e}")

# --- RUTE API UNTUK HTML ---
@app.route('/sensor_data')
def get_sensor_data():
    return jsonify(latest_data)

# --- LOGIKA STREAM KAMERA OPENCV ---
# Inisialisasi kamera Raspi (0 untuk kamera bawaan/USB pertama)
camera = cv2.VideoCapture(0)

# Atur resolusi agar stream lancar di jaringan Netbird
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

def gen_frames():  
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode frame menjadi format JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            
            # Yield frame dalam format multipart HTTP untuk streaming video
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    # Pastikan file index.html berada di dalam folder "templates"
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    # Mengembalikan stream video ke tag <img> di HTML
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- JALANKAN SERVER FLASK ---
if __name__ == '__main__':
    print("Mulai server Flask Kelompok 3 di port 5000...")
    # host='0.0.0.0' agar bisa diakses dari IP Netbird (laptopmu)
    app.run(host='0.0.0.0', port=5000, debug=False)
