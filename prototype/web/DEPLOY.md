# Deploying the web UI

The `prototype/` directory ships everything needed to deploy the FastAPI demo
behind a public HTTPS URL. Default target: **Fly.io** (free allowance, no
GitHub repo required, deploy from your laptop with `flyctl`).

## Local dev

```bash
cd prototype
python -m venv .venv && source .venv/bin/activate    # or .\.venv\Scripts\activate on Windows
pip install -r requirements.txt
# .env should contain OPENROUTER_API_KEY=... (already there if you ran run.py)
uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
# open http://127.0.0.1:8000
```

`Run mock` works without any API key. `Run real` needs `OPENROUTER_API_KEY`
(or `ANTHROPIC_API_KEY`) in the environment and counts toward the daily cap
(default 10).

## Deploy to Fly.io (recommended)

1. Install flyctl:
   - Windows PowerShell: `iwr https://fly.io/install.ps1 -useb | iex`
   - macOS / Linux: `curl -L https://fly.io/install.sh | sh`
2. `fly auth signup` (or `fly auth login` if you already have an account)
3. From `prototype/`:
   ```bash
   fly launch --no-deploy --copy-config --name tilt-trading-agents
   # Accept the existing fly.toml. Pick a region close to your mentors.
   ```
4. Set the API key as a secret (NOT committed, NOT in the image):
   ```bash
   fly secrets set OPENROUTER_API_KEY=sk-or-...
   # optional second key, used as fallback if OpenRouter is missing:
   # fly secrets set ANTHROPIC_API_KEY=sk-ant-...
   ```
5. Deploy:
   ```bash
   fly deploy
   ```
6. `fly open` — opens the public URL.

The free `shared-cpu-1x / 512MB` machine fits inside Fly's free allowance.
`auto_stop_machines = "stop"` puts the VM to sleep when idle (so it doesn't
burn quota); the first request after sleep takes ~3s to wake.

### Daily cap persistence

The 10-real-runs/day counter lives in `output/.daily_cap.json` inside the
container. On a redeploy or VM restart the counter resets. For a stricter
guarantee, attach a Fly volume:

```bash
fly volumes create tilt_data --size 1 --region fra
```

Then add this to `fly.toml` under `[mounts]`:

```toml
[mounts]
  source = "tilt_data"
  destination = "/app/output"
```

For the demo that's overkill — restarts are rare and a soft cap suffices.

## Alternative: Render

1. Push the repo to GitHub.
2. Render → New → Web Service → connect repo, set root directory to `prototype`.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn web.app:app --host 0.0.0.0 --port $PORT`
5. Environment: add `OPENROUTER_API_KEY` (and optionally `ANTHROPIC_API_KEY`,
   `REAL_DAILY_LIMIT`).
6. Free plan; sleeps after 15 minutes idle.

## Alternative: HuggingFace Spaces (Docker)

1. Create a Space, type "Docker", visibility public or private.
2. Push `prototype/` contents to the Space's Git repo (HF will use the
   Dockerfile automatically).
3. Set `OPENROUTER_API_KEY` in Space → Settings → Secrets.

## What NOT to ship

- `.env` (your API key)
- `output/.daily_cap.json` (will be re-created)
- `.venv/` (rebuilt in the image)

`.dockerignore` already excludes these. Verify with `docker build` locally
before deploying:

```bash
cd prototype
docker build -t tilt-demo .
docker run -p 8000:8000 -e OPENROUTER_API_KEY=$OPENROUTER_API_KEY tilt-demo
```
