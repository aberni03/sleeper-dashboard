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
import re
import sleeper as S

ENABLE_EXTERNAL = True           # set False to run entirely offline on the proxy

# How much the FantasyPros cross-position board moves a lineup decision. At 0 the
# lineup is pure Sleeper projections; at 1 it is pure expert consensus. The point
# of blending: a bench player projected 2 points lower but 20 spots higher on the
# consensus board is a legitimate start, and projections alone never surface him.
FP_BLEND = 0.35

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
def _fc_rows(superflex, num_teams, ppr):
    """Raw FantasyCalc payload. Shared by fantasy_values() and pick_values() so
    players and rookie picks cost a single request."""
    import requests
    url = (f"{FC_URL}?isDynasty=true&numQbs={2 if superflex else 1}"
           f"&numTeams={num_teams}&ppr={ppr}")
    try:
        return requests.get(url, timeout=15).json() or []
    except Exception:
        return []


_PICK_RE = re.compile(r"^(\d{4})\s+(\d)(?:st|nd|rd|th)(?:\s+\((Early|Mid|Late)\))?$")
ROUND_SUFFIX = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th"}


@S.cache(ttl=6 * 3600)
def pick_values(superflex, num_teams, ppr):
    """Rookie-pick prices, split into generic and tier-specific lookups.

    FantasyCalc only tiers the next draft class (Early/Mid/Late on 2027 at time
    of writing); later years are priced generically because nobody knows who will
    be picking where. Returns {"generic", "tiered", "tier_season", "scale"}.
    """
    generic, tiered = {}, {}
    rows = _fc_rows(superflex, num_teams, ppr)
    top = max((r.get("value") or 0) for r in rows) if rows else 1
    for r in rows:
        pl = r.get("player") or {}
        if pl.get("position") != "PICK":
            continue
        m = _PICK_RE.match((pl.get("name") or "").strip())
        if not m:
            continue
        year, rnd, tier = int(m.group(1)), int(m.group(2)), m.group(3)
        val = r.get("value") or 0
        if tier:
            tiered[(year, rnd, tier)] = val
        else:
            generic[(year, rnd)] = val
    tier_season = min((y for y, _, _ in tiered), default=None)
    return {"generic": generic, "tiered": tiered, "tier_season": tier_season,
            "scale": 99.0 / (top or 1)}


# How much of the Early/Mid/Late spread to trust N drafts out. The next class is
# taken at face value; beyond that, today's standings say less and less about who
# will be picking where, so the tier effect decays toward the generic price.
TIER_DECAY = (1.0, 0.5, 0.25)


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
    rows = _fc_rows(superflex, num_teams, ppr)
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

    def __init__(self, ctx, players, projections=None, fp=None):
        self.ctx = ctx
        self.players = players
        self.proj = projections or {}
        self.fp_idx = fp or {}
        self.mode = "external" if ENABLE_EXTERNAL else "proxy"
        self._ext = {}
        self._picks = None
        if ENABLE_EXTERNAL:
            lg = ctx["league"]
            rec = (lg.get("scoring_settings", {}) or {}).get("rec", 0)
            nteams = ctx["num_teams"] or 12
            self._ext = fantasy_values(ctx["superflex"], nteams, rec)
            if ctx["format"] == "dynasty":
                self._picks = pick_values(ctx["superflex"], nteams, rec)
        self.dynasty = ctx["format"] == "dynasty"

    def value(self, pid):
        """Asset value used for trades/roster strength. Dynasty→long-term, redraft→win-now."""
        if self.mode == "external":
            v = self._ext.get(str(pid))
            if v:
                return v["dyn"] if self.dynasty else v["redraft"]
        return proxy_value(pid, self.players)          # K/DEF/deep bench, or API down

    def pick_value(self, season, rnd, tier):
        """FantasyCalc value for one rookie pick, tier-adjusted.

        An exact tiered price is used when FantasyCalc publishes one. Otherwise
        the tier's premium/discount is carried over from the class that IS tiered
        and decayed by how many drafts away it is — a 2029 1st from a projected
        cellar team is worth more than a generic 2029 1st, but far less
        confidently than a 2027 one.
        """
        pv = self._picks
        if not pv:
            return 0
        exact = pv["tiered"].get((season, rnd, tier))
        if exact is not None:
            return exact
        base = pv["generic"].get((season, rnd))
        if base is None:
            return 0
        ts = pv["tier_season"]
        if not ts or tier is None:
            return base
        ref_t = pv["tiered"].get((ts, rnd, tier))
        ref_g = pv["generic"].get((ts, rnd))
        if not ref_t or not ref_g:
            return base
        ratio = ref_t / ref_g
        out = max(0, season - ts)
        w = TIER_DECAY[min(out, len(TIER_DECAY) - 1)]
        return int(round(base * (1 + (ratio - 1) * w)))

    def pick_scale(self):
        """Divisor turning a raw pick value into the internal 0-100 scale."""
        return self._picks["scale"] if self._picks else 0.0

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

    def fp(self, pid):
        """FantasyPros consensus row for this week: pos_rank, ecr, std, grade.
        None when unmatched or when the FantasyPros layer is off."""
        return self.fp_idx.get(str(pid))

    def fp_pos_rank(self, pid):
        """Numeric slice of 'WR12' -> 12. None when unranked."""
        row = self.fp_idx.get(str(pid))
        pr = (row or {}).get("pos_rank") or ""
        digits = "".join(ch for ch in str(pr) if ch.isdigit())
        return int(digits) if digits else None

    def fp_overall(self, pid):
        """Cross-position consensus rank (FLEX board, or superflex where QBs
        count). This is the only rank that makes RB20 vs WR22 comparable."""
        row = self.fp_idx.get(str(pid))
        return (row or {}).get("overall")

    def confidence(self, pid):
        """How settled the experts are on this player, from their spread.
        Projections cannot express this — one number never shows dissent."""
        row = self.fp_idx.get(str(pid))
        sd = (row or {}).get("std")
        if sd is None:
            return None
        return "high" if sd <= 2.0 else "medium" if sd <= 5.0 else "low"

    def fp_points(self, pid):
        """Consensus rank expressed on a points-like scale so it can be weighed
        against a projection. Overall 1 lands near 22, 70th near 8, 200th near 1."""
        ovr = self.fp_overall(pid)
        if not ovr:
            return None
        return 22.0 * math.exp(-ovr / 70.0)

    def start_score(self, pid):
        """Ranking score for lineup decisions.

        Blends Sleeper's projection with the FantasyPros cross-position board, so
        a player the experts rank far higher can outrank a slightly better
        projection. Falls back to projections alone when unranked.
        """
        pts = self.points(pid)
        base = pts if pts > 0 else self.value(pid) / 10.0
        fp = self.fp_points(pid)
        if fp is None or not FP_BLEND:
            return base
        return (1 - FP_BLEND) * base + FP_BLEND * fp
