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
def start_sit(ctx, valuer, players, alt_tol=0.75):
    """Compare the current starters to the optimal lineup and surface swaps.

    Swaps are paired BY SLOT, not by raw score: a bench player is only ever
    suggested against a starter whose slot he's actually eligible to fill, so a
    QB never shows up as a swap for an RB. Where two bench options are within a
    hair of each other on projection, both are offered ("start B or C over A") —
    that call is usually matchup or gut, not math.
    """
    me = ctx["my_roster"]
    if not me:
        return None
    pids = me["players"]
    lineup, bench = optimal_lineup(pids, ctx["roster_positions"], players, valuer.start_score)
    optimal_ids = {pid for _, pid in lineup if pid}
    starters = [str(p) if p and str(p) != "0" else None for p in me["starters"]]
    current = {p for p in starters if p}

    def row(pid, slot=None):
        pi = pinfo(pid, players)
        return {**pi, "slot": slot, "pts": round(valuer.points(pid), 1),
                "val": round(valuer.value(pid), 1), "score": round(valuer.start_score(pid), 2)}

    lineup_rows = [row(pid, slot) for slot, pid in lineup if pid]
    bench_rows = [row(pid) for pid in bench if pinfo(pid, players)["pos"] in SKILL]

    incoming = optimal_ids - current
    outgoing = set(current - optimal_ids)

    swaps = []
    for i, (slot, pid) in enumerate(lineup):
        if not pid or pid not in incoming:
            continue
        elig = FLEX_ELIG.get(slot, set())
        # prefer the player literally sitting in this slot today; otherwise the
        # weakest benchable starter who could legally occupy it
        cur = starters[i] if i < len(starters) else None
        out = cur if cur in outgoing else None
        if out is None:
            legal = [p for p in outgoing if pinfo(p, players)["pos"] in elig]
            out = min(legal, key=valuer.start_score) if legal else None
        if out is None:
            continue
        outgoing.discard(out)

        best_pts = valuer.points(pid)
        alts = []
        if best_pts > 0:                      # "close" is meaningless with no projections
            band = max(alt_tol, best_pts * 0.05)
            alts = [b for b in bench
                    if b != pid
                    and pinfo(b, players)["pos"] in elig
                    and abs(valuer.points(b) - best_pts) <= band
                    and valuer.points(b) > 0]
            alts.sort(key=valuer.points, reverse=True)
        swaps.append({"slot": slot,
                      "in": row(pid, slot), "out": row(out, slot),
                      "alts": [row(a, slot) for a in alts[:2]],
                      "gain": round(best_pts - valuer.points(out), 1)})

    swaps.sort(key=lambda x: x["gain"], reverse=True)
    return {
        "lineup": lineup_rows,
        "bench": sorted(bench_rows, key=lambda r: r["score"], reverse=True),
        "swaps": swaps,
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
        cands.append({**pi, "val": round(val, 1), "buzz": buzz, "pts": round(pts, 1),
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
        c["score"] = round(gain * 8 + max(0.0, bench_delta) * 3 + c["pts"] * 1.0
                           + nd * 20 + c["val"] * 0.30 + buzz_term, 1)

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
        if c["buzz"]:
            why.append(f"+{c['buzz']:,} adds this week")
        c["why"] = " · ".join(why)
        c.pop("pre", None)
        out.append(c)

    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:limit]


# ── projected standings & rookie picks ────────────────────────────────────────
def power_rankings(ctx, valuer, players):
    """Project where each team finishes — which is what sets rookie draft order.

    Blends roster asset value with actual record. In September a 1-0 record says
    almost nothing and roster strength says almost everything; by November it's
    the reverse, so the record's weight grows with games played rather than being
    fixed. Returns rows sorted best -> worst with a proj_rank.
    """
    teams, _ = positional_strength(ctx, valuer, players)
    rows = []
    for t in ctx["teams"]:
        rid = t["roster_id"]
        g = t["wins"] + t["losses"] + t["ties"]
        rows.append({"rid": rid, "name": t["name"], "is_mine": t["is_mine"],
                     "strength": teams[rid]["total"], "games": g,
                     "winpct": ((t["wins"] + 0.5 * t["ties"]) / g) if g else 0.5,
                     "record": f'{t["wins"]}-{t["losses"]}' + (f'-{t["ties"]}' if t["ties"] else "")})
    top = max((r["strength"] for r in rows), default=0) or 1
    played = max((r["games"] for r in rows), default=0)
    w = min(played / 10.0, 0.65)              # record tops out at 65% of the blend
    for r in rows:
        r["score"] = round((1 - w) * (r["strength"] / top) + w * r["winpct"], 4)
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
def positional_strength(ctx, valuer, players):
    """Per-team value totals by position + starter-quality, plus league averages."""
    core = ["QB", "RB", "WR", "TE"]
    teams = {}
    for t in ctx["teams"]:
        by = {pos: [] for pos in core}
        for pid in t["players"]:
            pos = pinfo(pid, players)["pos"]
            if pos in by:
                by[pos].append(valuer.value(pid))
        strength = {pos: round(sum(sorted(v, reverse=True)[:3]), 1) for pos, v in by.items()}  # top-3 depth
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


def _lineup_value(pids, ctx, valuer, players):
    """Total asset value of the best startable lineup these players can field.

    This is the roster-construction test: it prices a deal by what it does to the
    lineup you can actually start, so a trade that stacks a position you can only
    start one of, or that leaves a slot unfillable, shows up as a loss.
    """
    lu, _ = optimal_lineup(pids, ctx["roster_positions"], players, valuer.value)
    return sum(valuer.value(pid) for _, pid in lu if pid)


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
    extras = sorted(r.get("raw", 0) for r in longer)[:k]      # the k cheapest
    adj = sum(min(vv * c["pct"], c["cap"] + i * c["step"]) for i, vv in enumerate(extras))
    adj += max(0, (k - 1) * c["flat"])
    return (adj, 0.0) if ng < nt else (0.0, adj)


TRADE_SHAPES = {(1, 1), (2, 1), (2, 2)}      # (players out, players in)
MAX_PER_PARTNER = 2                          # one rival shouldn't fill the board


def trade_ideas(ctx, valuer, players, max_ideas=6, tolerance=0.20):
    """Mutually-beneficial trades, including packages.

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
    need_bar = 1.00 if stacked else 1.05
    sur_bar = 1.12 if stacked else 1.02

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
                # 1-for-1: my second-best surplus piece for their closest match
                one = give_pool[1]
                shapes.append(([one], [min(get_pool, key=lambda r: abs(r["val"] - one["val"]))]))

                # A package should send pieces from DIFFERENT positions — no team
                # wants two TEs when it starts one. Prefer a second piece from
                # another surplus spot; only double up on one position as a last
                # resort, and the partner-lineup test below still has to agree.
                second = None
                for alt in surplus:
                    if alt == my_sur:
                        continue
                    alt_pool = players_at(my_rid, alt)
                    if len(alt_pool) >= dedicated.get(alt, 1) + 2:
                        second = alt_pool[1]
                        break
                if second is None and len(give_pool) >= max(keep + 2, 3):
                    second = give_pool[2]

                if second is not None:
                    pair = [one, second]
                    tot = sum(r["val"] for r in pair)
                    # 2-for-1 consolidation: two pieces for their best at my need
                    stud = min(get_pool, key=lambda r: abs(r["val"] - tot))
                    if stud["val"] > pair[0]["val"] * 1.05:
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
                    if len(gives) > 1 and not all(r["id"] in their_started for r in gives):
                        continue
                    # same rule for me when I'm the one taking on more bodies
                    if len(gets) > 1:
                        my_lu, _ = optimal_lineup(after, ctx["roster_positions"],
                                                  players, valuer.value)
                        my_started = {pid for _, pid in my_lu if pid}
                        if not all(r["id"] in my_started for r in gets):
                            continue

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
                        "lineup_delta": lineup_delta, "their_lineup_delta": their_delta,
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
    seen, headline, per_partner, uniq = set(), set(), {}, []
    for i in sorted(ideas, key=lambda x: (x["lineup_delta"], x["my_net"], x["fairness"]),
                    reverse=True):
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
        seen.add(key)
        headline.add(head)
        per_partner[rid] = per_partner.get(rid, 0) + 1
        uniq.append(i)
    return uniq[:max_ideas]


# ── weekly digest (the headline output) ───────────────────────────────────────
def weekly_digest(ctx, valuer, players, trend_add):
    """One compact recommendation set per league: lineup / waivers / trades."""
    ss = start_sit(ctx, valuer, players)
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
