"""Decision engine: optimal lineups, start/sit deltas, waiver targets, and
win-win trade ideas — built on top of the Valuer (proxy now, external later).
Everything returns plain dicts/lists so the UI stays dumb."""
from values import Valuer, pinfo, FLEX_ELIG, BENCH_SLOTS, SKILL


# ── lineup optimization ───────────────────────────────────────────────────────
def _startable_slots(roster_positions):
    return [s for s in roster_positions if s not in BENCH_SLOTS]


def optimal_lineup(pids, roster_positions, players, score_fn):
    """Greedy optimal: fill most-restrictive slots first with the highest scorer.
    Returns (lineup[list of (slot,pid)], bench[list of pid])."""
    slots = _startable_slots(roster_positions)
    slots = sorted(slots, key=lambda s: len(FLEX_ELIG.get(s, {"?"})))     # single-pos before flex
    avail = sorted([str(p) for p in pids], key=score_fn, reverse=True)
    used, lineup = set(), []
    for slot in slots:
        elig = FLEX_ELIG.get(slot, set())
        pick = None
        for pid in avail:
            if pid in used:
                continue
            if pinfo(pid, players)["pos"] in elig:
                pick = pid
                break
        if pick:
            used.add(pick)
        lineup.append((slot, pick))
    bench = [p for p in avail if p not in used]
    return lineup, bench


# ── start / sit ───────────────────────────────────────────────────────────────
def start_sit(ctx, valuer, players):
    """Compare the current starters to the optimal lineup; surface swaps."""
    me = ctx["my_roster"]
    if not me:
        return None
    pids = me["players"]
    lineup, bench = optimal_lineup(pids, ctx["roster_positions"], players, valuer.start_score)
    optimal_ids = {pid for _, pid in lineup if pid}
    current = {str(p) for p in me["starters"] if p and str(p) != "0"}

    def row(pid, slot=None):
        pi = pinfo(pid, players)
        return {**pi, "slot": slot, "pts": round(valuer.points(pid), 1),
                "val": round(valuer.value(pid), 1), "score": round(valuer.start_score(pid), 2)}

    lineup_rows = [row(pid, slot) for slot, pid in lineup if pid]
    bench_rows = [row(pid) for pid in bench if pinfo(pid, players)["pos"] in SKILL]

    # swaps: optimal players not currently started, and current starters left out
    starts = [row(pid) for pid in (optimal_ids - current)]
    sits = [row(pid) for pid in (current - optimal_ids)]
    starts.sort(key=lambda r: r["score"], reverse=True)
    sits.sort(key=lambda r: r["score"])
    return {
        "lineup": lineup_rows,
        "bench": sorted(bench_rows, key=lambda r: r["score"], reverse=True),
        "start": starts,
        "sit": sits,
        "proj_total": round(sum(r["pts"] for r in lineup_rows), 1),
        "have_projections": any(r["pts"] > 0 for r in lineup_rows),
        "set_lineup": bool(current),
    }


