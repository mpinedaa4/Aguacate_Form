"""
Servidor Flask - Encuesta Aguacate Hass
Ejecutar: python server.py
La app estará disponible en: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
import csv
import io

app = Flask(__name__, static_folder=".")

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response

@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return "", 204

DB_PATH = "encuesta_aguacate.db"


# ─── Inicializar base de datos ────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Crear tabla si no existe
    c.execute("""
        CREATE TABLE IF NOT EXISTS respuestas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha       TEXT,
            dureza      REAL    NOT NULL,
            color       REAL    NOT NULL,
            peso_g      REAL    NOT NULL,
            precio_cop  REAL    NOT NULL,
            forma       TEXT    NOT NULL,
            olor        TEXT    NOT NULL
        )
    """)
    # Agregar columna probabilidad si no existe
    c.execute("PRAGMA table_info(respuestas)")
    cols = [col[1] for col in c.fetchall()]
    if "prob_compra" not in cols:
        c.execute("ALTER TABLE respuestas ADD COLUMN prob_compra REAL")
    conn.commit()
    conn.close()



def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Servir el HTML principal ─────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "encuesta.html")


# ─── Guardar respuesta ────────────────────────────────────────
@app.route("/api/respuesta", methods=["POST"])
def guardar_respuesta():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Sin datos"}), 400

    required = ["dureza", "color", "peso_g", "precio_cop", "forma", "olor"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Falta el campo: {field}"}), 400

    # Validaciones
    try:
        dureza     = float(data["dureza"])
        color      = float(data["color"])
        peso_g     = float(data["peso_g"])
        precio_cop = float(data["precio_cop"])
        forma      = str(data["forma"])
        olor       = str(data["olor"])
        prob_compra = float(data.get("prob_compra", 0.5))
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Tipo de dato inválido: {e}"}), 400

    if not (0 <= dureza <= 10):
        return jsonify({"error": "Dureza debe estar entre 0 y 10"}), 400
    if not (0 <= color <= 10):
        return jsonify({"error": "Color debe estar entre 0 y 10"}), 400
    if not (50 <= peso_g <= 1000):
        return jsonify({"error": "Peso debe estar entre 50 y 1000 g"}), 400
    if not (500 <= precio_cop <= 100000):
        return jsonify({"error": "Precio debe estar entre 500 y 100000 COP"}), 400
    if forma not in ("simetrico", "irregular"):
        return jsonify({"error": "Forma inválida"}), 400
    if olor not in ("fresco", "descompuesto"):
        return jsonify({"error": "Olor inválido"}), 400
    if not (0 <= prob_compra <= 1):
        return jsonify({"error": "Probabilidad de compra debe estar entre 0 y 1"}), 400

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO respuestas (fecha, dureza, color, peso_g, precio_cop, forma, olor, prob_compra)
        VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?)
    """, (dureza, color, peso_g, precio_cop, forma, olor, prob_compra))
    conn.commit()
    new_id = c.lastrowid
    conn.close()

    return jsonify({"ok": True, "id": new_id}), 201


# ─── Obtener todas las respuestas (admin) ─────────────────────
@app.route("/api/respuestas", methods=["GET"])
def obtener_respuestas():
    # Verificar credenciales básicas
    auth = request.headers.get("X-Admin-Token", "")
    if auth != ADMIN_TOKEN:
        return jsonify({"error": "No autorizado"}), 401

    conn = get_conn()
    rows = conn.execute("SELECT * FROM respuestas ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ─── Exportar CSV (admin) ─────────────────────────────────────
@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    auth = request.headers.get("X-Admin-Token", "")
    if auth != ADMIN_TOKEN:
        return jsonify({"error": "No autorizado"}), 401

    conn = get_conn()
    rows = conn.execute("SELECT * FROM respuestas ORDER BY id").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "fecha", "dureza", "color", "peso_g", "precio_cop", "forma", "olor", "prob_compra"])
    for row in rows:
        writer.writerow(list(row))

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=respuestas_aguacate_hass.csv"}
    )


# ─── Borrar todos los registros (admin) ───────────────────────
@app.route("/api/respuestas", methods=["DELETE"])
def borrar_respuestas():
    auth = request.headers.get("X-Admin-Token", "")
    if auth != ADMIN_TOKEN:
        return jsonify({"error": "No autorizado"}), 401

    conn = get_conn()
    conn.execute("DELETE FROM respuestas")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ─── Conteo rápido ────────────────────────────────────────────
@app.route("/api/count", methods=["GET"])
def count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM respuestas").fetchone()[0]
    conn.close()
    return jsonify({"count": n})


# ─── CREDENCIALES ADMIN ───────────────────────────────────────
# Cambia este token por uno seguro antes de usar en producción
ADMIN_TOKEN = "aguacate_admin_2025"


if __name__ == "__main__":
    init_db()  # crea la base de datos si no existe
    app.run(host="0.0.0.0", port=5000, debug=True)