# Deploying to eraugher.site

This is the web version of the POS system: a Flask server (`server.py`) that
serves the same frontend and reuses the same SQLite backend (`db.py`), gated
behind a login page since it's now reachable over the internet.

## What changed from the desktop version

- `app.py` (pywebview launcher) → replaced by `server.py` (Flask app)
- `frontend/pywebview-shim.js` (new) → makes `window.pywebview.api.X()` call
  `POST /api/X` on the server, so `app.js` did not need any changes
- Login page (`frontend/login.html`) + session-based auth added
- `db.py`, `api.py`, `app.js`, `style.css`, `index.html` — same logic as before

## 1. Push this to GitHub

Create a new repo (or add to your existing one) and push this `pos_web`
folder's contents to it. Render deploys from a GitHub repo.

## 2. Create the service on Render

1. Go to https://render.com → sign up / log in → **New +** → **Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app --bind 0.0.0.0:$PORT`
4. **Add a persistent disk** (Render dashboard → your service → Disks):
   - Mount path: `/opt/render/project/src/data`
   - This is required — without it, the SQLite database is wiped every time
     you redeploy, since Render's regular filesystem is not persistent.
5. **Environment variables** (Render dashboard → Environment):
   - `SECRET_KEY` — any long random string (e.g. generate with
     `python3 -c "import secrets; print(secrets.token_hex(32))"`)
   - `POS_ADMIN_USER` — your login username, e.g. `admin`
   - `POS_ADMIN_PASSWORD` — your login password (change this from the default)
6. Click **Create Web Service**. Render will build and deploy it, giving you
   a URL like `https://pos-system-xyz.onrender.com`.
7. Visit that URL and confirm you can log in and use the app before moving on.

## 3. Point eraugher.site at it

In Render:
- Go to your service → **Settings** → **Custom Domains** → **Add Custom Domain**
- Enter `eraugher.site` (and `www.eraugher.site` if you want both)
- Render will show you DNS records to add (usually a `CNAME` for `www` and an
  `A`/`ANAME` record for the root domain)

In Namecheap:
- Log in → **Domain List** → `eraugher.site` → **Manage** → **Advanced DNS**
- Add the records Render gave you (delete any conflicting default "Parking
  Page" records first)
- DNS changes can take anywhere from a few minutes to a few hours to
  propagate

Render automatically issues an HTTPS certificate for the domain once DNS is
pointed correctly.

## Notes on this being a real online service now

- This app was originally designed to run offline on one trusted machine. On
  the web, a few extra things now matter that didn't before:
  - Change `POS_ADMIN_PASSWORD` from the default immediately
  - Keep `SECRET_KEY` private — don't commit it to the repo
  - Everything currently shares a single admin login (no per-cashier
    accounts, no roles). Fine for one person running the shop; if you'll have
    multiple staff and want individual logins/audit trails, that's a
    follow-up feature to add
  - Back up `data/pos.db` periodically (e.g. Render's disk snapshots, or a
    scheduled export) since it's now your business's live sales record
