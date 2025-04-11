from flask import Flask, render_template, request, redirect, url_for, Response
import sqlite3
from collections import defaultdict
from datetime import datetime
import csv

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
        CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vesdas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vesda_id TEXT NOT NULL,
            building_id INTEGER,
            last_battery_date TEXT,
            trouble_status TEXT,
            notes TEXT,
            FOREIGN KEY(building_id) REFERENCES buildings(id)
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
@app.route("/")
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM buildings")
    buildings = cursor.fetchall()
    conn.close()
    return render_template("home.html", buildings=buildings)

@app.route("/building/<int:building_id>", methods=["GET", "POST"])
def building_view(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM buildings WHERE id = ?", (building_id,))
    building = cursor.fetchone()
    if not building:
        conn.close()
        return "Building not found", 404

    if request.method == "POST":
        vesda_id = request.form["vesda_id"]
        last_battery_date = request.form["last_battery_date"] or "N/A"
        trouble_status = request.form["trouble_status"]
        notes = request.form["notes"]

        if request.form.get("id"):  # editing existing
            vesda_id_edit = request.form["id"]
            cursor.execute("SELECT * FROM vesdas WHERE id = ?", (vesda_id_edit,))
            original = cursor.fetchone()

            # Track history if changes occurred
            fields = ["vesda_id", "last_battery_date", "trouble_status", "notes"]
            new_values = [vesda_id, last_battery_date, trouble_status, notes]
            for i, field in enumerate(fields):
                old_value = original[field]
                new_value = new_values[i]
                if str(old_value) != str(new_value):
                    cursor.execute("""
                        INSERT INTO vesda_history (vesda_id, timestamp, field, old_value, new_value)
                        VALUES (?, ?, ?, ?, ?)
                    """, (original["vesda_id"], datetime.utcnow().isoformat(), field, old_value, new_value))

            cursor.execute("""
                UPDATE vesdas SET vesda_id = ?, last_battery_date = ?,
                trouble_status = ?, notes = ? WHERE id = ?
            """, (vesda_id, last_battery_date, trouble_status, notes, vesda_id_edit))
        else:  # adding new
            cursor.execute("""
                INSERT INTO vesdas (vesda_id, building_id, last_battery_date, trouble_status, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (vesda_id, building_id, last_battery_date, trouble_status, notes))

        conn.commit()
        conn.close()
        return redirect(url_for("building_view", building_id=building_id))

    # --- Filtering ---
    search = request.args.get("search", "")
    only_troubled = request.args.get("troubled")

    query = "SELECT * FROM vesdas WHERE building_id = ?"
    params = [building_id]

    if search:
        query += " AND (vesda_id LIKE ? OR notes LIKE ?)"
        params.extend((f"%{search}%", f"%{search}%"))

    if only_troubled:
        query += " AND trouble_status IS NOT NULL AND trouble_status != '' AND lower(trouble_status) NOT IN ('normal', 'good', 'clear')"

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

    return render_template("index.html", building=building, vesdas=vesdas, search=search, only_troubled=only_troubled, vesda_to_edit=vesda_to_edit)

@app.route("/delete/<int:vesda_id>/<int:building_id>", methods=["POST"])
def delete_vesda(vesda_id, building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vesdas WHERE id = ?", (vesda_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("building_view", building_id=building_id))

@app.route("/add_building", methods=["POST"])
def add_building():
    name = request.form.get("name")
    if name:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO buildings (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
    return redirect(url_for("home"))

@app.route("/export_csv/<int:building_id>")
def export_csv(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vesdas WHERE building_id = ?", (building_id,))
    vesdas = cursor.fetchall()
    conn.close()

    def generate():
        yield "vesda_id,building,last_battery_date,trouble_status,notes\n"
        for v in vesdas:
            yield f"{v['vesda_id']},{building_id},{v['last_battery_date']},{v['trouble_status']},{v['notes']}\n"

    return Response(generate(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=vesdas_building_{building_id}.csv"})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)