"""Decision engine: optimal lineups, start/sit deltas, waiver targets, and
win-win trade ideas — built on top of the Valuer (proxy now, external later).
Everything returns plain dicts/lists so the UI stays dumb."""
import math
from values import Valuer, pinfo, FLEX_ELIG, BENCH_SLOTS, SKILL


# ── lineup optimization ───────────────────────────────────────────────────────
def _startable_slots(roster_positions):
    return [s for s in roster_positions if s not in BENCH_SLOTS]


def optimal_lineup(pids, roster_positions, players, score_fn):
    """Greedy optimal: fill most-restrictive slots first with the highest scorer.

    Returns (lineup, bench) where lineup is [(slot, pid)] in the LEAGUE's slot
    order — the same order as Sleeper's `starters` array — so callers can tell
    which slot a change actually lands in. Fill order stays most-restrictive-first
    (QB before FLEX) so a flex slot never steals a player a dedicated slot needs.
    """
    slots = _startable_slots(roster_positions)
    fill_order = sorted(range(len(slots)),
                        key=lambda i: len(FLEX_ELIG.get(slots[i], {"?"})))
    avail = sorted([str(p) for p in pids], key=score_fn, reverse=True)
    used, filled = set(), {}
    for i in fill_order:
        elig = FLEX_ELIG.get(slots[i], set())
        for pid in avail:
            if pid in used:
                continue
            if pinfo(pid, players)["pos"] in elig:
                filled[i] = pid
                used.add(pid)
                break
    lineup = [(slots[i], filled.get(i)) for i in range(len(slots))]
    bench = [p for p in avail if p not in used]
    return lineup, bench


# ── start / sit ───────────────────────────────────────────────────────────────
def start_sit(ctx, valuer, players, alt_tol=1.5, locked=None):
    """Compare the current starters to the optimal lineup and surface swaps.

    Swaps are paired BY SLOT, not by raw score: a bench player is only ever
    suggested against a starter whose slot he's actually eligible to fill, so a
    QB never shows up as a swap for an RB. Where two bench options are within a
    hair of each other, both are offered ("start B or C over A") — that call is
    usually matchup or gut, not math. Closeness is measured on the blended score
    (projection + consensus), not projection alone, so a player the experts like
    far more can surface even when he projects slightly lower.
    """
    me = ctx["my_roster"]
    if not me:
        return None
    locked = locked or set()

    def played(pid):
        """His NFL game has kicked off — the slot is decided either way."""
        return (pinfo(pid, players).get("team") or "") in locked

    pids = me["players"]
    lineup, bench = optimal_lineup(pids, ctx["roster_positions"], players, valuer.start_score)
    optimal_ids = {pid for _, pid in lineup if pid}
    starters = [str(p) if p and str(p) != "0" else None for p in me["starters"]]
    current = {p for p in starters if p}

    def row(pid, slot=None):
        pi = pinfo(pid, players)
        fp = valuer.fp(pid) or {}
        return {**pi, "slot": slot, "pts": round(valuer.points(pid), 1),
                "val": round(valuer.value(pid), 1), "score": round(valuer.start_score(pid), 2),
                "pos_rank": fp.get("pos_rank"), "ecr": fp.get("ecr"), "std": fp.get("std"),
                "overall": fp.get("overall"),
                "grade": fp.get("grade"), "opp": fp.get("opp")}

    lineup_rows = [row(pid, slot) for slot, pid in lineup if pid]
    bench_rows = [row(pid) for pid in bench if pinfo(pid, players)["pos"] in SKILL]

    incoming = optimal_ids - current
    outgoing = set(current - optimal_ids)

    swaps = []
    for i, (slot, pid) in enumerate(lineup):
        if not pid or pid not in incoming:
            continue
        if played(pid):
            continue                       # cannot start someone already played
        elig = FLEX_ELIG.get(slot, set())
        # prefer the player literally sitting in this slot today; otherwise the
        # weakest benchable starter who could legally occupy it
        cur = starters[i] if i < len(starters) else None
        out = cur if cur in outgoing else None
        if out is None:
            legal = [p for p in outgoing if pinfo(p, players)["pos"] in elig]
            out = min(legal, key=valuer.start_score) if legal else None
        if out is None or played(out):
            continue                       # his game is done; benching him is moot
        outgoing.discard(out)

        best_pts = valuer.points(pid)
        best_score = valuer.start_score(pid)
        alts = []
        if best_score > 0:
            band = max(alt_tol, best_score * 0.08)
            alts = [b for b in bench
                    if b != pid and b != out and not played(b)
                    and pinfo(b, players)["pos"] in elig
                    and abs(valuer.start_score(b) - best_score) <= band
                    and (valuer.points(b) > 0 or valuer.fp_overall(b))]
            # Projections are level by construction here, so ordering by them is
            # noise. Use the CROSS-POSITION consensus board: for a flex slot the
            # candidates are different positions, and "RB29 vs WR29" compares
            # nothing — one overall board is what actually ranks them.
            alts.sort(key=lambda b: (valuer.fp_overall(b) or 9999,
                                     valuer.fp_pos_rank(b) or 999,
                                     -valuer.points(b)))
        o_in, o_out = valuer.fp_overall(pid), valuer.fp_overall(out)
        swaps.append({"slot": slot,
                      "in": row(pid, slot), "out": row(out, slot),
                      "alts": [row(a, slot) for a in alts[:2]],
                      "confidence": valuer.confidence(pid),
                      # positive = the incoming player is that many spots higher
                      # on the consensus board; gain is the projection difference,
                      # which may be negative when consensus drives the call
                      "rank_delta": round(o_out - o_in) if (o_in and o_out) else None,
                      "gain": round(best_pts - valuer.points(out), 1)})

    swaps.sort(key=lambda x: (x["rank_delta"] or 0, x["gain"]), reverse=True)

    # Close calls: slots where the lineup is already right, but only just. Worth
    # surfacing because "no change needed" and "this was nearly a coin flip" are
    # different answers, and the second one is where a matchup read or late injury
    # news actually changes your mind.
    touched = {x["in"]["id"] for x in swaps} | {x["out"]["id"] for x in swaps}
    close = []
    for slot, pid in lineup:
        if not pid or pid in touched or played(pid):
            continue
        elig = FLEX_ELIG.get(slot, set())
        rivals = [b for b in bench
                  if b not in touched and not played(b)
                  and pinfo(b, players)["pos"] in elig
                  and valuer.start_score(b) > 0]
        if not rivals:
            continue
        best = max(rivals, key=valuer.start_score)
        held, pushed = valuer.start_score(pid), valuer.start_score(best)
        band = max(alt_tol, held * 0.08)
        if 0 <= held - pushed <= band:
            close.append({"slot": slot,
                          "starter": row(pid, slot), "challenger": row(best, slot),
                          "margin": round(held - pushed, 2)})
    close.sort(key=lambda c: c["margin"])
    return {
        "lineup": lineup_rows,
        "bench": sorted(bench_rows, key=lambda r: r["score"], reverse=True),
        "swaps": swaps,
        "close_calls": close,
        "start": [x["in"] for x in swaps],     # kept: flat views still read these
        "sit": [x["out"] for x in swaps],
        "proj_total": round(sum(r["pts"] for r in lineup_rows), 1),
        "have_projections": any(r["pts"] > 0 for r in lineup_rows),
        "set_lineup": bool(current),
    }


# ── waivers ───────────────────────────────────────────────────────────────────
def waiver_targets(ctx, valuer, players, trend_add, limit=12, shortlist=45):
    """Rank free agents by what they would actually do for THIS roster.

    Three signals, in weight order:
      1. Lineup gain — rebuild the optimal lineup with the player added and diff
         the projected total. This is what makes it slot-aware: a WR4 who can
         slide into FLEX scores real points, a QB2 in a 1QB league scores zero,
         and the comparison is against your own bench rather than the league.
      2. Positional need — how far this roster sits below league average at the
         player's position (the "weak at QB" signal).
      3. Trending adds — buzz breaks ties, it never leads.

    Scoring the exact lineup gain means rebuilding a lineup per candidate, so the
    pool is cheaply prefiltered to `shortlist` before the expensive pass.
    """
    rostered = set()
    for t in ctx["teams"]:
        rostered.update(str(p) for p in t["players"])
    trend = {str(t["player_id"]): t.get("count", 0) for t in trend_add}

    teams, avg = positional_strength(ctx, valuer, players)
    mine = ctx["my_roster"]
    my_str = teams[mine["roster_id"]]["strength"] if mine else {}
    need = {}
    for pos in ("QB", "RB", "WR", "TE"):
        a = avg.get(pos, 0)
        raw = max(0.0, (a - my_str.get(pos, 0)) / a) if a else 0.0
        need[pos] = round(min(raw, 0.60), 2)     # clamped: a bare position shouldn't
                                                 # outrank every real upgrade elsewhere

    my_pids = [str(p) for p in mine["players"]] if mine else []
    rpos = ctx["roster_positions"]

    def lineup_pts(pids):
        lu, _ = optimal_lineup(pids, rpos, players, valuer.start_score)
        return sum(valuer.points(pid) for _, pid in lu if pid)

    base = lineup_pts(my_pids) if my_pids else 0.0

    # what each position would actually be replacing on my bench
    started = set()
    if my_pids:
        lu, _ = optimal_lineup(my_pids, rpos, players, valuer.start_score)
        started = {pid for _, pid in lu if pid}
    bench_bar = {}
    for pid in my_pids:
        if pid in started:
            continue
        pos = pinfo(pid, players)["pos"]
        bench_bar[pos] = max(bench_bar.get(pos, 0.0), valuer.points(pid))

    # The weakest body on the bench is what an add would actually replace. A
    # strongly-ranked free agent is worth taking even when he doesn't crack the
    # lineup, provided someone worse is occupying a roster spot. On an optimized
    # roster this term is ~0 and fewer targets surface, which is correct.
    droppable = None
    for pid in my_pids:
        if pid in started or pinfo(pid, players)["pos"] not in SKILL:
            continue
        if droppable is None or valuer.start_score(pid) < valuer.start_score(droppable):
            droppable = pid
    drop_bar = valuer.start_score(droppable) if droppable else 0.0
    drop_name = pinfo(droppable, players)["name"] if droppable else None

    # ── stage 1: cheap prefilter over every free agent ────────────────────────
    cands = []
    for pid, p in players.items():
        if pid in rostered:
            continue
        pos = p.get("position")
        if pos not in SKILL:
            continue
        if (p.get("team") or "FA") == "FA":                      # retired / no NFL team
            continue
        val = valuer.value(pid)
        buzz = trend.get(pid, 0)
        pts = valuer.points(pid)
        if val <= 0 and buzz == 0 and pts <= 0:
            continue
        pi = pinfo(pid, players)
        fp = valuer.fp(pid) or {}
        cands.append({**pi, "val": round(val, 1), "buzz": buzz, "pts": round(pts, 1),
                      "pos_rank": fp.get("pos_rank"), "ecr": fp.get("ecr"),
                      "std": fp.get("std"), "grade": fp.get("grade"),
                      "pre": val + min(buzz / 500.0, 40) + pts * 1.5})
    cands.sort(key=lambda c: c["pre"], reverse=True)

    # ── stage 2: exact lineup gain for the shortlist ──────────────────────────
    out = []
    for c in cands[:shortlist]:
        gain = round(max(0.0, lineup_pts(my_pids + [c["id"]]) - base), 1) if my_pids else 0.0
        nd = need.get(c["pos"], 0.0)
        bench_delta = round(c["pts"] - bench_bar.get(c["pos"], 0.0), 1)
        buzz_term = 4.0 * math.log10(1 + c["buzz"] / 50.0) if c["buzz"] else 0.0
        c["gain"] = gain
        c["need"] = nd
        c["bench_delta"] = bench_delta
        # expert consensus: a WR30 sitting on the wire is a signal a projection
        # can miss entirely, so a strong positional rank earns weight
        pr = valuer.fp_pos_rank(c["id"])
        fp_bonus = max(0.0, 60 - pr) * 0.25 if pr else 0.0
        c["fp_bonus"] = round(fp_bonus, 1)
        # straight upgrade on the worst body you're rostering
        drop_delta = round(valuer.start_score(c["id"]) - drop_bar, 1) if droppable else 0.0
        c["drop_delta"] = drop_delta
        c["drop_name"] = drop_name
        c["score"] = round(gain * 8 + max(0.0, bench_delta) * 3 + c["pts"] * 1.0
                           + nd * 20 + c["val"] * 0.30 + buzz_term + fp_bonus
                           + max(0.0, drop_delta) * 2.0, 1)

        why = []
        if gain > 0:
            why.append(f"+{gain:.1f} proj to your lineup")
        elif bench_delta > 0:
            why.append(f"+{bench_delta:.1f} over your best bench {c['pos']}")
        elif c["pts"] > 0:
            why.append(f"{c['pts']:.1f} proj — your starters project higher")
        if nd >= 0.50:
            why.append(f"you have almost nothing at {c['pos']}")
        elif nd >= 0.10:
            why.append(f"{nd*100:.0f}% below league avg at {c['pos']}")
        if c.get("pos_rank"):
            why.append(f"experts have him {c['pos_rank']} this week")
        if drop_delta > 1.0 and drop_name:
            why.append(f"clear upgrade on {drop_name}, your weakest bench spot")
        if c["buzz"]:
            why.append(f"+{c['buzz']:,} adds this week")
        c["why"] = " · ".join(why)
        c.pop("pre", None)
        out.append(c)

    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:limit]


