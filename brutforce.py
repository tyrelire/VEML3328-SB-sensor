import requests
import json
import time
from datetime import datetime

# === CONFIG ===
BASE_BARCODE = 501520023
DELTA = 20000
SLEEP_BETWEEN_CALLS = 0.2

BARCODE_API_URL = "http://192.168.40.59/suivi_numero_api.php"
CONFIG_API_URL = "http://163.172.70.144/time_tracking/webservices/get_config_by_reference.php"

OUTPUT_FILE = f"found_barcodes_with_limits_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

results = []

for barcode in range(BASE_BARCODE - DELTA, BASE_BARCODE + DELTA + 1):
    print(f"[*] Testing barcode: {barcode}")

    try:
        params = {
            "numserie": str(barcode),
            "client": "",
            "article": "",
            "excel": "0"
        }
        resp = requests.get(BARCODE_API_URL, params=params, timeout=5)
        resp.raise_for_status()

        data = json.loads(resp.content.decode('utf-8-sig'))

        if not data.get("donnees") or not isinstance(data["donnees"], list) or len(data["donnees"]) == 0:
            continue

        produit = data["donnees"][0]
        code_article = produit.get("code_article", "").strip()

        if not code_article:
            continue

        print(f"  [+] Found product with code_article: {code_article}")

        config_resp = requests.get(CONFIG_API_URL, params={"reference": code_article}, timeout=5)
        config_resp.raise_for_status()
        raw_content = config_resp.content.decode("utf-8-sig")

        raw_data = json.loads(raw_content)

        if not raw_data or not isinstance(raw_data, list) or len(raw_data) == 0:
            print(f"  [-] No limits for code_article {code_article}")
            continue

        entry = raw_data[0]

        limits = {
            "red": {
                "min": int(entry.get("p1red_min_red", 0)),
                "max": int(entry.get("p1red_max_red", 65535))
            },
            "green": {
                "min": int(entry.get("p1red_min_green", 0)),
                "max": int(entry.get("p1red_max_green", 65535))
            },
            "blue": {
                "min": int(entry.get("p1red_min_blue", 0)),
                "max": int(entry.get("p1red_max_blue", 65535))
            }
        }

        has_meaningful_limits = any(
            (limits[color]["min"] > 0 or limits[color]["max"] < 65535)
            for color in ["red", "green", "blue"]
        )

        if has_meaningful_limits:
            print(f"  [✅] Storing barcode {barcode} with limits.")
            result_entry = {
                "barcode": barcode,
                "code_article": code_article,
                "product": produit,
                "limits": limits
            }
            results.append(result_entry)

            with open(OUTPUT_FILE, "a") as f:
                f.write(json.dumps(result_entry, ensure_ascii=False) + "\n")
        else:
            print(f"  [-] Limits for {code_article} are default / uninteresting.")

    except Exception as e:
        print(f"[ERROR] Barcode {barcode}: {e}")

    time.sleep(SLEEP_BETWEEN_CALLS)

print()
print(f"[DONE] Finished scanning. Results saved in {OUTPUT_FILE}")
