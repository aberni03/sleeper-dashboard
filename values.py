"""Value + projection layer.

Trade values come from FantasyCalc's public API (no key required), keyed by
Sleeper player id so the join onto roster data is exact. One request serves both
formats: the dynasty response carries `value` (long-term) and `redraftValue`
(win-now) side by side, and Valuer.value() picks per league format.

ENABLE_EXTERNAL still gates the network call. With it off — or if the request
fails, or for positions FantasyCalc doesn't cover (K, DEF) — everything falls
back to proxy_value(), a search-rank proxy off Sleeper's own metadata, so the
app is fully functional either way.

Weekly projections come from Sleeper's own endpoint via the data layer."""
import math
import sleeper as S

ENABLE_EXTERNAL = True           # set False to run entirely offline on the proxy

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


# ── external value source: FantasyCalc ────────────────────────────────
FC_URL = "https://api.fantasycalc.com/values/current"


@S.cache(ttl=6 * 3600)
def fantasy_values(superflex, num_teams, ppr):
    """FantasyCalc current values, keyed by Sleeper player id.

    Returns {sleeper_id: {'dyn', 'redraft', 'raw_dyn', 'raw_redraft', ...}}.

    Two scales are kept deliberately:
      * raw_*  — FantasyCalc's own numbers (0–11000ish), so what the UI shows can
                 be checked straight against fantasycalc.com.
      * dyn/redraft — those same values normalized to 0–100 to match
                 proxy_value(), so the value term can't swamp projected points in
                 start_score(). Internal math only; never display these.

    One request covers both formats: the dynasty payload's `redraftValue` is
    identical to the dedicated redraft endpoint's `value` (verified across all
    199 shared players), and it carries 423 players instead of 199.

    Note: FantasyCalc has no TEP parameter, so tight-end premium isn't reflected
    here — it's format-aware for superflex, team count and PPR only.
    """
    import requests
    url = (f"{FC_URL}?isDynasty=true&numQbs={2 if superflex else 1}"
           f"&numTeams={num_teams}&ppr={ppr}")
    try:
        rows = requests.get(url, timeout=15).json()
    except Exception:
        return {}
    if not rows:
        return {}

    top_dyn = max((r.get("value") or 0) for r in rows) or 1
    top_red = max((r.get("redraftValue") or 0) for r in rows) or 1

    out = {}
    for r in rows:
        pl = r.get("player") or {}
        sid = pl.get("sleeperId")
        if not sid:                                       # picks/oddities without a Sleeper id
            continue
        out[str(sid)] = {
            "dyn": round(99.0 * (r.get("value") or 0) / top_dyn, 1),
            "redraft": round(99.0 * (r.get("redraftValue") or 0) / top_red, 1),
            "raw_dyn": r.get("value") or 0,
            "raw_redraft": r.get("redraftValue") or 0,
            "trend30": r.get("trend30Day") or 0,
            "pos_rank": r.get("positionRank"),
            "ovr_rank": r.get("overallRank"),
        }
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
            self._ext = fantasy_values(ctx["superflex"], ctx["num_teams"] or 12, rec)
        self.dynasty = ctx["format"] == "dynasty"

    def value(self, pid):
        """Asset value used for trades/roster strength. Dynasty→long-term, redraft→win-now."""
        if self.mode == "external":
            v = self._ext.get(str(pid))
            if v:
                return v["dyn"] if self.dynasty else v["redraft"]
        return proxy_value(pid, self.players)          # K/DEF/deep bench, or API down

    def raw_value(self, pid):
        """FantasyCalc's own value on their native scale — the number to show a
        human, and the one that matches fantasycalc.com. 0 when uncovered."""
        v = self._ext.get(str(pid)) if self.mode == "external" else None
        if not v:
            return 0
        return v["raw_dyn"] if self.dynasty else v["raw_redraft"]

    def covered(self, pid):
        """True when FantasyCalc actually prices this player (vs the rank proxy)."""
        return bool(self._ext.get(str(pid))) if self.mode == "external" else False

    def trend30(self, pid):
        """30-day value trend from FantasyCalc (0 when unknown). Rising/falling
        assets for the waiver + trade views."""
        v = self._ext.get(str(pid)) if self.mode == "external" else None
        return (v or {}).get("trend30", 0)

    def points(self, pid):
        """This-week projected points (0 if unknown)."""
        return self.proj.get(str(pid), 0.0)

    def start_score(self, pid):
        """Ranking score for lineup decisions — projections if we have them, else value."""
        pts = self.points(pid)
        return pts if pts > 0 else self.value(pid) / 10.0