# ── this week's matchups ──────────────────────────────────────────────────────
WEEK_SD = 27.0          # typical spread of a single team's weekly score


def week_matchups(ctx, valuer, players, rows):
    """Pair up this week's matchups and price both sides, live-aware.

    Before kickoff each side is just its projected starters. Once points are on
    the board the expected final becomes what's already scored plus the
    projection of starters yet to score — so refreshing mid-slate reflects both
    the games in progress and any projection changes for the later window (a
    player ruled out sees his projection collapse, which flows straight through).

    Known limitation: a starter who has played and genuinely scored zero is
    indistinguishable from one who hasn't kicked off, so his projection is still
    counted. That biases a live number slightly high, never low.

    Win probability treats the remaining points as normal around that expectation
    with a ~27 point spread per team, shrinking as the slate completes: a 10
    point edge before kickoff is only about 60/40, but the same edge with one
    player left is close to decided.
    """
    by_team = {t["roster_id"]: t for t in ctx["teams"]}
    groups = {}
    for r in rows:
        mid = r.get("matchup_id")
        if mid is None:
            continue
        groups.setdefault(mid, []).append(r)

    out = []
    for mid in sorted(groups):
        pair = groups[mid]
        if len(pair) != 2:
            continue                       # bye weeks / odd league sizes
        sides = []
        for r in pair:
            starters = [str(x) for x in (r.get("starters") or []) if x and str(x) != "0"]
            spts = r.get("starters_points") or []
            live = round(r.get("points") or 0, 1)
            proj_all = sum(valuer.points(x) for x in starters)
            remaining, yet = 0.0, 0
            for i, pid in enumerate(starters):
                scored = spts[i] if i < len(spts) else 0
                if not scored:
                    remaining += valuer.points(pid)
                    yet += 1
            tm = by_team.get(r["roster_id"], {})
            sides.append({"rid": r["roster_id"], "name": tm.get("name", "?"),
                          "is_mine": bool(tm.get("is_mine")),
                          "proj": round(proj_all, 1), "live": live,
                          "yet_to_play": yet,
                          "expected": round(live + remaining, 1)})
        a, b = sides
        started = (a["live"] > 0 or b["live"] > 0)
        # uncertainty shrinks with the share of the lineup still to play
        share = max(a["yet_to_play"], b["yet_to_play"]) / max(
            1, max(len(x.get("starters") or []) for x in pair))
        spread = WEEK_SD * math.sqrt(2) * max(0.15, share)
        pa = 0.5 * (1 + math.erf((a["expected"] - b["expected"]) / (spread * math.sqrt(2))))
        a["win"], b["win"] = round(pa * 100), round((1 - pa) * 100)
        out.append({"a": a, "b": b, "mine": a["is_mine"] or b["is_mine"],
                    "live": started})
    return out


# ── projected standings & rookie picks ────────────────────────────────────────
def power_rankings(ctx, valuer, players, ros=None):
    """Project where each team finishes.

    Three inputs, because no one of them is enough on its own:

      rest-of-season points  what the roster is actually projected to score from
                             here, over the startable lineup — the most direct
                             read on results, and the reason a stacked bench does
                             not inflate anyone
      roster asset value     positional depth, which carries injury tolerance and
                             the long view a single week's projection misses
      actual record          noise in September and signal in November, so its
                             weight grows with games played rather than being
                             fixed

    This is NOT a season simulation: no schedule, no head-to-head, no Monte
    Carlo. Two teams with identical rosters rank identically even if one drew a
    far harder slate. Returns rows sorted best -> worst with a proj_rank.
    """
    teams, _ = positional_strength(ctx, valuer, players)
    rows = []
    for t in ctx["teams"]:
        rid = t["roster_id"]
        g = t["wins"] + t["losses"] + t["ties"]
        pids = [str(p) for p in t["players"]]
        ros_pts = 0.0
        if ros:
            lu, _ = optimal_lineup(pids, ctx["roster_positions"], players,
                                   lambda x: ros.get(str(x), 0.0))
            ros_pts = sum(ros.get(str(pid), 0.0) for _, pid in lu if pid)
        rows.append({"rid": rid, "name": t["name"], "is_mine": t["is_mine"],
                     "strength": teams[rid]["total"], "ros": ros_pts, "games": g,
                     "winpct": ((t["wins"] + 0.5 * t["ties"]) / g) if g else 0.5,
                     "record": f'{t["wins"]}-{t["losses"]}'
                               + (f'-{t["ties"]}' if t["ties"] else "")})
    top_str = max((r["strength"] for r in rows), default=0) or 1
    top_ros = max((r["ros"] for r in rows), default=0) or 1
    played = max((r["games"] for r in rows), default=0)
    w = min(played / 10.0, 0.65)              # record tops out at 65% of the blend
    for r in rows:
        roster = ((0.6 * (r["ros"] / top_ros) + 0.4 * (r["strength"] / top_str))
                  if ros else (r["strength"] / top_str))
        r["score"] = round((1 - w) * roster + w * r["winpct"], 4)
    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["proj_rank"] = i
    return rows, round(w, 2)


def pick_tier(proj_rank, num_teams):
    """Early / Mid / Late for a pick, from its original owner's projected finish.

    Draft order is reverse standings: the projected worst team picks first, so
    ITS pick is the Early (most valuable) one. Split into thirds.
    """
    if not num_teams:
        return None
    from_bottom = num_teams - proj_rank + 1          # 1 = projected worst team
    third = max(1, round(num_teams / 3))
    if from_bottom <= third:
        return "Early"
    if from_bottom <= 2 * third:
        return "Mid"
    return "Late"


