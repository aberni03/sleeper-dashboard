"""Value + projection layer.

API-LAST DESIGN: the external trade-value source (FantasyCalc) is gated behind
ENABLE_EXTERNAL and defaults OFF. Until it's switched on, everything runs on a
search-rank proxy derived from Sleeper's own player metadata, so the whole app is
functional today. Weekly projections come from Sleeper's own endpoint (already
part of the data layer), and are used when available.

When we do the 'wire up the APIs' step:
  * set ENABLE_EXTERNAL = True
  * DYNASTY leagues  -> DynastyNerds trade values (format/superflex/TEP aware)
  * REDRAFT leagues  -> a blend of multiple redraft sources (rest-of-season)
  The Valuer.value() method already branches dynasty vs redraft, so only the two
  loader functions below get swapped in — nothing in analysis.py or app.py changes.
  (fantasy_values() below is a working placeholder proving the interface.)"""
import math
import sleeper as S

ENABLE_EXTERNAL = False          # ← flip to True in the API step

SKILL = {"QB", "RB", "WR", "TE"}
FLEX_ELIG = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"},
    "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}
START_SLOTS = set(FLEX_ELIG) - set()          # anything not BN/IR/TAXI is startable
BENCH_SLOTS = {"BN", "IR", "TAXI"}


def pinfo(pid, players):
    """Normalized player row."""
    p = players.get(str(pid)) or {}
    name = p.get("full_name") or " ".join(filter(None, [p.get("first_name"), p.get("last_name")])) \
        or p.get("last_name") or str(pid)
    pos = p.get("position") or (p.get("fantasy_positions") or ["?"])[0]
    return {
        "id": str(pid),
        "name": name,
        "pos": pos,
        "team": p.get("team") or "FA",
        "age": p.get("age"),
        "rank": p.get("search_rank"),
        "injury": p.get("injury_status"),
        "years_exp": p.get("years_exp"),
    }


def proxy_value(pid, players):
    """0–100 proxy from Sleeper's global search_rank (lower rank = better).
    Used until the external value API is switched on."""
    p = players.get(str(pid)) or {}
    sr = p.get("search_rank")
    if sr is None or sr >= 9999:
        return 0.0
    # rank 1 ≈ 99, rank 60 ≈ 61, rank 150 ≈ 29, rank 300 ≈ 8
    return round(100.0 * math.exp(-sr / 130.0), 1)


# ── external value source (OFF until the API step) ────────────────────────────
# PLACEHOLDER: proves the interface. Replaced at API-step by:
#   dynasty_values()  -> DynastyNerds
#   redraft_values()  -> blended multi-source rest-of-season
def fantasy_values(superflex, num_teams, ppr, tep):
    """FantasyCalc current values. Returns {player_name_key: {'dyn':x,'redraft':y}}.
    Only called when ENABLE_EXTERNAL is True."""
    import requests
    url = ("https://api.fantasycalc.com/values/current"
           f"?isDynasty=true&numQbs={2 if superflex else 1}&numTeams={num_teams}&ppr={ppr}")
    try:
        rows = requests.get(url, timeout=15).json()
    except Exception:
        return {}
    out = {}
    for r in rows:
        pl = r.get("player", {})
        key = _namekey(pl.get("name", ""))
        if key:
            out[key] = {"dyn": r.get("value", 0), "redraft": r.get("redraftValue", 0)}
    return out


def _namekey(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


# ── unified accessor the rest of the app uses ─────────────────────────────────
class Valuer:
    """One object per league that answers value/projection questions.
    Swaps transparently between proxy (now) and external (later)."""

    def __init__(self, ctx, players, projections=None):
        self.ctx = ctx
        self.players = players
        self.proj = projections or {}
        self.mode = "external" if ENABLE_EXTERNAL else "proxy"
        self._ext = {}
        if ENABLE_EXTERNAL:
            lg = ctx["league"]
            rec = (lg.get("scoring_settings", {}) or {}).get("rec", 0)
            self._ext = fantasy_values(ctx["superflex"], ctx["num_teams"] or 12, rec,
                                       (lg.get("scoring_settings", {}) or {}).get("bonus_rec_te", 0))
        self.dynasty = ctx["format"] == "dynasty"

    def value(self, pid):
        """Asset value used for trades/roster strength. Dynasty→long-term, redraft→win-now."""
        if self.mode == "external":
            k = _namekey(pinfo(pid, self.players)["name"])
            v = self._ext.get(k)
            if v:
                return v["dyn"] if self.dynasty else v["redraft"]
        return proxy_value(pid, self.players)

    def points(self, pid):
        """This-week projected points (0 if unknown)."""
        return self.proj.get(str(pid), 0.0)

    def start_score(self, pid):
        """Ranking score for lineup decisions — projections if we have them, else value."""
        pts = self.points(pid)
        return pts if pts > 0 else self.value(pid) / 10.0
