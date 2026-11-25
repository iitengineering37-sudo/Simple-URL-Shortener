# Simple URL Shortener

A professional URL shortener web application built with **Python, Flask and SQLite**. The whole application (backend, REST API, HTML, CSS and JavaScript) lives in a single file, `app.py`.

**Designed & Developed By Rushikesh Ghodke**
IICT,JNEC,MGM University, Chh-Sambhajinagar.

## Project Objectives
- Convert long URLs into short, unique, shareable URLs.
- Practise full-stack development: backend, database, REST API and frontend.
- Prepare a project that can be deployed publicly on Render.

## Features
- Validates `http` and `https` URLs
- Unique random 6-character codes generated with Python's `secrets` module
- SQLite storage, with the database and table created automatically
- Duplicate URLs return the existing short code
- HTTP 302 redirection and a friendly 404 page for unknown codes
- Copy-to-clipboard button and success/error notifications
- REST API (`POST /api/shorten`) and health check (`GET /health`)
- Responsive light-green and white design

## Technologies Used
Python 3, Flask, SQLite, HTML5, CSS3, JavaScript, REST API, Gunicorn, GitHub, Render.

## Project Structure
```
Simple_URL_Shortener/
├── app.py             # entire application
├── requirements.txt   # Flask, Gunicorn
├── Procfile           # production start command
├── render.yaml        # Render service + persistent disk
├── .gitignore
├── README.md
└── urls.db            # created automatically (not committed)
```

## Installation and Local Run (Windows)
```
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** in your browser. Stop the server with `Ctrl + C`.

(macOS/Linux: `python3 -m venv venv && source venv/bin/activate`.)

## Configuration (environment variables)
| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_PATH` | SQLite file location (use the persistent disk on Render) | `urls.db` next to `app.py` |
| `BASE_URL` | Force the domain used in short URLs (optional) | detected from the request |
| `SECRET_KEY` | Flask secret key | random value at start-up |
| `PORT` | Port for `python app.py` | `5000` |
| `FLASK_DEBUG` | Set to `1` for local debugging only | `0` (off) |

## API Documentation

### `POST /api/shorten`
Request (`Content-Type: application/json`):
```json
{ "url": "https://www.example.com" }
```
Response `201 Created` (`200 OK` if the URL was already shortened):
```json
{
  "original_url": "https://www.example.com",
  "short_code": "abc123",
  "short_url": "https://your-domain.com/abc123"
}
```
Errors: `400` invalid or missing URL, `415` body is not JSON, `500` database failure. Error body: `{"error": "message"}`.

Example (Windows PowerShell):
```
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/shorten -ContentType "application/json" -Body '{"url":"https://www.example.com"}'
```
Example (curl):
```
curl -X POST http://127.0.0.1:5000/api/shorten -H "Content-Type: application/json" -d "{\"url\":\"https://www.example.com\"}"
```

### `GET /health`
```json
{ "status": "ok", "message": "URL Shortener is running" }
```

### `GET /<short_code>`
Redirects (HTTP 302) to the original URL, or shows a 404 page if the code does not exist.

## Database
File: `urls.db` (SQLite). Table `urls`:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key, auto-increment |
| `original_url` | TEXT | unique |
| `short_code` | TEXT | unique |
| `created_at` | TIMESTAMP | defaults to the current time |

All queries are parameterized. Unique constraints prevent duplicate codes, and a collision triggers a retry with a new code.

## Testing
1. Start the app and open the homepage.
2. Paste `https://www.python.org` and select **Shorten URL**, then **Copy URL**.
3. Open the short link; it must redirect to python.org.
4. Shorten the same URL again; the same code is returned.
5. Try `ftp://x.com` or `hello`; an error message appears.
6. Visit `http://127.0.0.1:5000/AAAAAA`; a 404 page appears.
7. Visit `http://127.0.0.1:5000/health`.

## Upload to GitHub
1. Create an empty repository on github.com (for example `simple-url-shortener`), with no README.
2. In the project folder run:
```
git init
git add .
git commit -m "Initial commit: Simple URL Shortener"
git branch -M main
git remote add origin https://github.com/<your-username>/simple-url-shortener.git
git push -u origin main
```
`.gitignore` keeps `venv/` and `*.db` out of the repository.

## Deploy on Render
1. Sign in at render.com with GitHub.
2. Choose **New + > Blueprint**, select your repository, and Render reads `render.yaml`.
   (Alternatively choose **New + > Web Service** and use: Build `pip install -r requirements.txt`, Start `gunicorn app:app --bind 0.0.0.0:$PORT`.)
3. **Persistent disk:** Render disks need a paid instance type (the blueprint uses `starter`). The disk mounts at `/var/data` and `DATABASE_PATH=/var/data/urls.db` stores the database there so links survive restarts and redeploys.
   On a free instance there is no disk: remove the `disk:` block, set `plan: free` and delete `DATABASE_PATH`. Links will then be lost whenever the service restarts.
4. Wait for the deploy to finish, then open `https://<your-service>.onrender.com`.
5. Check `https://<your-service>.onrender.com/health`.

## Developer
**Rushikesh Ghodke**
IICT,JNEC,MGM University, Chh-Sambhajinagar.
