"""
Simple URL Shortener
Designed & Developed By Rushikesh Ghodke
IICT,JNEC,MGM University, Chh-Sambhajinagar.

Single-file Flask application: backend, SQLite, REST API and frontend.
"""
import ipaddress
import os
import re
import secrets
import sqlite3
import string
from contextlib import contextmanager
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, render_template_string, request
from werkzeug.middleware.proxy_fix import ProxyFix

# --------------------------------------------------------------------------
# Configuration (environment based, no hardcoded secrets)
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "urls.db"))
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")  # optional, e.g. https://my-app.onrender.com
CODE_LENGTH = 6
ALPHABET = string.ascii_letters + string.digits
CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{6}$")
RESERVED_CODES = {"health", "static"}
MAX_URL_LENGTH = 2048
MAX_CODE_ATTEMPTS = 10

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["JSON_SORT_KEYS"] = False
app.json.sort_keys = False
# Render terminates HTTPS at its proxy; trust forwarded headers so short URLs use https.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
@contextmanager
def get_db():
    """Open a SQLite connection and always close it afterwards."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create the database directory, file and table automatically."""
    directory = os.path.dirname(os.path.abspath(DATABASE_PATH))
    os.makedirs(directory, exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT NOT NULL UNIQUE,
                short_code   TEXT NOT NULL UNIQUE,
                created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
LABEL_PATTERN = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def valid_host(host):
    """Accept localhost, IP addresses and well-formed domain names (including IDN)."""
    if host == "localhost":
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    try:
        ascii_host = host.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError:
        return False
    labels = ascii_host.split(".")
    return len(labels) >= 2 and all(LABEL_PATTERN.match(label) for label in labels)


def validate_url(value):
    """Return (clean_url, error_message). Only http/https URLs are accepted."""
    if not isinstance(value, str) or not value.strip():
        return None, "Please enter a URL."
    url = value.strip()
    if len(url) > MAX_URL_LENGTH:
        return None, f"URL is too long (maximum {MAX_URL_LENGTH} characters)."
    if re.search(r"\s", url):
        return None, "URL must not contain spaces."
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        parsed.port  # raises ValueError for an invalid port such as :99999
    except ValueError:
        return None, "That does not look like a valid URL."
    if parsed.scheme.lower() not in ("http", "https"):
        return None, "URL must start with http:// or https://"
    if parsed.username is not None or parsed.password is not None:
        return None, "URLs containing a username or password are not allowed."
    if not host or not valid_host(host):
        return None, "URL must contain a valid domain name."
    return url, None


def generate_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def find_by_url(conn, url):
    return conn.execute(
        "SELECT original_url, short_code FROM urls WHERE original_url = ?", (url,)
    ).fetchone()


def create_short_url(url):
    """Return (row, created). Reuses the code if the URL was already shortened."""
    with get_db() as conn:
        existing = find_by_url(conn, url)
        if existing:
            return existing, False
        for _ in range(MAX_CODE_ATTEMPTS):
            code = generate_code()
            if code.lower() in RESERVED_CODES:
                continue
            try:
                conn.execute(
                    "INSERT INTO urls (original_url, short_code) VALUES (?, ?)",
                    (url, code),
                )
                return {"original_url": url, "short_code": code}, True
            except sqlite3.IntegrityError:
                # Either the code collided or another request stored this URL first.
                existing = find_by_url(conn, url)
                if existing:
                    return existing, False
        raise RuntimeError("Could not generate a unique short code.")


def build_short_url(code):
    base = BASE_URL or request.host_url.rstrip("/")
    return f"{base}/{code}"


def wants_json():
    return request.path.startswith("/api/")


# --------------------------------------------------------------------------
# Frontend (HTML + CSS + JS embedded)
# --------------------------------------------------------------------------
BASE_CSS = r"""
:root{
  --bg:#f4fbf6; --surface:#ffffff; --mint:#e3f4e9; --mint-2:#cfeadb;
  --green:#1f9d55; --green-dark:#14703d; --ink:#12301f; --muted:#5a7264;
  --line:#d8eadf; --danger:#b42318; --danger-bg:#fdecea;
  --radius:18px; --shadow:0 10px 30px -12px rgba(20,112,61,.25);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:80px}
body{font-family:'Manrope',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--ink);background:var(--bg);line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit}
:focus-visible{outline:3px solid var(--green);outline-offset:3px;border-radius:8px}
.wrap{width:min(1080px,92%);margin-inline:auto}
nav{position:sticky;top:0;z-index:20;background:rgba(244,251,246,.9);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;align-items:center;justify-content:space-between;height:68px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:1.1rem;text-decoration:none}
.logo svg{width:34px;height:34px}
.links{display:flex;gap:6px;list-style:none}
.links a{display:block;padding:8px 14px;border-radius:999px;text-decoration:none;font-weight:600;color:var(--muted);transition:background .2s,color .2s}
.links a:hover{background:var(--mint);color:var(--green-dark)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:0;cursor:pointer;font:inherit;font-weight:700;padding:14px 26px;border-radius:14px;background:var(--green);color:#fff;text-decoration:none;transition:transform .15s,background .2s,box-shadow .2s;box-shadow:0 8px 18px -8px rgba(31,157,85,.7)}
.btn:hover{background:var(--green-dark);transform:translateY(-1px)}
.btn:disabled{opacity:.6;cursor:wait;transform:none}
.btn.ghost{background:var(--mint);color:var(--green-dark);box-shadow:none}
.btn.ghost:hover{background:var(--mint-2)}
footer{margin-top:90px;background:var(--ink);color:#d7efe0;text-align:center;padding:44px 20px}
footer strong{display:block;color:#fff;font-size:1.1rem;letter-spacing:.2px}
footer span{display:block;margin-top:6px;color:#9fc7ae;font-size:.95rem}
footer .bar{width:56px;height:4px;border-radius:4px;background:var(--green);margin:0 auto 18px}
@media (max-width:640px){.links a{padding:8px 10px;font-size:.92rem}.logo span{display:none}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

FONT_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap" rel="stylesheet">'

LOGO_SVG = '<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="11" fill="#1f9d55"/><path d="M16 24l8-8M17.5 12.5l2-2a5 5 0 017 7l-2 2M22.5 27.5l-2 2a5 5 0 01-7-7l2-2" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/></svg>'

FOOTER_HTML = """
<footer>
  <div class="bar"></div>
  <strong>Designed &amp; Developed By Rushikesh Ghodke</strong>
  <span>IICT,JNEC,MGM University, Chh-Sambhajinagar.</span>
</footer>
"""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simple URL Shortener</title>
<meta name="description" content="Transform long URLs into short, powerful links that are easy to share and manage.">
""" + FONT_LINK + """
<style>""" + BASE_CSS + r"""
.hero{padding:76px 0 40px}
.hero h1{font-size:clamp(2.2rem,5.6vw,4rem);line-height:1.08;font-weight:800;letter-spacing:-1.5px;max-width:15ch}
.hero p{margin-top:20px;font-size:1.15rem;color:var(--muted);max-width:52ch}
.hero-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:40px;align-items:center}
.demo{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:26px;font-family:ui-monospace,Consolas,monospace;font-size:.82rem}
.demo .long{color:var(--muted);word-break:break-all;text-decoration:line-through;text-decoration-color:var(--mint-2);text-decoration-thickness:2px}
.demo .arrow{display:block;margin:14px 0;color:var(--green);font-weight:800}
.demo .short{display:inline-block;background:var(--mint);color:var(--green-dark);padding:10px 16px;border-radius:12px;font-weight:700;font-size:1.05rem}
.tool{margin-top:34px;background:var(--surface);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow);padding:34px}
.tool h2{font-size:1.4rem;margin-bottom:18px}
.row{display:flex;gap:12px}
.row input{flex:1;min-width:0;font:inherit;padding:15px 18px;border:2px solid var(--line);border-radius:14px;background:var(--bg);color:var(--ink);transition:border-color .2s,background .2s}
.row input:focus{outline:none;border-color:var(--green);background:#fff}
.result{display:none;margin-top:22px;padding:18px;border-radius:16px;background:var(--mint);border:1px solid var(--mint-2)}
.result.show{display:block}
.result small{color:var(--muted);font-weight:600}
.result .out{display:flex;gap:12px;align-items:center;margin-top:8px}
.result a{flex:1;min-width:0;overflow-wrap:anywhere;font-weight:800;font-size:1.15rem;color:var(--green-dark)}
.toast{position:fixed;right:20px;bottom:20px;z-index:50;max-width:min(360px,90vw);padding:14px 18px;border-radius:14px;font-weight:600;color:#fff;background:var(--green-dark);box-shadow:0 14px 30px -10px rgba(0,0,0,.35);transform:translateY(20px);opacity:0;pointer-events:none;transition:transform .25s,opacity .25s}
.toast.show{transform:none;opacity:1}
.toast.error{background:var(--danger)}
section.block{padding-top:84px}
section.block>.wrap>h2{font-size:clamp(1.6rem,3.4vw,2.2rem);letter-spacing:-.5px;margin-bottom:10px}
section.block>.wrap>p.lead{color:var(--muted);max-width:60ch;margin-bottom:30px}
.features{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:18px}
.feature{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px}
.feature .ic{width:42px;height:42px;border-radius:12px;background:var(--mint);display:grid;place-items:center;margin-bottom:14px}
.feature .ic svg{width:22px;height:22px;stroke:var(--green-dark);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.feature h3{font-size:1.05rem;margin-bottom:6px}
.feature p{color:var(--muted);font-size:.95rem}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px;counter-reset:s;list-style:none}
.steps li{counter-increment:s;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px}
.steps li::before{content:counter(s);display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:var(--green);color:#fff;font-weight:800;margin-bottom:14px}
.steps h3{font-size:1.05rem;margin-bottom:4px}
.steps p{color:var(--muted);font-size:.95rem}
.about{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:30px;color:var(--muted);max-width:760px}
@media (max-width:820px){.hero-grid{grid-template-columns:1fr}.demo{display:none}}
@media (max-width:560px){.row{flex-direction:column}.tool{padding:22px}.result .out{flex-direction:column;align-items:stretch}}
</style>
</head>
<body>
<nav>
  <div class="wrap">
    <a class="logo" href="#top">""" + LOGO_SVG + r"""<span>Simple URL Shortener</span></a>
    <ul class="links">
      <li><a href="#shorten">URL Shortener</a></li>
      <li><a href="#about">About</a></li>
      <li><a href="#features">Features</a></li>
    </ul>
  </div>
</nav>

<header class="hero" id="top">
  <div class="wrap hero-grid">
    <div>
      <h1>Shorten Your Links. Simplify Your Sharing.</h1>
      <p>Transform long URLs into short, powerful links that are easy to share and manage.</p>
    </div>
    <div class="demo" aria-hidden="true">
      <span class="long">https://www.example.com/products/category/summer-collection?utm_source=newsletter&amp;ref=12345</span>
      <span class="arrow">&darr; 6 characters</span>
      <span class="short">your-site.com/aB3xY9</span>
    </div>
  </div>
</header>

<main class="wrap">
  <section class="tool" id="shorten">
    <h2>Shorten a link</h2>
    <div class="row">
      <input id="url" type="url" inputmode="url" autocomplete="off" placeholder="https://www.example.com/your/very/long/link" aria-label="Long URL">
      <button class="btn" id="go" type="button">Shorten URL</button>
    </div>
    <div class="result" id="result" aria-live="polite">
      <small>Your short link</small>
      <div class="out">
        <a id="short" href="#" target="_blank" rel="noopener"></a>
        <button class="btn ghost" id="copy" type="button">Copy URL</button>
      </div>
    </div>
  </section>

  <section class="block" id="features">
    <div class="wrap" style="width:100%">
      <h2>Features</h2>
      <p class="lead">Everything you need to turn a long link into a short one.</p>
      <div class="features">
        <div class="feature"><div class="ic"><svg viewBox="0 0 24 24"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg></div><h3>Fast URL shortening</h3><p>Paste a link and get a short one in a moment.</p></div>
        <div class="feature"><div class="ic"><svg viewBox="0 0 24 24"><path d="M12 3l2.6 5.5 6 .8-4.4 4.2 1.1 6-5.3-2.9-5.3 2.9 1.1-6L3.4 9.3l6-.8z"/></svg></div><h3>Unique short codes</h3><p>Each link gets its own random 6-character code.</p></div>
        <div class="feature"><div class="ic"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg></div><h3>Secure database storage</h3><p>Links are saved in SQLite using parameterized queries.</p></div>
        <div class="feature"><div class="ic"><svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div><h3>Instant redirection</h3><p>Visitors reach the original page right after clicking.</p></div>
        <div class="feature"><div class="ic"><svg viewBox="0 0 24 24"><path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/></svg></div><h3>REST API support</h3><p>Create short links from your own code with POST /api/shorten.</p></div>
      </div>
    </div>
  </section>

  <section class="block" id="how">
    <div class="wrap" style="width:100%">
      <h2>How it works</h2>
      <p class="lead">Three steps from long link to shareable link.</p>
      <ol class="steps">
        <li><h3>Paste your long URL</h3><p>Enter any http:// or https:// link in the box above.</p></li>
        <li><h3>Generate your short link</h3><p>Select Shorten URL to create a unique short code.</p></li>
        <li><h3>Share your short link</h3><p>Copy the short link and send it anywhere.</p></li>
      </ol>
    </div>
  </section>

  <section class="block" id="about">
    <div class="wrap" style="width:100%">
      <h2>About</h2>
      <div class="about">Simple URL Shortener is a Python and Flask web application that stores links in SQLite and redirects short codes to their original pages. It was built as a first-year engineering internship project by Rushikesh Ghodke.</div>
    </div>
  </section>
</main>
""" + FOOTER_HTML + r"""
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>
(function () {
  var input = document.getElementById('url');
  var go = document.getElementById('go');
  var box = document.getElementById('result');
  var link = document.getElementById('short');
  var copyBtn = document.getElementById('copy');
  var toast = document.getElementById('toast');
  var timer;

  function notify(msg, isError) {
    toast.textContent = msg;
    toast.className = 'toast show' + (isError ? ' error' : '');
    clearTimeout(timer);
    timer = setTimeout(function () { toast.className = 'toast'; }, 3500);
  }

  async function shorten() {
    var value = input.value.trim();
    if (!value) { notify('Please enter a URL.', true); input.focus(); return; }
    go.disabled = true; go.textContent = 'Shortening...';
    box.classList.remove('show');
    try {
      var res = await fetch('/api/shorten', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: value })
      });
      var data = await res.json();
      if (!res.ok) { notify(data.error || 'Something went wrong. Try again.', true); return; }
      link.textContent = data.short_url;
      link.href = data.short_url;
      box.classList.add('show');
      notify('Short link ready.');
    } catch (e) {
      notify('Could not reach the server. Check your connection.', true);
    } finally {
      go.disabled = false; go.textContent = 'Shorten URL';
    }
  }

  async function copy() {
    var text = link.textContent;
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      var t = document.createElement('textarea');
      t.value = text; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); } catch (e2) { notify('Copy failed. Select the link and copy it manually.', true); document.body.removeChild(t); return; }
      document.body.removeChild(t);
    }
    notify('Copied to clipboard.');
  }

  go.addEventListener('click', shorten);
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter') shorten(); });
  copyBtn.addEventListener('click', copy);
})();
</script>
</body>
</html>
"""

ERROR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ code }} - Simple URL Shortener</title>
""" + FONT_LINK + """
<style>""" + BASE_CSS + r"""
body{min-height:100vh;display:flex;flex-direction:column}
main{flex:1;display:grid;place-items:center;padding:60px 0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow);padding:48px 36px;max-width:520px;text-align:center}
.card .num{font-size:4.5rem;font-weight:800;color:var(--green);letter-spacing:-3px;line-height:1}
.card h1{font-size:1.6rem;margin:14px 0 8px}
.card p{color:var(--muted);margin-bottom:26px}
footer{margin-top:0}
</style>
</head>
<body>
<nav><div class="wrap"><a class="logo" href="/">""" + LOGO_SVG + r"""<span>Simple URL Shortener</span></a></div></nav>
<main class="wrap">
  <div class="card">
    <div class="num">{{ code }}</div>
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    <a class="btn" href="/">Shorten a new link</a>
  </div>
