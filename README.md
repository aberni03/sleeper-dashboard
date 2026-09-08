# Fantasy Command Center (Sleeper)

A Streamlit dashboard that pulls all your Sleeper leagues into one place —
lineup, waiver, and trade decisions across every league at once, split by
**dynasty** vs **redraft/guillotine**. Username-driven, so you can share the link
and others enter their own Sleeper username (`?u=username`).

## Run it

```bash
cd sleeper-dashboard
pip install -r requirements.txt      # first time only
streamlit run app.py
```

Then open http://localhost:8501. Enter a Sleeper username at the top
(defaults to `aberni3`). To stop: `pkill -f "streamlit run"`.

## Working across two Macs

The folder lives in iCloud Drive, so edits sync between laptop and desktop
automatically. Two rules keep that painless:

1. **Don't edit on both machines at once.** Let iCloud finish syncing (Finder
   shows no cloud/progress icon) before switching machines, or iCloud writes a
   "conflicted copy" file. Git history is the safety net if it happens.
2. **The venv is not in iCloud.** Each machine gets its own, since installed
   packages are platform-specific:
   ```bash
   python3 -m venv ~/.venvs/sleeper-dashboard
   ~/.venvs/sleeper-dashboard/bin/pip install -r requirements.txt
   ~/.venvs/sleeper-dashboard/bin/streamlit run app.py
   ```

The ~16MB player cache also lives outside iCloud
(`~/Library/Caches/sleeper-dashboard`) so it doesn't churn sync daily. Override
with `SLEEPER_DATA_DIR` if you want it elsewhere; it re-downloads if deleted.

## Deploying to Streamlit Community Cloud

Deployed as a **private app**, so a handful of named people can use it while the
FantasyPros layer stays on — that's personal use, not publishing to the web.

1. Repo: <https://github.com/aberni03/sleeper-dashboard> (private).
2. At <https://share.streamlit.io> → **Create app** → *Deploy a public app from
   GitHub* → pick this repo, branch `main`, main file `app.py`.
   A private repo yields a private app automatically.
3. After it deploys: **⋮ → Settings → Sharing**, add each viewer's email. They
   sign in with Google or a one-time email link. The cap is far above the
   handful this is meant for; you get one private app on the free tier.
4. Every push to `main` redeploys.

### What the deployed app needs

Nothing. No API keys, no secrets, no paid tier — Sleeper's API, FantasyCalc and
FantasyPros are all reachable unauthenticated. `requirements.txt` is the whole
build. Caches land in `~/.cache/sleeper-dashboard` on the container, which is
writable.

### Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `SLEEPER_DASH_FP` | on | Set to `0` to disable the FantasyPros layer. Do that **only** if the app is ever made public — serving their rankings to anyone with the link is redistribution. Off, everything falls back to Sleeper projections. |
| `SLEEPER_DATA_DIR` | platform cache dir | Where the player file and rankings cache are written. |

A cold container pays about 45 seconds on first load per scoring format: five
FantasyPros requests spaced by the 5 second crawl delay their robots.txt asks
for. It is cached on disk for 3 hours after that, and Community Cloud clears the
disk when the app sleeps or redeploys, so the first visitor after a wake-up
waits.

## Files

- `app.py`      — Streamlit UI (command center, tabs, action center)
- `sleeper.py`  — Sleeper API data layer (cached; works for any username)
- `values.py`   — value/projection layer; `ENABLE_EXTERNAL` flag gates the paid
                  trade-value source (DynastyNerds / blended redraft). Currently
                  uses a search-rank proxy + live Sleeper projections.
- `analysis.py` — start/sit optimizer, waiver ranking, win-win trade engine, digest

## Notes

- No password/login needed — Sleeper's public API is read-only.
- The `data/` folder holds a cached copy of Sleeper's ~12k-player file; it
  re-downloads automatically if missing, so it's safe to delete.
- TODO: wire real trade values (set `ENABLE_EXTERNAL = True` in `values.py`).
