from flask import Flask, render_template, jsonify
import smbus
import time
import threading
from collections import deque

app = Flask(__name__)

# I2C setup
I2C_ADDR = 0x10
bus = smbus.SMBus(1)

data_lock = threading.Lock()
sensor_data = {
    "red": 0,
    "green": 0,
    "blue": 0,
    "total_light": 0,
    "ir": 0
}

# Buffers pour moyenne glissante
buffer_size = 5  # Nombre de points pour lisser les variations
buffers = {
    "red": deque(maxlen=buffer_size),
    "green": deque(maxlen=buffer_size),
    "blue": deque(maxlen=buffer_size),
    "total_light": deque(maxlen=buffer_size),
    "ir": deque(maxlen=buffer_size)
}

def average(buf):
    return sum(buf) // len(buf) if buf else 0

def init_veml3328():
    CONFIG = 0x0000
    config_swapped = ((CONFIG & 0xFF) << 8) | (CONFIG >> 8)
    bus.write_word_data(I2C_ADDR, 0x00, config_swapped)
    time.sleep(0.1)

def read_word(register):
    raw = bus.read_word_data(I2C_ADDR, register)
    return ((raw & 0xFF) << 8) | (raw >> 8)

def read_all_channels():
    clear = read_word(0x04)
    red   = read_word(0x05)
    green = read_word(0x06)
    blue  = read_word(0x07)
    ir    = read_word(0x08)
    return red, green, blue, clear, ir

def sensor_loop():
    while True:
        try:
            red, green, blue, clear, ir = read_all_channels()

            buffers["red"].append(red)
            buffers["green"].append(green)
            buffers["blue"].append(blue)
            buffers["total_light"].append(clear)
            buffers["ir"].append(ir)

            with data_lock:
                sensor_data["red"] = average(buffers["red"])
                sensor_data["green"] = average(buffers["green"])
                sensor_data["blue"] = average(buffers["blue"])
                sensor_data["total_light"] = average(buffers["total_light"])
                sensor_data["ir"] = average(buffers["ir"])

            print(f"[LOG] R: {sensor_data['red']}, G: {sensor_data['green']}, B: {sensor_data['blue']}, Light: {sensor_data['total_light']}, IR: {sensor_data['ir']}")
            time.sleep(1)
        except Exception as e:
            print("Erreur de lecture :", e)
            break

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    with data_lock:
        return jsonify(sensor_data)

if __name__ == "__main__":
    init_veml3328()
    t = threading.Thread(target=sensor_loop)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
