from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# --- Database Utilities ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vesdas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vesda_id TEXT NOT NULL,
            building TEXT,
            last_battery_date TEXT,
            trouble_status TEXT,
            notes TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vesda_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vesda_id TEXT,
            timestamp TEXT,
            field TEXT,
            old_value TEXT,
            new_value TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        vesda_id = request.form["vesda_id"]
        building = request.form["building"]
        last_battery_date = request.form["last_battery_date"] or "N/A"
        trouble_status = request.form["trouble_status"]
        notes = request.form["notes"]

        if request.form.get("id"):  # editing existing
            vesda_id_edit = request.form["id"]
            cursor.execute("SELECT * FROM vesdas WHERE id = ?", (vesda_id_edit,))
            original = cursor.fetchone()

            # Track history if changes occurred
            fields = ["vesda_id", "building", "last_battery_date", "trouble_status", "notes"]
            new_values = [vesda_id, building, last_battery_date, trouble_status, notes]
            for i, field in enumerate(fields):
                old_value = original[field]
                new_value = new_values[i]
                if str(old_value) != str(new_value):
                    cursor.execute("""
                        INSERT INTO vesda_history (vesda_id, timestamp, field, old_value, new_value)
                        VALUES (?, ?, ?, ?, ?)
                    """, (original["vesda_id"], datetime.utcnow().isoformat(), field, old_value, new_value))

            cursor.execute("""
                UPDATE vesdas SET vesda_id = ?, building = ?, last_battery_date = ?,
                trouble_status = ?, notes = ? WHERE id = ?
            """, (vesda_id, building, last_battery_date, trouble_status, notes, vesda_id_edit))
        else:  # adding new
            cursor.execute("""
                INSERT INTO vesdas (vesda_id, building, last_battery_date, trouble_status, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (vesda_id, building, last_battery_date, trouble_status, notes))

        conn.commit()
        conn.close()
        return redirect("/")

    # --- Filtering ---
    search = request.args.get("search", "")
    only_troubled = request.args.get("troubled")

    query = "SELECT * FROM vesdas WHERE 1=1"
    params = []

    if search:
        query += " AND (vesda_id LIKE ? OR building LIKE ?)"
        params.extend((f"%{search}%", f"%{search}%"))

    if only_troubled:
        query += " AND trouble_status IS NOT NULL AND trouble_status != '' AND lower(trouble_status) NOT IN ('normal', 'good')"

    cursor.execute(query, params)
    vesdas = cursor.fetchall()

    # --- Handle inline editing ---
    edit_id = request.args.get("edit_id")
    vesda_to_edit = None
    if edit_id:
        for v in vesdas:
            if str(v["id"]) == edit_id:
                vesda_to_edit = v
                break

    conn.close()

    return render_template("index.html", vesdas=vesdas, search=search, only_troubled=only_troubled, vesda_to_edit=vesda_to_edit)

@app.route("/delete/<int:vesda_id>", methods=["POST"])
def delete_vesda(vesda_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vesdas WHERE id = ?", (vesda_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
