from flask import Flask, Response, render_template
import cv2

# Tambahkan parameter template_folder='webapp' agar Flask tahu di mana mencari file HTML-mu
app = Flask(__name__, template_folder='webapp')
cap = cv2.VideoCapture(0) # Ubah ke 2 jika pakai /dev/video2

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            # Encode ke JPG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            # Format standar untuk stream web (Multipart)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# 1. Route utama untuk halaman web
@app.route('/')
def index():
    return render_template('index.html')

# 2. Route khusus untuk aliran video (Pastikan hanya ada SATU fungsi bernama video_feed di seluruh file ini)
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Tetap jalankan di 0.0.0.0 agar bisa diakses lewat Netbird
    app.run(host='0.0.0.0', port=5000)
