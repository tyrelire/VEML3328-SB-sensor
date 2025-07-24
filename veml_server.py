import os
import logging
import random
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response
import requests
import json
from flask import send_file, abort
import tempfile
import shutil

I2C_ADDR = 0x10
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log"
log_file = os.path.join(log_dir, log_file_name)

logging.basicConfig(level=logging.INFO, handlers=[
    logging.FileHandler(log_file, mode='w'),
    logging.StreamHandler()
])
logger = logging.getLogger()

app = Flask(__name__)

def init_veml3328():
    CONFIG = 0x0000
    config_swapped = ((CONFIG & 0xFF) << 8) | (CONFIG >> 8)
    bus.write_word_data(I2C_ADDR, 0x00, config_swapped)
    time.sleep(0.1)
    logger.info("VEML3328 initialisé avec succès (registre 0x00 = 0x0000)")

try:
    import smbus
    bus = smbus.SMBus(1)
    IS_SIMULATION = False
    logger.info("Mode réel : SMBus actif")
except ImportError:
    IS_SIMULATION = True
    logger.warning("Mode simulation : SMBus non dispo")
    init_veml3328()
    bus = None

I2C_ADDR = 0x10

def read_channel(reg):
    if IS_SIMULATION:
        return random.randint(0, 65535)
    lsb = bus.read_byte_data(I2C_ADDR, reg)
    msb = bus.read_byte_data(I2C_ADDR, reg + 1)
    return (msb << 8) | lsb

def read_all_channels():
    return {
        "red": read_channel(0x05),
        "green": read_channel(0x06),
        "blue": read_channel(0x07),
        "total_light": read_channel(0x04),
        "ir": read_channel(0x08)
    }

def scale_8bit_to_16bit(val8):
    return int(val8) * 257

@app.route("/")
def menu():
    return render_template("index.html")

@app.route("/barcode")
def barcode_page():
    return render_template("barcode.html")

@app.route("/select-model")
def select_model():
    return render_template("select-model.html")

@app.route("/dev")
def dev_page():
    return render_template("dev.html")


@app.route("/api/logname")
def api_logname():
    return jsonify({"log_filename": log_file_name})

@app.route("/api/product")
def api_product():
    barcode = request.args.get("barcode")
    if not barcode:
        return jsonify({"error": "No barcode provided"}), 400
    remote_url = f"http://192.168.40.59/suivi_numero_api.php?numserie={barcode}&client=&article=&excel=0"
    logger.info(f"Requete produit vers : {remote_url}")
    try:
        r = requests.get(remote_url, timeout=5)
        r.raise_for_status()
        content = r.content.decode('utf-8-sig')
        data = json.loads(content)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Erreur produit : {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/products")
def api_products():
    try:
        r = requests.get("http://163.172.70.144/time_tracking/webservices/get_products.php", timeout=5)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        logger.error(f"Erreur récupération produits : {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/config")
def api_config():
    code_article = request.args.get("code_article")
    if not code_article:
        return jsonify({"error": "No code_article provided"}), 400
    config_url = f"http://163.172.70.144/time_tracking/webservices/get_config_by_reference.php?reference={code_article}"
    logger.info(f"Requête limites vers : {config_url}")
    try:
        r = requests.get(config_url, timeout=5)
        r.raise_for_status()
        raw_content = r.content.decode("utf-8-sig")
        raw_data = json.loads(raw_content)
        if not raw_data or not isinstance(raw_data, list) or len(raw_data) == 0:
            logger.warning(f"Aucune limite définie pour {code_article}")
            return jsonify({})
        entry = raw_data[0]

        limits = {
            "red": {
                "min": scale_8bit_to_16bit(entry.get("p1red_min_red", 0)),
                "max": scale_8bit_to_16bit(entry.get("p1red_max_red", 255))
            },
            "green": {
                "min": scale_8bit_to_16bit(entry.get("p1red_min_green", 0)),
                "max": scale_8bit_to_16bit(entry.get("p1red_max_green", 255))
            },
            "blue": {
                "min": scale_8bit_to_16bit(entry.get("p1red_min_blue", 0)),
                "max": scale_8bit_to_16bit(entry.get("p1red_max_blue", 255))
            }
        }

        logger.info(f"Limites finales converties en 16 bits : {limits}")
        return jsonify(limits)
    except Exception as e:
        logger.error(f"Erreur config : {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/measure-stream")
def api_measure_stream():
    limits_raw = request.args.get("limits")
    try:
        limits = json.loads(limits_raw) if limits_raw else {}
    except:
        limits = {}

    logger.info(f"Test stream lancé avec limites : {limits}")

    def generate():
        all_values = []
        failed_checks = []
        final_result = "GO"
        start_time = time.time()
        while time.time() - start_time < 8:
            values = read_all_channels()
            logger.info(f"Mesure en cours : {values}")
            all_values.append(values)

            for k, v in limits.items():
                try:
                    min_v = int(v["min"])
                    max_v = int(v["max"])
                    raw_value = values.get(k, 0)
                    if raw_value < min_v or raw_value > max_v:
                        final_result = "NO GO"

                        value_8bit = round(raw_value / 257)
                        min_8bit = round(min_v / 257)
                        max_8bit = round(max_v / 257)

                        failed_checks.append({
                            "channel": k,
                            "value_raw": raw_value,
                            "value_8bit": value_8bit,
                            "min_raw": min_v,
                            "max_raw": max_v,
                            "min_8bit": min_8bit,
                            "max_8bit": max_8bit
                        })
                        break
                except Exception as e:
                    logger.error(f"Erreur de validation limite: {e}")
                    continue

            line = json.dumps({"values": values})
            yield f"data: {line}\n\n"
            time.sleep(0.5)

        with open(os.path.join(log_dir, f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"), "w") as f:
            for entry in all_values:
                f.write(f"{entry}\n")
            f.write(f"Resultat final: {final_result}\n")
            if failed_checks:
                f.write(f"Non conformités: {failed_checks}\n")

        result_message = {
            "final_result": final_result,
            "failed_checks": failed_checks if failed_checks else None
        }
        yield f"data: {json.dumps(result_message)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route("/api/last-test-log")
def api_last_test_log():
    test_logs = sorted([f for f in os.listdir(log_dir) if f.startswith("test_")], reverse=True)
    if test_logs:
        return jsonify({"test_log_filename": test_logs[0]})
    return jsonify({"test_log_filename": None})

@app.route("/download-log/<filename>")
def download_log(filename):
    if not (filename.endswith(".log") and (".." not in filename)):
        return abort(403)

    path = os.path.join(log_dir, filename)
    if not os.path.isfile(path):
        return abort(404)

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copy2(path, tmp.name)
            tmp_path = tmp.name

        return send_file(tmp_path, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Erreur envoi fichier log : {e}")
        return f"Erreur : {e}", 500



if __name__ == "__main__":
    logger.info(f"Flask en ligne sur 0.0.0.0:5000 • Log : {log_file}")
    app.run(host="0.0.0.0", port=5000, debug=False)