# ── waivers ───────────────────────────────────────────────────────────────────
def waiver_targets(ctx, valuer, players, trend_add, limit=12):
    """Rank the best available (unrostered) players; blend value + trending buzz."""
    rostered = set()
    for t in ctx["teams"]:
        rostered.update(str(p) for p in t["players"])
    trend = {str(t["player_id"]): t.get("count", 0) for t in trend_add}

    cands = []
    for pid, p in players.items():
        if pid in rostered:
            continue
        pos = p.get("position")
        if pos not in SKILL:
            continue
        if (p.get("team") or "FA") == "FA":                      # skip free-agent-less/retired
            continue
        val = valuer.value(pid)
        buzz = trend.get(pid, 0)
        if val <= 0 and buzz == 0:
            continue
        pi = pinfo(pid, players)
        score = val + min(buzz / 500.0, 40)                      # buzz nudges, value leads
        cands.append({**pi, "val": round(val, 1), "buzz": buzz,
                      "pts": round(valuer.points(pid), 1), "score": round(score, 1)})
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands[:limit]


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
def trade_ideas(ctx, valuer, players, max_ideas=6, tolerance=0.20):
    """Find mutually-beneficial swaps: I trade from a position of surplus into my
    need; the partner does the mirror. Values must be within `tolerance`."""
    if ctx["trades_disabled"] or not ctx["my_roster"]:
        return []
    core = ["QB", "RB", "WR", "TE"]
    teams, avg = positional_strength(ctx, valuer, players)
    mine = ctx["my_roster"]
    my_rid = mine["roster_id"]
    my_str = teams[my_rid]["strength"]

    # my surplus (above avg) and needs (below or near avg — relative weak spots)
    surplus = sorted([p for p in core if my_str[p] > avg[p] * 1.08], key=lambda p: my_str[p] - avg[p], reverse=True)
    needs = sorted([p for p in core if my_str[p] < avg[p] * 0.98], key=lambda p: avg[p] - my_str[p], reverse=True)
    if not needs:                                          # stacked roster: target relatively weakest spots
        needs = sorted(core, key=lambda p: my_str[p] - avg[p])[:2]
    if not surplus or not needs:
        return []

    def players_at(rid, pos):
        rt = next(t for t in ctx["teams"] if t["roster_id"] == rid)
        rows = [{**pinfo(pid, players), "val": valuer.value(pid)} for pid in rt["players"]]
        return sorted([r for r in rows if r["pos"] == pos and r["val"] > 0],
                      key=lambda r: r["val"], reverse=True)

    ideas = []
    for rid, tm in teams.items():
        if rid == my_rid:
            continue
        # partner should be strong where I'm weak, and weak where I'm strong
        for my_need in needs:
            for my_sur in surplus:
                if tm["strength"][my_need] < avg[my_need] * 1.05:
                    continue                                   # they aren't rich at my need
                if tm["strength"][my_sur] > avg[my_sur] * 1.02:
                    continue                                   # they don't need my surplus
                give_pool = players_at(my_rid, my_sur)          # I give a surplus asset
                get_pool = players_at(rid, my_need)             # I get a need asset
                if len(give_pool) < 2 or not get_pool:
                    continue
                give = give_pool[1]                              # trade my 2nd-best (keep the stud)
                # match a partner player of similar value
                target = min(get_pool, key=lambda r: abs(r["val"] - give["val"]))
                gv, tv = give["val"], target["val"]
                if max(gv, tv) == 0 or abs(gv - tv) / max(gv, tv) > tolerance:
                    continue
                ideas.append({
                    "partner": tm["name"], "partner_rid": rid,
                    "give": give, "get": target,
                    "my_pos_out": my_sur, "my_pos_in": my_need,
                    "fairness": round(100 - abs(gv - tv) / max(gv, tv) * 100, 0),
                    "rationale": f"You're deep at {my_sur} (need {my_need}); "
                                 f"{tm['name']} is the mirror. Values within "
                                 f"{abs(gv-tv)/max(gv,tv)*100:.0f}%.",
                })
    # dedupe by (give,get) and keep the fairest
    seen, uniq = set(), []
    for i in sorted(ideas, key=lambda x: x["fairness"], reverse=True):
        k = (i["give"]["id"], i["get"]["id"])
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
        for s_in, s_out in zip(ss["start"], ss["sit"]):
            lineup_moves.append(f"Start {s_in['name']} over {s_out['name']}")
    return {
        "name": ctx["name"], "format": ctx["format"],
        "lineup_moves": lineup_moves,
        "waivers": [f"{w['name']} ({w['pos']})" for w in wv[:3]],
        "trades": [f"{t['give']['name']} → {t['get']['name']} w/ {t['partner']}" for t in tr],
        "start_sit": ss, "waiver_rows": wv, "trade_rows": tr,
    }
