import os
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify
import smbus
import time
import threading
from collections import deque

# === CONFIGURATION DU LOGGING: fichier + terminal ===
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"
log_path = os.path.join(log_dir, log_filename)

log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_path, mode='w')
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

# === FLASK & CAPTEUR SETUP ===
app = Flask(__name__)
I2C_ADDR = 0x10
bus = smbus.SMBus(1)

data_lock = threading.Lock()
sensor_data = {
    "red": 0,
    "green": 0,
    "blue": 0,
    "total_light": 0,
    "ir": 0,
    "corrected_red": 0,
    "corrected_green": 0,
    "corrected_blue": 0,
    "lux_estimate": 0
}

buffer_size = 1
buffers = {k: deque(maxlen=buffer_size) for k in ["red", "green", "blue", "total_light", "ir"]}

def average(buffer):
    return sum(buffer) // len(buffer) if buffer else 0

def init_veml3328():
    try:
        CONFIG = 0x0003  # IT = 100 ms, gain normal, active, mode auto
        config_swapped = ((CONFIG & 0xFF) << 8) | (CONFIG >> 8)
        bus.write_word_data(I2C_ADDR, 0x00, config_swapped)
        time.sleep(0.2)
        logger.info("Capteur VEML3328 initialisé avec succès.")
    except Exception as e:
        logger.error(f"Erreur d'initialisation du capteur : {e}")

def read_channel(lsb_reg):
    lsb = bus.read_byte_data(I2C_ADDR, lsb_reg)
    msb = bus.read_byte_data(I2C_ADDR, lsb_reg + 1)
    return (msb << 8) | lsb

def read_all_channels():
    clear = read_channel(0x04)
    red   = read_channel(0x05)
    green = read_channel(0x06)
    blue  = read_channel(0x07)
    ir    = read_channel(0x08)
    return red, green, blue, clear, ir

def estimate_lux(green, it_ms=100):
    return round(green * 0.0025) if green else 0

def sensor_loop():
    while True:
        try:
            red, green, blue, clear, ir = read_all_channels()

            buffers["red"].append(red)
            buffers["green"].append(green)
            buffers["blue"].append(blue)
            buffers["total_light"].append(clear)
            buffers["ir"].append(ir)

            avg_red = average(buffers["red"])
            avg_green = average(buffers["green"])
            avg_blue = average(buffers["blue"])
            avg_clear = average(buffers["total_light"])
            avg_ir = average(buffers["ir"])

            with data_lock:
                sensor_data.update({
                    "red": avg_red,
                    "green": avg_green,
                    "blue": avg_blue,
                    "total_light": avg_clear,
                    "ir": avg_ir,
                    "corrected_red": int((avg_red / avg_clear) * 65535) if avg_clear else 0,
                    "corrected_green": int((avg_green / avg_clear) * 65535) if avg_clear else 0,
                    "corrected_blue": int((avg_blue / avg_clear) * 65535) if avg_clear else 0,
                    "lux_estimate": estimate_lux(avg_green)
                })

            logger.info(
                f"R={avg_red}, G={avg_green}, B={avg_blue}, Light={avg_clear}, IR={avg_ir}, Lux={sensor_data['lux_estimate']}"
            )
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"Erreur de lecture capteur : {e}")
            break

@app.route("/")
def index():
    logger.info("Accès à la page d'accueil.")
    return render_template("index.html")

@app.route("/api/data")
def api_data():
    logger.info("API /api/data appelée.")
    with data_lock:
        return jsonify(sensor_data)

if __name__ == "__main__":
    init_veml3328()
    t = threading.Thread(target=sensor_loop)
    t.daemon = True
    t.start()
    logger.info("Application Flask démarrée.")
    app.run(host="0.0.0.0", port=5000, debug=False)
