from flask import Flask, render_template, request, redirect, url_for, Response, flash
import sqlite3
from collections import defaultdict
from datetime import datetime
import csv
import os
import io
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# --- Database Utilities ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

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
            floor TEXT,
            type TEXT,
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

@app.route("/delete_all_vesdas/<int:building_id>", methods=["POST"])
def delete_all_vesdas(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vesdas WHERE building_id = ?", (building_id,))
    conn.commit()
    conn.close()
    flash("All VESDAs have been deleted.")
    return redirect(url_for("building_view", building_id=building_id))


# --- Route Example for Adding/Updating VESDA ---
@app.route("/building/<int:building_id>", methods=["GET", "POST"])
def building_view(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        form = request.form
        vesda_id = form.get("vesda_id")
        floor = form.get("floor")
        vesda_type = form.get("type")
        last_battery_date = form.get("last_battery_date") or "N/A"
        trouble_status = form.get("trouble_status")
        notes = form.get("notes")
        edit_id = form.get("id")

        if edit_id:
            cursor.execute("""
                UPDATE vesdas SET
                vesda_id = ?, floor = ?, type = ?, last_battery_date = ?, trouble_status = ?, notes = ?
                WHERE id = ?
            """, (vesda_id, floor, vesda_type, last_battery_date, trouble_status, notes, edit_id))
        else:
            cursor.execute("""
                INSERT INTO vesdas (vesda_id, building_id, floor, type, last_battery_date, trouble_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (vesda_id, building_id, floor, vesda_type, last_battery_date, trouble_status, notes))

        conn.commit()
        return redirect(url_for("building_view", building_id=building_id))

    # Load vesdas
    search = request.args.get("search", "")
    only_troubled = request.args.get("troubled") == "on"
    edit_id = request.args.get("edit_id")

    query = "SELECT * FROM vesdas WHERE building_id = ?"
    params = [building_id]

    if search:
        query += " AND (vesda_id LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if only_troubled:
        query += " AND LOWER(trouble_status) NOT IN ('normal', 'good', 'clear')"

    cursor.execute(query, params)
    vesdas = cursor.fetchall()

    building = conn.execute("SELECT * FROM buildings WHERE id = ?", (building_id,)).fetchone()
    vesda_to_edit = conn.execute("SELECT * FROM vesdas WHERE id = ?", (edit_id,)).fetchone() if edit_id else None

    conn.close()
    return render_template("index.html", building=building, vesdas=vesdas, search=search, only_troubled=only_troubled,
                           vesda_to_edit=vesda_to_edit)

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

@app.route("/import_csv/<int:building_id>", methods=["POST"])
def import_csv(building_id):
    if "csv_file" not in request.files:
        flash("No file part")
        return redirect(request.referrer)

    file = request.files["csv_file"]
    if file.filename == "":
        flash("No selected file")
        return redirect(request.referrer)

    if file:
        import io
        conn = get_db_connection()
        cursor = conn.cursor()

        stream = io.StringIO(file.stream.read().decode("UTF-8"))
        reader = csv.DictReader(stream)
        count = 0


        for row in reader:
            print("ROW:", row)

            notes = row.get("notes", "")
            last_battery_date = row.get("last_battery_date", "")

            if "replace batts" in notes.lower():
                (last_battery_date) = ""
            try:
                cursor.execute("""
                    INSERT INTO vesdas (vesda_id, building_id, floor, type, last_battery_date, trouble_status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get("vesda_id"),
                    building_id,
                    row.get("floor", ""),
                    row.get("type", "Old").strip(),
                    last_battery_date,
                    row.get("trouble_status", ""),
                    row.get("notes", "")
                ))
                count += 1
            except Exception as e:
                print("IMPORT ERROR:", e)

        cursor.execute("SELECT COUNT(*) FROM vesdas WHERE building_id = ?", (building_id,))
        print("Total rows for building:", cursor.fetchone()[0])

        conn.commit()
        conn.close()
        flash(f"CSV imported successfully! {count} rows added.")

    return redirect(url_for("building_view", building_id=building_id))



@app.route("/export_csv/<int:building_id>")
def export_csv(building_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vesdas WHERE building_id = ?", (building_id,))
    vesdas = cursor.fetchall()
    conn.close()

    def generate():
        yield "vesda_id,building,floor,last_battery_date,trouble_status,notes\n"
        for v in vesdas:
            yield f"{v['vesda_id']},{building_id},{v['floor']},{v['last_battery_date']},{v['trouble_status']},{v['notes']}\n"

    return Response(generate(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=vesdas_building_{building_id}.csv"})
init_db()

if __name__ == "__main__":
    app.run(debug=True)