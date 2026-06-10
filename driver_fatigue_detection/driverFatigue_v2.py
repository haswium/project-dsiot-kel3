# importing the necessary packages
from scipy.spatial import distance as dist
from imutils import face_utils
import numpy as np
import imutils
import dlib
import cv2

import time # Perbaikan import time
import paho.mqtt.client as mqtt
import json # untuk data ESP

# --- KONFIGURASI ---
subscriber = "100.88.25.26" 
topic_cam = "/status_cam"
topic_tired = "/is_tired"
topic_hrv = "/hrv"

latest_bpm = 0
latest_rmssd = 0

# --- FUNGSI MQTT ---
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[SUKSES] Terhubung ke VPS Broker ({subscriber})")
    client.subscribe(topic_hrv)
    print(f"Mendengarkan topik: {topic_hrv} ...")

def on_message(client, userdata, msg):
    global latest_bpm, latest_rmssd
    if msg.topic == topic_hrv:
        try:
            # Membaca data JSON dari ESP: {"bpm": 80, "rmssd": 25.5}
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            latest_bpm = data.get("bpm", 0)
            latest_rmssd = data.get("rmssd", 0)
        except Exception as e:
            pass

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
print("Menghubungkan ke MQTT Broker di VPS...")
client.connect(subscriber, 1883, 60)
client.loop_start() # Jalankan MQTT di background

#calculating eye aspect ratio
def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C)
    return ear

#calculating mouth aspect ratio
def mouth_aspect_ratio(mou):
    X   = dist.euclidean(mou[0], mou[6])
    Y1  = dist.euclidean(mou[2], mou[10])
    Y2  = dist.euclidean(mou[4], mou[8])
    Y   = (Y1+Y2)/2.0
    mar = Y/X
    return mar

camera = cv2.VideoCapture('http://100.88.166.213:5000/video_feed')
predictor_path = 'shape_predictor_68_face_landmarks.dat'

# define constants for aspect ratios
EYE_AR_THRESH = 0.25
EYE_AR_CONSEC_FRAMES = 48
MOU_AR_THRESH = 0.75

COUNTER = 0
yawnStatus = False
yawns = 0

detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(predictor_path)
(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
(mStart, mEnd) = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]

# Timer untuk Publish
last_publish_time = time.time()

# loop over capturing video
while True:
    ret, frame = camera.read()
    if not ret:
        continue

    frame = imutils.resize(frame, width=640)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    prev_yawn_status = yawnStatus
    rects = detector(gray, 0)

    # Secara bawaan, anggap tidak ngantuk
    kamera_deteksi_ngantuk = False

    # loop over the face detections
    for rect in rects:
        shape = predictor(gray, rect)
        shape = face_utils.shape_to_np(shape)

        leftEye = shape[lStart:lEnd]
        rightEye = shape[rStart:rEnd]
        mouth = shape[mStart:mEnd]
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)
        mouEAR = mouth_aspect_ratio(mouth)
        ear = (leftEAR + rightEAR) / 2.0

        leftEyeHull = cv2.convexHull(leftEye)
        rightEyeHull = cv2.convexHull(rightEye)
        mouthHull = cv2.convexHull(mouth)
        cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 255), 1)
        cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 255), 1)
        cv2.drawContours(frame, [mouthHull], -1, (0, 255, 0), 1)

        if ear < EYE_AR_THRESH:
            COUNTER += 1
            cv2.putText(frame, "Eyes Closed ", (10, 30),cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            if COUNTER >= EYE_AR_CONSEC_FRAMES:
                cv2.putText(frame, "DROWSINESS ALERT!", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                kamera_deteksi_ngantuk = True # Perbaikan nama variabel!
        else:
            COUNTER = 0
            cv2.putText(frame, "Eyes Open ", (10, 30),cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.putText(frame, "EAR: {:.2f}".format(ear), (480, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        if mouEAR > MOU_AR_THRESH:
            cv2.putText(frame, "Yawning ", (10, 70),cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            yawnStatus = True
            output_text = "Yawn Count: " + str(yawns + 1)
            cv2.putText(frame, output_text, (10,100),cv2.FONT_HERSHEY_SIMPLEX, 0.7,(255,0,0),2)
        else:
            yawnStatus = False

        if prev_yawn_status == True and yawnStatus == False:
            yawns+=1

        cv2.putText(frame, "MAR: {:.2f}".format(mouEAR), (480, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # --- BLOK PUBLISH MQTT (Di luar loop deteksi wajah agar selalu jalan) ---
    current_time = time.time()
    if current_time - last_publish_time >= 1.0: # Filter 1 detik
        last_publish_time = current_time

        # 1. Tentukan Pesan Kamera
        msg_cam = "pengendara ngantuk" if kamera_deteksi_ngantuk else "pengendara tidak ngantuk"

        # 2. Tentukan Status HRV
        hrv_ngantuk = False
        if latest_bpm > 0: 
            if latest_bpm > 105:
                hrv_status = "Takikardia (>105)" 
            elif 85 <= latest_bpm <= 105:
                hrv_status = "Normal (Fokus)"
            else: 
                hrv_status = "Mengantuk/Kritis (<85)"
                hrv_ngantuk = True
        else:
            hrv_status = "Menunggu Data HRV..."

        # 3. LOGIKA AND (FINAL DECISION)
        if kamera_deteksi_ngantuk and hrv_ngantuk:
            msg_is_tired = "pengendara ngantuk"
        else:
            msg_is_tired = "pengendara tidak ngantuk"

        # 4. Kirim ke VPS
        client.publish(topic_cam, msg_cam)
        client.publish(topic_tired, msg_is_tired)

        print(f"BPM: {latest_bpm} ({hrv_status}) | CAM: {msg_cam} | FINAL: {msg_is_tired}")

    # show the frame
    cv2.imshow("Frame", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

# do a bit of cleanup
cv2.destroyAllWindows()
camera.release()
client.disconnect()