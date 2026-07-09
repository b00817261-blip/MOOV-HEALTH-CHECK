# Deploying the MOOV Health Check website

The app is a single self-contained Python web server (standard library only).
It binds to `$PORT` and keeps its data as JSON files under `$MOOV_DATA_DIR`
(default `reports/`), so it deploys to any host that runs a long-lived process
and gives it a port.

## Fastest free option — Render (no credit card)

1. Push this repo to GitHub (already done for the working branch).
2. Go to <https://render.com>, sign up, and click **New → Blueprint**.
3. Pick this repository. Render reads [`render.yaml`](render.yaml), installs the
   app, and starts it with `moov-health-check serve`.
4. In a minute you get a public URL like `https://moov-health-check.onrender.com`.
   Open `…/login`, sign in as the **head of the desk**, add your groups, and
   share the invite links.

Prefer not to use the Blueprint? **New → Web Service** → connect the repo →
Runtime **Python 3**, Build `pip install -e .`, Start `moov-health-check serve`.

> **Free-plan storage:** the free web service has an ephemeral disk and sleeps
> after ~15 min idle, so groups/tasks/updates **reset on redeploy or restart** —
> fine for a prototype/demo. For permanent data, attach a Render **Disk** (paid)
> and set `MOOV_DATA_DIR` to its mount path (both are prepared in `render.yaml`),
> or move storage to a hosted database (see below).

## Any container host — Docker

A portable [`Dockerfile`](Dockerfile) is included. It works on Render, Railway,
Fly.io, Google Cloud Run, or a plain VM:

```bash
docker build -t moov .
docker run -p 8000:8000 moov          # then open http://localhost:8000/login
```

- **Fly.io** (free allowance, persistent volumes): `fly launch` (it detects the
  Dockerfile), add a volume, and set `MOOV_DATA_DIR` to the mount path.
- **Railway**: New Project → Deploy from repo → it builds the Dockerfile.

## Run it on any small VM / server

```bash
pip install -e .
MOOV_DATA_DIR=/srv/moov/reports moov-health-check serve   # reads $PORT if set
```

Put it behind a reverse proxy (Caddy/nginx) for HTTPS. There are no passwords —
run it on a trusted network/VPN, or add auth at the proxy if it must be public.

## About Vercel

Vercel runs *serverless functions* with an ephemeral, read-only filesystem and
no long-running process, so this app's "persistent JSON files + one server"
design does not fit it as-is. Running on Vercel would require a serverless
adapter **and** swapping file storage for a hosted store (Vercel Postgres/KV/
Blob). The hosts above run the app unchanged, which is why they're recommended.

## Environment variables

| Variable | Default | What it does |
|----------|---------|--------------|
| `PORT` | `8000` | Port to bind (most hosts set this for you). |
| `MOOV_DATA_DIR` | `reports` | Where groups/tasks/updates/settings are stored. |
| `MOOV_ROSTER` | `config/teams.json` | The group tree file (created on first run). |
