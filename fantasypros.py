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

REDISTRIBUTION: reading this for your own dashboard is not the same as serving
it from a public URL — that republishes their product. ENABLE_FP is the gate:
leave it on locally, off in a public deployment, where everything degrades
gracefully to Sleeper projections.
"""
import re
import json
import time
import requests

import sleeper as S

ENABLE_FP = True                      # off in a public deploy (see module docstring)

BASE = "https://www.fantasypros.com/nfl/rankings"
CRAWL_DELAY = 5                       # seconds, per their robots.txt
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
_ECR_RE = re.compile(r"var\s+ecrData\s*=\s*(\{.*?\});\s*\n", re.S)

POSITIONS = ("QB", "RB", "WR", "TE")
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


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


def _fetch_url(url, week):
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
    out = {}
    for i, pos in enumerate(POSITIONS):
        if i:
            time.sleep(CRAWL_DELAY)            # honour robots.txt
        d = _fetch(pos, slug, week)
        if not d:
            continue
        rows = d.get("players") or []
        if rows:
            out[pos] = rows
    return out


@S.cache(ttl=3 * 3600)
def overall(slug, week, superflex):
    """{normalized name+pos key: (overall_rank, std)} off the cross-position board."""
    d = _fetch_url(_url_overall(slug, superflex), week)
    out = {}
    for r in (d or {}).get("players", []):
        key = (_namekey(r.get("player_name")), r.get("player_position_id"))
        out[key] = (_num(r.get("rank_ecr")), _num(r.get("rank_std")))
    return out


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

    time.sleep(CRAWL_DELAY)
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