</main>
""" + FOOTER_HTML + r"""
</body>
</html>
"""


def error_page(status, title, message):
    html = render_template_string(ERROR_HTML, code=status, title=title, message=message)
    return html, status


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/health")
def health():
    return jsonify(status="ok", message="URL Shortener is running")


@app.route("/api/shorten", methods=["POST"])
def api_shorten():
    if not request.is_json:
        return jsonify(error="Content-Type must be application/json."), 415
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "url" not in payload:
        return jsonify(error='Request body must be JSON like {"url": "https://example.com"}.'), 400

    url, error = validate_url(payload["url"])
    if error:
        return jsonify(error=error), 400

    try:
        row, created = create_short_url(url)
    except (sqlite3.Error, RuntimeError):
        app.logger.exception("Failed to store URL")
        return jsonify(error="Could not save the URL. Please try again."), 500

    return (
        jsonify(
            original_url=row["original_url"],
            short_code=row["short_code"],
            short_url=build_short_url(row["short_code"]),
        ),
        201 if created else 200,
    )


@app.route("/<short_code>")
def follow(short_code):
    if not CODE_PATTERN.match(short_code):
        return error_page(404, "Link not found", "This short link does not exist or may have been typed incorrectly.")
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT original_url FROM urls WHERE short_code = ?", (short_code,)
            ).fetchone()
    except sqlite3.Error:
        app.logger.exception("Database error during redirect")
        return error_page(500, "Something went wrong", "We could not look up this link. Please try again shortly.")
    if row is None:
        return error_page(404, "Link not found", "This short link does not exist or may have been typed incorrectly.")
    return redirect(row["original_url"], code=302)


# --------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_e):
    if wants_json():
        return jsonify(error="Resource not found."), 404
    return error_page(404, "Page not found", "The page you are looking for does not exist.")


@app.errorhandler(405)
def method_not_allowed(_e):
    if wants_json():
        return jsonify(error="Method not allowed."), 405
    return error_page(405, "Method not allowed", "This page does not support that request.")


@app.errorhandler(500)
def server_error(_e):
    if wants_json():
        return jsonify(error="Internal server error."), 500
    return error_page(500, "Something went wrong", "An unexpected error occurred. Please try again.")


# Create the database when the module loads (works for python app.py and Gunicorn).
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"  # off unless explicitly enabled locally
    app.run(host="127.0.0.1" if debug else "0.0.0.0", port=port, debug=debug)
