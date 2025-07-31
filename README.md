# VEML3328-SB-SENSOR

Interface web Flask pour tester des projecteurs LED à l’aide du capteur de lumière **VEML3328**, avec affichage en temps réel des données, comparaison aux tolérances, et génération automatique de logs.

---

## Fonctionnalités

- **Mesures des canaux** : rouge, vert, bleu, blanc (total_light), infrarouge
- **Tests automatisés** selon configuration (temps + limites)
- **Résultat GO / NO GO** avec détail des erreurs
- **Interface web** simple et rapide
- **Logs complets** téléchargeables

---

## Structure du projet

```
VEML3328-SB-SENSOR/
│
├── veml_server.py                # Serveur Flask principal (API + interface web)
├── brutforce.py                  # Script utilitaire pour tests bruts
├── found_barcodes_with_limits_*.txt # Exports des résultats de tests
├── requirement.txt               # Dépendances Python
├── logs/                         # Dossier des logs générés automatiquement
│
├── static/                       # Fichiers statiques pour l’interface web
│   ├── js/                       # Scripts JavaScript
│   │   ├── barcode.js
│   │   ├── dev.js
│   │   └── select-model.js
│   └── styles/                   # Feuilles de style CSS (optionnel)
│       ├── barcode.css
│       ├── dev.css
│       ├── index.css
│       └── select-model.css
│
├── templates/                    # Templates HTML pour Flask
│   ├── index.html                # Page d’accueil
│   ├── barcode.html              # Page de scan code-barres
│   ├── dev.html                  # Mode développeur
│   └── select-model.html         # Sélection du modèle
```

Chaque dossier/fichier a un rôle précis :

- **veml_server.py** : point d’entrée du serveur, gère les routes et l’API.
- **brutforce.py** : utilitaire pour des tests ou manipulations directes.
- **logs/** : tous les logs générés lors des tests et mesures.
- **static/** : ressources front-end (JS/CSS) pour l’interface utilisateur.
- **templates/** : pages HTML affichées par Flask.
- **requirement.txt** : liste des dépendances Python à installer.
- **found*barcodes_with_limits*\*.txt** : historiques/export des tests réalisés.

---

## API & Routes Flask

Voici la liste des routes disponibles sur le serveur Flask :

| Route                            | Méthode | Description                                                                    |
| -------------------------------- | ------- | ------------------------------------------------------------------------------ |
| `/`                              | GET     | Page d’accueil (interface web principale)                                      |
| `/barcode`                       | GET     | Page de scan de code-barres                                                    |
| `/select-model`                  | GET     | Page de sélection du modèle                                                    |
| `/dev`                           | GET     | Mode développeur                                                               |
| `/api/logname`                   | GET     | Renvoie le nom du fichier log courant (JSON)                                   |
| `/api/product?barcode=...`       | GET     | Infos produit via code-barres (JSON, requête externe)                          |
| `/api/products`                  | GET     | Liste des produits disponibles (JSON, requête externe)                         |
| `/api/config?code_article=...`   | GET     | Limites/tolérances pour un article donné (JSON, requête externe)               |
| `/api/measure-stream?limits=...` | GET     | Stream SSE des mesures en temps réel selon la config (JSON, résultat GO/NO GO) |
| `/api/last-test-log`             | GET     | Renvoie le nom du dernier log de test généré (JSON)                            |
| `/download-log/<filename>`       | GET     | Téléchargement d’un fichier log (sécurisé)                                     |

### Détail des principales routes API

- **`/api/logname`** :

  - Renvoie le nom du fichier log courant.
  - Format : `{ "log_filename": "..." }`

- **`/api/product?barcode=...`** :

  - Renvoie les infos d’un produit à partir d’un code-barres.
  - Format : `{ ... }` (dépend de la réponse externe)

- **`/api/config?code_article=...`** :

  - Renvoie la configuration (limites/tolérances) pour un article donné.
  - Format : `{ ... }` (dépend de la réponse externe)

- **`/api/measure-stream?limits=...`** :

  - Stream SSE (Server-Sent Events) des mesures en temps réel.
  - Paramètre : `limits` (JSON encodé, configuration des phases et tolérances)
  - Renvoie des événements JSON :
    - `{ "time_ms": ..., "values": { ... } }` (valeurs à chaque phase)
    - `{ "final_result": "GO"|"NO GO", "failed_checks": [...] }` (résultat final)

- **`/api/last-test-log`** :

  - Renvoie le nom du dernier log de test généré.
  - Format : `{ "test_log_filename": "..." }`

- **`/download-log/<filename>`** :
  - Permet de télécharger un fichier log généré.
  - Sécurisé (vérification du nom de fichier).

---

## ⚙️ Installation

### Prérequis

- Python 3.7+
- Capteur **VEML3328** connecté via I2C (bus 1 sur Raspberry Pi, adresse `0x10`)
- Ou utilisation sans capteur (mode simulation automatique)

### Installation

```bash
git clone https://github.com/ton-utilisateur/VEML3328-SB-SENSOR.git
cd VEML3328-SB-SENSOR
pip install -r requirement.txt
python3 veml_server.py
Accessible sur : http://localhost:5000
```
