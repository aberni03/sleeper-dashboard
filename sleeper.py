"""Sleeper data layer — username-driven so the same code serves you and anyone
you share the link with. All network calls are cached (in-memory via streamlit
where available, and the big players file to disk)."""
import os, json, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

API = "https://api.sleeper.app/v1"
PROJ = "https://api.sleeper.app"          # projections live off the /v1 path
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "sleeper-dashboard/0.1"})

# ── optional streamlit cache (falls back to a plain dict cache off-app) ────────
try:
    import streamlit as st
    cache = st.cache_data
except Exception:                                         # running outside streamlit (tests/CLI)
    def cache(ttl=None):
        def deco(fn):
            store = {}
            def wrap(*a, **k):
                key = (a, tuple(sorted(k.items())))
                if key not in store:
                    store[key] = fn(*a, **k)
                return store[key]
            return wrap
        return deco


def _get(url, default=None):
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code != 200:
            return default
        return r.json()
    except Exception:
        return default


# ── players master file (≈5MB, ~11k players) — cached to disk for a day ───────
def load_players(max_age_hours=24):
    fp = os.path.join(DATA, "players_nfl.json")
    if os.path.exists(fp) and (time.time() - os.path.getmtime(fp)) < max_age_hours * 3600:
        with open(fp) as f:
            return json.load(f)
    data = _get(f"{API}/players/nfl", default={})
    if data:
        with open(fp, "w") as f:
            json.dump(data, f)
    elif os.path.exists(fp):                              # network failed: fall back to stale copy
        with open(fp) as f:
            return json.load(f)
    return data or {}


@cache(ttl=3600)
def nfl_state():
    return _get(f"{API}/state/nfl", default={}) or {}


@cache(ttl=1800)
def resolve_user(username):
    """username OR user_id -> user object (dict) or None."""
    u = _get(f"{API}/user/{username}")
    return u if (u and u.get("user_id")) else None


@cache(ttl=600)
def user_leagues(user_id, season):
    return _get(f"{API}/user/{user_id}/leagues/nfl/{season}", default=[]) or []


@cache(ttl=300)
def league_rosters(league_id):
    return _get(f"{API}/league/{league_id}/rosters", default=[]) or []


@cache(ttl=600)
def league_users(league_id):
    return _get(f"{API}/league/{league_id}/users", default=[]) or []


@cache(ttl=120)
def league_matchups(league_id, week):
    return _get(f"{API}/league/{league_id}/matchups/{week}", default=[]) or []


@cache(ttl=600)
def trending(kind="add", hours=24, limit=200):
    """kind = 'add' or 'drop'. Returns [{player_id, count}]."""
    url = f"{API}/players/nfl/trending/{kind}?lookback_hours={hours}&limit={limit}"
    return _get(url, default=[]) or []


@cache(ttl=600)
def projections(season, week, scoring="ppr"):
    """Undocumented but stable weekly projections endpoint.
    Returns {player_id: projected_points} for the given scoring key."""
    url = f"{PROJ}/projections/nfl/{season}/{week}?season_type=regular"
    rows = _get(url, default=[]) or []
    key = {"ppr": "pts_ppr", "half_ppr": "pts_half_ppr", "std": "pts_std"}.get(scoring, "pts_ppr")
    out = {}
    for r in rows:
        pid = r.get("player_id")
        pts = (r.get("stats") or {}).get(key)
        if pid and pts is not None:
            out[str(pid)] = float(pts)
    return out


# ── format helpers ────────────────────────────────────────────────────────────
def league_format(league):
    """Return one of: 'dynasty', 'keeper', 'guillotine', 'redraft'."""
    s = league.get("settings", {}) or {}
    t = s.get("type")
    if t == 3:
        return "guillotine"
    if t == 2:
        return "dynasty"
    if t == 1:
        return "keeper"
    return "redraft"


def is_superflex(league):
    pos = league.get("roster_positions", []) or []
    return "SUPER_FLEX" in pos or pos.count("QB") > 1