def pick_inventory(ctx, seasons):
    """Who currently holds which future rookie pick.

    Every roster starts owning its own pick in every round of every season; the
    traded_picks feed then reassigns the ones that moved. A pick's VALUE tracks
    its original owner (that's whose finish sets the draft slot), while its
    OWNER is who can trade it.
    """
    rounds = range(1, (ctx.get("draft_rounds") or 4) + 1)
    holder = {}
    for t in ctx["teams"]:
        for yr in seasons:
            for rnd in rounds:
                holder[(yr, rnd, t["roster_id"])] = t["roster_id"]
    for tp in ctx.get("traded_picks") or []:
        try:
            key = (int(tp["season"]), int(tp["round"]), int(tp["roster_id"]))
            new_owner = int(tp["owner_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if key in holder:
            holder[key] = new_owner
    inv = {}
    for (yr, rnd, original), owner in holder.items():
        inv.setdefault(owner, []).append({"season": yr, "round": rnd, "original_rid": original})
    for rows in inv.values():
        rows.sort(key=lambda r: (r["season"], r["round"]))
    return inv


# ── team strength (for trades) ────────────────────────────────────────────────
def starting_capacity(roster_positions):
    """(dedicated slots, flex-contested slots) per position.

    The two are not the same thing and cannot be added. A dedicated slot is a
    guaranteed start; a flex is contested — the flex spots compete across running
    back, receiver and tight end, so granting each of them a full extra slot
    counted the same seat three times.
    """
    ded = dict(_dedicated_slots(roster_positions))
    flex = {}
    for slot in _startable_slots(roster_positions):
        elig = FLEX_ELIG.get(slot, set())
        if len(elig) <= 1:
            continue
        if "QB" in elig:
            # Superflex. Nominally contested, in practice never: a quarterback
            # outscores every flex alternative, so that seat is a second starting
            # quarterback and counts as one. The other positions it nominally
            # accepts stay contested, because they are.
            ded["QB"] = ded.get("QB", 0) + 1
            for pos in elig - {"QB"}:
                flex[pos] = min(flex.get(pos, 0) + 1, 1)
        else:
            for pos in elig:
                flex[pos] = min(flex.get(pos, 0) + 1, 1)      # at most one
    return ded, flex


DEPTH_DECAY = 0.35          # each body beyond a startable slot
FLEX_WEIGHT = 0.6           # a flex seat is contested, not guaranteed


def positional_strength(ctx, valuer, players):
    """Per-team value by position, weighted by what the league actually starts.

    Summing the top three flat treats depth as if it plays. At quarterback and
    tight end in a one-slot league it does not: a team with three middling
    quarterbacks outranked a team with an elite one, which is backwards. Players
    within the startable count carry full weight and everyone behind them decays
    sharply, so the starter dominates where there is only one slot, while running
    back and receiver still reward the depth a flex can use.
    """
    core = ["QB", "RB", "WR", "TE"]
    ded, flex = starting_capacity(ctx["roster_positions"])
    teams = {}
    for t in ctx["teams"]:
        by = {pos: [] for pos in core}
        for pid in t["players"]:
            pos = pinfo(pid, players)["pos"]
            if pos in by:
                by[pos].append(valuer.value(pid))
        strength = {}
        for pos, vals in by.items():
            vals.sort(reverse=True)
            n = max(1, ded.get(pos, 1))          # guaranteed starters
            f = flex.get(pos, 0)                 # one contested flex seat at most
            total = 0.0
            for i, val in enumerate(vals[:n + f + 3]):
                if i < n:
                    total += val
                elif i < n + f:
                    total += val * FLEX_WEIGHT
                else:
                    total += val * (DEPTH_DECAY ** (i - n - f + 1))
            strength[pos] = round(total, 1)
        teams[t["roster_id"]] = {"name": t["name"], "is_mine": t["is_mine"],
                                 "strength": strength, "total": round(sum(strength.values()), 1)}
    avg = {pos: round(sum(tm["strength"][pos] for tm in teams.values()) / max(len(teams), 1), 1)
           for pos in core}
    return teams, avg


# ── win-win trades ────────────────────────────────────────────────────────────
def _dedicated_slots(roster_positions):
    """Starting slots that accept exactly one position (QB/RB/WR/TE counts)."""
    out = {}
    for slot in _startable_slots(roster_positions):
        elig = FLEX_ELIG.get(slot, set())
        if len(elig) == 1:
            pos = next(iter(elig))
            out[pos] = out.get(pos, 0) + 1
    return out


def _replacement(ctx, valuer, players, rid):
    """Value of the best player at each position who is NOT in the optimal lineup.

    Derived from the lineup itself rather than a slot count, so FLEX, REC_FLEX and
    SUPER_FLEX are handled correctly: in superflex your QB2 is a starter and its
    replacement is your QB3, while in a 1QB league that same QB2 IS the
    replacement. That distinction is what makes package deals judgeable — trading
    depth that never starts costs you close to nothing.
    """
    rt = next(t for t in ctx["teams"] if t["roster_id"] == rid)
    pids = [str(p) for p in rt["players"]]
    _, bench = optimal_lineup(pids, ctx["roster_positions"], players, valuer.value)
    repl = {}
    for pid in bench:
        pos = pinfo(pid, players)["pos"]
        repl[pos] = max(repl.get(pos, 0.0), valuer.value(pid))
    return repl


def _lineup_value_raw(pids, ctx, valuer, players):
    """The same startable lineup, totalled in FantasyCalc's own units.

    _lineup_value() works on the internal 0-100 scale, which is right for the
    engine and meaningless to read: a "+1.3" next to player chips reading 3,848
    places nothing. This returns the number in the units already on screen, so a
    lineup change is directly comparable to the values of the players causing it.
    """
    lu, _ = optimal_lineup(pids, ctx["roster_positions"], players, valuer.value)
    return sum(valuer.raw_value(pid) for _, pid in lu if pid)


def lineup_points_over_weeks(pids, ctx, players, weekly_maps):
    """Points from re-picking the best lineup EACH week and summing.

    This is what "rest of season" should mean: the answer to a trade is the net
    of what you gain and what the man replacing your outgoing player scores, week
    by week. Summing projections first and choosing one lineup gets byes wrong,
    because a player projected zero that week still occupies his slot.
    """
    total = 0.0
    for wk in weekly_maps:
        lu, _ = optimal_lineup(pids, ctx["roster_positions"], players,
                               lambda x: wk.get(str(x), 0.0))
        total += sum(wk.get(str(pid), 0.0) for _, pid in lu if pid)
    return total



def _ros_delta(before, after, ctx, players, weekly_maps):
    """Rest-of-season points change, net of whoever replaces the outgoing player.

    Uses the per-week maps rather than a season total, so a starter on his bye
    does not hold his slot while his replacement scores nothing.
    """
    if not weekly_maps:
        return None
    return round(lineup_points_over_weeks(after, ctx, players, weekly_maps)
                 - lineup_points_over_weeks(before, ctx, players, weekly_maps), 1)

def _lineup_points(pids, ctx, valuer, players):
    """Projected points of the best startable lineup — the weekly-score view of a
    trade, alongside the asset-value view in _lineup_value()."""
    lu, _ = optimal_lineup(pids, ctx["roster_positions"], players, valuer.start_score)
    return sum(valuer.points(pid) for _, pid in lu if pid)


def _lineup_value(pids, ctx, valuer, players):
    """Total asset value of the best startable lineup these players can field.

    This is the roster-construction test: it prices a deal by what it does to the
    lineup you can actually start, so a trade that stacks a position you can only
    start one of, or that leaves a slot unfillable, shows up as a loss.
    """
    lu, _ = optimal_lineup(pids, ctx["roster_positions"], players, valuer.value)
    return sum(valuer.value(pid) for _, pid in lu if pid)


def trade_edge(idea):
    """How good a deal is, in one number.

    Lineup impact cannot be the primary key. A pick trade changes nothing this
    Sunday by definition, and a bad team dumping a bench player for a first is
    still its best available move — sorting on lineup delta buries exactly the
    trades a rebuild should be making. So value over replacement leads, this
    week's points and startable roster value contribute when they exist, and
    partner fit is added because it is a different question from fairness:
    fairness asks whether a deal is even, fit asks whether they'll say yes. A
    rival thin at the position you're sending will tolerate a worse price.
    """
    # A pick counts at full value in my_net because nothing replaces it, which
    # let pick returns crowd out real players in the neutral ranking. Charge a
    # modest amount for anything that cannot take the field; the tanking view is
    # where picks are supposed to win.
    picks_in = sum(1 for r in idea.get("gets", []) if r.get("pos") == "PICK")
    return round(
        idea["my_net"]
        + max(0.0, idea.get("pts_delta", 0.0)) * 1.5
        + max(0.0, idea.get("lineup_delta", 0.0)) * 0.5
        + idea.get("partner_fit", 0.0) * 12.0
        - picks_in * 9.0, 2)


def _surplus_over_replacement(rows, repl):
    """Sum of each player's value above his position's replacement level.

    Units are the Valuer's 0-100 asset-value scale (normalized FantasyCalc) —
    NOT fantasy points, and not season-long. The only points figure anywhere in
    the app is Sleeper's weekly projection.
    """
    return sum(max(0.0, r["val"] - repl.get(r["pos"], 0.0)) for r in rows)


# FantasyCalc's published "waiver adjustment" for uneven trades. Since this app
# prices players with FantasyCalc's values, it uses FantasyCalc's own constants
# rather than a curve of our own invention. Their model: the side receiving MORE
# bodies has to cut someone to fit them, so each extra body is worth only a
# capped fraction of face value, and that difference is credited to the side
# receiving FEWER players. Net effect: consolidating means paying a premium.
# Source: fantasycalc.com/frequently-asked-questions#waiver-adjustment
FC_ADJ = {
    "dynasty": {"pct": 0.6982, "cap": 753, "step": 0.23, "flat": 0},
    "redraft": {"pct": 0.42, "cap": 550, "step": 0.0, "flat": 200},
}


def package_adjustment(gives, gets, dynasty):
    """Value credited to each side for an uneven package, on FantasyCalc's scale.

    Returns (adj_to_gives, adj_to_gets). The k lowest-valued assets on the
    longer side each contribute min(value*pct, cap + i*step); the total goes to
    the shorter side.
    """
    ng, nt = len(gives), len(gets)
    if ng == nt or not gives or not gets:
        return 0.0, 0.0
    c = FC_ADJ["dynasty"] if dynasty else FC_ADJ["redraft"]
    longer = gives if ng > nt else gets
    k = abs(ng - nt)
    # Only PLAYERS cost a roster spot. A draft pick is not a body — taking two
    # picks back forces nobody to cut anyone until the draft — so charging for
    # them made a 26% overpay in picks read as 95% fair.
    bodies = sorted(r.get("raw", 0) for r in longer if r.get("pos") != "PICK")
    extras = bodies[:k]
    adj = sum(min(vv * c["pct"], c["cap"] + i * c["step"]) for i, vv in enumerate(extras))
    adj += max(0, (len(extras) - 1) * c["flat"])
    return (adj, 0.0) if ng < nt else (0.0, adj)


TRADE_SHAPES = {(1, 1), (2, 1), (2, 2)}      # (players out, players in)
MAX_PER_PARTNER = 2                          # one rival shouldn't fill the board


def trade_ideas(ctx, valuer, players, max_ideas=6, tolerance=0.20,
                weekly_maps=None):
    """At least one idea for every league that allows trading.

    The strict pass demands a lot: a partner rich exactly where you're thin and
    thin where you're deep, values inside 20%, and both sides ahead on value over
    replacement. On a balanced roster in a shallow league nothing clears that, and
    an empty board is not a useful answer. So the search runs in passes, each
    loosening one constraint, and stops at the first that produces something:

      1. strict — the mirror-image partner described above
      2. wider  — 30% value band, partner screen relaxed
      3. open   — drop the positional mirror entirely; any fair deal that helps
                  both rosters counts
      4. wider  — same, with a 40% value band
      5. picks  — for a rebuilding roster, sell a win-now piece for draft capital

    Later passes are looser, not laxer: fairness and the both-sides-benefit test
    hold throughout. Only the search for a partner widens.
    """
    passes = [
        dict(tolerance=tolerance, mirror=True, need_mult=1.0, sur_mult=1.0),
        dict(tolerance=0.30, mirror=True, need_mult=0.95, sur_mult=1.15),
        dict(tolerance=0.30, mirror=False, need_mult=0.0, sur_mult=9.0),
        dict(tolerance=0.40, mirror=False, need_mult=0.0, sur_mult=9.0),
    ]
    found = []
    for kw in passes:
        found = _trade_search(ctx, valuer, players, max_ideas * 3,
                              weekly_maps=weekly_maps, **kw)
        if found:
            break
    return _diversify(found + _pick_ideas(ctx, valuer, players,
                                          weekly_maps=weekly_maps), max_ideas)


def _diversify(ideas, max_ideas):
    """Make sure the board shows more than one kind of deal.

    Ranking alone buries the interesting ones: widening the 1-for-1 search made
    it generate so many qualifying candidates that packages and pick trades never
    reached the board at all. So the best example of each distinct shape is
    seated first, and only then are the remaining slots filled by rank.
    """
    if not ideas:
        return []
    order = sorted(ideas, key=lambda x: (trade_edge(x), x["fairness"]), reverse=True)
    # A deal can be perfectly fair and still pointless — swapping a first for a
    # replacement-level body prices out fine and gains you nothing. The floor sits
    # above zero rather than at it: a trade worth a fraction of a point is noise
    # on a board meant to be scanned, and it crowds out the ones worth reading.
    # A league is never left empty, though — the best idea always shows.
    MIN_EDGE = 2.0
    worth_it = [i for i in order if trade_edge(i) >= MIN_EDGE]
    order = worth_it if worth_it else order[:1]
    picked, seen_shapes = [], set()
    for i in order:                       # one of each shape first
        if i["shape"] not in seen_shapes:
            seen_shapes.add(i["shape"])
            picked.append(i)
    rest = [i for i in order if i not in picked]
    picked = picked[:max_ideas] + rest[:max(0, max_ideas - len(picked))]
    return sorted(picked, key=lambda x: (trade_edge(x), x["fairness"]),
                  reverse=True)[:max_ideas]


def _trade_search(ctx, valuer, players, max_ideas=6, tolerance=0.20,
                  mirror=True, need_mult=1.0, sur_mult=1.0, weekly_maps=None):
    """One pass of the trade search. See trade_ideas() for how passes escalate.

    Shapes are deliberately limited to TRADE_SHAPES — 1-for-1, 2-for-1
    (consolidation) and 2-for-2. Bigger packages are harder to get accepted and
    much harder to price honestly, so they're out of scope. Every shape is judged on
    value over replacement for BOTH rosters, not on raw totals — two bench pieces
    for one starter can be a genuine win for both sides even when the raw values
    look lopsided, because the depth being sent out was never in a lineup.
    """
    if ctx["trades_disabled"] or not ctx["my_roster"]:
        return []
    core = ["QB", "RB", "WR", "TE"]
    teams, avg = positional_strength(ctx, valuer, players)
    mine = ctx["my_roster"]
    my_rid = mine["roster_id"]
    my_str = teams[my_rid]["strength"]
    dedicated = _dedicated_slots(ctx["roster_positions"])
    my_repl = _replacement(ctx, valuer, players, my_rid)

    my_pids = [str(p) for p in mine["players"]]
    my_base_lineup = _lineup_value(my_pids, ctx, valuer, players)
    my_base_raw = _lineup_value_raw(my_pids, ctx, valuer, players)
    my_base_points = _lineup_points(my_pids, ctx, valuer, players)
    # who actually starts for me — a package should send players who don't
    _my_lu, _ = optimal_lineup(my_pids, ctx["roster_positions"], players, valuer.value)
    my_starters = {pid for _, pid in _my_lu if pid}

    surplus = sorted([p for p in core if my_str[p] > avg[p] * 1.08],
                     key=lambda p: my_str[p] - avg[p], reverse=True)
    needs = sorted([p for p in core if my_str[p] < avg[p] * 0.98],
                   key=lambda p: avg[p] - my_str[p], reverse=True)
    stacked = not needs           # above average everywhere: no hole to fill
    if not needs:
        needs = sorted(core, key=lambda p: my_str[p] - avg[p])[:2]
    if not surplus or not needs:
        return []
    # A stacked roster isn't filling holes, it's consolidating depth into quality,
    # so partners only need to be respectable at the target rather than rich in it.
    need_bar = (1.00 if stacked else 1.05) * need_mult
    sur_bar = (1.12 if stacked else 1.02) * sur_mult
    if not mirror:                       # open pass: any partner is a candidate
        need_bar, sur_bar = 0.0, 99.0

    def players_at(rid, pos):
        rt = next(t for t in ctx["teams"] if t["roster_id"] == rid)
        rows = [{**pinfo(pid, players), "val": valuer.value(pid),
                 "raw": valuer.raw_value(pid) if hasattr(valuer, "raw_value") else 0}
                for pid in rt["players"]]
        return sorted([r for r in rows if r["pos"] == pos and r["val"] > 0],
                      key=lambda r: r["val"], reverse=True)

    ideas = []
    for rid, tm in teams.items():
        if rid == my_rid:
            continue
        their_repl = _replacement(ctx, valuer, players, rid)
        their_pids = [str(x) for x in
                      next(t for t in ctx["teams"] if t["roster_id"] == rid)["players"]]
        their_base_lineup = _lineup_value(their_pids, ctx, valuer, players)
        their_base_points = _lineup_points(their_pids, ctx, valuer, players)
        for my_need in needs:
            for my_sur in surplus:
                if my_need == my_sur:
                    continue                                   # not a trade, a shuffle
                if tm["strength"][my_need] < avg[my_need] * need_bar:
                    continue                                   # they aren't strong at my need
                if tm["strength"][my_sur] > avg[my_sur] * sur_bar:
                    continue                                   # they don't need my surplus
                give_pool = players_at(my_rid, my_sur)
                get_pool = players_at(rid, my_need)
                if len(give_pool) < 2 or not get_pool:
                    continue
                keep = dedicated.get(my_sur, 1)                 # bodies I must keep

                shapes = []
                # 1-for-1: try each of my non-stud pieces at this position, not
                # only the second-best. With a single candidate there is often no
                # asset on the other roster inside the fairness band, which is
                # what produced empty boards — this widens the search, not the
                # gates. give_pool[0] is never offered: you keep the stud.
                for one in give_pool[1:4]:
                    shapes.append(([one],
                                   [min(get_pool, key=lambda r: abs(r["val"] - one["val"]))]))
                one = give_pool[1]                  # packages build off this one

                # A package should send pieces from DIFFERENT positions — no team
                # wants two TEs when it starts one. Prefer a second piece from
                # another surplus spot; only double up on one position as a last
                # resort, and the partner-lineup test below still has to agree.
                # Consolidation means sending depth that never cracks the lineup,
                # not your second-best player. Building the pair from bench pieces
                # is both more realistic and what makes the deal possible: asking
                # for someone better than your own RB2 rules out almost everything.
                bench_at = lambda pos: [r for r in players_at(my_rid, pos)
                                        if r["id"] not in my_starters]
                depth = bench_at(my_sur)
                for alt in surplus:
                    if alt != my_sur:
                        depth += bench_at(alt)
                depth.sort(key=lambda r: r["val"], reverse=True)
                pair = depth[:2] if len(depth) >= 2 else None

                if pair is not None:
                    one_pkg = pair[0]
                    tot = sum(r["val"] for r in pair)
                    # 2-for-1 consolidation: two pieces for their best at my need
                    stud = min(get_pool, key=lambda r: abs(r["val"] - tot))
                    if stud["val"] > one_pkg["val"] * 1.05:
                        shapes.append((pair, [stud]))
                    # 2-for-2: pull the second piece back from a different position
                    other_needs = [n for n in needs if n != my_need] or [my_need]
                    back_pool = get_pool + players_at(rid, other_needs[0])
                    seen_ids = set()
                    back_pool = [r for r in back_pool
                                 if not (r["id"] in seen_ids or seen_ids.add(r["id"]))]
                    if len(back_pool) >= 2:
                        best2, bestd = None, None
                        for i in range(len(back_pool)):
                            for j in range(i + 1, len(back_pool)):
                                a, b = back_pool[i], back_pool[j]
                                if a["pos"] == b["pos"] and a["pos"] not in ("RB", "WR"):
                                    continue          # two QBs / two TEs: no
                                d = abs(a["val"] + b["val"] - tot)
                                if bestd is None or d < bestd:
                                    bestd, best2 = d, [a, b]
                        if best2:
                            shapes.append((pair, best2))

                for gives, gets in shapes:
                    if (len(gives), len(gets)) not in TRADE_SHAPES:
                        continue
                    gv = sum(r["val"] for r in gives)
                    tv = sum(r["val"] for r in gets)
                    # fairness on FantasyCalc's raw scale plus their uneven-package
                    # adjustment, so a 2-for-1 has to pay the consolidation premium
                    g_raw = sum(r.get("raw", 0) for r in gives)
                    t_raw = sum(r.get("raw", 0) for r in gets)
                    if g_raw and t_raw:
                        ag, at = package_adjustment(gives, gets, ctx["format"] == "dynasty")
                        g_cmp, t_cmp = g_raw + ag, t_raw + at
                    else:
                        g_cmp, t_cmp = gv, tv           # uncovered players: no adjustment
                    if max(g_cmp, t_cmp) == 0 or abs(g_cmp - t_cmp) / max(g_cmp, t_cmp) > tolerance:
                        continue
                    # win-win test on value over replacement, both directions
                    my_net = _surplus_over_replacement(gets, my_repl) - \
                        _surplus_over_replacement(gives, my_repl)
                    their_net = _surplus_over_replacement(gives, their_repl) - \
                        _surplus_over_replacement(gets, their_repl)
                    if my_net <= 0 or their_net <= 0:
                        continue
                    # roster construction: does my actual startable lineup improve?
                    out_ids = {r["id"] for r in gives}
                    after = [x for x in my_pids if x not in out_ids] + [r["id"] for r in gets]
                    lineup_delta = round(
                        _lineup_value(after, ctx, valuer, players) - my_base_lineup, 1)
                    _after_raw = _lineup_value_raw(after, ctx, valuer, players)
                    lineup_delta_raw = round(_after_raw - my_base_raw)
                    # as a share of your own starting lineup, which needs no scale
                    lineup_pct = round(100.0 * (_after_raw - my_base_raw)
                                       / my_base_raw, 1) if my_base_raw else 0.0
                    # weekly scoring outlook, separate from long-term asset value
                    pts_delta = round(
                        _lineup_points(after, ctx, valuer, players) - my_base_points, 1)
                    # ...and a usability test from THEIR side. A consolidating
                    # partner's starting lineup gets WORSE by design (they trade
                    # quality for depth), so requiring it to improve would reject
                    # every package. What actually matters is whether they can USE
                    # every piece: if the second body rides their bench, no one
                    # accepts. This is what rules out "two TEs for a QB".
                    in_ids = {r["id"] for r in gets}
                    their_after = ([x for x in their_pids if x not in in_ids]
                                   + [r["id"] for r in gives])
                    their_lu, _ = optimal_lineup(their_after, ctx["roster_positions"],
                                                 players, valuer.value)
                    their_started = {pid for _, pid in their_lu if pid}
                    their_delta = round(
                        sum(valuer.value(pid) for pid in their_started) - their_base_lineup, 1)
                    _their_base_raw = _lineup_value_raw(their_pids, ctx, valuer, players)
                    _their_after_raw = _lineup_value_raw(their_after, ctx, valuer, players)
                    their_raw_delta = round(_their_after_raw - _their_base_raw)
                    their_lineup_pct = round(100.0 * (_their_after_raw - _their_base_raw)
                                             / _their_base_raw, 1) if _their_base_raw else 0.0
                    their_pts_delta = round(
                        _lineup_points(their_after, ctx, valuer, players)
                        - their_base_points, 1)
                    if len(gives) > 1 and not all(r["id"] in their_started for r in gives):
                        continue
                    # same rule for me when I'm the one taking on more bodies
                    if len(gets) > 1:
                        my_lu, _ = optimal_lineup(after, ctx["roster_positions"],
                                                  players, valuer.value)
                        my_started = {pid for _, pid in my_lu if pid}
                        if not all(r["id"] in my_started for r in gets):
                            continue

                    # how badly the partner needs what I'm sending — they'll
                    # tolerate a worse price at a position they're thin at
                    fit = 0.0
                    for r in gives:
                        a = avg.get(r["pos"], 0)
                        if a:
                            fit = max(fit, min(1.0, max(0.0,
                                      (a - tm["strength"].get(r["pos"], 0)) / a)))
                    shape = f"{len(gives)}-for-{len(gets)}"
                    gnames = " + ".join(r["name"] for r in gives)
                    tnames = " + ".join(r["name"] for r in gets)
                    if len(gives) > len(gets):
                        why = (f"Consolidation: you start {dedicated.get(my_sur, 1)} at {my_sur}, "
                               f"so {gives[-1]['name']} is depth you don't play. "
                               f"Turns it into a starter at {my_need}.")
                    else:
                        why = (f"You're deep at {my_sur} (need {my_need}); "
                               f"{tm['name']} is the mirror.")
                    ideas.append({
                        "partner": tm["name"], "partner_rid": rid,
                        "shape": shape,
                        "gives": gives, "gets": gets,
                        "give": gives[0], "get": gets[0],       # headline pieces
                        "give_raw": sum(r["raw"] for r in gives),
                        "get_raw": sum(r["raw"] for r in gets),
                        "my_net": round(my_net, 1), "their_net": round(their_net, 1),
                        "partner_fit": round(fit, 2),
                        "lineup_delta": lineup_delta, "their_lineup_delta": their_delta,
                        "pts_delta": pts_delta, "their_pts_delta": their_pts_delta,
                        "ros_delta": _ros_delta(my_pids, after, ctx, players, weekly_maps),
                        "their_ros_delta": _ros_delta(their_pids, their_after, ctx,
                                                      players, weekly_maps),
                        "lineup_delta_raw": lineup_delta_raw,
                        "their_lineup_delta_raw": their_raw_delta,
                        "lineup_pct": lineup_pct, "their_lineup_pct": their_lineup_pct,
                        "my_pos_out": my_sur, "my_pos_in": my_need,
                        "fairness": round(100 - abs(g_cmp - t_cmp) / max(g_cmp, t_cmp) * 100, 0),
                        "package_adj": round((ag if g_raw and t_raw else 0)
                                             + (at if g_raw and t_raw else 0), 0),
                        "rationale": f"{why} You send {gnames}, you get {tnames}. "
                                     f"Values within "
                                     f"{abs(g_cmp-t_cmp)/max(g_cmp,t_cmp)*100:.0f}% "
                                     f"after the roster-spot adjustment.",
                    })

    # Variety filter. Four different routes to the same player read as the same
    # trade to a human, so keep only the best offer for each asset acquired, and
    # stop any one partner from filling the whole board.
    seen, headline, per_partner, per_give, uniq = set(), set(), {}, {}, []
    # rank on what the deal actually improves: startable roster value, this
    # week's points, then surplus over replacement and fairness
    for i in sorted(ideas, key=lambda x: (trade_edge(x), x["fairness"]), reverse=True):
        key = (tuple(sorted(r["id"] for r in i["gives"])),
               tuple(sorted(r["id"] for r in i["gets"])))
        if key in seen:
            continue
        head = i["gets"][0]["id"]                  # the main piece coming back
        if head in headline:
            continue
        rid = i["partner_rid"]
        if per_partner.get(rid, 0) >= MAX_PER_PARTNER:
            continue
        # three ways to move the same player reads as one idea, not three
        out_key = i["gives"][0]["id"]
        if per_give.get(out_key, 0) >= MAX_PER_PARTNER:
            continue
        seen.add(key)
        headline.add(head)
        per_partner[rid] = per_partner.get(rid, 0) + 1
        per_give[out_key] = per_give.get(out_key, 0) + 1
        uniq.append(i)
    return uniq[:max_ideas]


def _fit_for(ctx, valuer, players, rid, gives):
    """Partner's positional need for what they're receiving, 0-1. Picks score 0:
    everyone can use a pick, so it says nothing about acceptance."""
    teams, avg = positional_strength(ctx, valuer, players)
    strength = teams.get(rid, {}).get("strength", {})
    fit = 0.0
    for r in gives:
        a = avg.get(r["pos"], 0)
        if a and r["pos"] != "PICK":
            fit = max(fit, min(1.0, max(0.0, (a - strength.get(r["pos"], 0)) / a)))
    return round(fit, 2)


def _pick_ideas(ctx, valuer, players, max_ideas=3, tolerance=0.30, ros=None,
                weekly_maps=None):
    """Trade draft capital, in whichever direction this roster should be moving.

    Projected finish decides the side you're on, because that is what a pick is
    worth to each team. A contender's own first is a late pick and a year away;
    the talent it buys plays this season. A rebuilding roster wants the mirror.

      top third    -> give picks, get talent  (buy now, the pick is cheap to you)
      bottom third -> give win-now talent, get picks (sell, it's worth more to them)
      middle       -> nothing; no clear direction to lean

    Picks are priced by their ORIGINAL owner's projected finish, so a cellar
    team's first is valued as the early pick it will become.
    """
    if ctx["format"] != "dynasty" or ctx["trades_disabled"] or not ctx["my_roster"]:
        return []
    if not getattr(valuer, "pick_scale", None) or not valuer.pick_scale():
        return []

    pranks, _ = power_rankings(ctx, valuer, players, ros=ros)
    n_teams = ctx["num_teams"] or len(pranks)
    rank_of = {r["rid"]: r["proj_rank"] for r in pranks}
    name_of = {t["roster_id"]: t["name"] for t in ctx["teams"]}
    my_rid = ctx["my_roster"]["roster_id"]
    my_rank = rank_of.get(my_rid)
    if not my_rank:
        return []
    contending = my_rank <= n_teams / 3.0
    rebuilding = my_rank > (2 * n_teams) / 3.0
    if not (contending or rebuilding):
        return []

    cur = int(ctx.get("season") or 0)
    if not cur:
        return []
    inv = pick_inventory(ctx, [cur + 1, cur + 2, cur + 3])
    scale = valuer.pick_scale()

    def pick_rows(rid):
        out = []
        for pk in inv.get(rid, []):
            orig = pk["original_rid"]
            tier = pick_tier(rank_of.get(orig, n_teams), n_teams)
            raw = valuer.pick_value(pk["season"], pk["round"], tier)
            if not raw:
                continue
            suffix = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(pk["round"],
                                                                  f'{pk["round"]}th')
            out.append({"id": f'PICK|{pk["season"]}|{pk["round"]}|{orig}',
                        "name": f'{pk["season"]} {suffix} ({tier})',
                        "pos": "PICK", "team": name_of.get(orig, "?"),
                        "val": round(raw * scale, 1), "raw": raw})
        return sorted(out, key=lambda r: r["raw"], reverse=True)

    def roster_rows(rid, win_now_only=False):
        rt = next(t for t in ctx["teams"] if t["roster_id"] == rid)
        out = []
        for pid in rt["players"]:
            pid = str(pid)
            raw = valuer.raw_value(pid)
            if not raw:
                continue
            skew = valuer.win_now_skew(pid)
            if win_now_only and (skew is None or skew < 1.10):
                continue
            out.append({**pinfo(pid, players), "val": valuer.value(pid),
                        "raw": raw, "skew": skew or 1.0})
        return out

    my_pids = [str(x) for x in ctx["my_roster"]["players"]]
    base_val = _lineup_value(my_pids, ctx, valuer, players)
    base_pts = _lineup_points(my_pids, ctx, valuer, players)
    my_repl = _replacement(ctx, valuer, players, my_rid)

    def combos(rows, cap=2):
        """Singles and pairs only — the same two-asset ceiling as player trades."""
        out = [[r] for r in rows]
        for i in range(min(len(rows), 6)):
            for j in range(i + 1, min(len(rows), 6)):
                out.append([rows[i], rows[j]])
        return out

    ideas = []
    for tm in ctx["teams"]:
        rid = tm["roster_id"]
        if rid == my_rid:
            continue
        their_rank = rank_of.get(rid, n_teams)

        if contending:
            # they should be selling: bottom half, and I want their win-now talent
            if their_rank <= n_teams / 2.0:
                continue
            gives_pool = combos(pick_rows(my_rid))
            gets_pool = [[r] for r in sorted(roster_rows(rid), key=lambda r: -r["raw"])[:8]]
            why = (f'You project {my_rank} of {n_teams}. Your own picks are late ones a '
                   f'year out; {tm["name"]} projects {their_rank} and should want them.')
        else:
            # I'm selling win-now pieces to a contender
            if their_rank > n_teams / 2.0:
                continue
            gives_pool = [[r] for r in sorted(roster_rows(my_rid, win_now_only=True),
                                              key=lambda r: -(r["raw"] * r["skew"]))[:5]]
            gets_pool = combos(pick_rows(rid))
            why = (f'You project {my_rank} of {n_teams}, so a win-now piece is worth more '
                   f'to {tm["name"]} (projected {their_rank}) than to you.')
        if not gives_pool or not gets_pool:
            continue

        for gives in gives_pool[:14]:
            g_raw = sum(r["raw"] for r in gives)
            if not g_raw:
                continue
            best = min(gets_pool, key=lambda c: abs(sum(x["raw"] for x in c) - g_raw))
            t_raw = sum(x["raw"] for x in best)
            if not t_raw or abs(g_raw - t_raw) / max(g_raw, t_raw) > tolerance:
                continue
            out_ids = {r["id"] for r in gives}
            after = ([x for x in my_pids if x not in out_ids]
                     + [r["id"] for r in best if not r["id"].startswith("PICK|")])
            ideas.append({
                "partner": tm["name"], "partner_rid": rid,
                "shape": f'{len(gives)}-for-{len(best)}',
                "gives": gives, "gets": best,
                "give": gives[0], "get": best[0],
                "give_raw": g_raw, "get_raw": t_raw,
                "my_net": round(sum(x["val"] for x in best)
                                - sum(max(0.0, r["val"] - my_repl.get(r["pos"], 0.0))
                                      for r in gives), 1),
                "their_net": round(sum(r["val"] for r in gives)
                                   - sum(x["val"] for x in best), 1),
                "lineup_delta": round(_lineup_value(after, ctx, valuer, players) - base_val, 1),
                "their_lineup_delta": 0.0,
                "pts_delta": round(_lineup_points(after, ctx, valuer, players) - base_pts, 1),
                "ros_delta": _ros_delta(my_pids, after, ctx, players, weekly_maps),
                "their_ros_delta": _ros_delta(
                    [str(x) for x in tm["players"]],
                    [str(x) for x in tm["players"]
                     if str(x) not in {r["id"] for r in best}]
                    + [r["id"] for r in gives if not r["id"].startswith("PICK|")],
                    ctx, players, weekly_maps),
                "my_pos_out": gives[0]["pos"], "my_pos_in": best[0]["pos"],
                "partner_fit": _fit_for(ctx, valuer, players, rid, gives),
                "fairness": round(100 - abs(g_raw - t_raw) / max(g_raw, t_raw) * 100, 0),
                "package_adj": 0,
                "rationale": (f'{why} You send '
                              f'{" + ".join(r["name"] for r in gives)}, you get '
                              f'{" + ".join(r["name"] for r in best)}.'),
            })

    seen, uniq = set(), []
    for i in sorted(ideas, key=lambda x: x["fairness"], reverse=True):
        k = (tuple(r["id"] for r in i["gives"]), tuple(r["id"] for r in i["gets"]))
        if k in seen or i["partner_rid"] in {j["partner_rid"] for j in uniq}:
            continue
        seen.add(k)
        uniq.append(i)
    return uniq[:max_ideas]


def block_ideas(ctx, valuer, players, give_ids, want=None, max_ideas=10,
                tolerance=0.25, picks_by_team=None, weekly_maps=None,
                stance='Competing'):
    """Trade ideas built around players YOU name, not ones the engine picks.

    The main search decides both sides; here the outgoing piece is fixed and the
    question is only what comes back. That inverts the filtering: every rival is
    a candidate, and the screen is fairness plus whether the deal helps them,
    rather than a positional mirror. `want` narrows the return to one position or
    to picks when you know what you're shopping for.

    `stance` changes what counts as a good return. Competing ranks on this
    season: points now and over the remaining weeks. Tanking inverts that — a
    rebuilding roster wants long-term value and draft capital, and a lineup that
    scores less this year is a feature, because the pick improves with the losses.

    The band widens in steps if nothing clears, so naming a player and a target
    rarely comes back empty when a defensible deal exists.
    """
    if ctx["trades_disabled"] or not ctx["my_roster"] or not give_ids:
        return []
    my_rid = ctx["my_roster"]["roster_id"]
    my_pids = [str(p) for p in ctx["my_roster"]["players"]]
    my_repl = _replacement(ctx, valuer, players, my_rid)
    base_val = _lineup_value(my_pids, ctx, valuer, players)
    base_pts = _lineup_points(my_pids, ctx, valuer, players)
    dedicated = _dedicated_slots(ctx["roster_positions"])
    ded, _flex = starting_capacity(ctx["roster_positions"])

    gives = []
    for pid in give_ids:
        pid = str(pid)
        gives.append({**pinfo(pid, players), "val": valuer.value(pid),
                      "raw": valuer.raw_value(pid)})
    g_raw = sum(r["raw"] for r in gives)
    if not g_raw:
        return []

    out_ids = {r["id"] for r in gives}
    after_base = [x for x in my_pids if x not in out_ids]
    dynasty = ctx["format"] == "dynasty"

    def scan(tol):
      ideas = []
      for tm in ctx["teams"]:
        rid = tm["roster_id"]
        if rid == my_rid:
            continue
        their_pids = [str(x) for x in tm["players"]]
        their_repl = _replacement(ctx, valuer, players, rid)
        their_base = _lineup_value(their_pids, ctx, valuer, players)

        pool = []
        if want != "Picks":
            for pid in their_pids:
                pi = pinfo(pid, players)
                if want and want != "Anything" and pi["pos"] != want:
                    continue
                raw = valuer.raw_value(pid)
                if raw:
                    pool.append({**pi, "val": valuer.value(pid), "raw": raw})
        if dynasty and want in (None, "Anything", "Picks") and picks_by_team:
            pool += picks_by_team.get(rid, [])
        if not pool:
            continue
        pool.sort(key=lambda r: -r["raw"])

        # Filler: everything else that team could add to square a deal. Asking
        # for a tight end and getting two back matches on value but not on how
        # anyone plays — you start one. When the position has a single starting
        # slot, the return carries one of them and the balance comes from another
        # position or a pick.
        filler = []
        if want and want not in ("Anything", "Picks"):
            for pid in their_pids:
                pi = pinfo(pid, players)
                if pi["pos"] == want:
                    continue
                raw = valuer.raw_value(pid)
                if raw:
                    filler.append({**pi, "val": valuer.value(pid), "raw": raw})
            if dynasty and picks_by_team:
                filler += picks_by_team.get(rid, [])
            filler.sort(key=lambda r: -r["raw"])
        one_only = want not in (None, "Anything", "Picks") and ded.get(want, 0) <= 1

        combos = [[r] for r in pool]
        if one_only:
            for r in pool[:6]:
                for f in filler[:8]:
                    # the position you asked for has to be the piece, not the
                    # throw-in: a tight end plus a better quarterback is a
                    # quarterback trade wearing a disguise
                    if f["raw"] >= r["raw"]:
                        continue
                    combos.append([r, f])
        else:
            for i in range(min(len(pool), 8)):
                for j in range(i + 1, min(len(pool), 8)):
                    combos.append([pool[i], pool[j]])

        best_for_team = []
        for gets in combos:
            if (len(gives), len(gets)) not in TRADE_SHAPES and \
               (len(gets), len(gives)) not in TRADE_SHAPES:
                continue
            t_raw = sum(r["raw"] for r in gets)
            ag, at = package_adjustment(gives, gets, dynasty)
            g_cmp, t_cmp = g_raw + ag, t_raw + at
            if not max(g_cmp, t_cmp):
                continue
            gap = abs(g_cmp - t_cmp) / max(g_cmp, t_cmp)
            # Asymmetric on purpose. Overpaying slightly is how a deal gets
            # accepted; being handed a 25% surplus is a proposal nobody signs, so
            # the band is tight in your favour and looser against you.
            if t_cmp > g_cmp and gap > min(tol, 0.12):
                continue
            if gap > tol:
                continue
            my_net = (_surplus_over_replacement(gets, my_repl)
                      - _surplus_over_replacement(gives, my_repl))
            their_net = (_surplus_over_replacement(gives, their_repl)
                         - _surplus_over_replacement(gets, their_repl))
            real_in = [r["id"] for r in gets if not r["id"].startswith("PICK|")]
            after = after_base + real_in
            their_after = ([x for x in their_pids
                            if x not in {r["id"] for r in gets}]
                           + [r["id"] for r in gives])
            their_lu = round(_lineup_value(their_after, ctx, valuer, players)
                             - their_base, 1)

            # Value over replacement cannot judge a side that is giving picks: a
            # pick counts at full value because nothing replaces it, while the
            # player coming back only counts above their own replacement. On any
            # fair pick-for-player deal that arithmetic is negative no matter how
            # much the trade helps them, which is why shopping a player for picks
            # returned nothing at all. Picks do not play, so judge that side on
            # whether their startable lineup actually improves.
            picks_moving = any(r["pos"] == "PICK" for r in gets + gives)
            good_for_them = their_lu > 0 if picks_moving else their_net > 0
            if my_net <= 0 or not good_for_them:
                continue
            fit = _fit_for(ctx, valuer, players, rid, gives)
            best_for_team.append({
                "partner": tm["name"], "partner_rid": rid,
                "shape": f"{len(gives)}-for-{len(gets)}",
                "gives": gives, "gets": gets, "give": gives[0], "get": gets[0],
                "give_raw": g_raw, "get_raw": t_raw,
                "my_net": round(my_net, 1), "their_net": round(their_net, 1),
                "partner_fit": fit,
                "lineup_delta": round(_lineup_value(after, ctx, valuer, players) - base_val, 1),
                "their_lineup_delta": their_lu,
                "pts_delta": round(_lineup_points(after, ctx, valuer, players) - base_pts, 1),
                "their_pts_delta": round(
                    _lineup_points(their_after, ctx, valuer, players)
                    - _lineup_points(their_pids, ctx, valuer, players), 1),
                "ros_delta": _ros_delta(my_pids, after, ctx, players, weekly_maps),
                "their_ros_delta": _ros_delta(their_pids, their_after, ctx,
                                              players, weekly_maps),
                "fairness": round(100 - abs(g_cmp - t_cmp) / max(g_cmp, t_cmp) * 100, 0),
                "package_adj": round(ag + at),
                "my_pos_out": gives[0]["pos"], "my_pos_in": gets[0]["pos"],
                "rationale": (f'{tm["name"]} for '
                              f'{" + ".join(r["name"] for r in gets)}. '
                              f'Values within '
                              f'{abs(g_cmp-t_cmp)/max(g_cmp,t_cmp)*100:.0f}%.'),
            })
        # At most two from any one rival, and never two routes to the same
        # player: "Lamar Jackson" and "Lamar Jackson plus a throw-in" score
        # identically and read as one idea.
        best_for_team.sort(key=lambda x: block_edge(x, stance), reverse=True)
        seen_head, kept = set(), []
        for i in best_for_team:
            # key on the NAME, not the id: two teams' 2027 firsts can share a
            # tier and render identically, so id-deduping still showed one idea
            # twice
            h = i["gets"][0]["name"]
            if h in seen_head:
                continue
            seen_head.add(h)
            kept.append(i)
            if len(kept) == 2:
                break
        ideas += kept
      return ideas

    found = []
    for tol in (tolerance, 0.35, 0.45):
        found = scan(tol)
        if found:
            break
    found.sort(key=lambda x: (block_edge(x, stance), x["fairness"]), reverse=True)
    return found[:max_ideas]


def block_edge(idea, stance="Top ideas"):
    """Rank a shopping-list idea by what the roster is trying to do.

    Top ideas is the neutral ranking — the same edge used everywhere else.

    Competing is this season and nothing else. Rest-of-season points lead, and a
    pick coming back is a penalty rather than a bonus: it cannot start for you in
    November, which is the whole reason a contender trades one away.

    Tanking is the mirror. Long-term value and picks acquired lead, and a lineup
    that scores less is mildly good, because a worse record is a better pick.
    """
    picks_in = sum(1 for r in idea.get("gets", []) if r.get("pos") == "PICK")
    fit = idea.get("partner_fit", 0.0) * 12.0
    if stance == "Tanking":
        return round(idea["my_net"]
                     + max(0.0, idea.get("lineup_delta", 0.0)) * 0.5
                     + picks_in * 8.0
                     - min(0.0, idea.get("ros_delta") or 0.0) * 0.02
                     + fit, 2)
    if stance == "Competing":
        # Deliberately excludes my_net. Value over replacement counts a pick at
        # full value because nothing replaces it, which made picks outrank real
        # players even here — the opposite of what a contender wants. This season
        # only: points now, points over the remaining weeks, and a flat penalty
        # for anything that cannot take the field.
        return round(max(0.0, idea.get("ros_delta") or 0.0) * 0.5
                     + max(0.0, idea.get("pts_delta", 0.0)) * 2.0
                     - picks_in * 40.0
                     + fit, 2)
    return trade_edge(idea)


# ── weekly digest (the headline output) ───────────────────────────────────────
def weekly_digest(ctx, valuer, players, trend_add, locked=None):
    """One compact recommendation set per league: lineup / waivers / trades."""
    ss = start_sit(ctx, valuer, players, locked=locked)
    wv = waiver_targets(ctx, valuer, players, trend_add, limit=5)
    tr = trade_ideas(ctx, valuer, players, max_ideas=3)
    lineup_moves = []
    if ss:
        for sw in ss["swaps"]:
            alt = "".join(f" or {a['name']}" for a in sw["alts"])
            lineup_moves.append(f"{sw['slot']}: start {sw['in']['name']}{alt} over {sw['out']['name']}")
    return {
        "name": ctx["name"], "format": ctx["format"],
        "lineup_moves": lineup_moves,
        "waivers": [f"{w['name']} ({w['pos']})" for w in wv[:3]],
        "trades": [f"{t['give']['name']} → {t['get']['name']} w/ {t['partner']}" for t in tr],
        "start_sit": ss, "waiver_rows": wv, "trade_rows": tr,
    }


# ── guillotine ────────────────────────────────────────────────────────────────
GUILLOTINE_SD = 26.0        # spread of a team's weekly score around its projection


# Waiver prices scale with what the LEAGUE has left to spend, not with what you
# have. A $200 bid is cheap when everyone is holding $1,000 and close to
# all-in when the field is down to $300 each, so every tier below is a share of
# the average remaining budget. As eliminations and spending drain the market
# the whole board reprices itself, which is the point.
BID_TIERS = {
    "RB": ((5, 0.20), (10, 0.10), (20, 0.05), (36, 0.02), (70, 0.01)),
    "WR": ((5, 0.20), (10, 0.10), (20, 0.05), (36, 0.02), (70, 0.01)),
    "TE": ((2, 0.25), (5, 0.05), (10, 0.025), (24, 0.01)),
    "QB": ((5, 0.10), (10, 0.025), (20, 0.01), (32, 0.005)),
    # No kickers or defences. They are streamed off the wire for the minimum
    # every week, and a board that prices them crowds out the players a budget
    # is actually for.
}


def guillotine_market(ctx, dead=None, weeks_left=1):
    """The FAAB market: what is left in it, and how much of it is yours.

    Every source on this format says to play the other budgets rather than your
    own, and none of the tools show you them. Two teams holding $800 are in
    completely different positions depending on whether the field average is
    $700 or $150, so what matters is your share of what remains — that is the
    fraction of the league's buying power you control.
    """
    dead = {int(r) for r in (dead or ())}
    budget = ctx.get("waiver_budget") or 0
    alive = [t for t in ctx["teams"] if int(t["roster_id"]) not in dead]
    if not alive or not budget:
        return {}
    left = {t["roster_id"]: max(0, budget - (t.get("waiver_budget_used") or 0))
            for t in alive}
    total = sum(left.values())
    avg = total / len(alive)
    my_rid = ctx["my_roster"]["roster_id"] if ctx["my_roster"] else None
    mine = left.get(my_rid, 0)
    rivals = sorted(((t, left[t["roster_id"]]) for t in alive
                     if t["roster_id"] != my_rid), key=lambda x: -x[1])
    top_rival = rivals[0][1] if rivals else 0
    return {
        "alive": len(alive), "budget": budget, "mine": mine, "total": total,
        "avg": avg, "share": (100.0 * mine / total) if total else 0.0,
        "even_share": 100.0 / len(alive),
        "multiple": (mine / avg) if avg else 0.0,
        "rank": sum(1 for v in left.values() if v > mine) + 1,
        "top_rival": top_rival,
        # With more money than anyone else holds in total you can simply bid a
        # dollar past their whole budget and take whoever you want.
        "bully": mine > top_rival and top_rival > 0,
        "pace": mine / max(1, weeks_left),
        "rivals": [{"name": t["name"], "roster_id": t["roster_id"], "left": v,
                    "share": (100.0 * v / total) if total else 0.0}
                   for t, v in rivals],
    }


def guillotine_bids(ctx, players, ros_pts, market, weekly_maps, dead=None, limit=12):
    """A fair-value bid on every free agent worth one, priced off the market.

    The tier a player lands in comes from where his rest-of-season projection
    puts him at his own position across the whole player pool — a top-five back
    is a top-five back whether he was drafted there or shaken loose by a chop.
    Two adjustments on top, both from how the format actually trades: a bye
    still to come is a week you are paying for and not using, and a player who
    has already had his is worth more than his ranking says.
    """
    if not market or not market.get("avg"):
        return []
    dead = {int(r) for r in (dead or ())}
    owned = {str(p) for t in ctx["teams"] if int(t["roster_id"]) not in dead
             for p in t["players"]}
    # positional rank across every player with a projection, not just free
    # agents, so the tier means the same thing all season
    ranked = {}
    for pid, pts in ros_pts.items():
        info = pinfo(pid, players)
        if not info["team"] or info["pos"] not in BID_TIERS:
            continue
        ranked.setdefault(info["pos"], []).append((float(pts), str(pid)))
    rank_of = {}
    for pos, rows in ranked.items():
        for i, (_pts, pid) in enumerate(sorted(rows, reverse=True), 1):
            rank_of[pid] = (pos, i)

    out = []
    for pid, (pos, rk) in rank_of.items():
        if pid in owned:
            continue
        pct = next((p for cut, p in BID_TIERS[pos] if rk <= cut), None)
        if pct is None:
            continue
        price = pct * market["avg"]
        # a bye still ahead is a week of the price you cannot use
        bye = next((i for i, wk in enumerate(weekly_maps)
                    if wk.get(pid, 0.0) <= 0), None)
        note = ""
        if bye == 0:
            price, note = price * 0.6, "out this week"
        elif bye is not None and bye <= 3:
            price, note = price * 0.75, f"bye in {bye} wk{'s' if bye > 1 else ''}"
        elif bye is None:
            price, note = price * 1.15, "no bye left"
        if price < 1:
            continue
        out.append({"pid": pid, "pos": pos, "rank": rk, "note": note,
                    "name": pinfo(pid, players)["name"],
                    "team": pinfo(pid, players)["team"],
                    "price": int(round(price)),
                    "of_mine": (100.0 * price / market["mine"]) if market["mine"] else 0.0,
                    "ros": round(float(ros_pts.get(pid, 0.0)), 1)})
    # Whole tiers price identically, so break the tie on rest-of-season points
    # rather than leaving it to dict order.
    return sorted(out, key=lambda x: (-x["price"], -x["ros"]))[:limit]


def guillotine_dead(week_scores):
    """Roster ids already guillotined, replayed from the weeks that have finished.

    Sleeper carries no "eliminated" flag on a roster, so the casualty list is
    reconstructed from the rule itself: the lowest score of each completed week
    goes out, and a team that is out cannot go out again. Reading it from the
    scoreboard rather than from how empty a roster looks means the field shrinks
    correctly whether or not Sleeper wipes the players of a team that was cut.

    week_scores is one {roster_id: points} map per COMPLETED week, in order.
    """
    dead = set()
    for scores in week_scores:
        live = {rid: pts for rid, pts in scores.items() if rid not in dead}
        if len(live) < 2 or not any(v > 0 for v in live.values()):
            continue                     # no scores for that week; invent nobody
        dead.add(min(live, key=lambda r: live[r]))
    return dead


def guillotine_outlook(ctx, valuer, players, weekly_maps, week_start,
                       dead=None, sims=3000):
    """Week-by-week survival odds in a guillotine league.

    The lowest score each week is eliminated, so the question is never "am I
    good" but "am I last". That cannot be answered a week at a time: the field
    shrinks as teams go out, and a score that survives week one comfortably can
    be last among the eight teams still standing in week ten. So the season is
    simulated — each alive team draws a score around its projection for that
    week, the lowest goes out, repeat — and the odds fall out of how often you
    are the one eliminated.

    Teams already guillotined are dropped before any of that. They are still in
    the league's roster list and would otherwise project near zero and absorb
    every week's elimination, which would read as safety that isn't there.

    Returns (rows, summary). Each row is one week: your projection, where it
    ranks in the field that week, the chance you go out THAT week, the chance
    you are still alive going into it, and the holes that make a bad week bad —
    starters not playing, slots below their own normal output, and the positions
    where your starters fall short of what the rest of the league gets.
    """
    try:
        import numpy as np
    except Exception:
        return [], {}
    dead = {int(r) for r in (dead or ())}
    my_rid = ctx["my_roster"]["roster_id"] if ctx["my_roster"] else None
    if my_rid is not None and int(my_rid) in dead:
        return [], {"eliminated": True, "teams": len(ctx["teams"]) - len(dead)}
    teams = [t for t in ctx["teams"] if int(t["roster_id"]) not in dead]
    n = len(teams)
    if n < 3 or not weekly_maps or my_rid is None:
        return [], {}
    idx_of = {t["roster_id"]: i for i, t in enumerate(teams)}
    if my_rid not in idx_of:
        return [], {}
    me = idx_of[my_rid]
    weeks = len(weekly_maps)

    # projected lineup points per team per remaining week, and the same split by
    # the position of whoever actually filled each slot — that split is what
    # turns "you are weak" into "you are weak at wide receiver".
    proj = np.zeros((weeks, n))
    pos_pts = {}
    detail = []
    for w, wk in enumerate(weekly_maps):
        holes = []
        for t in teams:
            i = idx_of[t["roster_id"]]
            pids = [str(p) for p in t["players"]]
            lu, _ = optimal_lineup(pids, ctx["roster_positions"], players,
                                   lambda x: wk.get(str(x), 0.0))
            proj[w][i] = sum(wk.get(str(pid), 0.0) for _, pid in lu if pid)
            for slot, pid in lu:
                if not pid:
                    continue
                pos = pinfo(pid, players)["pos"]
                if pos not in SKILL and pos not in ("K", "DEF"):
                    continue
                arr = pos_pts.setdefault(pos, np.zeros((weeks, n)))
                arr[w][i] += wk.get(str(pid), 0.0)
            if t["roster_id"] == my_rid:
                # What the lineup looks like this week, slot by slot. The bye
                # itself is invisible — the optimiser already replaces the man on
                # bye — so the damage shows up as a slot that scores less than it
                # usually does, which is the comparison made below.
                for slot, pid in lu:
                    holes.append((slot,
                                  pinfo(pid, players)["name"] if pid else None,
                                  wk.get(str(pid), 0.0) if pid else 0.0))
                # who would normally start but is out this week
                for pid in pids:
                    if wk.get(str(pid), 0.0) <= 0 and any(
                            m.get(str(pid), 0.0) > 6 for m in weekly_maps):
                        holes.append(("OUT", pinfo(pid, players)["name"], 0.0))
        detail.append(holes)

    rng = np.random.default_rng(12345)
    elim_week = np.full((sims, n), -1)
    alive = np.ones((sims, n), dtype=bool)
    for w in range(weeks):
        draw = proj[w] + rng.normal(0.0, GUILLOTINE_SD, size=(sims, n))
        draw[~alive] = np.inf                      # already out, cannot be last
        low = draw.argmin(axis=1)
        rows_ix = np.arange(sims)
        still = alive.sum(axis=1) > 1              # stop when one team remains
        elim_week[rows_ix[still], low[still]] = w
        alive[rows_ix[still], low[still]] = False

    # A slot's normal output, so a weak week can say WHICH slot went soft.
    normal = {}
    for holes in detail:
        for slot, _name, pts in holes:
            if slot != "OUT":
                normal.setdefault(slot, []).append(pts)
    normal = {k: sorted(v)[len(v) // 2] for k, v in normal.items() if v}

    out = []
    for w in range(weeks):
        gone_before = (elim_week[:, me] >= 0) & (elim_week[:, me] < w)
        this_week = elim_week[:, me] == w
        others = np.delete(proj[w], me)
        out.append({
            "week": week_start + w,
            "points": round(float(proj[w][me]), 1),
            # margin over the projected chop line: the lowest score that is not
            # yours. Negative means you ARE the projected chop.
            "cushion": round(float(proj[w][me] - others.min()), 1),
            "field_low": round(float(proj[w].min()), 1),
            "field_median": round(float(np.median(proj[w])), 1),
            "rank": int((proj[w] > proj[w][me]).sum()) + 1, "teams": n,
            "elim_pct": round(100.0 * this_week.mean(), 1),
            "alive_pct": round(100.0 * (~gone_before).mean(), 1),
            "out": [nm for s_, nm, _ in detail[w] if s_ == "OUT" and nm],
            "soft": sorted(
                ((slot, name, round(normal.get(slot, 0.0) - pts, 1))
                 for slot, name, pts in detail[w]
                 if slot != "OUT" and normal.get(slot, 0.0) - pts > 1.0),
                key=lambda x: -x[2])[:4],
            "lag": _positional_lag(pos_pts, w, me),
        })

    # Chronic weakness: a position that trails most weeks is a standing FAAB
    # problem, not a one-week dip, and it should be bought before the dip lands.
    chronic = []
    for pos, arr in pos_pts.items():
        gaps = [float(np.median(arr[w]) - arr[w][me]) for w in range(weeks)]
        meds = [float(np.median(arr[w])) for w in range(weeks)]
        tot, med_tot = sum(gaps), sum(meds)
        if med_tot <= 0 or tot <= 0:
            continue
        short = sum(1 for g, m in zip(gaps, meds) if m > 0 and g / m >= 0.15)
        if short >= max(2, weeks // 4) and tot / med_tot >= 0.10:
            pct = round(100.0 * tot / med_tot)
            chronic.append({"pos": pos, "weeks": short, "of": weeks, "pct": pct,
                            "gap": round(tot / weeks, 1),
                            "urgency": _faab_urgency(pct)})
    chronic.sort(key=lambda c: -c["pct"])

    # Where each rival is thin, so a blocking bid can be aimed at the team that
    # actually needs the player rather than at the best player on the wire.
    weak_by_team = {}
    med_tot = {pos: float(np.median(arr, axis=1).sum()) for pos, arr in pos_pts.items()}
    for t in teams:
        i = idx_of[t["roster_id"]]
        best = None
        for pos, arr in pos_pts.items():
            if med_tot[pos] <= 0:
                continue
            d = (med_tot[pos] - float(arr[:, i].sum())) / med_tot[pos]
            if best is None or d > best[1]:
                best = (pos, d)
        if best and best[1] >= 0.10:
            weak_by_team[t["roster_id"]] = {"pos": best[0], "pct": round(100 * best[1])}

    survived = (elim_week[:, me] < 0).mean()
    return out, {"survive_pct": round(100.0 * survived, 1), "sims": sims,
                 "teams": n, "dead": len(dead), "chronic": chronic,
                 "weak_by_team": weak_by_team,
                 # Down to a handful of teams everyone is stacked and the low
                 # score is no longer some collapsed roster — it is whoever had
                 # the quiet Sunday. Protecting a floor stops paying there and
                 # chasing a ceiling starts.
                 "endgame": n <= 5}


def _faab_urgency(pct):
    """How hard to bid on a position, given how far behind the field it is."""
    if pct >= 40:
        return "bid aggressively"
    if pct >= 25:
        return "worth a real bid"
    return "worth an upgrade"


def _positional_lag(pos_pts, w, me, min_pts=2.0, min_pct=0.15):
    """Positions where your starters trail the league median this week.

    Compared against the median rather than the mean so one stacked roster
    doesn't make the whole league look unreachable, and reported in both points
    and percent because a 4-point hole at tight end and a 4-point hole at
    running back are not the same problem.
    """
    import numpy as np
    lag = []
    for pos, arr in pos_pts.items():
        mine = float(arr[w][me])
        med = float(np.median(arr[w]))
        gap = med - mine
        if med <= 0 or gap < min_pts or gap / med < min_pct:
            continue
        pct = round(100.0 * gap / med)
        lag.append({"pos": pos, "mine": round(mine, 1), "median": round(med, 1),
                    "gap": round(gap, 1), "pct": pct,
                    "urgency": _faab_urgency(pct)})
    return sorted(lag, key=lambda x: -x["gap"])[:4]


def guillotine_bid_advice(ctx, valuer, players, weekly_maps, week_start, ros_pts,
                          market, pid, dead=None, sims=1500):
    """What to bid on one specific player, and why.

    Market fair value is only the anchor. Three things move a real bid off it,
    and all three are knowable:

    What he does for YOUR lineup. Rest-of-season points mean nothing if they sit
    on your bench — what counts is the change in the lineup you would actually
    start, week by week, with the byes and the replacements that follow from it.

    What he buys you in survival. This is the only currency in the format, so
    the roster is simulated twice, with him and without, off the same random
    draws so the difference is his and not the noise. A player who moves you
    two points a week and a player who moves you two points in the exact weeks
    you were projected last are worth very different money.

    Who else wants him. A rival who is thin at his position and still holding
    budget is a bidder; one who is thin and broke is not. Fair value wins an
    uncontested auction and loses a contested one.
    """
    pid = str(pid)
    if not market or not market.get("mine"):
        return {}
    import copy
    my_rid = ctx["my_roster"]["roster_id"] if ctx["my_roster"] else None
    if my_rid is None:
        return {}
    dead = {int(r) for r in (dead or ())}
    if any(pid in [str(p) for p in t["players"]] for t in ctx["teams"]
           if int(t["roster_id"]) not in dead):
        return {}

    info = pinfo(pid, players)
    pos = info["pos"]

    # paired simulation: same seed, same draws, one roster change between them
    before, s_before = guillotine_outlook(ctx, valuer, players, weekly_maps,
                                          week_start, dead=dead, sims=sims)
    if not before:
        return {}
    after_ctx = copy.deepcopy(ctx)
    for t in after_ctx["teams"]:
        if t["roster_id"] == my_rid:
            t["players"] = list(t["players"]) + [pid]
    after_ctx["my_roster"] = next(t for t in after_ctx["teams"]
                                  if t["roster_id"] == my_rid)
    after, s_after = guillotine_outlook(after_ctx, valuer, players, weekly_maps,
                                        week_start, dead=dead, sims=sims)
    survive_delta = s_after.get("survive_pct", 0.0) - s_before.get("survive_pct", 0.0)
    pts_delta = (sum(r["points"] for r in after) - sum(r["points"] for r in before))
    per_week = pts_delta / max(1, len(before))
    # the weeks he actually rescues, which is where the case for him lives
    saves = sorted(((b["week"], round(a["points"] - b["points"], 1),
                     round(b["elim_pct"] - a["elim_pct"], 1))
                    for a, b in zip(after, before) if a["points"] - b["points"] > 0.5),
                   key=lambda x: -x[2])[:4]

    fair = 0
    rk = None
    ranked = sorted(((float(v), str(k)) for k, v in ros_pts.items()
                     if pinfo(k, players)["pos"] == pos and pinfo(k, players)["team"]),
                    reverse=True)
    for i, (_p, q) in enumerate(ranked, 1):
        if q == pid:
            rk = i
            break
    if rk is not None and pos in BID_TIERS:
        pct = next((p for cut, p in BID_TIERS[pos] if rk <= cut), None)
        if pct:
            fair = pct * market["avg"]

    # who else is short here and can still pay for it
    weak = (s_before.get("weak_by_team") or {})
    contested = [r for r in market["rivals"]
                 if (weak.get(r["roster_id"]) or {}).get("pos") == pos
                 and r["left"] >= max(1, fair)]
    rich = [r for r in market["rivals"] if r["left"] >= max(1, fair)]

    # Need lifts the bid, competition lifts it again, and both are bounded: a
    # player who does nothing for the lineup does not become worth more because
    # other people want him.
    need_mult = 1.0 + min(0.8, max(0.0, per_week) / 8.0)
    comp_mult = 1.0 + 0.12 * min(4, len(contested))

    # Then patience, which is the whole early-season argument. Fair value above
    # is what he COSTS, and it is highest in September because that is when
    # every budget is full — the published price curves have the same player
    # going for roughly a tenth of his September price by December. So paying
    # the September number does not just cost money, it costs the several
    # players that money buys later, and the bid is discounted for it.
    span = max(1, (week_start + len(weekly_maps) - 1) - 1)
    progress = min(1.0, max(0.0, (week_start - 1) / span))
    patience = 0.55 + 0.45 * progress

    # Unless you might not be there. December prices are worth nothing to a
    # team chopped in October, so near-term danger cancels the discount.
    base = 100.0 / max(1, s_before.get("teams", 1))
    near = [r["elim_pct"] for r in before[:3]]
    urgency = min(1.0, max(0.0, (sum(near) / max(1, len(near)) / base) - 1.0))
    patience += (1.0 - patience) * urgency

    rec = fair * need_mult * comp_mult * patience
    # A dollar held is a dollar that still has to win something later, and it
    # wins nothing at all if you are chopped first — so the ceiling scales with
    # what the player is actually worth to your survival.
    ceiling = market["mine"] * min(0.9, 0.15 + 0.06 * max(0.0, survive_delta)) * patience
    # A dollar past the biggest rival budget cannot be beaten. None, if that
    # is more than you hold.
    outright = market["top_rival"] + 1
    if outright > market["mine"]:
        outright = None

    why = "market" if rec < ceiling else "ceiling"
    rec = min(rec, ceiling)

    # Nothing above the biggest rival budget buys anything — a dollar past it
    # cannot be beaten — and anything below it can be. So when the player is
    # worth real survival and that number is inside what he is worth, that IS
    # the number, whether it is above the market price or below it. This is
    # what stops a fat budget from losing a player it could not be outbid on,
    # and equally stops it from paying four times over to win.
    if outright and outright <= ceiling and survive_delta >= 3.0:
        rec, why = float(outright), "outright"
    # Never price a player who measurably helps at nothing.
    if survive_delta > 0.5:
        rec = max(rec, 1.0)
    return {
        "pid": pid, "name": info["name"], "pos": pos, "team": info["team"],
        "pos_rank": rk, "ros": round(float(ros_pts.get(pid, 0.0)), 1),
        "fair": int(round(fair)), "rec": int(round(rec)),
        "max": int(round(min(market["mine"], max(rec * 1.4, ceiling)))),
        "outright": outright,
        "patience": round(patience, 2), "urgency": round(urgency, 2), "why": why,
        "of_budget": (100.0 * rec / market["mine"]) if market["mine"] else 0.0,
        "leaves": int(market["mine"] - round(rec)),
        "per_week": round(per_week, 1), "ros_gain": round(pts_delta, 1),
        "survive_before": s_before.get("survive_pct", 0.0),
        "survive_after": s_after.get("survive_pct", 0.0),
        "survive_delta": round(survive_delta, 1),
        "contested": [r["name"] for r in contested],
        "rich": len(rich), "saves": saves,
    }


def guillotine_targets(ctx, valuer, players, weekly_maps, week_start, trend_add=None,
                       limit=6):
    """Positions worth bidding on, and who is available to fill them.

    Ranked by how much a position costs you across the remaining weeks: a slot
    that goes empty on a bye is a guaranteed zero, and a slot filled by a body
    barely above replacement bleeds points every week. Both are FAAB problems
    before they are lineup problems.
    """
    if not ctx["my_roster"] or not weekly_maps:
        return []
    my_pids = [str(p) for p in ctx["my_roster"]["players"]]
    cost, by_slot = {}, {}
    for w, wk in enumerate(weekly_maps):
        lu, _ = optimal_lineup(my_pids, ctx["roster_positions"], players,
                               lambda x: wk.get(str(x), 0.0))
        for slot, pid in lu:
            elig = FLEX_ELIG.get(slot, set())
            pos = next(iter(elig)) if len(elig) == 1 else "FLEX"
            pts = wk.get(str(pid), 0.0) if pid else 0.0
            by_slot.setdefault(pos, []).append(pts)
    # A position is worth bidding on when it is weak every week, or when it
    # collapses in some weeks — a season-long hole and a bye-week cliff are
    # different problems and both cost points.
    rows = []
    for pos, vals in by_slot.items():
        if not vals:
            continue
        vals_sorted = sorted(vals)
        floor = vals_sorted[0]
        med = vals_sorted[len(vals_sorted) // 2]
        worst_weeks = [week_start + i for i, v in enumerate(vals) if v <= med - 3.0]
        rows.append({"pos": pos, "median": round(med, 1), "floor": round(floor, 1),
                     "dip": round(med - floor, 1), "weak_weeks": worst_weeks[:4],
                     "cost": round((med - floor) + max(0.0, 9.0 - med) * 2, 1)})
    rows.sort(key=lambda r: -r["cost"])
    return rows[:limit]
