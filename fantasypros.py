"""FantasyPros expert-consensus rankings (ECR), by week and position.

WHY THIS EXISTS: Sleeper gives one projected number per player. It cannot tell
you whether that number is a settled opinion or a coin flip. FantasyPros polls
~65-70 experts, so alongside the consensus rank it publishes the spread — and
`rank_std` (how much the experts disagree) is a signal projections simply do not
carry. A 0.0 standard deviation means every expert agrees; a 12.0 means the room
is split and the start/sit call is really a gut call.

ACCESS: the rankings pages embed the full dataset in a `var ecrData = {...}`
blob. FantasyPros' robots.txt disallows /api/, /json/, /ajax/ and /nfl/ranker/
but NOT /nfl/rankings/, and asks for a 5 second crawl delay, which this module
honours. Their official API is key-only (403 without one).

REDISTRIBUTION: reading this for your own dashboard — locally, or on a private
deployment only you can open — is not the same as serving it from a public URL,
which republishes their product. ENABLE_FP gates it, and defaults ON; set
SLEEPER_DASH_FP=0 for a public deploy. With it off, everything degrades
gracefully to Sleeper projections.
"""
import os
import re
import json
import time
import requests

import sleeper as S

# On by default, which is right for personal use — running this locally, or on a
# private deployment only you can open, is your own use of their site. Set
# SLEEPER_DASH_FP=0 in the environment to turn it off without editing code, which
# is what a PUBLIC deployment should do: serving their rankings to anyone with
# the link is redistribution, not personal use.
ENABLE_FP = os.environ.get("SLEEPER_DASH_FP", "1") not in ("0", "false", "False")

BASE = "https://www.fantasypros.com/nfl/rankings"
CRAWL_DELAY = 5                       # seconds, per their robots.txt
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
_ECR_RE = re.compile(r"var\s+ecrData\s*=\s*(\{.*?\});\s*\n", re.S)

POSITIONS = ("QB", "RB", "WR", "TE")
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


# ── disk cache ────────────────────────────────────────────────────────────────
# The crawl delay, not the network, is what makes a cold load slow: five requests
# five seconds apart. Streamlit's cache dies with the process, so every restart
# paid that again. Persisting to the same cache dir as the player file makes a
# restart instant and keeps us well under FantasyPros' request budget.
DISK_TTL = 3 * 3600


def _disk_path(key):
    return os.path.join(S.DATA, f"fp_{key}.json")


def _disk_get(key, max_age=DISK_TTL):
    fp = _disk_path(key)
    try:
        if os.path.exists(fp) and (time.time() - os.path.getmtime(fp)) < max_age:
            with open(fp) as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _disk_put(key, obj):
    try:
        with open(_disk_path(key), "w") as f:
            json.dump(obj, f)
    except Exception:
        pass
    return obj


def scoring_slug(rec):
    """FantasyPros URL slug for a league's reception scoring."""
    if rec >= 1:
        return "ppr"
    if rec >= 0.5:
        return "half-point-ppr"
    return ""                          # standard has no prefix


def _url_overall(slug, superflex):
    """Cross-position board: FLX ranks RB/WR/TE against each other, superflex (OP)
    adds QB. This is the ranking that makes a flex decision answerable — RB20 vs
    WR22 is meaningless positionally, but one of them is higher on this board."""
    name = "superflex" if superflex else "flex"
    return f"{BASE}/{slug}-{name}.php" if slug else f"{BASE}/{name}.php"


def _url(pos, slug):
    # QB (and K/DST) rankings don't vary by reception scoring, and the
    # scoring-prefixed QB URL 302-redirects, so ask for the bare page.
    if pos == "QB" or not slug:
        return f"{BASE}/{pos.lower()}.php"
    return f"{BASE}/{slug}-{pos.lower()}.php"


def _num(x):
    """FantasyPros ships its numbers as strings ("1.40"), so coerce or drop."""
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _namekey(name):
    """Normalize for matching against Sleeper: lowercase alnum, no suffixes."""
    n = (name or "").lower().replace(".", " ").replace("'", "").replace("-", " ")
    n = _SUFFIX.sub(" ", n)
    return "".join(ch for ch in n if ch.isalnum())


def _fetch(pos, slug, week):
    return _fetch_url(_url(pos, slug), week)


