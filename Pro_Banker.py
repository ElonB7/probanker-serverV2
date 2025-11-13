import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import threading, time, random, winsound, os, json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import requests  # Für Serverkommunikation

spielername = None
spielerpasswort = None

login_info_label = None
logout_button = None

SERVER_URL = "http://localhost:5000"

# === Setup ===
START_PIN = "1234"
KONTEN_ORDNER = "konten"
os.makedirs(KONTEN_ORDNER, exist_ok=True)

kontostand = 0.0
transaktionen = []
aktuelles_konto = None

def show_loading_bar():
    loading_window = tk.Toplevel(root)
    loading_window.title("Anmeldung läuft...")
    loading_window.geometry("300x80")
    loading_window.resizable(False, False)

    label = tk.Label(loading_window, text="Bitte warten...")
    label.pack(pady=5)

    progress = ttk.Progressbar(loading_window, mode='indeterminate')
    progress.pack(pady=5, padx=10, fill='x')
    progress.start()

    return loading_window, progress

def speichere_login(name, pw):
    with open("login.json", "w", encoding="utf-8") as f:
        json.dump({"name": name, "passwort": pw}, f)

def lade_login():
    if os.path.exists("login.json"):
        with open("login.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def loesche_login():
    if os.path.exists("login.json"):
        os.remove("login.json")

def sende_stats():
    if not spielername or not spielerpasswort:
        return
    try:
        payload = {
            "name": spielername,
            "passwort": spielerpasswort,
            "kontostand": round(kontostand, 2),
            "level": level_label.cget("text")
        }
        requests.post(f"{SERVER_URL}/update_stats", json=payload)
        print("✅ Daten automatisch übertragen")
    except:
        print("❌ Fehler beim automatischen Senden")

def versuche_auto_login():
    global spielername, spielerpasswort
    daten = lade_login()
    if daten:
        spielername = daten["name"]
        spielerpasswort = daten["passwort"]
        try:
            res = requests.post(f"{SERVER_URL}/login", json=daten).json()
            if res["status"] == "ok":
                print(f"✅ Auto-Login erfolgreich: {spielername}")
                sende_stats()
        except:
            print("❌ Auto-Login fehlgeschlagen")

# === Konto-Handling ===
def konto_pfad(name):
    return os.path.join(KONTEN_ORDNER, f"{name}.json")

def konto_liste():
    return [f[:-5] for f in os.listdir(KONTEN_ORDNER) if f.endswith(".json")]

def konto_laden(name):
    global kontostand, transaktionen, aktuelles_konto
    aktuelles_konto = name
    pfad = konto_pfad(name)
    if os.path.exists(pfad):
        with open(pfad, "r") as f:
            data = json.load(f)
            kontostand = data["kontostand"]
            transaktionen.clear()
            transaktionen.extend(data["transaktionen"])
    else:
        kontostand = 0.0
        transaktionen.clear()
        add_transaktion("Startguthaben", 50.0)
    konto_var.set(name)
    aktualisiere_gui()
    zeige_graph()

def konto_speichern():
    if not aktuelles_konto: return
    pfad = konto_pfad(aktuelles_konto)
    with open(pfad, "w") as f:
        json.dump({"kontostand": kontostand, "transaktionen": transaktionen}, f, indent=2)

def konto_anlegen():
    name = simpledialog.askstring("Neues Konto", "Name des neuen Kontos:")
    if name:
        if os.path.exists(konto_pfad(name)):
            status_label.config(text="Konto existiert bereits!", fg="red")
        else:
            konto_laden(name)
            konto_speichern()
            konto_var.set(name)
            konto_auswahl["menu"].add_command(label=name, command=lambda n=name: konto_laden(n))
            status_label.config(text=f"Konto '{name}' erstellt!", fg="lime")

def konto_umbenennen():
    if not aktuelles_konto:
        status_label.config(text="Kein Konto ausgewählt!", fg="red")
        return
    neuer_name = simpledialog.askstring("Konto umbenennen", "Neuer Kontoname:")
    if not neuer_name:
        return
    if os.path.exists(konto_pfad(neuer_name)):
        status_label.config(text="Name existiert bereits!", fg="red")
        return
    try:
        os.rename(konto_pfad(aktuelles_konto), konto_pfad(neuer_name))
        konto_laden(neuer_name)
        konto_auswahl["menu"].delete(0, "end")
        for name in konto_liste():
            konto_auswahl["menu"].add_command(label=name, command=lambda n=name: konto_laden(n))
        status_label.config(text=f"Konto umbenannt zu '{neuer_name}'", fg="lime")
    except Exception as e:
        status_label.config(text=f"Fehler: {e}", fg="red")

# === Transaktionen ===
def add_transaktion(beschreibung, betrag):
    global kontostand
    kontostand += betrag
    jetzt = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    transaktionen.append({"beschreibung": beschreibung, "betrag": betrag})
    konto_speichern()
    aktualisiere_gui()
    zeige_graph()
    sende_stats()

def geld_senden():
    try:
        betrag = float(eingabe_betrag.get())
        empfänger = eingabe_empfänger.get().strip()

        if betrag <= 0 or betrag > kontostand or not empfänger:
            status_label.config(text="Ungültige Eingabe!", fg="red")
            return

        payload = {
            "sender": spielername,
            "passwort": spielerpasswort,
            "empfänger": empfänger,
            "betrag": round(betrag, 2)
        }

        res = requests.post(f"{SERVER_URL}/send_money", json=payload).json()

        if res["status"] == "ok":
            add_transaktion(f"Überweisung an {empfänger}", -betrag)
            status_label.config(text="✅ Geld gesendet!", fg="lime")
        else:
            status_label.config(text=f"❌ {res['msg']}", fg="red")

    except Exception as e:
        status_label.config(text=f"Fehler bei Eingabe: {e}", fg="red")

def prüfe_eingänge():
    try:
        res = requests.get(f"{SERVER_URL}/incoming/{spielername}").json()
        neue = res.get("eingänge", [])

        for eintrag in neue:
            betrag = eintrag["betrag"]
            absender = eintrag["absender"]
            add_transaktion(f"Überweisung von {absender}", betrag)

        if neue:
            status_label.config(text=f"📥 {len(neue)} neue Überweisung(en)!", fg="lime")

    except Exception as e:
        print("Fehler beim Abrufen der Eingänge:", e)

def starte_eingangscheck():
    prüfe_eingänge()
    root.after(10000, starte_eingangscheck)  # alle 10 Sekunden

# === Multiplayer Login & Leaderboard ===
def leaderboard_login():
    global spielername, spielerpasswort
    spielername = simpledialog.askstring("Login", "Spielername:")
    spielerpasswort = simpledialog.askstring("Passwort", "Passwort:", show="*")

    def show_loading_bar():
        loading_window = tk.Toplevel(root)
        loading_window.title("Anmeldung läuft...")
        loading_window.geometry("300x80")
        loading_window.resizable(False, False)

        label = tk.Label(loading_window, text="Bitte warten...")
        label.pack(pady=5)

        progress = ttk.Progressbar(loading_window, mode='indeterminate')
        progress.pack(pady=5, padx=10, fill='x')
        progress.start()

        return loading_window, progress

    def do_login():
        loading_window, progress = show_loading_bar()
        try:
            res = requests.post(f"{SERVER_URL}/login", json={
                "name": spielername,
                "passwort": spielerpasswort
            }).json()

            progress.stop()
            loading_window.destroy()

            if res["status"] == "ok":
                speichere_login(spielername, spielerpasswort)
                status_label.config(text=f"✅ Angemeldet als: {spielername}", fg="lime")
                update_login_ui()
                simpledialog.messagebox.showinfo("Login", "✅ Erfolgreich eingeloggt!")
                starte_eingangscheck()
            else:
                status_label.config(text=res["msg"], fg="red")
                simpledialog.messagebox.showerror("Login fehlgeschlagen", "❌ Falsches Passwort. Versuch es erneut.")
        except Exception as e:
            progress.stop()
            loading_window.destroy()
            status_label.config(text="❌ Server nicht erreichbar!", fg="red")
            simpledialog.messagebox.showerror("Fehler", f"❌ Serverfehler: {e}")

    threading.Thread(target=do_login).start()

def after_register():
    time.sleep(3000)
    leaderboard_login()

def leaderboard_register():
    global spielername, spielerpasswort
    spielername = simpledialog.askstring("Registrieren", "Neuer Spielername:")
    spielerpasswort = simpledialog.askstring("Passwort", "Passwort:", show="*")
    try:
        res = requests.post(f"{SERVER_URL}/register", json={
            "name": spielername,
            "passwort": spielerpasswort
        }).json()
        if res["status"] == "ok":
            status_label.config(text="✅ Registrierung erfolgreich! (Bitte logge dich jetzt ein um dein Konto zu verwenden!)", fg="lime")
            sende_stats() # ← direkt nach Registrierung übertragen
            after_register()
        else:
            status_label.config(text=res["msg"], fg="red")
    except:
        status_label.config(text="❌ Server nicht erreichbar!", fg="red")

def change_password():
    old = simpledialog.askstring("Altes Passwort", "Altes Passwort:", show="*")
    new = simpledialog.askstring("Neues Passwort", "Neues Passwort:", show="*")
    try:
        res = requests.post("{SERVER_URL}/change_password", json={
            "name": spielername,
            "old": old,
            "new": new
        }).json()
        status_label.config(text=res["msg"], fg="lime" if res["status"] == "ok" else "red")
    except:
        status_label.config(text="❌ Fehler beim Ändern!", fg="red")

# === ElonPro Belohnung ===
def elonpro_belohnung():
    def worker():
        while True:
            time.sleep(random.randint(15, 45))
            if kontostand < 100 or random.random() < 0.3:
                add_transaktion("ElonPro Belohnung", 50.00)
                winsound.PlaySound("kaching.wav", winsound.SND_FILENAME)
                status_label.config(text="🎁 ElonPro hat dich belohnt!", fg="lime")
                time.sleep(3)
                status_label.config(text="")
    threading.Thread(target=worker, daemon=True).start()

# === Level-System ===
def update_level():
    if kontostand < 100:
        level_label.config(text="LVL 1: 💀 Broke Level", fg="red")
    elif kontostand < 500:
        level_label.config(text="LVL 2: 😐 Ok Level", fg="orange")
    elif kontostand < 1000:
        level_label.config(text="LVL 3: 🙂 Guter Gehalt!", fg="yellow")
    elif kontostand < 2000:
        level_label.config(text="Lvl 4: 💰 Brashki bemämmert am Geld machen!", fg="red")
    elif kontostand < 5000:
        level_label.config(text="Lvl 5: 📝 Dayum Daniel! Woher das ganze geld?", fg="white")
    elif kontostand < 7000:
        level_label.config(text="Lvl 6: 🥶 Schon tuff! Du wirst ja langsam reich!", fg="cyan")
    else:
        level_label.config(text="Lvl ⩋₴௹↸?! : 🤑 MR.BEAST!", fg="lime")

def aktualisiere_gui():
    kontostand_label.config(text=f"Kontostand: {kontostand:.2f} €")
    for i in tree.get_children():
        tree.delete(i)
    for t in transaktionen:
        tree.insert("", "end", values=(t["beschreibung"], f"{t['betrag']:.2f} €"))
    update_level()

# === Graph ===
def zeige_graph():
    for widget in frame_graph.winfo_children():
        widget.destroy()

    daten = {}
    for t in transaktionen:
        tag = t.get("datum", "Unbekannt").split(" ")[0]  # Nur das Datum, ohne Uhrzeit
        daten.setdefault(tag, {"income": 0, "expense": 0})
        if t["betrag"] >= 0:
            daten[tag]["income"] += t["betrag"]
        else:
            daten[tag]["expense"] += abs(t["betrag"])

    tage = list(daten.keys())
    einnahmen = [daten[t]["income"] for t in tage]
    ausgaben = [daten[t]["expense"] for t in tage]

    fig, ax = plt.subplots()
    ax.plot(tage, einnahmen, label="Einnahmen", color="green", marker="o")
    ax.plot(tage, ausgaben, label="Ausgaben", color="red", marker="x")
    ax.set_title("Finanzverlauf")
    ax.set_xlabel("Datum (Tagesansicht!)")
    ax.set_ylabel("Betrag (€)")
    ax.tick_params(axis='x', rotation=45)
    ax.legend()
    ax.grid(True)

    canvas = FigureCanvasTkAgg(fig, master=frame_graph)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

def autosyncron():
    time.sleep(15000)
    sende_stats()
    autosyncron()

# === Splashscreen ===
def splashscreen():
    splash = tk.Toplevel()
    splash.overrideredirect(True)
    splash.geometry("400x200+600+300")
    splash.configure(bg="#121212")

    tk.Label(splash, text="💸 ProBanker wird geladen...", font=("Small Fonts", 20), bg="#121212", fg="cyan").pack(pady=30)
    tk.Label(splash, text="Bitte warten...", font=("Modern", 12), bg="#121212", fg="grey").pack(pady=10)

    progress = ttk.Progressbar(splash, orient="horizontal", length=300, mode="determinate")
    progress.pack(pady=20)
    progress.start(10)

    def close_splash():
        splash.destroy()
        pin_abfrage()

    splash.after(5000, close_splash)

# === GUI ===
root = tk.Tk()
root.withdraw()
root.title("ProBanker")
root.geometry("700x600")
root.configure(bg="#121212")

style = ttk.Style()
style.theme_use("clam")
style.configure("TNotebook.Tab", font=("Segoe UI", 11), padding=[10, 5], background="#333333", foreground="white")
style.map("TNotebook.Tab", background=[("selected", "#00ffff")])

tabs = ttk.Notebook(root)
tabs.pack(expand=1, fill="both")

def pin_abfrage():
    pin = simpledialog.askstring("PIN", "Bitte gib deine PIN ein: (1234)", show="*")
    if pin == START_PIN:
        root.deiconify()
        elonpro_belohnung()
        konto_laden(konto_liste()[0] if konto_liste() else "Standard")
    else:
        root.destroy()

root.after(100, splashscreen)

def update_login_ui():
    if spielername:
        login_info_label.config(text=f"✅🙌 Angemeldetes Konto: {spielername}")
        logout_button.pack(pady=2)
    else:
        login_info_label.config(text="")
        logout_button.pack_forget()

# === Tabs ===
frame_uebersicht = tk.Frame(tabs, bg="#121212")
tabs.add(frame_uebersicht, text="Übersicht")

konten = konto_liste()
startwert = konten[0] if konten else "Kein Konto"
konto_var = tk.StringVar(value=startwert)
if not konten:
    konten = [startwert]

konto_auswahl = tk.OptionMenu(frame_uebersicht, konto_var, *konten, command=konto_laden)
konto_auswahl.config(bg="#333", fg="white")
konto_auswahl.pack(pady=5)

tk.Label(frame_uebersicht, text=f"Einstellungen", bg="#121212", fg="white").pack(pady=12)
ttk.Button(frame_uebersicht, text=f"✏️ Konto umbenennen", command=lambda: konto_umbenennen()).pack(pady=13)

ttk.Button(frame_uebersicht, text="➕ Konto anlegen", command=konto_anlegen).pack(pady=5)

kontostand_label = tk.Label(frame_uebersicht, text="", font=("Segoe UI", 16), bg="#47270C", fg="cyan")
kontostand_label.pack(pady=10)

ttk.Button(frame_uebersicht, text="Überweisung starten", command=lambda: tabs.select(2)).pack(pady=5)

frame_umsaetze = tk.Frame(tabs, bg="#121212")
tabs.add(frame_umsaetze, text="Umsätze")

tree = ttk.Treeview(frame_umsaetze, columns=("datum", "Beschreibung", "Betrag"), show="headings")
tree.heading("datum", text="datum")
tree.heading("Beschreibung", text="Beschreibung")
tree.heading("Betrag", text="Betrag")
tree.pack(pady=10, fill="both", expand=True)

frame_ueberweisung = tk.Frame(tabs, bg="#121212")
tabs.add(frame_ueberweisung, text="Überweisung")

tk.Label(frame_ueberweisung, text="Empfänger:", bg="#121212", fg="white").pack(pady=5)
eingabe_empfänger = tk.Entry(frame_ueberweisung)
eingabe_empfänger.pack()

tk.Label(frame_ueberweisung, text="Betrag (€):", bg="#121212", fg="white").pack(pady=5)
eingabe_betrag = tk.Entry(frame_ueberweisung)
eingabe_betrag.pack()

ttk.Button(frame_ueberweisung, text="Senden", command=geld_senden).pack(pady=10)

status_label = tk.Label(frame_ueberweisung, text="", bg="#121212", fg="white")
status_label.pack()

frame_level = tk.Frame(tabs, bg="#121212")
tabs.add(frame_level, text="Level")

level_label = tk.Label(frame_level, text="", font=("Segoe UI", 16), bg="#121212")
level_label.pack(pady=20)

frame_graph = tk.Frame(tabs, bg="#121212")
tabs.add(frame_graph, text="📊 Graph")
zeige_graph()

frame_leaderboard = tk.Frame(tabs, bg="#121212")
tabs.add(frame_leaderboard, text="🌍 Leaderboard")

login_info_label = tk.Label(frame_leaderboard, text="", bg="#121212", fg="white", font=("Segoe UI", 9))
login_info_label.pack()

versuche_auto_login()

def logout():
    global spielername, spielerpasswort
    spielername = None
    spielerpasswort = None
    loesche_login()
    status_label.config(text="🚪 Abgemeldet", fg="orange")
    update_login_ui()

ttk.Button(frame_leaderboard, text="🔐 Login", command=leaderboard_login).pack(pady=5)
ttk.Button(frame_leaderboard, text="🆕 Registrieren", command=leaderboard_register).pack(pady=5)
logout_button = ttk.Button(frame_leaderboard, text="🚪 Abmelden", command=logout)

ttk.Button(text="📤 Daten manuell übertragen", command=sende_stats).pack(pady=5)

def lade_leaderboard():
    global spielername, spielerpasswort

    if not spielername or not spielerpasswort:
        spielername = simpledialog.askstring("Login", "Spielername:")
        spielerpasswort = simpledialog.askstring("Passwort", "Passwort:", show="*")

    # Lokale Daten übertragen
    try:
        payload = {
            "name": spielername,
            "passwort": spielerpasswort,
            "kontostand": round(kontostand, 2),
            "level": level_label.cget("text")
        }
        requests.post(f"{SERVER_URL}/update_stats", json=payload)
    except Exception as e:
        print("Fehler beim Senden der lokalen Daten:", e)

    # Leaderboard abrufen
    try:
        res = requests.get(f"{SERVER_URL}/leaderboard").json()
        for widget in frame_leaderboard.winfo_children()[3:]:
            widget.destroy()
        for name, daten in res.items():
            text = f"{name}: {daten['kontostand']} € – {daten['level']}"
            tk.Label(frame_leaderboard, text=text, bg="#303030", fg="white").pack()
    except:
        status_label.config(text="❌ Leaderboard-Fehler", fg="red")
    versuche_auto_login()

ttk.Button(frame_leaderboard, text="📊 Leaderboard laden", command=lade_leaderboard).pack(pady=10)
versuche_auto_login()

# === Kursdaten ===
kurse = {
    "ElonCoin": {"wert": 100.0, "verlauf": [], "besitz": 1},
    "BroToken": {"wert": 50.0, "verlauf": [], "besitz": 1},
    "MemeStock": {"wert": 200.0, "verlauf": [], "besitz": 1}
}

def update_kurse():
    for name, kurs in kurse.items():
        delta = kurs["wert"] * random.uniform(-0.045, 0.05)
        kurs["wert"] = max(1.0, round(kurs["wert"] + delta, 2))
        kurs["verlauf"].append(kurs["wert"])
    zeige_kurs_graph()
    aktualisiere_kurs_gui()
    root.after(5000, update_kurse)

def kaufe_kurs(name):
    global kontostand
    kurs = kurse[name]
    if kontostand >= kurs["wert"]:
        kontostand -= kurs["wert"]
        kurs["besitz"] += 1
        add_transaktion(f"Gekauft: {name}", -kurs["wert"])
        status_kurs.config(text=f"{name} gekauft!", fg="lime")
    else:
        status_kurs.config(text="Nicht genug Geld!", fg="red")

def verkaufe_kurs(name):
    global kontostand
    kurs = kurse[name]
    if kurs["besitz"] > 0:
        kontostand += kurs["wert"]
        kurs["besitz"] -= 1
        add_transaktion(f"Verkauft: {name}", kurs["wert"])
        status_kurs.config(text=f"{name} verkauft!", fg="cyan")
    else:
        status_kurs.config(text="Du besitzt keine!", fg="red")

def aktualisiere_kurs_gui():
    for widget in frame_kurse_links.winfo_children():
        widget.destroy()
    for name, kurs in kurse.items():
        tk.Label(frame_kurse_links, text=f"{name}: {kurs['wert']:.2f} €", bg="#121212", fg="white").pack()
        tk.Label(frame_kurse_links, text=f"Besitz: {kurs['besitz']}", bg="#121212", fg="gray").pack()
        ttk.Button(frame_kurse_links, text=f"Kaufen {name}", command=lambda n=name: kaufe_kurs(n)).pack(pady=2)
        ttk.Button(frame_kurse_links, text=f"Verkaufen {name}", command=lambda n=name: verkaufe_kurs(n)).pack(pady=2)
    tk.Label(frame_kurse_links, text=f"Einstellungen", bg="#121212", fg="white").pack()
    ttk.Button(frame_kurse_links, text=f"✏️ Konto umbenennen", command=lambda: konto_umbenennen()).pack(pady=10)
    tk.Label(frame_kurse_links, text=f"Kontostand: {kontostand:.2f} €", bg="#121212", fg="white").pack()

def zeige_kurs_graph():
    for widget in frame_kurse_rechts.winfo_children():
        widget.destroy()
    fig, ax = plt.subplots()
    for name, kurs in kurse.items():
        ax.plot(kurs["verlauf"][-20:], label=name, marker="o")
    ax.set_title("Kursverlauf")
    ax.set_ylabel("Wert (€)")
    ax.set_xlabel("Zeit (Ticks)")
    ax.grid(True)
    ax.legend()
    canvas = FigureCanvasTkAgg(fig, master=frame_kurse_rechts)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

# === GUI-Tab: Kurse ===
frame_kurse = tk.Frame(tabs, bg="#121212")
tabs.add(frame_kurse, text="📈 Kurse")

frame_kurse_links = tk.Frame(frame_kurse, bg="#121212")
frame_kurse_links.pack(side="left", fill="y", padx=10)

frame_kurse_rechts = tk.Frame(frame_kurse, bg="#121212")
frame_kurse_rechts.pack(side="right", fill="both", expand=True)

status_kurs = tk.Label(frame_kurse, text="", bg="#121212", fg="white")
status_kurs.pack(side="bottom", pady=5)

update_kurse()
# === Mainloop ===

root.mainloop()