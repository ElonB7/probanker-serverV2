from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib
import os

app = Flask(__name__)

# Datenbank-URL von Render (z. B. postgres://...)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Passwort-Hashing
def hash_passwort(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# --------------------
# Datenbank-Modelle
# --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    passwort = db.Column(db.String(120), nullable=False)
    kontostand = db.Column(db.Integer, default=1000)
    level = db.Column(db.Integer, default=1)
    skin = db.Column(db.String(80), nullable=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    msg = db.Column(db.Text, nullable=False)
    zeit = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    betrag = db.Column(db.Float, nullable=False)
    zeit = db.Column(db.DateTime, default=datetime.utcnow)
    abgeholt = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

# --------------------
# Routes
# --------------------

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    passwort = data.get('passwort')

    if User.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': 'Benutzername existiert bereits.'}), 409

    new_user = User(name=name, passwort=hash_passwort(passwort))
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Registrierung erfolgreich.'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    name = data.get('name')
    passwort = data.get('passwort')

    user = User.query.filter_by(name=name, passwort=hash_passwort(passwort)).first()
    if user:
        return jsonify({
            'success': True,
            'message': 'Login erfolgreich.',
            'kontostand': user.kontostand,
            'level': user.level,
            'skin': user.skin
        }), 200
    else:
        return jsonify({'success': False, 'message': 'Ungültige Zugangsdaten.'}), 401


@app.route("/chat", methods=["POST"])
def chat_post():
    data = request.json
    name = data["name"]
    pw = data["passwort"]
    msg = data["msg"]

    user = User.query.filter_by(name=name, passwort=hash_passwort(pw)).first()
    if not user:
        return jsonify({"status": "error", "msg": "Authentifizierung fehlgeschlagen!"})

    chat_msg = ChatMessage(user_id=user.id, msg=msg)
    db.session.add(chat_msg)
    db.session.commit()

    return jsonify({"status": "ok"})


@app.route("/chat", methods=["GET"])
def chat_get():
    messages = ChatMessage.query.order_by(ChatMessage.zeit.desc()).limit(50).all()
    return jsonify([{
        "name": User.query.get(m.user_id).name,
        "msg": m.msg,
        "zeit": m.zeit.strftime("%H:%M:%S")
    } for m in reversed(messages)])


@app.route("/update_stats", methods=["POST"])
def update_stats():
    data = request.json
    name = data["name"]
    pw = data["passwort"]

    user = User.query.filter_by(name=name, passwort=hash_passwort(pw)).first()
    if not user:
        return jsonify({"status": "error", "msg": "Authentifizierung fehlgeschlagen!"})

    user.kontostand = data.get("kontostand", user.kontostand)
    user.level = data.get("level", user.level)
    if "skin" in data:
        user.skin = data["skin"]

    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/incoming/<name>", methods=["GET"])
def incoming(name):
    user = User.query.filter_by(name=name).first()
    if not user:
        return jsonify({"status": "error", "msg": "❌ Spieler nicht gefunden!"})

    eingänge = Transaction.query.filter_by(receiver_id=user.id, abgeholt=False).all()

    result = []
    for t in eingänge:
        sender = User.query.get(t.sender_id)
        result.append({
            "absender": sender.name if sender else "Unbekannt",
            "betrag": t.betrag,
            "zeit": t.zeit.strftime("%H:%M:%S")
        })
        t.abgeholt = True  # nach Abruf als "gesehen" markieren

    db.session.commit()
    return jsonify({"status": "ok", "eingänge": result})

@app.route("/send_money", methods=["POST"])
def send_money():
    data = request.get_json()
    sender = data.get("sender")
    empfänger = data.get("empfänger")
    betrag = data.get("betrag")
    passwort = data.get("passwort")

    sender_user = User.query.filter_by(name=sender, passwort=hash_passwort(passwort)).first()
    empfänger_user = User.query.filter_by(name=empfänger).first()

    if not sender_user or not empfänger_user:
        return jsonify({"status": "error", "msg": "❌ Sender oder Empfänger nicht gefunden!"})
    if sender_user.kontostand < betrag:
        return jsonify({"status": "error", "msg": "❌ Nicht genug Guthaben!"})

    sender_user.kontostand -= betrag
    empfänger_user.kontostand += betrag

    # Neue Transaktion speichern
    t = Transaction(sender_id=sender_user.id, receiver_id=empfänger_user.id, betrag=betrag)
    db.session.add(t)
    db.session.commit()

    return jsonify({"status": "ok", "msg": "✅ Geld erfolgreich gesendet!"})


@app.route("/change_password", methods=["POST"])
def change_password():
    data = request.json
    name = data["name"]
    old_pw = data["old"]
    new_pw = data["new"]

    user = User.query.filter_by(name=name, passwort=hash_passwort(old_pw)).first()
    if not user:
        return jsonify({"status": "error", "msg": "Falsches Passwort!"})

    user.passwort = hash_passwort(new_pw)
    db.session.commit()
    return jsonify({"status": "ok", "msg": "Passwort geändert!"})


@app.route("/leaderboard", methods=["GET"])
def leaderboard():
    users = User.query.order_by(User.kontostand.desc()).all()
    return jsonify({
        u.name: {
            "kontostand": u.kontostand,
            "level": u.level,
            "skin": u.skin
        } for u in users
    })


port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)