_last_request = [0.0]


def _throttle():
    """Space real requests by the crawl delay. Applied at the request layer, not
    around the callers, so a cache hit costs nothing — that distinction is the
    whole difference between a 15 second warm start and an instant one."""
    gap = time.time() - _last_request[0]
    if gap < CRAWL_DELAY:
        time.sleep(CRAWL_DELAY - gap)
    _last_request[0] = time.time()


def _fetch_url(url, week):
    _throttle()
    params = {"week": week} if week else None
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=25)
        if r.status_code != 200:
            return None
        m = _ECR_RE.search(r.text)
        if not m:
            return None
        return json.loads(m.group(1))
    except Exception:
        return None


@S.cache(ttl=3 * 3600)
def rankings(slug, week):
    """{position: [player rows]} for one week and scoring format.

    Rows keep FantasyPros' own field names so the table tab can show exactly what
    they publish. Empty positions are omitted — asking for a week whose rankings
    aren't out yet returns players=[] from their side, not an error.
    """
    if not ENABLE_FP:
        return {}
    key = f"pos_{slug or 'std'}_{week}"
    cached = _disk_get(key)
    if cached is not None:
        return cached
    out = {}
    for pos in POSITIONS:
        d = _fetch(pos, slug, week)
        if not d:
            continue
        rows = d.get("players") or []
        if rows:
            out[pos] = rows
    return _disk_put(key, out) if out else out


@S.cache(ttl=3 * 3600)
def overall(slug, week, superflex):
    """{normalized name+pos key: (overall_rank, std)} off the cross-position board."""
    key = f"ovr_{slug or 'std'}_{week}_{'sf' if superflex else 'flx'}"
    cached = _disk_get(key)
    if cached is None:
        d = _fetch_url(_url_overall(slug, superflex), week)
        rows = [(r.get("player_name"), r.get("player_position_id"),
                 _num(r.get("rank_ecr")), _num(r.get("rank_std")))
                for r in (d or {}).get("players", [])]
        cached = _disk_put(key, rows) if rows else rows
    return {(_namekey(n), pos): (e, sd) for n, pos, e, sd in cached}


@S.cache(ttl=3 * 3600)
def by_sleeper_id(slug, week, superflex=False):
    """Index FantasyPros rows onto Sleeper player ids.

    Matched on normalized name + position, with team as the tiebreak when a name
    is ambiguous. FantasyPros publishes no Sleeper id, so this is the join.
    """
    players = S.load_players()
    idx = {}
    for pid, p in players.items():
        pos = p.get("position")
        if pos not in POSITIONS:
            continue
        nm = p.get("full_name") or " ".join(
            filter(None, [p.get("first_name"), p.get("last_name")]))
        key = (_namekey(nm), pos)
        idx.setdefault(key, []).append((pid, (p.get("team") or "").upper()))

    # One board per league: FLX ranks RB/WR/TE against each other, superflex (OP)
    # adds QBs. A QB has no flex rank in a 1QB league and that is correct — you
    # never start him in a flex slot there, so there is nothing to compare against.
    ovr = overall(slug, week, superflex)

    out, unmatched = {}, []
    for pos, rows in rankings(slug, week).items():
        for r in rows:
            key = (_namekey(r.get("player_name")), pos)
            cands = idx.get(key) or []
            if not cands:
                unmatched.append(r.get("player_name"))
                continue
            team = (r.get("player_team_id") or "").upper()
            pid = next((c[0] for c in cands if c[1] == team), cands[0][0])
            out[pid] = {
                "pos_rank": r.get("pos_rank"),
                "ecr": _num(r.get("rank_ecr")),
                "best": _num(r.get("rank_min")),
                "worst": _num(r.get("rank_max")),
                "avg": _num(r.get("rank_ave")),
                "std": _num(r.get("rank_std")),
                "grade": r.get("start_sit_grade"),
                "opp": r.get("player_opponent"),
                "owned": _num(r.get("player_owned_avg")),
                "team": team,
                "pos": pos,
                "name": r.get("player_name"),
            }
            o = ovr.get((_namekey(r.get("player_name")), pos))
            out[pid]["overall"] = o[0] if o else None
            out[pid]["overall_std"] = o[1] if o else None
    return {"by_id": out, "unmatched": unmatched}
