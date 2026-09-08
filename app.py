"""Fantasy Command Center — Sleeper.  Run:  streamlit run app.py
Username-driven so the same deploy serves you and anyone you share the link with
(?u=their_username).  Design mirrors the CFB Totals Edge dashboard."""
import streamlit as st
import sleeper as S
import analysis as A
from values import Valuer, ENABLE_EXTERNAL, pinfo

st.set_page_config(page_title="Fantasy Command Center", page_icon="🏈",
                   layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@600;700&display=swap');
:root{--bg:#070b16;--card:#111a2e;--card2:#0c1424;--line:#1e2c47;--txt:#eef3fc;--mut:#7e8db0;
--grn:#19e59b;--red:#ff4d73;--amb:#ffc24b;--cyan:#38d6ff;--vio:#8b7bff;}
*{font-family:'Inter',sans-serif;}
.stApp{background:radial-gradient(1200px 500px at 15% -10%,#132449 0%,#070b16 55%) fixed;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1200px;}
.mono{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}
.hero{background:linear-gradient(110deg,#16224a 0%,#0e1730 60%);border:1px solid var(--line);
  border-radius:20px;padding:20px 26px;margin-bottom:14px;position:relative;overflow:hidden;}
.hero:before{content:'';position:absolute;right:-40px;top:-40px;width:220px;height:220px;
  background:radial-gradient(circle,rgba(25,229,155,.22),transparent 70%);}
.hero h1{font-size:29px;font-weight:900;color:#fff;margin:0;letter-spacing:-.7px;}
.hero h1 .ac{background:linear-gradient(90deg,var(--grn),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hero .sub{color:var(--mut);font-size:13px;margin-top:5px;} .hero .sub b{color:var(--grn);}
.note{background:linear-gradient(160deg,#10233f,#0b1526);border:1px solid #26406a;border-radius:11px;
  padding:9px 14px;margin:2px 0 14px;color:#9fb0d0;font-size:12px;} .note b{color:#c7d2ea;}
.kpi{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:16px;padding:14px 18px;}
.kpi .n{font-size:25px;font-weight:900;color:var(--txt);line-height:1;} .kpi .n.g{color:var(--grn);} .kpi .n.c{color:var(--cyan);}
.kpi .l{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin-top:6px;font-weight:600;}
.daybar{display:flex;align-items:center;gap:10px;margin:18px 0 10px;}
.daybar span{color:#cdd7ee;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;}
.daybar .ln{flex:1;height:1px;background:linear-gradient(90deg,var(--line),transparent);}
button[data-baseweb="tab"]{font-size:14px!important;font-weight:800!important;letter-spacing:.6px;text-transform:uppercase;color:#6f7f9e!important;padding:8px 2px!important;}
button[data-baseweb="tab"]:hover{color:#c7d2ea!important;}
button[data-baseweb="tab"][aria-selected="true"]{color:#eef3fc!important;}
div[data-baseweb="tab-list"]{gap:26px!important;border-bottom:1px solid #17233b;margin-bottom:12px;}
div[data-baseweb="tab-highlight"]{background:#19e59b!important;height:2.5px!important;}
div[data-baseweb="tab-border"]{display:none!important;}
/* league digest card */
.lgcard{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);
  border-left:4px solid #23324f;border-radius:14px;padding:14px 18px;margin-bottom:11px;}
.lgcard.dyn{border-left-color:var(--vio);} .lgcard.rd{border-left-color:var(--cyan);}
.lgcard h3{margin:0 0 3px;font-size:16px;font-weight:800;color:#fff;}
.lgcard .meta{color:var(--mut);font-size:11.5px;margin-bottom:9px;}
.lgcard .rec{color:#c7d2ea;font-weight:700;}
.mv{margin:6px 0;} .mv .h{font-size:10.5px;text-transform:uppercase;letter-spacing:.8px;font-weight:800;color:var(--mut);margin-bottom:3px;}
.mv .h.s{color:var(--grn);} .mv .h.w{color:var(--cyan);} .mv .h.t{color:var(--amb);}
.mv .i{color:#dbe4f7;font-size:13px;line-height:1.5;} .mv .i b{color:#fff;}
.mv .none{color:#5b688a;font-size:12.5px;font-style:italic;}
/* player rows */
.thead{display:grid;grid-template-columns:64px 1fr 46px 60px 60px;gap:10px;padding:0 14px 5px;color:var(--mut);font-size:10px;text-transform:uppercase;letter-spacing:.6px;font-weight:700;}
.prow{display:grid;grid-template-columns:64px 1fr 46px 60px 60px;gap:10px;align-items:center;
  background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);border-left:3px solid #23324f;
  border-radius:10px;padding:9px 14px;margin-bottom:5px;font-size:13px;}
.prow.st{border-left-color:var(--grn);} .prow.be{border-left-color:#39415a;opacity:.9;}
.prow .slot{color:var(--mut);font-size:11px;font-weight:800;text-transform:uppercase;}
.prow .nm{color:#fff;font-weight:700;} .prow .nm .tm{color:var(--mut);font-weight:600;font-size:11px;margin-left:6px;}
.prow .nm .inj{color:var(--red);font-weight:800;font-size:10px;margin-left:6px;}
.prow .pos{color:#b9c6e3;font-weight:700;text-align:center;}
.prow .pts{color:#fff;font-weight:800;text-align:right;font-family:'JetBrains Mono',monospace;}
.prow .val{color:var(--mut);text-align:right;font-family:'JetBrains Mono',monospace;}
/* swap + trade cards */
.swap{display:grid;grid-template-columns:1fr 34px 1fr;gap:10px;align-items:center;
  background:linear-gradient(160deg,#12203b,#0c1424);border:1px solid #26406a;border-radius:12px;padding:11px 15px;margin-bottom:8px;}
.swap .side .k{font-size:9.5px;text-transform:uppercase;letter-spacing:.7px;font-weight:800;}
.swap .side .k.in{color:var(--grn);} .swap .side .k.out{color:var(--red);}
.swap .side .n{color:#fff;font-weight:700;font-size:14px;} .swap .side .n .m{color:var(--mut);font-size:11px;font-weight:600;}
.swap .ar{color:var(--grn);font-size:18px;font-weight:900;text-align:center;}
.trade{background:linear-gradient(160deg,#13203b,#0c1424);border:1px solid #2a3a5c;border-radius:14px;padding:14px 18px;margin-bottom:10px;}
.trade .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px;}
.trade .top .p{color:#fff;font-weight:800;font-size:15px;} .trade .top .p .w{color:var(--mut);font-weight:600;font-size:12px;}
.trade .fair{background:rgba(25,229,155,.16);color:var(--grn);font-weight:800;font-size:12px;padding:4px 11px;border-radius:20px;}
.trade .legs{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.trade .leg{background:#0e1830;border:1px solid var(--line);border-radius:10px;padding:10px 13px;}
.trade .leg .k{font-size:10px;text-transform:uppercase;letter-spacing:.6px;font-weight:800;margin-bottom:4px;}
.trade .leg .k.g{color:var(--grn);} .trade .leg .k.r{color:var(--red);}
.trade .leg .n{color:#fff;font-weight:700;font-size:14px;} .trade .leg .n .m{color:var(--mut);font-size:11px;}
.trade .why{color:#9fb0d0;font-size:12px;margin-top:9px;line-height:1.5;}
/* standings */
.srow{display:grid;grid-template-columns:30px 1fr 70px 90px;gap:10px;align-items:center;
  background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:9px;padding:8px 14px;margin-bottom:4px;font-size:13px;}
.srow.me{border-color:var(--grn);box-shadow:0 0 0 1px rgba(25,229,155,.25) inset;}
.srow .rk{color:var(--mut);font-weight:800;text-align:center;} .srow .tn{color:#eef3fc;font-weight:700;} .srow.me .tn{color:var(--grn);}
.srow .rec{color:#c7d2ea;text-align:center;font-weight:700;} .srow .pf{color:var(--mut);text-align:right;font-family:'JetBrains Mono',monospace;}
.badge{display:inline-block;padding:3px 10px;border-radius:16px;font-size:11px;font-weight:800;}
.badge.dyn{background:rgba(139,123,255,.18);color:var(--vio);} .badge.rd{background:rgba(56,214,255,.16);color:var(--cyan);}
.badge.sf{background:rgba(255,194,75,.16);color:var(--amb);} .badge.off{background:#2a3040;color:#8b93a7;}
.empty{color:#5b688a;font-size:13px;font-style:italic;padding:8px 2px;}
/* global action center */
.actionwrap{background:linear-gradient(120deg,#122748,#0b1424);border:1px solid #24365d;border-radius:18px;
  padding:16px 20px 8px;margin:6px 0 8px;position:relative;overflow:hidden;}
.actionwrap:before{content:'';position:absolute;left:-30px;top:-40px;width:200px;height:200px;background:radial-gradient(circle,rgba(25,229,155,.14),transparent 70%);}
.actionhd{font-size:15px;font-weight:900;color:#fff;letter-spacing:.3px;margin-bottom:2px;}
.actionsub{color:var(--mut);font-size:12px;margin-bottom:12px;} .actionsub b{color:var(--grn);}
.lane .lh{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.9px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #1c2942;}
.lane .lh.s{color:var(--grn);} .lane .lh.w{color:var(--cyan);} .lane .lh.t{color:var(--amb);}
.ai{display:block;margin-bottom:9px;line-height:1.4;} .ai .tag{display:inline-block;font-size:9.5px;font-weight:800;color:#8ea0c4;
  background:#0e1830;border:1px solid #23345a;border-radius:6px;padding:1px 6px;margin-bottom:2px;text-transform:uppercase;letter-spacing:.4px;}
.ai .txt{color:#e7edf7;font-size:13px;} .ai .txt b{color:#fff;} .ai .txt .g{color:var(--grn);font-weight:700;} .ai .txt .r{color:var(--red);}
.lane .none{color:#5b688a;font-size:12.5px;font-style:italic;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ── helpers ───────────────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def hdr(txt):
    st.markdown(f'<div class="daybar"><span>{esc(txt)}</span><div class="ln"></div></div>', unsafe_allow_html=True)

def inj_tag(pi):
    return f' <span class="inj">{esc(pi["injury"])}</span>' if pi.get("injury") else ""

# ── header + username (multi-user) ────────────────────────────────────────────
qp = st.query_params
default_user = qp.get("u", "aberni3")

st.markdown(
    '<div class="hero"><h1>🏈 Fantasy <span class="ac">Command Center</span></h1>'
    '<div class="sub">Stop logging into every league one by one — <b>every</b> lineup, waiver &amp; trade '
    'decision across all your Sleeper leagues, in one scan, split by <b>dynasty</b> vs <b>redraft/guillotine</b>.</div></div>',
    unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
with c1:
    username = st.text_input("Sleeper username", value=default_user,
                             label_visibility="collapsed", placeholder="Enter a Sleeper username…")
with c2:
    if st.button("↻ Refresh data", use_container_width=True):
        st.cache_data.clear(); st.rerun()

if username and username != qp.get("u"):
    st.query_params["u"] = username

if not username:
    st.info("Enter a Sleeper username to load leagues.")
    st.stop()

with st.spinner(f"Loading {username}'s leagues…"):
    data = S.load_all(username)
    players = S.load_players()

if not data:
    st.error(f"No Sleeper user found for **{username}**. Check the spelling and try again.")
    st.stop()
if not data["contexts"]:
    st.warning(f"**{username}** has no NFL leagues for {data['season']}.")
    st.stop()

proj = S.projections(data["season"], data["week"], "ppr")
trend = S.trending("add", 168, 250)

# value/projection status banner
vmode = ("<b>External trade values: ON</b> (FantasyCalc)" if ENABLE_EXTERNAL
         else "Trade/roster values: <b>preliminary</b> (Sleeper rank proxy) — external values connect in the API step")
st.markdown(f'<div class="note">👤 <b>{esc(data["user"]["display_name"])}</b> · '
            f'{data["season"]} · Week <b>{data["week"]}</b> &nbsp;·&nbsp; '
            f'Projections: <b>live from Sleeper</b> &nbsp;·&nbsp; {vmode}</div>', unsafe_allow_html=True)

# ── KPI strip ─────────────────────────────────────────────────────────────────
ndyn, nrd = len(data["groups"]["dynasty"]), len(data["groups"]["redraft"])
kc = st.columns(4)
for col, (n, l, cls) in zip(kc, [
        (len(data["contexts"]), "Leagues", ""), (ndyn, "Dynasty", "c"),
        (nrd, "Redraft / Guillotine", "c"), (f"Wk {data['week']}", data["season"], "g")]):
    col.markdown(f'<div class="kpi"><div class="n {cls}">{n}</div><div class="l">{esc(l)}</div></div>',
                 unsafe_allow_html=True)

# ── per-league compute (cached objects are cheap; done once per render) ────────
def valuer_for(ctx):
    return Valuer(ctx, players, proj)

_DIGEST_CACHE = {}
def digest_for(ctx):
    lid = ctx["league_id"]
    if lid not in _DIGEST_CACHE:
        _DIGEST_CACHE[lid] = A.weekly_digest(ctx, valuer_for(ctx), players, trend)
    return _DIGEST_CACHE[lid]

# ── global action center: every move across every league, in one place ────────
def render_action_center():
    lineup, waivers, trades = [], [], []
    for ctx in data["contexts"]:
        d = digest_for(ctx)
        tag = ctx["name"]
        ss = d["start_sit"]
        if ss:
            for s_in, s_out in zip(ss["start"], ss["sit"]):
                lineup.append((tag, s_in, s_out))
        for w in d["waiver_rows"][:2]:
            waivers.append((tag, w))
        for t in d["trade_rows"][:1]:
            trades.append((tag, t))
    waivers.sort(key=lambda x: x[1]["buzz"], reverse=True)

    n_l, n_w, n_t = len(lineup), len(waivers), len(trades)
    st.markdown(
        f'<div class="actionwrap"><div class="actionhd">⚡ This Week — Every League at Once</div>'
        f'<div class="actionsub">One scan instead of logging into {len(data["contexts"])} leagues: '
        f'<b>{n_l}</b> lineup changes · <b>{n_w}</b> waiver targets · <b>{n_t}</b> trade ideas.</div></div>',
        unsafe_allow_html=True)
    cols = st.columns(3)
    with cols[0]:
        items = "".join(
            f'<span class="ai"><span class="tag">{esc(tag)}</span><br>'
            f'<span class="txt">Start <b class="g">{esc(a["name"])}</b> ({a["pts"]:.1f}) '
            f'over <span class="r">{esc(b["name"])}</span></span></span>'
            for tag, a, b in lineup[:8]) or '<div class="none">All lineups optimal 🎉</div>'
        st.markdown(f'<div class="lane"><div class="lh s">🟢 Lineup changes</div>{items}</div>', unsafe_allow_html=True)
    with cols[1]:
        def witem(tag, w):
            buzz = f' · +{w["buzz"]:,} adds' if w["buzz"] else ""
            return (f'<span class="ai"><span class="tag">{esc(tag)}</span><br>'
                    f'<span class="txt">Add <b>{esc(w["name"])}</b> {esc(w["pos"])}{buzz}</span></span>')
        items = "".join(witem(tag, w) for tag, w in waivers[:8]) or '<div class="none">No standout adds</div>'
        st.markdown(f'<div class="lane"><div class="lh w">🔵 Waiver targets</div>{items}</div>', unsafe_allow_html=True)
    with cols[2]:
        items = "".join(
            f'<span class="ai"><span class="tag">{esc(tag)}</span><br>'
            f'<span class="txt">Give <span class="r">{esc(t["give"]["name"])}</span> '
            f'→ get <b class="g">{esc(t["get"]["name"])}</b> <span style="color:#7e8db0">vs {esc(t["partner"])}</span></span></span>'
            for tag, t in trades[:8]) or '<div class="none">No clear win-win yet</div>'
        st.markdown(f'<div class="lane"><div class="lh t">🟡 Trade ideas</div>{items}</div>', unsafe_allow_html=True)

# ── renderers ─────────────────────────────────────────────────────────────────
def render_digest_card(ctx, klass):
    d = digest_for(ctx)
    me = ctx["my_roster"]
    rec = f'{me["wins"]}-{me["losses"]}' + (f'-{me["ties"]}' if me["ties"] else "") if me else "—"
    sf = ' <span class="badge sf">SF</span>' if ctx["superflex"] else ""
    def block(cls, title, items, empty):
        lis = "".join(f'<div class="i">• {esc(x)}</div>' for x in items) if items else f'<div class="none">{empty}</div>'
        return f'<div class="mv"><div class="h {cls}">{title}</div>{lis}</div>'
    ss = d["start_sit"]
    line_items = d["lineup_moves"] or (["Lineup is already optimal"] if ss and ss["set_lineup"] else ["Set your Week %d lineup" % data["week"]])
    st.markdown(
        f'<div class="lgcard {klass}"><h3>{esc(ctx["name"])}</h3>'
        f'<div class="meta">{esc(ctx["format"].title())}{sf} · {ctx["num_teams"]} teams · '
        f'{esc(ctx["scoring_label"])} · <span class="rec">you: {rec}</span></div>'
        + block("s", "Lineup", line_items, "—")
        + block("w", "Waivers", d["waivers"], "No clear adds")
        + block("t", "Trades", d["trades"], "No obvious win-win right now")
        + '</div>', unsafe_allow_html=True)

def render_overview(ctx):
    hdr("Standings")
    for t in ctx["standings"]:
        me = " me" if t["is_mine"] else ""
        rec = f'{t["wins"]}-{t["losses"]}' + (f'-{t["ties"]}' if t["ties"] else "")
        st.markdown(
            f'<div class="srow{me}"><div class="rk">{t["rank"]}</div>'
            f'<div class="tn">{esc(t["name"])}</div><div class="rec">{rec}</div>'
            f'<div class="pf">{t["fpts"]:.0f} PF</div></div>', unsafe_allow_html=True)

def player_row(r, klass, show_slot=True):
    slot = f'<div class="slot">{esc(r["slot"])}</div>' if show_slot and r.get("slot") else '<div class="slot"></div>'
    pts = f'{r["pts"]:.1f}' if r["pts"] else "—"
    return (f'<div class="prow {klass}">{slot}'
            f'<div class="nm">{esc(r["name"])}<span class="tm">{esc(r["team"])}</span>{inj_tag(r)}</div>'
            f'<div class="pos">{esc(r["pos"])}</div>'
            f'<div class="pts">{pts}</div><div class="val">{r["val"]:.0f}</div></div>')

def render_startsit(ctx):
    ss = A.start_sit(ctx, valuer_for(ctx), players)
    if not ss:
        st.markdown('<div class="empty">Couldn\'t find your roster in this league.</div>', unsafe_allow_html=True)
        return
    if ss["start"] and ss["sit"]:
        hdr("Recommended changes")
        for s_in, s_out in zip(ss["start"], ss["sit"]):
            st.markdown(
                f'<div class="swap"><div class="side"><div class="k in">START</div>'
                f'<div class="n">{esc(s_in["name"])} <span class="m">{esc(s_in["pos"])}·{esc(s_in["team"])} '
                f'· {s_in["pts"]:.1f} pts</span></div></div><div class="ar">▶</div>'
                f'<div class="side"><div class="k out">SIT</div>'
                f'<div class="n">{esc(s_out["name"])} <span class="m">{esc(s_out["pos"])}·{esc(s_out["team"])} '
                f'· {s_out["pts"]:.1f} pts</span></div></div></div>', unsafe_allow_html=True)
    elif ss["set_lineup"]:
        st.markdown('<div class="note">✅ Your lineup already matches the optimal projection.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="note">Lineup not set yet — here\'s the optimal Week {data["week"]} lineup.</div>', unsafe_allow_html=True)

    hdr(f"Optimal lineup · proj {ss['proj_total']:.1f}")
    st.markdown('<div class="thead"><div>SLOT</div><div>PLAYER</div><div>POS</div><div>PROJ</div><div>VAL</div></div>', unsafe_allow_html=True)
    st.markdown("".join(player_row(r, "st") for r in ss["lineup"]), unsafe_allow_html=True)
    if ss["bench"]:
        hdr("Bench")
        st.markdown("".join(player_row({**r, "slot": "BN"}, "be") for r in ss["bench"][:10]), unsafe_allow_html=True)

def render_waivers(ctx):
    rows = A.waiver_targets(ctx, valuer_for(ctx), players, trend, limit=15)
    if not rows:
        st.markdown('<div class="empty">No available players surfaced.</div>', unsafe_allow_html=True)
        return
    hdr("Top available — value + trending buzz")
    st.markdown('<div class="thead"><div>BUZZ</div><div>PLAYER</div><div>POS</div><div>PROJ</div><div>VAL</div></div>', unsafe_allow_html=True)
    for r in rows:
        buzz = f'+{r["buzz"]:,}' if r["buzz"] else "—"
        pts = f'{r["pts"]:.1f}' if r["pts"] else "—"
        st.markdown(
            f'<div class="prow st"><div class="slot">{buzz}</div>'
            f'<div class="nm">{esc(r["name"])}<span class="tm">{esc(r["team"])}</span>{inj_tag(r)}</div>'
            f'<div class="pos">{esc(r["pos"])}</div><div class="pts">{pts}</div>'
            f'<div class="val">{r["val"]:.0f}</div></div>', unsafe_allow_html=True)

def render_trades(ctx):
    if ctx["trades_disabled"]:
        st.markdown('<div class="note">🔒 Trades are <b>disabled</b> in this league (guillotine/elimination format).</div>', unsafe_allow_html=True)
        return
    v = valuer_for(ctx)
    teams, avg = A.positional_strength(ctx, v, players)
    mine = teams.get(ctx["my_roster"]["roster_id"]) if ctx["my_roster"] else None
    if mine:
        hdr("Your positional strength vs league average")
        cols = st.columns(4)
        for col, pos in zip(cols, ["QB", "RB", "WR", "TE"]):
            mv, av = mine["strength"][pos], avg[pos]
            cls = "g" if mv >= av else "c"
            delta = "▲" if mv >= av else "▼"
            col.markdown(f'<div class="kpi"><div class="n {cls}">{mv:.0f}</div>'
                         f'<div class="l">{pos} · {delta} avg {av:.0f}</div></div>', unsafe_allow_html=True)
    ideas = A.trade_ideas(ctx, v, players, max_ideas=6)
    hdr("Win-win trade ideas")
    kind = "dynasty asset" if ctx["format"] == "dynasty" else "win-now"
    if not ideas:
        st.markdown('<div class="empty">No clean win-win surfaced with current values — '
                    'this sharpens a lot once external trade values are connected.</div>', unsafe_allow_html=True)
        return
    for t in ideas:
        st.markdown(
            f'<div class="trade"><div class="top"><div class="p">vs {esc(t["partner"])} '
            f'<span class="w">· {kind} values</span></div>'
            f'<div class="fair">{t["fairness"]:.0f}% fair</div></div>'
            f'<div class="legs"><div class="leg"><div class="k r">YOU GIVE</div>'
            f'<div class="n">{esc(t["give"]["name"])} <span class="m">{esc(t["give"]["pos"])} · {t["give"]["val"]:.0f}</span></div></div>'
            f'<div class="leg"><div class="k g">YOU GET</div>'
            f'<div class="n">{esc(t["get"]["name"])} <span class="m">{esc(t["get"]["pos"])} · {t["get"]["val"]:.0f}</span></div></div></div>'
            f'<div class="why">{esc(t["rationale"])}</div></div>', unsafe_allow_html=True)

# ── group section (dynasty / redraft) ─────────────────────────────────────────
def render_group(group_key, klass, label):
    ctxs = data["groups"][group_key]
    if not ctxs:
        st.markdown(f'<div class="empty">No {label.lower()} leagues.</div>', unsafe_allow_html=True)
        return
    hdr(f"This week across your {label.lower()} leagues")
    for ctx in ctxs:
        render_digest_card(ctx, klass)

    hdr("League detail")
    names = [c["name"] for c in ctxs]
    pick = st.selectbox("League", names, key=f"pick_{group_key}", label_visibility="collapsed")
    ctx = next(c for c in ctxs if c["name"] == pick)
    tabs = st.tabs(["Overview", "Start / Sit", "Waivers", "Trades"])
    with tabs[0]:
        render_overview(ctx)
    with tabs[1]:
        render_startsit(ctx)
    with tabs[2]:
        render_waivers(ctx)
    with tabs[3]:
        render_trades(ctx)

# ── global action center (the one-stop-shop payoff) ───────────────────────────
render_action_center()

# ── top-level split: Dynasty vs Redraft/Guillotine ────────────────────────────
top = st.tabs([f"🟣 DYNASTY ({ndyn})", f"🔵 REDRAFT / GUILLOTINE ({nrd})"])
with top[0]:
    render_group("dynasty", "dyn", "Dynasty")
with top[1]:
    render_group("redraft", "rd", "Redraft / Guillotine")

st.markdown('<div class="note" style="margin-top:22px">Data: Sleeper public API · '
            'Projections live · Trade values proxy until the API step. '
            'Share this dashboard — anyone can enter their own Sleeper username above (or use <b>?u=username</b>).</div>',
            unsafe_allow_html=True)
