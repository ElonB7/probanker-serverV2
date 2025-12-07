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

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    passwort = data.get('passwort')

    if User.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': 'Benutzername existiert bereits.'}), 409

    new_user = User(name=name, passwort=passwort)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Registrierung erfolgreich.'}), 201

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    passwort = db.Column(db.String(120), nullable=False)
    kontostand = db.Column(db.Integer, default=1000)


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    msg = db.Column(db.Text, nullable=False)
    zeit = db.Column(db.DateTime, default=datetime.utcnow)


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

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    name = data.get('name')
    passwort = data.get('passwort')

    user = User.query.filter_by(name=name, passwort=passwort).first()
    if user:
        return jsonify({'success': True, 'message': 'Login erfolgreich.', 'kontostand': user.kontostand}), 200
    else:
        return jsonify({'success': False, 'message': 'Ungültige Zugangsdaten.'}), 401

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