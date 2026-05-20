# Ini adalah directory untuk di dalam raspi

## libraries requirement 
- cv2
- imutils
- dlib
- scipy
- paho-mqtt

### create venv & install libraries
```bash
cd ~/
python -m venv venv_1
. ~/venv_1/bin/activate
pip install cv2 imutils dlib scipy paho-mqtt
```

## Script untuk stream kamera 
```bash
cd project-dsiot-kel3/raspi_comm
./stream.sh
```

## Script untuk publisher ke vps 
```bash
cd project-dsiot-kel3/raspi_comm
python3 publisher.py
```
