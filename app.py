import os
import sqlite3
from datetime import datetime, date
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "prescriptions"
DB_PATH = DATA_DIR / "medicare.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "webp"}

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-production")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            schedule TEXT NOT NULL,
            remaining INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dose_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            taken_date TEXT NOT NULL,
            taken_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'taken',
            FOREIGN KEY(medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );
        """)
init_db()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    with db() as con:
        medicines = con.execute("SELECT * FROM medicines ORDER BY name").fetchall()
        today = date.today().isoformat()
        taken_rows = con.execute(
            "SELECT medicine_id, COUNT(*) AS count FROM dose_logs WHERE taken_date=? AND status='taken' GROUP BY medicine_id",
            (today,)
        ).fetchall()
        taken_ids = {r["medicine_id"]: r["count"] for r in taken_rows}
        logs = con.execute("""
            SELECT dose_logs.*, medicines.name AS medicine_name
            FROM dose_logs JOIN medicines ON medicines.id=dose_logs.medicine_id
            ORDER BY dose_logs.id DESC LIMIT 8
        """).fetchall()
        prescriptions = con.execute("SELECT * FROM prescriptions ORDER BY id DESC").fetchall()
    total = len(medicines)
    taken = sum(taken_ids.values())
    adherence = min(100, round(taken / total * 100)) if total else 0
    low_stock = [m for m in medicines if m["remaining"] <= 7]
    return render_template("index.html", medicines=medicines, logs=logs,
                           prescriptions=prescriptions, adherence=adherence,
                           low_stock=low_stock, today=today)

@app.post("/medicines/add")
def add_medicine():
    name = request.form.get("name", "").strip()
    dosage = request.form.get("dosage", "").strip()
    schedule = request.form.get("schedule", "").strip()
    try:
        remaining = int(request.form.get("remaining", "0"))
        if remaining < 0 or remaining > 100000:
            raise ValueError()
    except ValueError:
        flash("Enter a valid non-negative pill count.", "error")
        return redirect(url_for("index"))
    if not name or not dosage or not schedule:
        flash("Please fill in the medicine name, dosage and schedule.", "error")
        return redirect(url_for("index"))
    if len(name) > 100 or len(dosage) > 100 or len(schedule) > 100:
        flash("One of the fields is too long.", "error")
        return redirect(url_for("index"))
    with db() as con:
        con.execute("INSERT INTO medicines(name,dosage,schedule,remaining,created_at) VALUES(?,?,?,?,?)",
                    (name, dosage, schedule, remaining, datetime.now().isoformat(timespec="seconds")))
    flash("Medicine added.", "success")
    return redirect(url_for("index"))

@app.post("/medicines/<int:medicine_id>/taken")
def mark_taken(medicine_id):
    with db() as con:
        medicine = con.execute("SELECT * FROM medicines WHERE id=?", (medicine_id,)).fetchone()
        if not medicine:
            flash("Medicine not found.", "error")
            return redirect(url_for("index"))
        now = datetime.now()
        con.execute("INSERT INTO dose_logs(medicine_id,taken_date,taken_time,status) VALUES(?,?,?,'taken')",
                    (medicine_id, now.date().isoformat(), now.strftime("%H:%M")))
        if medicine["remaining"] > 0:
            con.execute("UPDATE medicines SET remaining=remaining-1 WHERE id=?", (medicine_id,))
    flash("Dose marked as taken. Follow your prescribed instructions; this log does not confirm medical safety.", "success")
    return redirect(url_for("index"))

@app.post("/medicines/<int:medicine_id>/delete")
def delete_medicine(medicine_id):
    with db() as con:
        con.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
    flash("Medicine removed.", "success")
    return redirect(url_for("index"))

@app.post("/prescriptions/upload")
def upload_prescription():
    upload = request.files.get("prescription")
    notes = request.form.get("notes", "").strip()[:500]
    if not upload or not upload.filename:
        flash("Choose a prescription image or PDF first.", "error")
        return redirect(url_for("index"))
    if not allowed_file(upload.filename):
        flash("Allowed formats: PNG, JPG, JPEG, WEBP and PDF.", "error")
        return redirect(url_for("index"))
    original = secure_filename(upload.filename)[:180] or "prescription"
    stored = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{original}"
    upload.save(UPLOAD_DIR / stored)
    with db() as con:
        con.execute("INSERT INTO prescriptions(filename,original_name,uploaded_at,notes) VALUES(?,?,?,?)",
                    (stored, original, datetime.now().isoformat(timespec="seconds"), notes))
    flash("Prescription saved privately on this server. Check every medicine detail with your clinician or pharmacist before using it.", "success")
    return redirect(url_for("index"))

@app.get("/prescriptions/<int:prescription_id>/download")
def download_prescription(prescription_id):
    with db() as con:
        item = con.execute("SELECT * FROM prescriptions WHERE id=?", (prescription_id,)).fetchone()
    if not item:
        flash("Prescription not found.", "error")
        return redirect(url_for("index"))
    return send_from_directory(UPLOAD_DIR, item["filename"], as_attachment=True,
                               download_name=item["original_name"])

@app.post("/prescriptions/<int:prescription_id>/delete")
def delete_prescription(prescription_id):
    with db() as con:
        item = con.execute("SELECT filename FROM prescriptions WHERE id=?", (prescription_id,)).fetchone()
        if item:
            (UPLOAD_DIR / item["filename"]).unlink(missing_ok=True)
            con.execute("DELETE FROM prescriptions WHERE id=?", (prescription_id,))
    flash("Prescription deleted.", "success")
    return redirect(url_for("index"))

@app.get("/health")
def health():
    return jsonify(status="ok", service="MediCare+")

@app.errorhandler(413)
def too_large(_error):
    flash("File is too large. Maximum upload size is 8 MB.", "error")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
