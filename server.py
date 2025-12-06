from flask import Flask, request, jsonify
import hashlib, os
import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
        "eingänge": [],
        "skin": None   # 🔥 Skin-Feld direkt mit anlegen
    }
    speichere_nutzer_db()
    return jsonify({"status": "ok", "msg": "Registrierung erfolgreich!"})

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    passwort = db.Column(db.String(64), nullable=False)
    kontostand = db.Column(db.Float, default=0.0)
    level = db.Column(db.String(20), default="LVL 1")

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    msg = db.Column(db.Text, nullable=False)
    zeit = db.Column(db.DateTime, default=datetime.utcnow)

@app.before_first_request
def init_db():
    db.create_all()


# Speicher für Chat-Nachrichten
chat_messages = []

@app.route("/chat", methods=["POST"])
def chat_post():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    msg = data["msg"]

    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Authentifizierung fehlgeschlagen!"})

    chat_messages.append({
        "name": name,
        "msg": msg,
        "zeit": datetime.now().strftime("%H:%M:%S")
    })

    # Nur die letzten 100 Nachrichten behalten
    if len(chat_messages) > 100:
        chat_messages.pop(0)

    return jsonify({"status": "ok"})

@app.route("/chat", methods=["GET"])
def chat_get():
    return jsonify({"messages": chat_messages[-50:]})  # nur die letzten 50 anzeigen

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    user = nutzer_db.get(name)
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Login fehlgeschlagen!"})
    return jsonify({
        "status": "ok",
        "msg": "Login erfolgreich!",
        "kontostand": user["kontostand"],
        "level": user["level"],
        "skin": user.get("skin")   # 🔥 Skin mit zurückgeben
    })

@app.route("/update_stats", methods=["POST"])
def update_stats():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    user = nutzer_db.get(name)

    # Authentifizierung prüfen
    if not user or user["passwort"] != hash_passwort(pw):
        return jsonify({"status": "error", "msg": "Authentifizierung fehlgeschlagen!"})

    # Standardwerte aktualisieren
    user["kontostand"] = data["kontostand"]
    user["level"] = data["level"]

    # 🔥 Skin übernehmen, falls vorhanden
    if "skin" in data:
        user["skin"] = data["skin"]

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
    return jsonify({
        name: {
            "kontostand": user["kontostand"],
            "level": user["level"],
            "skin": user.get("skin", None)  # 🔥 Skin bleibt erhalten
        }
        for name, user in nutzer_db.items()
    })

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)