"""
server.py
Flask web server for the POS system.

Replaces app.py (the old pywebview desktop launcher). Serves the same
frontend/ files, and exposes every Api method as POST /api/<method>,
so app.js keeps working unmodified via the pywebview-shim.js shim.

Adds session-based login since this now runs on the open internet
instead of a single trusted machine, plus owner/cashier role-based
access control.
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

from datetime import timedelta
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ---------------- Credentials ----------------

def _passHash(hash_env, plain_env, default, label):
    """
    Resolves a password hash from environment variables, with a safe
    fallback for local development only. Fails loudly if credentials
    are missing when running on Render.
    """
    hash_val = os.environ.get(hash_env)
    if hash_val:
        return hash_val

    plain_val = os.environ.get(plain_env)
    if plain_val:
        return generate_password_hash(plain_val)

    if os.environ.get("RENDER") is None:
        # Not on Render — safe to use a placeholder for local testing
        return generate_password_hash(default)

    raise RuntimeError(
        f"{hash_env} or {plain_env} must be set in production ({label})"
    )


ADMIN_USERNAME = os.environ.get("POS_ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = _passHash(
    "POS_ADMIN_PASSWORD_HASH", "POS_ADMIN_PASSWORD", "changeme123", "admin"
)

CASHIER_USERNAME = os.environ.get("POS_CASHIER_USER", "cashier")
CASHIER_PASSWORD_HASH = _passHash(
    "POS_CASHIER_PASSWORD_HASH", "POS_CASHIER_PASSWORD", "changeme456", "cashier"
)


api = Api()

# Methods any logged-in user (owner or cashier) can call
_SHARED_METHODS = {"scan", "search_products", "get_available_imeis", "checkout"}

# Methods restricted to owners only
_OWNER_METHODS = {
    "add_product", "add_imei_units", "restock_qty",
    "get_all_products", "get_low_stock", "get_sales_history",
}

_EXPOSED_METHODS = _SHARED_METHODS | _OWNER_METHODS


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


def owner_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "unauthorized"}), 401
        if session.get("role") != "owner":
            return jsonify({"error": "forbidden"}), 403
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
        session["role"] = "owner"
        session.permanent = True
        return jsonify({"ok": True, "role": "owner"})

    if username == CASHIER_USERNAME and check_password_hash(CASHIER_PASSWORD_HASH, password):
        session.clear()
        session["logged_in"] = True
        session["username"] = username
        session["role"] = "cashier"
        session.permanent = True
        return jsonify({"ok": True, "role": "cashier"})

    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
@login_required
def me():
    return jsonify({"username": session.get("username"), "role": session.get("role")})


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

    if method_name in _OWNER_METHODS and session.get("role") != "owner":
        return jsonify({"error": "forbidden"}), 403

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