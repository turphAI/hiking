# Deploying hiking on the mini

The mini is the only host. The laptop never runs the hiking service.

hiking runs as its **own** service alongside turph and the rest of the suite.
turph owns the tailnet root; hiking is a separate Flask app on **port 5056**,
mounted at `/hiking` via `tailscale serve`. Fully decoupled — no shared
process, port, or database with any other app.

## What runs

- Flask (`backend/app.py`) bound to `127.0.0.1:5056`, supervised by launchd, KeepAlive on.
- `tailscale serve` mounts this app at `https://mini.tail5ef0b2.ts.net/hiking/`.
- The built SPA in `static/` (regenerated from `frontend/` on each deploy), base `/hiking/`.
- SQLite DB at `data/hiking.db` (gitignored).

Port 5056 is next in the suite's sequence: 5050 turph, 5051 witness, 5052
turphfolio, 5053 turphDocs, 5054 vasospasm, 5055 turphRetirement — checked
against every app's `DEPLOY.md` on 2026-08-19, nothing claims 5056+.

### A note on the /hiking mount

Every Flask route is **dual-mounted** under both the bare path (`/api/...`)
and the `/hiking`-prefixed path, same as witness/turphfolio/turphDocs — makes
the app correct whether `tailscale serve --set-path` strips or preserves the
prefix. `GET /api/health` echoes `matched_path` to confirm live behavior.

## One-time setup

After cloning the repo on the mini at `~/Projects/hiking`:

```sh
# Backend
cd ~/Projects/hiking/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "import db; db.init_db()"   # creates data/hiking.db
python3 seed.py                        # loads backend/data/seed_peaks.json
deactivate

# Frontend
cd ~/Projects/hiking/frontend
npm install
npm run build             # outputs to ../static/ with base /hiking/

# launchd
cp ~/Projects/hiking/infra/launchd/com.hiking.app.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hiking.app.plist

# Tailscale serve — mount hiking at /hiking without disturbing other apps' mounts.
tailscale serve --bg --set-path /hiking 5056
```

Verify:

```sh
curl -s http://127.0.0.1:5056/api/health
# {"matched_path":"/api/health","ok":true,"service":"hiking"}

curl -s https://mini.tail5ef0b2.ts.net/hiking/api/health

# Confirm every app's mount is still present, not clobbered.
tailscale serve status
```

## Updates (every deploy)

```sh
cd ~/Projects/hiking
git pull

# Backend deps if requirements.txt changed
cd backend && source .venv/bin/activate && pip install -r requirements.txt && deactivate

# Schema migrations apply automatically — app.py calls db.init_db() at module
# level, so the restart below already runs the user_version ladder.

# Frontend rebuild (always — bundle changes any time src/ changes)
cd ../frontend && npm install && npm run build

# Restart Flask
launchctl kickstart -k gui/$(id -u)/com.hiking.app
```

## Logs

```sh
tail -f ~/Projects/hiking/hiking.log
```

## Stopping / removing

```sh
launchctl unload ~/Library/LaunchAgents/com.hiking.app.plist
rm ~/Library/LaunchAgents/com.hiking.app.plist
tailscale serve --set-path /hiking off
```

## Why these choices

Matches the rest of the suite exactly (see `CLAUDE.md`) — Flask + SQLite +
launchd + `tailscale serve`, not because each was independently evaluated
here, but because deviating from the house pattern would be the choice that
needed justifying.
