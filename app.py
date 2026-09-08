"""Fantasy Command Center — Sleeper.  Run:  streamlit run app.py
Username-driven so the same deploy serves you and anyone you share the link with
(?u=their_username).  Design mirrors the CFB Totals Edge dashboard."""
import streamlit as st
import sleeper as S
import analysis as A
import values as VAL
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
/* header stat rail (CFB-style metric strip) */
.rail{display:flex;flex-wrap:wrap;align-items:center;gap:9px 28px;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);padding:11px 4px;margin:2px 0 14px;}
.rail .it{display:flex;align-items:baseline;gap:7px;}
.rail .k{font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:1.1px;color:var(--mut);}
.rail .v{font-size:14.5px;font-weight:900;color:#eef3fc;font-family:'JetBrains Mono',monospace;}
.rail .v.g{color:var(--grn);} .rail .v.c{color:var(--cyan);} .rail .v.a{color:var(--amb);} .rail .v.v{color:var(--vio);}
.rail .sp{flex:1;min-width:8px;}
.rail .upd{font-size:10.5px;color:#5b688a;letter-spacing:.7px;text-transform:uppercase;font-weight:700;}
/* selected KPI tile */
.kpi.on{border-color:var(--grn);box-shadow:0 0 0 1px rgba(25,229,155,.28) inset,0 0 24px rgba(25,229,155,.07);}
/* st.pills -> screenshot filter chips */
div[data-testid="stPills"] button,div[data-testid="stButtonGroup"] button{
  border-radius:22px!important;border:1px solid var(--line)!important;background:transparent!important;
  color:#9fb0d0!important;font-weight:700!important;font-size:12.5px!important;padding:6px 17px!important;}
div[data-testid="stPills"] button:hover,div[data-testid="stButtonGroup"] button:hover{
  border-color:#2e4470!important;color:#dbe4f7!important;}
div[data-testid="stPills"] button[aria-checked="true"],div[data-testid="stButtonGroup"] button[aria-checked="true"],
div[data-testid="stPills"] button[kind="pillsActive"],div[data-testid="stButtonGroup"] button[kind="pillsActive"]{
  border-color:var(--grn)!important;color:var(--grn)!important;background:rgba(25,229,155,.10)!important;}
/* league subheader inside an action lane (one per league, not per row) */
.lane .lgh{font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.9px;color:#8ea0c4;
  margin:13px 0 7px;padding-bottom:4px;border-bottom:1px dashed #1c2942;}
.lane .lgh.first{margin-top:2px;}
.ai .why{color:#7e8db0;font-size:11px;display:block;margin-top:1px;line-height:1.35;}
.ai .alt{color:var(--cyan);font-weight:700;}
.ai .sl{color:#8ea0c4;font-weight:800;font-size:10px;text-transform:uppercase;letter-spacing:.4px;margin-right:4px;}
.prow .whyline{color:#7e8db0;font-size:10.5px;font-weight:600;display:block;margin-top:2px;}
.swap .side .alt{color:var(--cyan);font-weight:700;font-size:12.5px;}
.swap .slotk{position:absolute;}
/* trade calculator */
.verdict{border-radius:14px;padding:13px 18px;margin:10px 0 4px;font-size:14px;font-weight:800;
  border:1px solid var(--line);background:linear-gradient(160deg,var(--card),var(--card2));}
.verdict.win{border-color:var(--grn);color:var(--grn);background:rgba(25,229,155,.08);}
.verdict.even{border-color:#2e4470;color:#c7d2ea;}
.verdict.lose{border-color:var(--red);color:var(--red);background:rgba(255,77,115,.07);}
.verdict .sub{display:block;font-size:12px;font-weight:600;color:#9fb0d0;margin-top:4px;}
/* league tag on a trade card */
.trade .lg{display:inline-block;font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;
  color:#8ea0c4;background:#0e1830;border:1px solid #23345a;border-radius:6px;padding:2px 8px;margin-right:8px;}
.trade .trend{font-size:11px;font-weight:800;margin-left:7px;}
.trade .trend.up{color:var(--grn);} .trade .trend.dn{color:var(--red);}
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

_TRADE_CACHE = {}
def trades_for(ctx, max_ideas=6):
    """Trade ideas per league, computed once — the global tab and the per-league
    detail view both read this."""
    lid = ctx["league_id"]
    if lid not in _TRADE_CACHE:
        _TRADE_CACHE[lid] = A.trade_ideas(ctx, valuer_for(ctx), players, max_ideas=max_ideas)
    return _TRADE_CACHE[lid]


# ── per-league deep dive ──────────────────────────────────────────────────────
def render_league_detail(ctx):
    """Standings, optimal lineup, waivers and trades for one league.

    This used to be a top-level Dynasty/Redraft tab; it now hangs off the This
    Week league filter, since picking a league there is the same choice.
    """
    me = ctx["my_roster"]
    rec = (f'{me["wins"]}-{me["losses"]}' + (f'-{me["ties"]}' if me["ties"] else "")) if me else "—"
    sf = ' · <b>superflex</b>' if ctx["superflex"] else ""
    st.markdown(f'<div class="note">{esc(ctx["format"].title())} · {ctx["num_teams"]} teams · '
                f'{esc(ctx["scoring_label"])}{sf} &nbsp;·&nbsp; your record: <b>{rec}</b></div>',
                unsafe_allow_html=True)
    tabs = st.tabs(["Overview", "Start / Sit", "Waivers", "Trades"])
    with tabs[0]:
        render_overview(ctx)
    with tabs[1]:
        render_startsit(ctx)
    with tabs[2]:
        render_waivers(ctx)
    with tabs[3]:
        render_trades(ctx)


# ── header stat rail ──────────────────────────────────────────────────────────
def render_stat_rail():
    w = l = t = 0
    for ctx in data["contexts"]:
        me = ctx["my_roster"]
        if me:
            w += me["wins"]; l += me["losses"]; t += me["ties"]
    n_moves = n_trades = 0
    for ctx in data["contexts"]:
        d = digest_for(ctx)
        ss = d["start_sit"]
        n_moves += len(ss["start"]) if ss else 0
        n_trades += len(trades_for(ctx))
    rec = f"{w}-{l}" + (f"-{t}" if t else "")
    pct = (100.0 * w / (w + l)) if (w + l) else 0.0
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        upd = datetime.now(ZoneInfo("America/New_York")).strftime("%-I:%M %p ET")
    except Exception:
        upd = ""
    items = [
        ("Combined record", rec, "g" if pct >= 50 else ""),
        ("Win %", f"{pct:.0f}%", "g" if pct >= 50 else "a"),
        ("Lineup moves", str(n_moves), "c"),
        ("Trade ideas", str(n_trades), "a"),
        ("Leagues", f"{len(data['contexts'])}", "v"),
    ]
    inner = "".join(f'<div class="it"><span class="k">{esc(k)}</span>'
                    f'<span class="v {c}">{esc(v)}</span></div>' for k, v, c in items)
    st.markdown(f'<div class="rail">{inner}<div class="sp"></div>'
                f'<div class="upd">Updated {esc(upd)}</div></div>', unsafe_allow_html=True)


# ── global action center: every move across every league, in one place ────────
def render_action_center():
    ctxs = data["contexts"]
    opts = ["All leagues"] + [c["name"] for c in ctxs]
    pick = st.pills("League", opts, default="All leagues", key="ac_league",
                    label_visibility="collapsed") or "All leagues"
    active = ctxs if pick == "All leagues" else [c for c in ctxs if c["name"] == pick]

    lineup, waivers, trades = {}, {}, {}
    for ctx in active:
        d = digest_for(ctx)
        nm = ctx["name"]
        ss = d["start_sit"]
        if ss and ss["swaps"]:
            lineup[nm] = ss["swaps"]
        w = [x for x in d["waiver_rows"][:3] if x["score"] > 0]
        if w:
            waivers[nm] = w
        t = trades_for(ctx)[:2]
        if t:
            trades[nm] = t

    n_l = sum(len(v) for v in lineup.values())
    n_w = sum(len(v) for v in waivers.values())
    n_t = sum(len(v) for v in trades.values())
    scope = f"{len(active)} league" + ("s" if len(active) != 1 else "")
    st.markdown(
        f'<div class="actionwrap"><div class="actionhd">⚡ This Week — Every League at Once</div>'
        f'<div class="actionsub">One scan instead of logging into {scope}: '
        f'<b>{n_l}</b> lineup changes · <b>{n_w}</b> waiver targets · <b>{n_t}</b> trade ideas.</div></div>',
        unsafe_allow_html=True)

    def lane(cls, title, groups, item_fn, empty):
        """One column. Each league name appears once as a subheader, then its rows."""
        if not groups:
            body = f'<div class="none">{empty}</div>'
        else:
            parts = []
            for i, (nm, items) in enumerate(groups.items()):
                parts.append(f'<div class="lgh{" first" if i == 0 else ""}">{esc(nm)}</div>')
                parts.extend(item_fn(x) for x in items)
            body = "".join(parts)
        st.markdown(f'<div class="lane"><div class="lh {cls}">{title}</div>{body}</div>',
                    unsafe_allow_html=True)

    def swap_item(sw):
        alt = "".join(f' <span class="alt">or {esc(a["name"])}</span>' for a in sw["alts"])
        gain = f' <span class="g">+{sw["gain"]:.1f}</span>' if sw["gain"] > 0 else ""
        return (f'<span class="ai"><span class="txt"><span class="sl">{esc(sw["slot"])}</span>'
                f'Start <b class="g">{esc(sw["in"]["name"])}</b>{alt} '
                f'over <span class="r">{esc(sw["out"]["name"])}</span>{gain}</span></span>')

    def waiver_item(w):
        return (f'<span class="ai"><span class="txt">Add <b>{esc(w["name"])}</b> '
                f'{esc(w["pos"])}</span>'
                + (f'<span class="why">{esc(w["why"])}</span>' if w.get("why") else "")
                + '</span>')

    def trade_item(t):
        return (f'<span class="ai"><span class="txt">Give <span class="r">{esc(t["give"]["name"])}</span> '
                f'→ get <b class="g">{esc(t["get"]["name"])}</b></span>'
                f'<span class="why">vs {esc(t["partner"])} · {t["fairness"]:.0f}% fair</span></span>')

    cols = st.columns(3)
    with cols[0]:
        lane("s", "🟢 Lineup changes", lineup, swap_item, "All lineups optimal 🎉")
    with cols[1]:
        lane("w", "🔵 Waiver targets", waivers, waiver_item, "No standout adds")
    with cols[2]:
        lane("t", "🟡 Trade ideas", trades, trade_item, "No clear win-win yet")

    if pick != "All leagues" and active:
        hdr(f"{active[0]['name']} — league detail")
        render_league_detail(active[0])

# ── renderers ─────────────────────────────────────────────────────────────────
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
    if ss["swaps"]:
        hdr("Recommended changes")
        for sw in ss["swaps"]:
            s_in, s_out = sw["in"], sw["out"]
            alt = "".join(
                f'<div class="alt">or {esc(a["name"])} '
                f'<span class="m">{esc(a["pos"])}·{a["pts"]:.1f}</span></div>'
                for a in sw["alts"])
            gain = f' · <span style="color:#19e59b">+{sw["gain"]:.1f}</span>' if sw["gain"] > 0 else ""
            st.markdown(
                f'<div class="swap"><div class="side"><div class="k in">START · {esc(sw["slot"])}{gain}</div>'
                f'<div class="n">{esc(s_in["name"])} <span class="m">{esc(s_in["pos"])}·{esc(s_in["team"])} '
                f'· {s_in["pts"]:.1f} pts</span></div>{alt}</div><div class="ar">▶</div>'
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
    hdr("Top available — lineup gain, positional need, then buzz")
    st.markdown('<div class="thead"><div>BUZZ</div><div>PLAYER</div><div>POS</div><div>PROJ</div><div>VAL</div></div>', unsafe_allow_html=True)
    for r in rows:
        buzz = f'+{r["buzz"]:,}' if r["buzz"] else "—"
        pts = f'{r["pts"]:.1f}' if r["pts"] else "—"
        why = f'<span class="whyline">{esc(r["why"])}</span>' if r.get("why") else ""
        st.markdown(
            f'<div class="prow st"><div class="slot">{buzz}</div>'
            f'<div class="nm">{esc(r["name"])}<span class="tm">{esc(r["team"])}</span>{inj_tag(r)}{why}</div>'
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
    ideas = trades_for(ctx)
    hdr("Win-win trade ideas")
    kind = "dynasty asset" if ctx["format"] == "dynasty" else "win-now"
    if not ideas:
        st.markdown('<div class="empty">No clean win-win surfaced with current values — '
                    'this sharpens a lot once external trade values are connected.</div>', unsafe_allow_html=True)
        return
    for t in ideas:
        st.markdown(trade_card(t, ctx), unsafe_allow_html=True)


def trade_leg(rows, kind):
    """One side of a deal. Shows FantasyCalc's own value per player so the number
    can be checked against fantasycalc.com directly."""
    k = "r" if kind == "give" else "g"
    label = "YOU GIVE" if kind == "give" else "YOU GET"
    body = "".join(
        f'<div class="n">{esc(r["name"])} <span class="m">{esc(r["pos"])}·{esc(r["team"])}'
        + (f' · {r["raw"]:,}' if r.get("raw") else "") + '</span></div>'
        for r in rows)
    return f'<div class="leg"><div class="k {k}">{label}</div>{body}</div>'


def trade_card(t, ctx, extra=""):
    kind = "dynasty asset" if ctx["format"] == "dynasty" else "win-now"
    gives, gets = t.get("gives", [t["give"]]), t.get("gets", [t["get"]])
    shape = f'<span class="lg">{esc(t.get("shape", "1-for-1"))}</span>'
    return (f'<div class="trade"><div class="top">'
            f'<div class="p">{shape}vs {esc(t["partner"])} '
            f'<span class="w">· {kind} values</span></div>'
            f'<div class="fair">{t["fairness"]:.0f}% fair</div></div>'
            f'<div class="legs">{trade_leg(gives, "give")}{trade_leg(gets, "get")}</div>'
            f'{extra}<div class="why">{esc(t["rationale"])}</div></div>')


# ── global trade ideas tab: every league's win-win swaps in one board ─────────
def render_trade_ideas_global():
    pool, blocked = [], []
    for ctx in data["contexts"]:
        if ctx["trades_disabled"]:
            blocked.append(ctx["name"])
            continue
        for t in trades_for(ctx):
            pool.append((ctx, t))

    if not pool:
        st.markdown('<div class="empty">No clean win-win surfaced across your leagues right now. '
                    'Ideas appear when one of your surplus positions lines up with a rival\'s need '
                    'at comparable value.</div>', unsafe_allow_html=True)
        if blocked:
            st.markdown(f'<div class="note">🔒 Trades disabled in: <b>{esc(", ".join(blocked))}</b> '
                        '(guillotine/elimination format).</div>', unsafe_allow_html=True)
        return

    dyn = [x for x in pool if x[0]["format"] == "dynasty"]
    rd = [x for x in pool if x[0]["format"] != "dynasty"]
    best = max(t["fairness"] for _, t in pool)

    kc = st.columns(4)
    tiles = [(len(pool), "Total ideas", "g", True), (len(dyn), "Dynasty", "v", False),
             (len(rd), "Redraft", "c", False), (f"{best:.0f}%", "Best fairness", "g", False)]
    for col, (n, l, cls, on) in zip(kc, tiles):
        col.markdown(f'<div class="kpi{" on" if on else ""}"><div class="n {cls}">{n}</div>'
                     f'<div class="l">{esc(l)}</div></div>', unsafe_allow_html=True)

    fmt_opts = ["All ideas", f"Dynasty ({len(dyn)})", f"Redraft ({len(rd)})"]
    pick = st.pills("Format", fmt_opts, default="All ideas", key="trade_fmt",
                    label_visibility="collapsed") or "All ideas"
    rows = dyn if pick.startswith("Dynasty") else rd if pick.startswith("Redraft") else pool

    if not rows:
        st.markdown('<div class="empty">No ideas in that format.</div>', unsafe_allow_html=True)
        return

    # group by league, best idea first within each — mirrors the day-grouped board
    by_league = {}
    for ctx, t in rows:
        by_league.setdefault(ctx["name"], (ctx, []))[1].append(t)
    order = sorted(by_league.values(), key=lambda x: max(t["fairness"] for t in x[1]), reverse=True)

    v_cache = {}
    for ctx, ideas in order:
        kind = "dynasty asset" if ctx["format"] == "dynasty" else "win-now"
        hdr(ctx["name"])
        v = v_cache.setdefault(ctx["league_id"], valuer_for(ctx))
        for t in sorted(ideas, key=lambda x: x["my_net"], reverse=True):
            tr = v.trend30(t["get"]["id"]) if hasattr(v, "trend30") else 0
            trend = (f'<div class="why" style="margin-top:6px">30-day trend on '
                     f'{esc(t["get"]["name"])}: '
                     f'<span class="trend {"up" if tr > 0 else "dn"}">'
                     f'{"▲" if tr > 0 else "▼"} {abs(tr):,}</span></div>') if tr else ""
            st.markdown(trade_card(t, ctx, trend), unsafe_allow_html=True)

    if blocked:
        st.markdown(f'<div class="note" style="margin-top:16px">🔒 Trades disabled in: '
                    f'<b>{esc(", ".join(blocked))}</b> (guillotine/elimination format).</div>',
                    unsafe_allow_html=True)


# ── interactive trade calculator ──────────────────────────────────────────────
def render_trade_calc():
    tradeable = [c for c in data["contexts"] if not c["trades_disabled"] and c["my_roster"]]
    if not tradeable:
        st.markdown('<div class="empty">No leagues with trading enabled.</div>',
                    unsafe_allow_html=True)
        return

    c1, c2 = st.columns(2)
    lname = c1.selectbox("League", [c["name"] for c in tradeable], key="calc_lg")
    ctx = next(c for c in tradeable if c["name"] == lname)
    partners = [t for t in ctx["teams"] if not t["is_mine"]]
    if not partners:
        st.markdown('<div class="empty">No other teams found.</div>', unsafe_allow_html=True)
        return
    pname = c2.selectbox("Trade partner", [t["name"] for t in partners], key="calc_pt")
    partner = next(t for t in partners if t["name"] == pname)
    me = next(t for t in ctx["teams"] if t["is_mine"])

    v = valuer_for(ctx)
    fmt = "dynasty" if ctx["format"] == "dynasty" else "redraft"

    def rows_for(team):
        rows = [{**pinfo(pid, players), "raw": v.raw_value(pid),
                 "val": v.value(pid), "pts": v.points(pid)} for pid in team["players"]]
        return sorted(rows, key=lambda r: (r["raw"], r["val"]), reverse=True)

    mine_rows, their_rows = rows_for(me), rows_for(partner)

    # ── rookie picks (dynasty only) ──────────────────────────────────────────
    pranks, rec_weight = A.power_rankings(ctx, v, players)
    if ctx["format"] == "dynasty" and v.pick_scale():
        rank_by_rid = {r["rid"]: r["proj_rank"] for r in pranks}
        name_by_rid = {t["roster_id"]: t["name"] for t in ctx["teams"]}
        cur = int(ctx.get("season") or data["season"])
        seasons = [cur + 1, cur + 2, cur + 3]
        inv = A.pick_inventory(ctx, seasons)
        scale = v.pick_scale()

        def pick_rows(team):
            out = []
            for pk in inv.get(team["roster_id"], []):
                orig = pk["original_rid"]
                tier = A.pick_tier(rank_by_rid.get(orig, ctx["num_teams"]), ctx["num_teams"])
                raw = v.pick_value(pk["season"], pk["round"], tier)
                if not raw:
                    continue
                suffix = VAL.ROUND_SUFFIX.get(pk["round"], f'{pk["round"]}th')
                # the ORIGINAL owner sets the draft slot, so that's the name to show
                owner_name = name_by_rid.get(orig, "?")
                if orig != team["roster_id"]:
                    owner_name += " (acquired)"
                out.append({"id": f'PICK|{pk["season"]}|{pk["round"]}|{orig}',
                            "name": f'{pk["season"]} {suffix} ({tier})',
                            "pos": "PICK", "team": owner_name,
                            "raw": raw, "val": round(raw * scale, 1), "pts": 0.0,
                            "injury": None})
            return sorted(out, key=lambda r: r["raw"], reverse=True)

        mine_rows += pick_rows(me)
        their_rows += pick_rows(partner)

    look = {r["id"]: r for r in mine_rows + their_rows}

    def label(pid):
        r = look[pid]
        tag = f'{r["raw"]:,}' if r["raw"] else "unpriced"
        if r["pos"] == "PICK":
            return f'🎟 {r["name"]} · {r["team"]} · {tag}'
        return f'{r["name"]} · {r["pos"]}-{r["team"]} · {tag}'

    s1, s2 = st.columns(2)
    send = s1.multiselect("You send", [r["id"] for r in mine_rows],
                          format_func=label, key="calc_send")
    recv = s2.multiselect("You get", [r["id"] for r in their_rows],
                          format_func=label, key="calc_recv")

    if not send and not recv:
        st.markdown('<div class="note">Pick players from each side to price the deal. '
                    f'Values are <b>FantasyCalc {esc(fmt)}</b>, format-adjusted for '
                    f'{ctx["num_teams"]} teams{" · superflex" if ctx["superflex"] else ""}.</div>',
                    unsafe_allow_html=True)
        return

    give_rows = [look[p] for p in send]
    get_rows = [look[p] for p in recv]
    gr = sum(r["raw"] for r in give_rows)
    tr_ = sum(r["raw"] for r in get_rows)
    diff = tr_ - gr
    fairness = (100 - abs(diff) / max(gr, tr_) * 100) if max(gr, tr_) else 0

    kc = st.columns(4)
    tiles = [(f"{gr:,}", "You send", "", False), (f"{tr_:,}", "You get", "", False),
             (f"{diff:+,}", "Net value", "g" if diff >= 0 else "", diff >= 0),
             (f"{fairness:.0f}%", "Fairness", "g" if fairness >= 85 else "c", False)]
    for col, (n, l, cls, on) in zip(kc, tiles):
        col.markdown(f'<div class="kpi{" on" if on else ""}"><div class="n {cls}">{n}</div>'
                     f'<div class="l">{esc(l)}</div></div>', unsafe_allow_html=True)

    # value over replacement for both rosters — the "does this actually help" test
    ded = A._dedicated_slots(ctx["roster_positions"])
    my_repl = A._replacement(ctx, v, players, me["roster_id"], ded)
    their_repl = A._replacement(ctx, v, players, partner["roster_id"], ded)
    my_net = (A._surplus_over_replacement(get_rows, my_repl)
              - A._surplus_over_replacement(give_rows, my_repl))
    their_net = (A._surplus_over_replacement(give_rows, their_repl)
                 - A._surplus_over_replacement(get_rows, their_repl))

    # weekly lineup impact on my roster
    my_pids = [str(x) for x in me["players"]]
    real = lambda ids: [x for x in ids if not str(x).startswith("PICK|")]
    after = [x for x in my_pids if x not in set(send)] + real(recv)

    def lp(pids):
        lu, _ = A.optimal_lineup(pids, ctx["roster_positions"], players, v.start_score)
        return sum(v.points(pid) for _, pid in lu if pid)

    d_pts = lp(after) - lp(my_pids)

    if my_net > 0 and their_net > 0:
        cls, head = "win", "Win-win — both rosters improve over replacement"
    elif my_net > 0:
        cls, head = "even", "Good for you — but they have little reason to accept"
    elif my_net <= 0 and their_net > 0:
        cls, head = "lose", "You're giving up more than you get"
    else:
        cls, head = "even", "Neither side clearly gains"
    st.markdown(
        f'<div class="verdict {cls}">{esc(head)}'
        f'<span class="sub">Surplus over replacement — asset value on a 0–100 scale, '
        f'<b>not</b> fantasy points: you {my_net:+.1f} · them {their_net:+.1f}'
        f'&nbsp;&nbsp;·&nbsp;&nbsp; Week {data["week"]} projected lineup: '
        f'<b>{d_pts:+.1f} pts</b> (weekly, not season-long)</span></div>',
        unsafe_allow_html=True)

    if ctx["format"] == "dynasty" and v.pick_scale():
        with st.expander("Projected draft order — what sets each pick's tier"):
            st.markdown(
                f'<div class="note">Rookie order is reverse standings, so the projected '
                f'<b>worst</b> team owns the <b>Early</b> (most valuable) pick. Projection blends '
                f'roster value with record; record currently carries <b>{rec_weight*100:.0f}%</b> '
                f'of the weight and grows as games are played.</div>', unsafe_allow_html=True)
            for r in reversed(pranks):
                tier = A.pick_tier(r["proj_rank"], ctx["num_teams"])
                me_c = " me" if r["is_mine"] else ""
                st.markdown(
                    f'<div class="srow{me_c}"><div class="rk">{ctx["num_teams"] - r["proj_rank"] + 1}</div>'
                    f'<div class="tn">{esc(r["name"])}</div>'
                    f'<div class="rec">{esc(r["record"])}</div>'
                    f'<div class="pf">{esc(tier)}</div></div>', unsafe_allow_html=True)

    if len(send) != len(recv) and send and recv:
        st.markdown(f'<div class="note">📦 <b>{len(send)}-for-{len(recv)}</b> — the side '
                    'receiving fewer players needs the best player in the deal, and the side '
                    'sending more frees a roster spot. Value over replacement above already '
                    'accounts for the depth you keep.</div>', unsafe_allow_html=True)


# ── header stat rail ──────────────────────────────────────────────────────────
render_stat_rail()

# ── top-level board ───────────────────────────────────────────────────────────
top = st.tabs(["⚡ This Week", "🤝 Trade Ideas", "🧮 Trade Calculator"])
with top[0]:
    render_action_center()
with top[1]:
    render_trade_ideas_global()
with top[2]:
    render_trade_calc()

st.markdown('<div class="note" style="margin-top:22px">Data: Sleeper public API · '
            'Projections live · Trade values from FantasyCalc. '
            'Share this dashboard — anyone can enter their own Sleeper username above (or use <b>?u=username</b>).</div>',
            unsafe_allow_html=True)
