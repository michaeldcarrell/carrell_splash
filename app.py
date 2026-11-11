"""carrell.us dashboard: public site list, plus private sites for signed-in Google users.

Access to private sites is checked live against each app's own user table, so
adding someone to meal_planner's AllowedUser list or inviting them to
Vaultwarden is all it takes for the card to appear here too.
"""
import json
import logging
import os
from datetime import timedelta
from pathlib import Path

import psycopg2
from flask import Flask, abort, jsonify, redirect, render_template, request, session
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

log = logging.getLogger("dashboard")
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "1") == "1",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
SITES_FILE = Path(os.environ.get("SITES_FILE", Path(__file__).with_name("sites.json")))

# One SQL check per gated app. Each query takes the lower-cased email and
# returns a row if that person has an account there.
ACCESS_CHECKS = {
    "meals": ("MEALS_DATABASE_URL", "SELECT 1 FROM meals_alloweduser WHERE lower(email) = %s"),
    "vault": ("VAULT_DATABASE_URL", "SELECT 1 FROM users WHERE lower(email) = %s AND enabled"),
}


def load_sites():
    # Read on every request so editing the bind-mounted sites.json needs no restart.
    return json.loads(SITES_FILE.read_text())["sites"]


def has_access(email, access):
    if access == "public":
        return True
    if access == "admin":
        return email in ADMIN_EMAILS
    check = ACCESS_CHECKS.get(access)
    if not check:
        return False
    env_var, sql = check
    dsn = os.environ.get(env_var)
    if not dsn:
        return False
    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (email,))
                return cur.fetchone() is not None
        finally:
            conn.close()
    except psycopg2.Error:
        # A DB outage hides the card rather than breaking the page.
        log.exception("access check %r failed", access)
        return False


@app.get("/")
def index():
    user = session.get("user")
    sites = load_sites()
    public = [s for s in sites if s["access"] == "public"]
    private = []
    if user:
        checked = {}
        for s in sites:
            if s["access"] == "public":
                continue
            if s["access"] not in checked:
                checked[s["access"]] = has_access(user["email"], s["access"])
            if checked[s["access"]]:
                private.append(s)
    return render_template("index.html", user=user, public=public, private=private, client_id=GOOGLE_CLIENT_ID)


@app.post("/auth/google")
def google_login():
    # Google Identity Services posts the ID token as JSON from our own page.
    # Requiring JSON forces a CORS preflight, so other sites can't log someone in here.
    if not request.is_json:
        abort(400)
    credential = (request.get_json(silent=True) or {}).get("credential")
    if not credential:
        abort(400)
    try:
        info = id_token.verify_oauth2_token(credential, google_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError:
        log.warning("rejected Google ID token")
        abort(401)
    if not info.get("email_verified"):
        abort(403)
    session.clear()
    session.permanent = True
    session["user"] = {
        "email": info["email"].lower(),
        "name": info.get("given_name") or info.get("name") or info["email"],
        "picture": info.get("picture", ""),
    }
    return jsonify(ok=True)


@app.post("/logout")
def logout():
    session.clear()
    return redirect("/", code=303)


@app.get("/healthz")
def healthz():
    return "ok"
