"""
server.py
Flask web server for the POS system.

Replaces app.py (the old pywebview desktop launcher). Serves the same
frontend/ files, and exposes every Api method as POST /api/<method>,
so app.js keeps working unmodified via the pywebview-shim.js shim.

Adds session-based login since this now runs on the open internet
instead of a single trusted machine.
"""

import os
from functools import wraps

from flask import Flask, request, jsonify, session, redirect, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

import db
from api import Api

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

app = Flask(__name__, static_folder=None)

# SECRET_KEY must be set as a real env var in production (Render dashboard).
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

ADMIN_USERNAME = os.environ.get("POS_ADMIN_USER", "admin")

# Prefer a pre-hashed password (POS_ADMIN_PASSWORD_HASH) in production.
# Falls back to hashing POS_ADMIN_PASSWORD at startup, or a default for
# local testing only.
_admin_hash_env = os.environ.get("POS_ADMIN_PASSWORD_HASH")
if _admin_hash_env:
    ADMIN_PASSWORD_HASH = _admin_hash_env
else:
    ADMIN_PASSWORD_HASH = generate_password_hash(
        os.environ.get("POS_ADMIN_PASSWORD", "RedDuckT")
    )

api = Api()

# Methods on Api that are safe to expose at /api/<name>
_EXPOSED_METHODS = {
    "scan", "search_products", "get_available_imeis", "checkout",
    "add_product", "add_imei_units", "restock_qty", "get_all_products",
    "get_low_stock", "get_sales_history",
}


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


# ---------------- Auth ----------------

@app.route("/login")
def login_page():
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
        session.clear()
        session["logged_in"] = True
        session["username"] = username
        session.permanent = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


# ---------------- Pages / static assets ----------------

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect("/login")
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/app.js")
def app_js():
    return send_from_directory(FRONTEND_DIR, "app.js")


@app.route("/style.css")
def style_css():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.route("/pywebview-shim.js")
def shim_js():
    return send_from_directory(FRONTEND_DIR, "pywebview-shim.js")


# ---------------- API dispatch ----------------

@app.route("/api/<method_name>", methods=["POST"])
@login_required
def api_dispatch(method_name):
    if method_name not in _EXPOSED_METHODS:
        return jsonify({"error": "unknown method"}), 404

    method = getattr(api, method_name)
    payload = request.get_json(force=True, silent=True) or {}
    args = payload.get("args", [])

    try:
        result = method(*args)
        return jsonify(result)
    except TypeError as e:
        return jsonify({"ok": False, "error": f"bad arguments: {e}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


db.init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
