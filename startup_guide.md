# Startup Guide

This guide shows how to run Image Analysis and Segmentation Platform locally for demos or evaluation.

## Requirements

- Python 3.12
- PowerShell
- Optional: Caddy for local HTTPS

## Start the Backend

From the repository root:

```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

Leave this window open while the app is running.

## Optional: Start HTTPS with Caddy

From the repository root:

```powershell
caddy run --config Caddyfile
```

If `caddy` is not on your `PATH`, use the full path to your local `caddy.exe`.

## Open the App

Without Caddy:
- App: `http://localhost:5000/index.html`
- API docs: `http://localhost:5000/docs`

With Caddy:
- App: `https://localhost/index.html`
- API docs: `https://localhost/docs`

## Demo Flow

1. Sign in through the UI.
2. Upload an image from the Upload page.
3. Create a job for that image.
4. Open the Jobs or Result page to review outputs.
5. If segmentation artifacts were generated, request `GET /api/images/{image_id}/segments`.

## Admin Tasks

Use `admin.html` to:
- sign in as admin
- create users
- delete users
- review job statistics

You can also use the API endpoints described in `README.md`.

## Stop the App

Press `Ctrl + C` in each PowerShell window.

## Common Issues

- If port `5000` is already in use, stop the existing process and restart the backend.
- If HTTPS is not working, confirm Caddy is installed and the `Caddyfile` is present in the repo root.
- If login fails, check the values in `backend/.env`.
