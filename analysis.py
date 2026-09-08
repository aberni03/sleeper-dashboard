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


def _replacement(ctx, valuer, players, rid, dedicated):
    """Value of the body that actually steps up when a starter is traded away.

    This is what makes package deals judgeable: trading your RB3 out of a 2-RB
    lineup costs you roughly nothing, because your RB4 slides in. Trading your
    RB1 costs you RB1 minus RB3. Raw value totals miss that entirely.
    """
    rt = next(t for t in ctx["teams"] if t["roster_id"] == rid)
    by = {}
    for pid in rt["players"]:
        by.setdefault(pinfo(pid, players)["pos"], []).append(valuer.value(pid))
    repl = {}
    for pos, vals in by.items():
        vals.sort(reverse=True)
        n = dedicated.get(pos, 1)
        repl[pos] = vals[n] if len(vals) > n else 0.0
    return repl


def _surplus_over_replacement(rows, repl):
    """Sum of each player's value above his position's replacement level.

    Units are the Valuer's 0-100 asset-value scale (normalized FantasyCalc) —
    NOT fantasy points, and not season-long. The only points figure anywhere in
    the app is Sleeper's weekly projection.
    """
    return sum(max(0.0, r["val"] - repl.get(r["pos"], 0.0)) for r in rows)


def trade_ideas(ctx, valuer, players, max_ideas=6, tolerance=0.20):
    """Mutually-beneficial trades, including packages.

    Shapes: 1-for-1, 2-for-1 (consolidation) and 2-for-2. Every shape is judged on
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
    my_repl = _replacement(ctx, valuer, players, my_rid, dedicated)

    surplus = sorted([p for p in core if my_str[p] > avg[p] * 1.08],
                     key=lambda p: my_str[p] - avg[p], reverse=True)
    needs = sorted([p for p in core if my_str[p] < avg[p] * 0.98],
                   key=lambda p: avg[p] - my_str[p], reverse=True)
    if not needs:
        needs = sorted(core, key=lambda p: my_str[p] - avg[p])[:2]
    if not surplus or not needs:
        return []

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
        their_repl = _replacement(ctx, valuer, players, rid, dedicated)
        for my_need in needs:
            for my_sur in surplus:
                if tm["strength"][my_need] < avg[my_need] * 1.05:
                    continue                                   # they aren't rich at my need
                if tm["strength"][my_sur] > avg[my_sur] * 1.02:
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
                # 2-for-1 consolidation: two depth pieces for their best at my need
                if len(give_pool) >= keep + 2 and len(give_pool) >= 3:
                    pair = [give_pool[1], give_pool[2]]
                    tot = sum(r["val"] for r in pair)
                    stud = min(get_pool, key=lambda r: abs(r["val"] - tot))
                    if stud["val"] > pair[0]["val"] * 1.05:     # the deal must land a clear best player
                        shapes.append((pair, [stud]))
                # 2-for-2
                if len(give_pool) >= keep + 2 and len(get_pool) >= 2:
                    pair = [give_pool[1], give_pool[2]] if len(give_pool) >= 3 else None
                    if pair:
                        tot = sum(r["val"] for r in pair)
                        best2, bestd = None, None
                        for i in range(len(get_pool)):
                            for j in range(i + 1, len(get_pool)):
                                d = abs(get_pool[i]["val"] + get_pool[j]["val"] - tot)
                                if bestd is None or d < bestd:
                                    bestd, best2 = d, [get_pool[i], get_pool[j]]
                        if best2:
                            shapes.append((pair, best2))

                for gives, gets in shapes:
                    gv = sum(r["val"] for r in gives)
                    tv = sum(r["val"] for r in gets)
                    if max(gv, tv) == 0 or abs(gv - tv) / max(gv, tv) > tolerance:
                        continue
                    # win-win test on value over replacement, both directions
                    my_net = _surplus_over_replacement(gets, my_repl) - \
                        _surplus_over_replacement(gives, my_repl)
                    their_net = _surplus_over_replacement(gives, their_repl) - \
                        _surplus_over_replacement(gets, their_repl)
                    if my_net <= 0 or their_net <= 0:
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
                        "my_pos_out": my_sur, "my_pos_in": my_need,
                        "fairness": round(100 - abs(gv - tv) / max(gv, tv) * 100, 0),
                        "rationale": f"{why} You send {gnames}, you get {tnames}. "
                                     f"Values within {abs(gv-tv)/max(gv,tv)*100:.0f}%.",
                    })

    # dedupe by the exact set of players involved; keep the fairest
    seen, uniq = set(), []
    for i in sorted(ideas, key=lambda x: (x["my_net"], x["fairness"]), reverse=True):
        k = (tuple(sorted(r["id"] for r in i["gives"])),
             tuple(sorted(r["id"] for r in i["gets"])))
        if k in seen:
            continue
        seen.add(k)
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
