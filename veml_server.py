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
        logger.info(f"Config brute renvoyée : {entry}")
        return jsonify(entry)

    except Exception as e:
        logger.error(f"Erreur config : {e}")
        return jsonify({})

@app.route("/api/measure-stream")
def api_measure_stream():
    config_raw = request.args.get("limits")
    try:
        config_list = json.loads(config_raw)
        config = config_list[0] if isinstance(config_list, list) else config_list
    except:
        return jsonify({"error": "Invalid config JSON"}), 400

    phase_to_main_color = {
        "p1red": "red",
        "p2green": "green",
        "p3blue": "blue",
        "p4white": "total_light"
    }

    phases = []
    for phase_name, color in phase_to_main_color.items():
        try:
            start = int(config.get(f"{phase_name}_start", 0))
            end = int(config.get(f"{phase_name}_end", 0))
            json_color = "white" if color == "total_light" else color
            min_val = int(config.get(f"{phase_name}_min_{json_color}", 0))
            max_val = int(config.get(f"{phase_name}_max_{json_color}", 0))

            # if min_val == 0 and max_val == 0:
            #     continue

            phases.append({
                "name": phase_name,
                "start": start,
                "end": end,
                "color": color,
                "limits": {
                    "min": min_val,
                    "max": max_val
                }
            })
        except Exception as e:
            logger.warning(f"Erreur parsing phase {phase_name}: {e}")

    logger.info(f"Phases extraites : {phases}")

    def generate():
        start_time = time.time()
        all_values = []
        failed_checks = []
        final_result = "GO"

        for phase in sorted(phases, key=lambda p: p["start"]):
            wait = phase["start"] - int((time.time() - start_time) * 1000)
            if wait > 0:
                time.sleep(wait / 1000)

            logger.info(f"Phase active : {phase['name']} ({phase['start']}–{phase['end']} ms)")
            elapsed = int((time.time() - start_time) * 1000)
            values = read_all_channels()
            all_values.append({"t": elapsed, "values": values})
            color = phase["color"]
            val_raw = values.get(color, 0)
            val_8bit = round((val_raw / 65535) * 255)
            min_ = phase["limits"]["min"]
            max_ = phase["limits"]["max"]

            logger.info(f"[{elapsed} ms] {color.upper()} = {val_raw} raw (~{val_8bit}/255), limites : {min_}–{max_}")

            if val_8bit < min_ or val_8bit > max_:
                final_result = "NO GO"
                failed_checks.append({
                    "phase": phase["name"],
                    "channel": color,
                    "value_raw": val_raw,
                    "value_8bit": val_8bit,
                    "min_raw": round((min_ / 255) * 65535),
                    "max_raw": round((max_ / 255) * 65535),
                    "min_8bit": min_,
                    "max_8bit": max_,
                    "time_ms": elapsed
                })

                logger.warning(f"⚠️ {color.upper()} hors limite pendant {phase['name']}")

            yield f"data: {json.dumps({'time_ms': elapsed, 'values': {color: val_raw}})}\n\n"

        log_path = os.path.join(log_dir, f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        with open(log_path, "w") as f:
            for entry in all_values:
                f.write(json.dumps(entry) + "\n")
            f.write(f"Resultat final: {final_result}\n")
            if failed_checks:
                f.write(f"Non conformités: {json.dumps(failed_checks)}\n")

        logger.info(f"Resultat final du test : {final_result}")
        yield f"data: {json.dumps({'final_result': final_result, 'failed_checks': failed_checks})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

# === Route API : renvoie le nom du dernier log de test généré ===
@app.route("/api/last-test-log")
def api_last_test_log():
    # Liste les fichiers de log commençant par "test_" et prend le plus récent
    test_logs = sorted([f for f in os.listdir(log_dir) if f.startswith("test_")], reverse=True)
    if test_logs:
        return jsonify({"test_log_filename": test_logs[0]})
    return jsonify({"test_log_filename": None})

# === Route API : téléchargement sécurisé d'un fichier log ===
@app.route("/download-log/<filename>")
def download_log(filename):
    # Vérifie que le nom de fichier est valide et ne contient pas de tentative d'accès interdit
    if not (filename.endswith(".log") and (".." not in filename)):
        return abort(403)

    path = os.path.join(log_dir, filename)
    if not os.path.isfile(path):
        return abort(404)

    try:
        # Copie le fichier dans un fichier temporaire pour éviter les problèmes de verrouillage
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copy2(path, tmp.name)
            tmp_path = tmp.name
        # Envoie le fichier en pièce jointe au client
        return send_file(tmp_path, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Erreur envoi fichier log : {e}")
        return f"Erreur : {e}", 500

# === Point d'entrée principal du serveur Flask ===
if __name__ == "__main__":
    logger.info(f"Flask en ligne sur 0.0.0.0:5000 • Log : {log_file}")
    app.run(host="0.0.0.0", port=5000, debug=False)
