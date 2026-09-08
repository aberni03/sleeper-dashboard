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

## Reviving on another Mac (via iCloud Drive)

1. This folder lives in iCloud Drive, so it's already synced to your other Mac.
2. **Copy it out of iCloud to a local working folder** (recommended so iCloud
   doesn't offload files while Streamlit runs):
   ```bash
   cp -R ~/Library/Mobile\ Documents/com~apple~CloudDocs/sleeper-dashboard ~/sleeper-dashboard
   cd ~/sleeper-dashboard
   ```
3. Make sure Python 3.11+ is installed, then run the steps under **Run it** above.
4. When you finish editing, copy the folder back to iCloud to save your changes.

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
