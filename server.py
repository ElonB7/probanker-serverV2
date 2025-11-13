from flask import Flask, request, jsonify
import hashlib, os
import json

DATEIPFAD = "konten.json"

# Beim Start laden
if os.path.exists(DATEIPFAD):
    with open(DATEIPFAD, "r") as f:
        nutzer_db = json.load(f)
else:
    nutzer_db = {}

app = Flask(__name__)

def hash_passwort(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def speichere_nutzer_db():
    with open(DATEIPFAD, "w") as f:
        json.dump(nutzer_db, f, indent=2)

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    pw = data["passwort"]

    if name in nutzer_db:
        return jsonify({"status": "error", "msg": "Name existiert bereits!"})

    nutzer_db[name] = {
        "passwort": hash_passwort(pw),
        "kontostand": 0.0,
        "level": "LVL 1",
        "eingänge": []
    }
    speichere_nutzer_db()
    return jsonify({"status": "ok", "msg": "Registrierung erfolgreich!"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Login fehlgeschlagen!"})
    return jsonify({"status": "ok", "msg": "Login erfolgreich!", "kontostand": user["kontostand"], "level": user["level"]})

@app.route("/update_stats", methods=["POST"])
def update_stats():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Authentifizierung fehlgeschlagen!"})
    user["kontostand"] = data["kontostand"]
    user["level"] = data["level"]
    speichere_nutzer_db()
    return jsonify({"status": "ok"})

@app.route("/send_money", methods=["POST"])
def send_money():
    data = request.get_json()
    sender = data.get("sender")
    empfänger = data.get("empfänger")
    betrag = data.get("betrag")
    passwort = data.get("passwort")

    if sender not in nutzer_db:
        return jsonify({"status": "error", "msg": "❌ Sender existiert nicht!"})

    gespeichertes_hash = nutzer_db[sender]["passwort"]
    if gespeichertes_hash != hash_passwort(passwort):
        return jsonify({"status": "error", "msg": "❌ Passwort falsch!"})

    if empfänger not in nutzer_db:
        return jsonify({"status": "error", "msg": "❌ Empfänger existiert nicht!"})

    if not isinstance(betrag, (int, float)) or betrag <= 0:
        return jsonify({"status": "error", "msg": "❌ Ungültiger Betrag!"})

    if nutzer_db[sender]["kontostand"] < betrag:
        return jsonify({"status": "error", "msg": "❌ Nicht genug Guthaben!"})

    nutzer_db[sender]["kontostand"] -= betrag
    nutzer_db[empfänger].setdefault("eingänge", []).append({
        "absender": sender,
        "betrag": betrag
    })
    speichere_nutzer_db()
    return jsonify({"status": "ok", "msg": "✅ Geld erfolgreich gesendet!"})

@app.route("/incoming/<name>", methods=["GET"])
def incoming(name):
    if name not in nutzer_db:
        return jsonify({"status": "error", "msg": "❌ Spieler nicht gefunden!"})

    eingänge = nutzer_db[name].get("eingänge", [])
    nutzer_db[name]["eingänge"] = []
    speichere_nutzer_db()
    return jsonify({"status": "ok", "eingänge": eingänge})

@app.route("/change_password", methods=["POST"])
def change_password():
    data = request.json
    name = data["name"]
    old_pw = data["old"]
    new_pw = data["new"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(old_pw):
        return jsonify({"status": "error", "msg": "Falsches Passwort!"})
    user["passwort"] = hash_passwort(new_pw)
    speichere_nutzer_db()
    return jsonify({"status": "ok", "msg": "Passwort geändert!"})

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify(nutzer_db)

port = int(os.environ.get("PORT", 5000))
from flask import Flask, request, jsonify
import hashlib, os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
cursor = conn.cursor()

app = Flask(__name__)
nutzer_db = {}  # Format: {name: {"passwort": hash, "kontostand": 0.0, "level": "LVL 1"}}

def hash_passwort(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

cursor.execute("""
CREATE TABLE IF NOT EXISTS nutzer (
    name TEXT PRIMARY KEY,
    passwort TEXT,
    kontostand REAL,
    level TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS eingänge (
    empfänger TEXT,
    absender TEXT,
    betrag REAL
)
""")

conn.commit()

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    pw = data["passwort"]

    if name in nutzer_db:
        return jsonify({"status": "error", "msg": "Name existiert bereits!"})

    nutzer_db[name] = {
        "passwort": hash_passwort(pw),
        "kontostand": 0.0,
        "level": "LVL 1",
        "eingänge": []  # ← wichtig für Multiplayer-Banking
    }

    return jsonify({"status": "ok", "msg": "Registrierung erfolgreich!"})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Login fehlgeschlagen!"})
    return jsonify({"status": "ok", "msg": "Login erfolgreich!", "kontostand": user["kontostand"], "level": user["level"]})

@app.route("/update_stats", methods=["POST"])
def update_stats():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Authentifizierung fehlgeschlagen!"})
    user["kontostand"] = data["kontostand"]
    user["level"] = data["level"]
    return jsonify({"status": "ok"})

@app.route("/send_money", methods=["POST"])
def send_money():
    data = request.get_json()
    sender = data.get("sender")
    empfänger = data.get("empfänger")
    betrag = data.get("betrag")
    passwort = data.get("passwort")

    if sender not in nutzer_db:
        return jsonify({"status": "error", "msg": "❌ Sender existiert nicht!"})

    gespeichertes_hash = nutzer_db[sender]["passwort"]
    if gespeichertes_hash != hash_passwort(passwort):
        return jsonify({"status": "error", "msg": "❌ Passwort falsch!"})

    if empfänger not in nutzer_db:
        return jsonify({"status": "error", "msg": "❌ Empfänger existiert nicht!"})

    if not isinstance(betrag, (int, float)) or betrag <= 0:
        return jsonify({"status": "error", "msg": "❌ Ungültiger Betrag!"})

    if nutzer_db[sender]["kontostand"] < betrag:
        return jsonify({"status": "error", "msg": "❌ Nicht genug Guthaben!"})

    # Geld abziehen
    nutzer_db[sender]["kontostand"] -= betrag

    # Überweisung beim Empfänger speichern
    if "eingänge" not in nutzer_db[empfänger]:
        nutzer_db[empfänger]["eingänge"] = []

    nutzer_db[empfänger]["eingänge"].append({
        "absender": sender,
        "betrag": betrag
    })

    return jsonify({"status": "ok", "msg": "✅ Geld erfolgreich gesendet!"})

@app.route("/incoming/<name>", methods=["GET"])
def incoming(name):
    if name not in nutzer_db:
        return jsonify({"status": "error", "msg": "❌ Spieler nicht gefunden!"})

    eingänge = nutzer_db[name].get("eingänge", [])
    nutzer_db[name]["eingänge"] = []  # nach Abruf löschen

    return jsonify({"status": "ok", "eingänge": eingänge})

@app.route("/change_password", methods=["POST"])
def change_password():
    data = request.json
    name = data["name"]
    old_pw = data["old"]
    new_pw = data["new"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(old_pw):
        return jsonify({"status": "error", "msg": "Falsches Passwort!"})
    user["passwort"] = hash_passwort(new_pw)
    return jsonify({"status": "ok", "msg": "Passwort geändert!"})

@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify(nutzer_db)

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)