def scoring_key(league):
    """Pick the projections scoring bucket that best matches this league's rec value."""
    rec = (league.get("scoring_settings", {}) or {}).get("rec", 0)
    if rec >= 1:
        return "ppr"
    if rec >= 0.5:
        return "half_ppr"
    return "std"


def group_of(league):
    """Top-level UI split the user asked for."""
    return "dynasty" if league_format(league) == "dynasty" else "redraft"


# ── assembled per-league context ──────────────────────────────────────────────
def scoring_label(league):
    sc = league.get("scoring_settings", {}) or {}
    rec = sc.get("rec", 0)
    ppr = "PPR" if rec >= 1 else ("½ PPR" if rec >= 0.5 else "Std")
    ptd = int(sc.get("pass_td", 4))
    te = sc.get("bonus_rec_te", 0)
    extra = f" · TEP" if te else ""
    return f"{ppr} · {ptd}pt PaTD{extra}"


def build_context(league, viewer_user_id):
    """Everything the UI needs for one league, from the viewer's perspective."""
    lid = league["league_id"]
    rosters = league_rosters(lid)
    users = {u["user_id"]: u for u in league_users(lid)}

    # map roster -> owner display name
    def team_name(r):
        oid = r.get("owner_id")
        u = users.get(oid, {})
        meta = u.get("metadata") or {}
        return meta.get("team_name") or u.get("display_name") or f"Roster {r.get('roster_id')}"

    teams = []
    my_roster = None
    for r in rosters:
        s = r.get("settings", {}) or {}
        owners = set(filter(None, [r.get("owner_id")] + (r.get("co_owners") or [])))
        entry = {
            "roster_id": r.get("roster_id"),
            "owner_id": r.get("owner_id"),
            "name": team_name(r),
            "players": r.get("players") or [],
            "starters": r.get("starters") or [],
            "wins": s.get("wins", 0),
            "losses": s.get("losses", 0),
            "ties": s.get("ties", 0),
            "fpts": s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100,
            "fpts_against": s.get("fpts_against", 0) + s.get("fpts_against_decimal", 0) / 100,
            "streak": (r.get("metadata") or {}).get("streak", ""),
            "record": (r.get("metadata") or {}).get("record", ""),
            "waiver_budget_used": s.get("waiver_budget_used", 0),
            "is_mine": viewer_user_id in owners,
        }
        teams.append(entry)
        if entry["is_mine"]:
            my_roster = entry

    # standings: by wins then points-for
    teams_sorted = sorted(teams, key=lambda t: (t["wins"], t["fpts"]), reverse=True)
    for i, t in enumerate(teams_sorted, 1):
        t["rank"] = i

    return {
        "league": league,
        "league_id": lid,
        "name": league.get("name", "League"),
        "format": league_format(league),
        "superflex": is_superflex(league),
        "num_teams": league.get("total_rosters") or league.get("settings", {}).get("num_teams"),
        "scoring_label": scoring_label(league),
        "scoring_key": scoring_key(league),
        "roster_positions": league.get("roster_positions", []),
        "waiver_budget": league.get("settings", {}).get("waiver_budget"),
        "trade_deadline": league.get("settings", {}).get("trade_deadline"),
        "trades_disabled": bool(league.get("settings", {}).get("disable_trades")),
        "teams": teams,
        "standings": teams_sorted,
        "my_roster": my_roster,
    }


def load_all(username, season=None):
    """Top-level entry: resolve a username and build contexts for every league,
    grouped into dynasty vs redraft/guillotine. Returns None if user not found."""
    user = resolve_user(username)
    if not user:
        return None
    uid = user["user_id"]
    state = nfl_state()
    season = season or state.get("league_season") or state.get("season")
    leagues = user_leagues(uid, season)
    contexts = [build_context(lg, uid) for lg in leagues]
    groups = {"dynasty": [], "redraft": []}
    for lg, ctx in zip(leagues, contexts):
        groups[group_of(lg)].append(ctx)
    return {
        "user": user,
        "user_id": uid,
        "season": season,
        "week": state.get("week") or state.get("display_week") or 1,
        "state": state,
        "contexts": contexts,
        "groups": groups,
    }
