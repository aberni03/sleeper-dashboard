"""Fantasy Command Center — Sleeper.  Run:  streamlit run app.py
Username-driven so the same deploy serves you and anyone you share the link with
(?u=their_username).  Design mirrors the CFB Totals Edge dashboard."""
import streamlit as st
import sleeper as S
import analysis as A
import values as VAL
import fantasypros as FP
from urllib.parse import quote_plus
from values import Valuer, ENABLE_EXTERNAL, pinfo, FLEX_ELIG

st.set_page_config(page_title="Fantasy Command Center", page_icon="🏈",
                   layout="wide", initial_sidebar_state="collapsed")

# Streamlit ships a viewport meta tag, but a deployed app can end up rendered at
# desktop width on a phone if anything overrides it; assert it explicitly.
st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1">',
            unsafe_allow_html=True)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@600;700&display=swap');
:root{--bg:#070b16;--card:#111a2e;--card2:#0c1424;--line:#1e2c47;--txt:#eef3fc;--mut:#7e8db0;
--grn:#19e59b;--red:#ff4d73;--amb:#ffc24b;--cyan:#38d6ff;--vio:#8b7bff;}
*{font-family:'Inter',sans-serif;}
.stApp{background:radial-gradient(1200px 500px at 15% -10%,#132449 0%,#070b16 55%) fixed;}
#MainMenu,footer{visibility:hidden;}
header[data-testid="stHeader"]{display:none!important;height:0!important;}
div[data-testid="stToolbar"]{display:none!important;}
div[data-testid="stDecoration"]{display:none!important;}
/* Streamlit sizes this container itself and its rule outranks a bare class
   selector, which is why the top gap survived hiding the header. Target the
   testid it actually ships. The bottom padding is generous for a scrolling doc
   and wasteful for a dashboard meant to be read in one screen. */
[data-testid="stMainBlockContainer"],.block-container{
  padding-top:.45rem!important;padding-bottom:1.25rem!important;max-width:1200px;}
.mono{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums;}
.masthome{text-decoration:none!important;color:inherit!important;display:block;cursor:pointer;}
.masthome:hover .ac{filter:brightness(1.12);}
.mast{padding:0 2px 0;}
.mast h1{font-size:26px;font-weight:900;color:#fff;margin:0;letter-spacing:-.6px;
  display:flex;align-items:baseline;gap:11px;flex-wrap:wrap;}
.mast h1 .ac{background:linear-gradient(90deg,var(--grn),var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.mast h1 .kicker{font-size:11px;font-weight:800;letter-spacing:1.7px;color:var(--mut);text-transform:uppercase;}
.mast .sub{color:var(--mut);font-size:12.5px;margin-top:2px;}
.statusline{display:flex;flex-wrap:wrap;gap:6px 22px;align-items:center;padding:2px 2px 0;
  font-size:11px;font-weight:700;letter-spacing:.9px;text-transform:uppercase;color:var(--mut);}
.statusline b{color:#c7d2ea;}
.statusline .on{color:var(--grn);}
.note{background:linear-gradient(160deg,#10233f,#0b1526);border:1px solid #26406a;border-radius:8px;
  padding:8px 13px;margin:2px 0 10px;color:#9fb0d0;font-size:12px;} .note b{color:#c7d2ea;}
.kpi{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);
  border-radius:10px;padding:12px 16px;margin-bottom:10px;}
.kpi .n{font-size:25px;font-weight:900;color:var(--txt);line-height:1;} .kpi .n.g{color:var(--grn);} .kpi .n.c{color:var(--cyan);}
.kpi .l{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:1px;margin-top:6px;font-weight:600;}
.daybar{display:flex;align-items:center;gap:10px;margin:13px 0 8px;}
.daybar span{color:#cdd7ee;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;}
.daybar .ln{flex:1;height:1px;background:linear-gradient(90deg,var(--line),transparent);}
button[data-baseweb="tab"]{font-size:14px!important;font-weight:800!important;letter-spacing:.6px;text-transform:uppercase;color:#6f7f9e!important;padding:8px 2px!important;}
button[data-baseweb="tab"]:hover{color:#c7d2ea!important;}
button[data-baseweb="tab"][aria-selected="true"]{color:#eef3fc!important;}
div[data-baseweb="tab-list"]{gap:26px!important;border-bottom:1px solid #17233b;margin-bottom:9px;}
div[data-baseweb="tab-highlight"]{background:#19e59b!important;height:2.5px!important;}
div[data-baseweb="tab-border"]{display:none!important;}
/* league digest card */
.lgcard{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);
  border-left:4px solid #23324f;border-radius:10px;padding:14px 18px;margin-bottom:11px;}
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
  border-radius:6px;padding:9px 14px;margin-bottom:5px;font-size:13px;}
.prow.st{border-left-color:var(--grn);} .prow.be{border-left-color:#39415a;opacity:.9;}
.prow .slot{color:var(--mut);font-size:11px;font-weight:800;text-transform:uppercase;}
.prow .nm{color:#fff;font-weight:700;} .prow .nm .tm{color:var(--mut);font-weight:600;font-size:11px;margin-left:6px;}
.prow .nm .inj{color:var(--red);font-weight:800;font-size:10px;margin-left:6px;}
.prow .pos{color:#b9c6e3;font-weight:700;text-align:center;}
.prow .pts{color:#fff;font-weight:800;text-align:right;font-family:'JetBrains Mono',monospace;}
.prow .val{color:var(--mut);text-align:right;font-family:'JetBrains Mono',monospace;}
/* swap + trade cards */
.swap{display:grid;grid-template-columns:1fr 34px 1fr;gap:10px;align-items:center;
  background:linear-gradient(160deg,#12203b,#0c1424);border:1px solid #26406a;border-radius:8px;padding:11px 15px;margin-bottom:8px;}
.swap .side .k{font-size:9.5px;text-transform:uppercase;letter-spacing:.7px;font-weight:800;}
.swap .side .k.in{color:var(--grn);} .swap .side .k.out{color:var(--red);}
.swap .side .n{color:#fff;font-weight:700;font-size:14px;} .swap .side .n .m{color:var(--mut);font-size:11px;font-weight:600;}
.swap .ar{color:var(--grn);font-size:18px;font-weight:900;text-align:center;}
.trade{background:linear-gradient(160deg,#13203b,#0c1424);border:1px solid #2a3a5c;border-radius:10px;padding:14px 18px;margin-bottom:10px;}
.trade .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px;}
.trade .top .p{color:#fff;font-weight:800;font-size:15px;} .trade .top .p .w{color:var(--mut);font-weight:600;font-size:12px;}
.trade .fair{background:rgba(25,229,155,.16);color:var(--grn);font-weight:800;font-size:12px;padding:4px 11px;border-radius:4px;}
.trade .legs{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.trade .leg{background:#0e1830;border:1px solid var(--line);border-radius:6px;padding:10px 13px;}
.trade .leg .k{font-size:10px;text-transform:uppercase;letter-spacing:.6px;font-weight:800;margin-bottom:4px;}
.trade .leg .k.g{color:var(--grn);} .trade .leg .k.r{color:var(--red);}
.trade .leg .n{color:#fff;font-weight:700;font-size:14px;} .trade .leg .n .m{color:var(--mut);font-size:11px;}
.trade .why{color:#9fb0d0;font-size:12px;margin-top:9px;line-height:1.5;}
.trade .impact2{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;margin-top:9px;
  padding-top:8px;border-top:1px solid var(--line);font-size:11.5px;font-weight:700;color:#8ea0c4;}
.trade .impact2.second{border-top:none;padding-top:0;margin-top:3px;}
.trade .impact2 .vs2{color:#4d5975;font-size:10px;text-transform:uppercase;letter-spacing:.6px;}
.trade .impact2 .g{color:var(--grn);} .trade .impact2 .r{color:var(--red);}
/* standings */
.srow{display:grid;grid-template-columns:30px 1fr 70px 90px;gap:10px;align-items:center;
  background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);border-radius:6px;padding:8px 14px;margin-bottom:4px;font-size:13px;}
.srow.me{border-color:var(--grn);box-shadow:0 0 0 1px rgba(25,229,155,.25) inset;}
.srow .rk{color:var(--mut);font-weight:800;text-align:center;} .srow .tn{color:#eef3fc;font-weight:700;} .srow.me .tn{color:var(--grn);}
.srow .rec{color:#c7d2ea;text-align:center;font-weight:700;} .srow .pf{color:var(--mut);text-align:right;font-family:'JetBrains Mono',monospace;}
.badge{display:inline-block;padding:3px 10px;border-radius:3px;font-size:11px;font-weight:800;}
.badge.dyn{background:rgba(139,123,255,.18);color:var(--vio);} .badge.rd{background:rgba(56,214,255,.16);color:var(--cyan);}
.badge.sf{background:rgba(255,194,75,.16);color:var(--amb);} .badge.off{background:#2a3040;color:#8b93a7;}
.empty{color:#5b688a;font-size:13px;font-style:italic;padding:8px 2px;}
/* global action center */
.actionwrap{background:linear-gradient(120deg,#122748,#0b1424);border:1px solid #24365d;
  border-radius:10px;padding:10px 16px;margin:4px 0 10px;position:relative;overflow:hidden;}
.actionwrap:before{content:'';position:absolute;left:-30px;top:-50px;width:170px;height:170px;
  background:radial-gradient(circle,rgba(25,229,155,.13),transparent 70%);}
.actionhd{font-size:14.5px;font-weight:900;color:#fff;letter-spacing:.3px;margin:0;
  display:flex;align-items:baseline;justify-content:space-between;gap:14px;flex-wrap:wrap;}
.actionhd .counts{font-size:11px;font-weight:700;color:var(--mut);letter-spacing:.5px;
  text-transform:uppercase;} .actionhd .counts b{color:var(--grn);font-weight:900;}
.actionsub{color:var(--mut);font-size:12px;margin:4px 0 2px;} .actionsub b{color:var(--grn);}
.lane .lh{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.9px;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #1c2942;}
.lane .lh.s{color:var(--grn);} .lane .lh.w{color:var(--cyan);} .lane .lh.t{color:var(--amb);}
.ai{display:block;margin-bottom:9px;line-height:1.4;} .ai .tag{display:inline-block;font-size:9.5px;font-weight:800;color:#8ea0c4;
  background:#0e1830;border:1px solid #23345a;border-radius:3px;padding:1px 6px;margin-bottom:2px;text-transform:uppercase;letter-spacing:.4px;}
.ai .txt{color:#e7edf7;font-size:13px;} .ai .txt b{color:#fff;} .ai .txt .g{color:var(--grn);font-weight:700;} .ai .txt .r{color:var(--red);}
.lane .none{color:#5b688a;font-size:12.5px;font-style:italic;}
/* a timestamp, not a headline: the bold uppercase letter-spaced treatment was
   what made this read loud, more than its size */
.upd{font-size:9.5px;color:#46536f;letter-spacing:.2px;font-weight:500;
  text-align:right;margin:4px 2px 0;white-space:nowrap;}
/* header controls: a small input and a quiet ghost button, not two big blocks */
.hdrctl div[data-testid="stTextInput"] input{
  background:#0d1526!important;border:1px solid var(--line)!important;border-radius:5px!important;
  color:#dbe4f7!important;font-size:12.5px!important;padding:7px 11px!important;height:34px!important;}
.hdrctl div[data-testid="stTextInput"] input:focus{border-color:#2e4470!important;box-shadow:none!important;}
.hdrctl div[data-testid="stTextInput"]{margin-bottom:0!important;}
.hdrctl button{background:transparent!important;border:1px solid var(--line)!important;
  border-radius:5px!important;color:#9fb0d0!important;font-size:12px!important;
  font-weight:700!important;height:34px!important;min-height:34px!important;
  padding:0 8px!important;white-space:nowrap!important;overflow:visible!important;
  display:flex!important;align-items:center!important;justify-content:center!important;}
.hdrctl button:hover{border-color:var(--grn)!important;color:var(--grn)!important;}
.hdrctl button p{font-size:12px!important;font-weight:700!important;
  white-space:nowrap!important;overflow:visible!important;text-overflow:clip!important;
  margin:0!important;line-height:1!important;}
/* matchup ticker — the track holds two copies of the same items, so translating
   it exactly half its width loops seamlessly with no visible jump */
.ticker{position:relative;overflow:hidden;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0a1224,#070b16);
  padding:8px 0;margin:0 0 9px;}
.ticker:before,.ticker:after{content:'';position:absolute;top:0;bottom:0;width:52px;z-index:2;pointer-events:none;}
.ticker:before{left:0;background:linear-gradient(90deg,#070b16,transparent);}
.ticker:after{right:0;background:linear-gradient(270deg,#070b16,transparent);}
.ticker .track{display:flex;width:max-content;animation:tickscroll 110s linear infinite;}
.ticker:hover .track{animation-play-state:paused;}
@keyframes tickscroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.tk{display:inline-flex;align-items:baseline;gap:7px;padding:0 20px;
  border-right:1px solid #17233b;white-space:nowrap;font-size:12.5px;}
.tk .lg{color:#4d5975;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.9px;}
.tk .t{color:#dbe4f7;font-weight:700;} .tk .t.me{color:var(--grn);}
.tk .p{color:#8ea0c4;font-family:'JetBrains Mono',monospace;font-weight:700;}
.tk .w{font-weight:800;font-family:'JetBrains Mono',monospace;}
.tk .w.up{color:var(--grn);} .tk .w.dn{color:#6f7f9e;}
.tk .vs{color:#4d5975;font-size:10px;font-weight:800;text-transform:uppercase;}
.tk .exp{color:#5b688a;font-size:10.5px;font-weight:700;font-family:'JetBrains Mono',monospace;}
.tk .lv{color:var(--red);font-size:9px;font-weight:900;letter-spacing:1px;
  background:rgba(255,77,115,.14);border-radius:3px;padding:1px 5px;}
@media (prefers-reduced-motion: reduce){
  .ticker .track{animation:none;} .ticker{overflow-x:auto;}
}
/* selected KPI tile */
.kpi.on{border-color:var(--grn);box-shadow:0 0 0 1px rgba(25,229,155,.28) inset,0 0 24px rgba(25,229,155,.07);}
/* st.pills -> screenshot filter chips */
div[data-testid="stPills"],div[data-testid="stButtonGroup"]{margin:4px 0 10px;}
div[data-testid="stPills"] button,div[data-testid="stButtonGroup"] button{
  border-radius:5px!important;border:1px solid var(--line)!important;background:transparent!important;
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
.lane .lh2{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.9px;
  color:var(--amb);margin:16px 0 8px;padding-bottom:6px;border-bottom:1px solid #1c2942;}
.lane .lh2 .sub2{display:block;margin-top:3px;font-size:10px;font-weight:600;
  letter-spacing:.2px;text-transform:none;color:#5b688a;}
.ai .keep{color:#dbe4f7;font-weight:700;} .ai .over{color:#8ea0c4;}
.ai .mg{color:#7e8db0;font-weight:700;font-size:10.5px;}
.ai .why{color:#7e8db0;font-size:11px;display:block;margin-top:1px;line-height:1.35;}
.ai .alt{color:var(--grn);font-weight:600;}
.ai .qt{color:#7e8db0;font-weight:700;}
.ai .pr{color:#7e8db0;font-size:10.5px;font-weight:600;}
.swap .side .pr{color:#7e8db0;font-size:11px;font-weight:600;}
.ai .sl{color:#8ea0c4;font-weight:800;font-size:10px;text-transform:uppercase;letter-spacing:.4px;margin-right:4px;}
.prow .whyline{color:#7e8db0;font-size:10.5px;font-weight:600;display:block;margin-top:2px;}
.swap .side .alt{color:var(--grn);font-weight:600;font-size:12.5px;}
.swap .slotk{position:absolute;}
/* leagues tab: team table */
.thead2{display:grid;grid-template-columns:34px 1fr 76px 78px 78px 72px;gap:10px;padding:0 14px 5px;
  color:var(--mut);font-size:10px;text-transform:uppercase;letter-spacing:.6px;font-weight:700;}
.trow{display:grid;grid-template-columns:34px 1fr 76px 78px 78px 72px;gap:10px;align-items:center;
  background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);
  border-radius:6px;padding:8px 14px;margin-bottom:4px;font-size:13px;}
.trow.me{border-color:var(--grn);box-shadow:0 0 0 1px rgba(25,229,155,.25) inset;}
.trow .rk{color:var(--mut);font-weight:800;text-align:center;}
.trow .tn{color:#eef3fc;font-weight:700;} .trow.me .tn{color:var(--grn);}
.trow .c{color:#c7d2ea;text-align:center;font-weight:700;}
.trow .n{color:var(--mut);text-align:right;font-family:'JetBrains Mono',monospace;}
.trow .n.g{color:var(--grn);} .trow .n.r{color:var(--red);}
/* leagues tab: lineup with consensus */
.lhead{display:grid;grid-template-columns:66px 1fr 44px 66px 60px 52px;gap:10px;padding:0 14px 5px;
  color:var(--mut);font-size:10px;text-transform:uppercase;letter-spacing:.6px;font-weight:700;}
.lrow{display:grid;grid-template-columns:66px 1fr 44px 66px 60px 52px;gap:10px;align-items:center;
  background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);
  border-left:3px solid #23324f;border-radius:6px;padding:9px 14px;margin-bottom:5px;font-size:13px;}
.lrow.st{border-left-color:var(--grn);} .lrow.be{border-left-color:#39415a;opacity:.92;}
.lrow.watch{border-left-color:var(--amb);opacity:1;background:linear-gradient(180deg,#16203a,var(--card2));}
.lrow .flag{color:var(--amb);font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.4px;margin-left:7px;}
.lrow .slot{color:var(--mut);font-size:11px;font-weight:800;text-transform:uppercase;}
.lrow .nm{color:#fff;font-weight:700;}
.lrow .nm .tm{color:var(--mut);font-weight:600;font-size:11px;margin-left:6px;}
.lrow .nm .inj{color:var(--red);font-weight:800;font-size:10px;margin-left:6px;}
.lrow .pos{color:#b9c6e3;font-weight:700;text-align:center;}
.lrow .rank{color:#cdd7ee;font-weight:800;text-align:center;font-size:12px;}
.lrow .rank .sd{display:block;color:#5b688a;font-size:9.5px;font-weight:600;letter-spacing:.2px;}
.lrow .pts{color:#fff;font-weight:800;text-align:right;font-family:'JetBrains Mono',monospace;}
.lrow .gr{text-align:center;font-weight:800;font-size:11px;color:#8ea0c4;}
.pickerlbl{font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:.9px;
  color:#8ea0c4;margin:2px 0 4px;}
/* the calculator's filter chips sit tighter than the page-level ones */
.stColumn div[data-testid="stPills"] button{padding:3px 11px!important;font-size:11.5px!important;}
.stColumn div[data-testid="stPills"]{margin:0 0 5px;}
/* weekly matchup, side by side */
.mhead{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
  padding:0 2px 7px;border-bottom:1px solid var(--line);margin-bottom:7px;}
.mhead .nm{font-size:13.5px;font-weight:800;color:#eef3fc;}
.mhead .nm.me{color:var(--grn);}
.mhead .tot{font-size:15px;font-weight:900;font-family:'JetBrains Mono',monospace;color:#fff;}
.mhead .win{font-size:10.5px;font-weight:800;color:var(--mut);margin-left:6px;}
.mhead .win.fav{color:var(--grn);}
.mrow{display:grid;grid-template-columns:52px 1fr 46px;gap:8px;align-items:center;
  padding:6px 10px;margin-bottom:3px;font-size:12.5px;border-radius:6px;
  background:linear-gradient(180deg,var(--card),var(--card2));border:1px solid var(--line);}
.mrow .sl{color:var(--mut);font-size:10px;font-weight:800;text-transform:uppercase;}
.mrow .nm{color:#eef3fc;font-weight:700;}
.mrow .nm .tm{color:var(--mut);font-weight:600;font-size:10px;margin-left:5px;}
.mrow .pt{text-align:right;font-weight:800;font-family:'JetBrains Mono',monospace;color:#fff;}
.mrow.empty2{opacity:.45;}
/* trade calculator: side-by-side positional strength */
.strgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:2px 0 10px;}
.strbox{background:linear-gradient(160deg,var(--card),var(--card2));border:1px solid var(--line);
  border-radius:10px;padding:11px 14px;}
.strbox h4{margin:0 0 8px;font-size:12px;font-weight:900;color:#fff;letter-spacing:.3px;
  display:flex;justify-content:space-between;align-items:baseline;gap:8px;}
.strbox h4 .who{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.strbox h4 .cap{margin-left:auto;padding-left:10px;flex:none;font-size:10px;font-weight:700;
  color:var(--mut);text-transform:uppercase;letter-spacing:.6px;}
.strrow{display:grid;grid-template-columns:42px 1fr 40px;gap:8px;align-items:center;margin-bottom:5px;}
.strrow .p{font-size:11px;font-weight:800;color:#b9c6e3;}
.strrow .bar{height:7px;border-radius:2px;background:#0e1830;position:relative;overflow:hidden;}
.strrow .bar i{position:absolute;left:0;top:0;bottom:0;border-radius:2px;display:block;}
.strrow .bar i.up{background:linear-gradient(90deg,#12b37a,var(--grn));}
.strrow .bar i.mid{background:linear-gradient(90deg,#7a6a2e,var(--amb));}
.strrow .bar i.dn{background:linear-gradient(90deg,#8a3550,var(--red));}
.strrow .v{font-size:10.5px;font-weight:800;text-align:right;font-family:'JetBrains Mono',monospace;}
.strrow .v.up{color:var(--grn);} .strrow .v.mid{color:var(--amb);} .strrow .v.dn{color:var(--red);}
/* trade calculator */
.verdict{border-radius:10px;padding:13px 18px;margin:10px 0 4px;font-size:14px;font-weight:800;
  border:1px solid var(--line);background:linear-gradient(160deg,var(--card),var(--card2));}
.verdict.win{border-color:var(--grn);color:var(--grn);background:rgba(25,229,155,.08);}
.verdict.even{border-color:#2e4470;color:#c7d2ea;}
.verdict.lose{border-color:var(--red);color:var(--red);background:rgba(255,77,115,.07);}
.verdict .sub{display:block;font-size:12px;font-weight:600;color:#9fb0d0;margin-top:4px;}
.verdict .impact{display:grid;grid-template-columns:1fr 108px 108px;gap:5px 10px;
  margin-top:9px;padding-top:8px;border-top:1px solid var(--line);
  font-size:12px;font-weight:700;color:#c7d2ea;}
.verdict .impact .ih{font-size:10px;font-weight:800;text-transform:uppercase;
  letter-spacing:.7px;color:var(--mut);}
.verdict .impact .k{color:var(--mut);font-weight:600;}
.verdict .impact .g{color:var(--grn);} .verdict .impact .r{color:var(--red);}
/* league tag on a trade card */
.trade .lg{display:inline-block;font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.5px;
  color:#8ea0c4;background:#0e1830;border:1px solid #23345a;border-radius:3px;padding:2px 8px;margin-right:8px;}
.trade .trend{font-size:11px;font-weight:800;margin-left:7px;}
.trade .trend.up{color:var(--grn);} .trade .trend.dn{color:var(--red);}
/* ── mobile ─────────────────────────────────────────────────────────────────
   Narrow screens only. Every rule sits inside the media query, so the desktop
   layout above is untouched. The fixed-width grids are what break first: they
   tighten here rather than dropping columns, so no data disappears on a phone. */
@media (max-width: 680px){
  [data-testid="stMainBlockContainer"],.block-container{
    padding-left:.55rem!important;padding-right:.55rem!important;padding-top:.3rem!important;}
  .mast{padding-bottom:6px;}
  .mast h1{font-size:20px;letter-spacing:-.4px;gap:7px;}
  .mast h1 .kicker{font-size:9.5px;letter-spacing:1.2px;}
  .mast .sub{font-size:12px;}
  .statusline{gap:4px 14px;font-size:9.5px;letter-spacing:.5px;}
  .kpi{padding:11px 13px;border-radius:10px;}
  .kpi .n{font-size:20px;} .kpi .l{font-size:9.5px;letter-spacing:.6px;}
  div[data-baseweb="tab-list"]{gap:13px!important;overflow-x:auto;flex-wrap:nowrap;}
  button[data-baseweb="tab"]{font-size:11.5px!important;letter-spacing:.3px;white-space:nowrap;}
  .daybar span{font-size:11.5px;letter-spacing:.9px;}
  .tk{font-size:11px;gap:5px;padding:0 13px;}
  .tk .lg{font-size:8px;} .ticker{padding:7px 0;}
  .ticker .track{animation-duration:75s;}
  .ticker:before,.ticker:after{width:26px;}
  /* rows: tighten, never drop a column */
  .thead,.prow{grid-template-columns:46px 1fr 30px 44px 42px;gap:6px;padding:8px 10px;font-size:12px;}
  .lhead,.lrow{grid-template-columns:42px 1fr 30px 52px 42px 38px;gap:5px;padding:8px 10px;font-size:12px;}
  .thead2,.trow{grid-template-columns:24px 1fr 54px 52px 52px 44px;gap:5px;padding:8px 10px;font-size:12px;}
  .srow{grid-template-columns:24px 1fr 54px 62px;padding:8px 10px;font-size:12px;}
  .mrow{grid-template-columns:44px 1fr 40px;gap:6px;padding:6px 8px;font-size:11.5px;}
  .mhead .nm{font-size:12.5px;} .mhead .tot{font-size:14px;}
  .strgrid{grid-template-columns:1fr;}
  .lrow .rank .sd{font-size:8.5px;}
  /* two-column blocks stack */
  .trade .legs{grid-template-columns:1fr;}
  .swap{grid-template-columns:1fr;gap:6px;}
  .swap .ar{transform:rotate(90deg);text-align:left;}
  .trade,.actionwrap{padding:12px 14px;}
  .note{font-size:11.5px;padding:8px 11px;}
  .ai .txt{font-size:12.5px;} .ai .why{font-size:10.5px;}
  .verdict{font-size:12.5px;padding:11px 14px;}
}
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
# The box owns its own state via a key, seeded once from the URL. Passing
# value=<query param> instead made Streamlit re-create the widget every time the
# param changed — typing a name updated the URL, which changed value=, which
# reset the box, which is why a name sometimes needed entering twice.
if "username_box" not in st.session_state:
    st.session_state["username_box"] = qp.get("u", "aberni3")

# The ticker runs along the very top edge, above the masthead — where a ticker
# belongs, and it puts live scores first for a tool you reopen all week rather
# than a title you have already read. Its slot is reserved here and filled once
# the data is loaded further down.
ticker_slot = st.container()

# Masthead and the controls share one row, so nothing below is pushed down by a
# full-width input that only needs a corner of the header.
h1, h2, h3 = st.columns([7, 2.1, 1.45], vertical_alignment="center")
with h1:
    # The title links home. st.tabs keeps its selection client-side and gives
    # Python no way to change it, but a plain navigation reloads the app and tabs
    # render fresh on the first one — so this lands on This Week without adding a
    # button or any other furniture. The username is carried so the reload does
    # not drop whoever is being viewed.
    _u = (st.session_state.get("username_box") or "").strip()
    _home = f"?u={quote_plus(_u)}" if _u else "?"
    st.markdown(
        f'<a class="masthome" href="{_home}" target="_self">'
        '<div class="mast"><h1>🏈 Fantasy <span class="ac">Command Center</span>'
        '<span class="kicker">Sleeper</span></h1>'
        '<div class="sub">Every lineup, waiver and trade decision across all your '
        'leagues — one scan.</div></div></a>', unsafe_allow_html=True)
with h2:
    st.markdown('<div class="hdrctl">', unsafe_allow_html=True)
    username = st.text_input("Sleeper username", key="username_box",
                             label_visibility="collapsed",
                             placeholder="Sleeper username…")
    st.markdown('</div>', unsafe_allow_html=True)
with h3:
    st.markdown('<div class="hdrctl">', unsafe_allow_html=True)
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        _upd = datetime.now(ZoneInfo("America/New_York")).strftime("%-I:%M %p ET")
    except Exception:
        _upd = ""
    st.markdown(f'<div class="upd">updated {esc(_upd)}</div></div>',
                unsafe_allow_html=True)

username = (username or "").strip()          # trailing spaces resolve to no user
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

# Projections are per scoring format, and three of these leagues are half PPR.
# Fetching one PPR map for everything overstated every receiver by three or four
# points a week, which fed the lineup optimiser, the start/sit calls and both
# point rows in the trade calculator.
_proj_cache = {}
def proj_for(ctx):
    key = ctx["scoring_key"]
    if key not in _proj_cache:
        _proj_cache[key] = S.projections(data["season"], data["week"], key)
    return _proj_cache[key]

proj = S.projections(data["season"], data["week"], "ppr")   # trending//waiver fallback
trend = S.trending("add", 168, 250)

# FantasyPros consensus, per scoring format actually in use across the leagues
_fp_cache = {}
def fp_for(ctx):
    """Expert-consensus index for this league's scoring. Falls back to an empty
    dict, so every downstream feature degrades to Sleeper projections alone."""
    if not FP.ENABLE_FP:
        return {}
    rec = (ctx["league"].get("scoring_settings", {}) or {}).get("rec", 0)
    slug = (FP.scoring_slug(rec), bool(ctx["superflex"]))
    if slug not in _fp_cache:
        try:
            _fp_cache[slug] = FP.by_sleeper_id(slug[0], data["week"], slug[1])["by_id"]
        except Exception:
            _fp_cache[slug] = {}
    return _fp_cache[slug]

# status line — flat, in the masthead's rhythm rather than another card
ndyn, nrd = len(data["groups"]["dynasty"]), len(data["groups"]["redraft"])
st.markdown(
    f'<div class="statusline">'
    f'<span>👤 <b>{esc(data["user"]["display_name"])}</b></span>'
    f'<span>{data["season"]} · Week <b>{data["week"]}</b></span>'
    f'<span><b>{len(data["contexts"])}</b> leagues · {ndyn} dynasty · {nrd} redraft</span>'
    f'<span>Projections <span class="on">live</span></span>'
    f'</div>', unsafe_allow_html=True)

# ── per-league compute (cached objects are cheap; done once per render) ────────
def valuer_for(ctx):
    return Valuer(ctx, players, proj_for(ctx), fp=fp_for(ctx))


_ros_cache = {}
def ros_for(ctx):
    """Rest-of-season projections for this league's remaining regular season."""
    w0, w1 = S.fantasy_weeks(ctx["league"], data["week"])
    key = (w0, w1, ctx["scoring_key"])
    if key not in _ros_cache:
        try:
            _ros_cache[key] = S.ros_projections(data["season"], w0,
                                                ctx["scoring_key"], w1)
        except Exception:
            _ros_cache[key] = {}
    return _ros_cache[key]


_maps_cache = {}
def weekly_maps_for(ctx):
    """Per-week projection maps for this league's remaining regular season."""
    w0, w1 = S.fantasy_weeks(ctx["league"], data["week"])
    key = (w0, w1, ctx["scoring_key"])
    if key not in _maps_cache:
        try:
            _maps_cache[key] = S.weekly_projection_maps(data["season"], w0,
                                                        ctx["scoring_key"], w1)
        except Exception:
            _maps_cache[key] = []
    return _maps_cache[key]


def rankings_for(ctx):
    """Projected finish, grounded in rest-of-season scoring as well as roster
    value and record."""
    return A.power_rankings(ctx, valuer_for(ctx), players, ros=ros_for(ctx))

_DIGEST_CACHE = {}
def digest_for(ctx):
    lid = ctx["league_id"]
    if lid not in _DIGEST_CACHE:
        _DIGEST_CACHE[lid] = A.weekly_digest(ctx, valuer_for(ctx), players, trend)
    return _DIGEST_CACHE[lid]

_TRADE_CACHE = {}
def trades_for(ctx, max_ideas=10):
    """Trade ideas per league, computed once — the global tab and the per-league
    detail view both read this."""
    lid = ctx["league_id"]
    if lid not in _TRADE_CACHE:
        _TRADE_CACHE[lid] = A.trade_ideas(ctx, valuer_for(ctx), players,
                                          max_ideas=max_ideas,
                                          weekly_maps=weekly_maps_for(ctx))
    return _TRADE_CACHE[lid]


# ── expert consensus rankings table ──────────────────────────────────────────
def render_rankings():
    if not FP.ENABLE_FP:
        st.markdown('<div class="note">Expert consensus is switched off '
                    '(<b>ENABLE_FP</b>). Everything runs on Sleeper projections.</div>',
                    unsafe_allow_html=True)
        return

    labels = {"ppr": "Full PPR", "half-point-ppr": "Half PPR", "": "Standard"}

    # League first: "my players" and "available" only mean anything inside one
    # league, since rosters differ. Picking a league also settles the scoring
    # format, because that's what decides which ranking set applies.
    lg_opts = ["All leagues"] + [c["name"] for c in data["contexts"]]
    lg_pick = st.pills("League", lg_opts, default="All leagues", key="rk_league",
                       label_visibility="collapsed") or "All leagues"
    scope = None if lg_pick == "All leagues" else \
        next((c for c in data["contexts"] if c["name"] == lg_pick), None)

    if scope is not None:
        rec = (scope["league"].get("scoring_settings", {}) or {}).get("rec", 0)
        slug = FP.scoring_slug(rec)
        picked = labels.get(slug, "Standard")
    else:
        scorings = {}
        for ctx in data["contexts"]:
            r = (ctx["league"].get("scoring_settings", {}) or {}).get("rec", 0)
            scorings.setdefault(FP.scoring_slug(r), []).append(ctx["name"])
        opts = [labels.get(k, k or "Standard") for k in scorings]
        picked = st.pills("Scoring", opts, default=opts[0], key="rk_scoring",
                          label_visibility="collapsed") or opts[0]
        slug = next(k for k in scorings if labels.get(k, "Standard") == picked)

    with st.spinner("Loading expert consensus…"):
        idx = FP.by_sleeper_id(slug, data["week"],
                               bool(scope["superflex"]) if scope is not None else False)
    rows = idx["by_id"]
    if not rows:
        st.markdown(f'<div class="note">No consensus published for week '
                    f'<b>{data["week"]}</b> yet — FantasyPros posts these as the '
                    'week approaches.</div>', unsafe_allow_html=True)
        return

    # roster membership, scoped to the chosen league (or pooled across all)
    mine, rostered = set(), set()
    for ctx in ([scope] if scope is not None else data["contexts"]):
        for t in ctx["teams"]:
            for pid in t["players"]:
                rostered.add(str(pid))
                if t["is_mine"]:
                    mine.add(str(pid))

    where = (f'<b>{esc(lg_pick)}</b>' if scope is not None
             else f'all {len(data["contexts"])} leagues')
    sf = bool(scope["superflex"]) if scope is not None else False
    board_name = "superflex" if sf else "flex"
    qb_note = "" if sf else " (QBs aren't on the flex board, so theirs is blank)"
    st.markdown(f'<div class="note">Expert consensus from FantasyPros — '
                f'{len(rows)} players · week {data["week"]} · {esc(picked)} · '
                f'roster status from {where}.<br><b>Ovr</b> is the FantasyPros '
                f'{esc(board_name)} ranking{qb_note}. <b>SD</b> is expert '
                'disagreement — near zero is unanimous, high means the call is a '
                'coin flip.</div>', unsafe_allow_html=True)

    # Roster cuts only mean something inside one league — "available" across a
    # pool of five different rosters isn't a real category — so they appear only
    # once a league is chosen.
    if scope is not None:
        c1, c2 = st.columns([3, 2])
        # "My Team" sits with the positions so picking a league then your roster
        # is one click rather than two separate filters
        pos_pick = c1.pills("Position", ["All", "QB", "RB", "WR", "TE", "My Team"],
                            default="All", key="rk_pos",
                            label_visibility="collapsed") or "All"
        who = c2.pills("Roster", ["Everyone", "Available"], default="Everyone",
                       key="rk_who", label_visibility="collapsed") or "Everyone"
        if pos_pick == "My Team":
            who = "My players"
    else:
        pos_pick = st.pills("Position", ["All", "QB", "RB", "WR", "TE"], default="All",
                            key="rk_pos", label_visibility="collapsed") or "All"
        who = "Everyone"

    recs = []
    for pid, d in rows.items():
        if pos_pick not in ("All", "My Team") and d["pos"] != pos_pick:
            continue
        if who.startswith("My players") and pid not in mine:
            continue
        if who.startswith("Available") and pid in rostered:
            continue
        recs.append((pid, d))
    # Across positions the overall board is the meaningful order; within one
    # position they agree, so this sorts correctly either way.
    # Order by the league's own cross-position board; anything it doesn't rank
    # (QBs in a 1QB league) falls to the bottom, ordered by positional ECR.
    recs.sort(key=lambda x: (x[1].get("overall") if x[1].get("overall") is not None
                             else 9999,
                             x[1]["ecr"] if x[1]["ecr"] is not None else 9999))

    if not recs:
        st.markdown('<div class="empty">Nothing matches that filter.</div>',
                    unsafe_allow_html=True)
        return

    import pandas as pd
    df = pd.DataFrame([{
        "Ovr": d.get("overall"), "Rank": d["pos_rank"], "Player": d["name"],
        "Tm": d["team"],
        "Opp": (d["opp"] or "").replace("vs. ", "vs "), "ECR": d["ecr"],
        "Best": d["best"], "Worst": d["worst"], "SD": d["std"],
        "Grade": d["grade"], "Rostered%": d["owned"],
        "Mine": "✓" if pid in mine else ("" if pid in rostered else "FA"),
    } for pid, d in recs])
    st.dataframe(df, width="stretch", hide_index=True, height=560,
                 column_config={
                     "Ovr": st.column_config.NumberColumn(
                         "Ovr", help="FantasyPros flex ranking", format="%d"),
                     "SD": st.column_config.NumberColumn(
                         "SD", help="Expert disagreement — low is settled", format="%.2f"),
                     "Rostered%": st.column_config.NumberColumn(format="%.0f%%"),
                 })
    if idx["unmatched"]:
        st.markdown(f'<div class="note">{len(idx["unmatched"])} ranked players '
                    f'could not be matched to a Sleeper id (mostly fullbacks and '
                    f'alias spellings): {esc(", ".join(idx["unmatched"][:8]))}.</div>',
                    unsafe_allow_html=True)


# ── leagues overview: every league's shape and standing in one place ─────────
def render_leagues_overview():
    ctxs = data["contexts"]
    w = l = t = 0
    pf = pa = 0.0
    ranks = []
    for ctx in ctxs:
        me = ctx["my_roster"]
        if not me:
            continue
        w += me["wins"]; l += me["losses"]; t += me["ties"]
        pf += me["fpts"]; pa += me["fpts_against"]
        row = next((x for x in ctx["standings"] if x["is_mine"]), None)
        if row:
            ranks.append(row["rank"])

    kc = st.columns(4)
    rec = f"{w}-{l}" + (f"-{t}" if t else "")
    # Before any game is final none of this means anything: every team is 0-0, so
    # "rank" is just the tiebreak order and points are zero. Say TBD rather than
    # print a number that looks real. These fill in as results land.
    played = (w + l + t) > 0
    tiles = [(rec, "Combined record", "g" if w >= l else "", True),
             (f"{pf:,.0f}" if played else "TBD", "Points for", "c", False),
             (f"{pf - pa:+,.0f}" if played else "TBD", "Point differential",
              "g" if (played and pf >= pa) else "", False),
             (f"{(sum(ranks)/len(ranks)):.1f}" if (played and ranks) else "TBD",
              "Average standing", "a", False)]
    for col, (n, lab, cls, on) in zip(kc, tiles):
        col.markdown(f'<div class="kpi{" on" if on else ""}"><div class="n {cls}">{n}</div>'
                     f'<div class="l">{esc(lab)}</div></div>', unsafe_allow_html=True)

    pick = st.pills("League", [c["name"] for c in ctxs], default=ctxs[0]["name"],
                    key="lg_pick", label_visibility="collapsed") or ctxs[0]["name"]
    ctx = next(c for c in ctxs if c["name"] == pick)
    me = ctx["my_roster"]

    badges = f'<span class="badge {"dyn" if ctx["format"] == "dynasty" else "rd"}">' \
             f'{esc(ctx["format"].upper())}</span>'
    if ctx["superflex"]:
        badges += ' <span class="badge sf">SUPERFLEX</span>'
    if ctx["trades_disabled"]:
        badges += ' <span class="badge off">NO TRADES</span>'
    bits = [f'{ctx["num_teams"]} teams', esc(ctx["scoring_label"])]
    if ctx.get("waiver_budget"):
        used = me.get("waiver_budget_used", 0) if me else 0
        bits.append(f'FAAB {ctx["waiver_budget"] - used} of {ctx["waiver_budget"]} left')
    if ctx.get("trade_deadline"):
        bits.append(f'trade deadline wk {ctx["trade_deadline"]}')
    st.markdown(f'<div class="note">{badges} &nbsp; {" · ".join(bits)}</div>',
                unsafe_allow_html=True)

    v = valuer_for(ctx)
    sub = st.tabs(["📋 My Lineup", "⚔️ Matchup", "📊 Team Rankings"])

    # ── your lineup, with this week's consensus alongside ────────────────────
    with sub[0]:
        me_ = ctx["my_roster"]
        ss = A.start_sit(ctx, v, players) if me_ else None
        if not ss:
            st.markdown('<div class="empty">You have no roster in this league.</div>',
                        unsafe_allow_html=True)
        else:
            multi_slots = {sl for sl in ctx["roster_positions"]
                           if len(FLEX_ELIG.get(sl, set())) > 1}

            # A bench player is "worth a look" when he'd out-rank the weakest
            # starter he is actually eligible to replace — that's the only
            # comparison that means anything.
            starter_by_slot = [(r.get("slot"), r) for r in ss["lineup"]]
            watch = set()
            for b in ss["bench"]:
                for sl, st_r in starter_by_slot:
                    if b["pos"] not in FLEX_ELIG.get(sl, set()):
                        continue
                    if b["score"] >= st_r["score"] * 0.92:
                        watch.add(b["id"])
                        break

            hdr(f'Starters · Week {data["week"]} · projected {ss["proj_total"]:.1f}')
            st.markdown('<div class="lhead"><div>SLOT</div><div>PLAYER</div><div>POS</div>'
                        '<div>EXPERTS</div><div>PROJ</div><div>FLEX</div></div>',
                        unsafe_allow_html=True)

            def lineup_row(r, klass, slot=None):
                rank = "—"
                if r.get("pos_rank"):
                    sd = (f'<span class="sd">sd {r["std"]:.1f}</span>'
                          if r.get("std") is not None else "")
                    rank = f'{esc(r["pos_rank"])}{sd}'
                flex = f'{r["overall"]:.0f}' if r.get("overall") else "—"
                pts = f'{r["pts"]:.1f}' if r["pts"] else "—"
                flag = ('<span class="flag">start?</span>'
                        if r["id"] in watch else "")
                return (f'<div class="lrow {klass}">'
                        f'<div class="slot">{esc(slot or r.get("slot") or "")}</div>'
                        f'<div class="nm">{esc(r["name"])}<span class="tm">{esc(r["team"])}</span>'
                        f'{inj_tag(r)}{flag}</div>'
                        f'<div class="pos">{esc(r["pos"])}</div>'
                        f'<div class="rank">{rank}</div>'
                        f'<div class="pts">{pts}</div>'
                        f'<div class="gr">{flex}</div></div>')

            st.markdown("".join(lineup_row(r, "st") for r in ss["lineup"]),
                        unsafe_allow_html=True)
            if ss["bench"]:
                hdr("Bench")
                st.markdown("".join(
                    lineup_row(r, "watch" if r["id"] in watch else "be", "BN")
                    for r in ss["bench"]), unsafe_allow_html=True)
                if watch:
                    st.markdown('<div class="note">Highlighted bench players score '
                                'within reach of a starter they could legally replace. '
                                '<b>FLEX</b> is the FantasyPros flex ranking.</div>',
                                unsafe_allow_html=True)

    # ── this week's matchup, side by side ────────────────────────────────────
    with sub[1]:
        try:
            games = A.week_matchups(ctx, v, players,
                                    S.league_matchups(ctx["league_id"], data["week"]))
        except Exception:
            games = []
        game = next((g for g in games if g["mine"]), None)
        if not game:
            st.markdown('<div class="empty">No matchup for you this week in this '
                        'league.</div>', unsafe_allow_html=True)
        else:
            a, b = ((game["a"], game["b"]) if game["a"]["is_mine"]
                    else (game["b"], game["a"]))
            rows_by_rid = {r["roster_id"]: r for r in
                           S.league_matchups(ctx["league_id"], data["week"])}
            slots = [x for x in ctx["roster_positions"] if x not in ("BN", "IR", "TAXI")]

            def side(sd):
                row = rows_by_rid.get(sd["rid"], {})
                starters = [str(x) if x and str(x) != "0" else None
                            for x in (row.get("starters") or [])]
                out = (f'<div class="mhead"><span class="nm{" me" if sd["is_mine"] else ""}">'
                       f'{esc(sd["name"])}</span><span><span class="tot">'
                       f'{(sd["live"] if game["live"] else sd["proj"]):.1f}</span>'
                       f'<span class="win{" fav" if sd["win"] >= 50 else ""}">'
                       f'{sd["win"]}%</span></span></div>')
                for i, slot in enumerate(slots):
                    pid = starters[i] if i < len(starters) else None
                    if not pid:
                        out += (f'<div class="mrow empty2"><div class="sl">{esc(slot)}</div>'
                                f'<div class="nm">—</div><div class="pt">—</div></div>')
                        continue
                    pi = pinfo(pid, players)
                    pts = v.points(pid)
                    out += (f'<div class="mrow"><div class="sl">{esc(slot)}</div>'
                            f'<div class="nm">{esc(pi["name"])}'
                            f'<span class="tm">{esc(pi["pos"])}·{esc(pi["team"])}</span>'
                            f'{inj_tag(pi)}</div>'
                            f'<div class="pt">{pts:.1f}</div></div>')
                return out

            hdr(f'Week {data["week"]} matchup')
            c1, c2 = st.columns(2)
            c1.markdown(side(a), unsafe_allow_html=True)
            c2.markdown(side(b), unsafe_allow_html=True)
            diff = a["proj"] - b["proj"]
            lead = "you" if diff >= 0 else esc(b["name"])
            st.markdown(f'<div class="note">Projected {"live totals · " if game["live"] else ""}'
                        f'edge: <b>{lead}</b> by <b>{abs(diff):.1f}</b>. Win probability '
                        'allows for a noisy week, so a small edge is close to a coin flip.'
                        '</div>', unsafe_allow_html=True)

    # ── season to date, with projected finish ────────────────────────────────
    with sub[2]:
        pranks, rec_weight = rankings_for(ctx)
        proj_rank = {r["rid"]: r["proj_rank"] for r in pranks}
        hdr("Standings · season to date")
        st.markdown('<div class="thead2"><div>#</div><div>TEAM</div><div>RECORD</div>'
                    '<div>PF</div><div>PA</div><div>PROJ</div></div>',
                    unsafe_allow_html=True)
        for tm in ctx["standings"]:
            recs = f'{tm["wins"]}-{tm["losses"]}' + (f'-{tm["ties"]}' if tm["ties"] else "")
            diff = tm["fpts"] - tm["fpts_against"]
            pr = proj_rank.get(tm["roster_id"], "—")
            st.markdown(
                f'<div class="trow{" me" if tm["is_mine"] else ""}">'
                f'<div class="rk">{tm["rank"]}</div><div class="tn">{esc(tm["name"])}</div>'
                f'<div class="c">{recs}</div>'
                f'<div class="n">{tm["fpts"]:,.1f}</div>'
                f'<div class="n">{tm["fpts_against"]:,.1f}</div>'
                f'<div class="n {"g" if diff >= 0 else "r"}">{pr}</div></div>',
                unsafe_allow_html=True)
        st.markdown(f'<div class="note">PROJ is projected finish — roster value '
                    f'blended with record, record currently weighted '
                    f'<b>{rec_weight*100:.0f}%</b> and rising as games are played.</div>',
                    unsafe_allow_html=True)


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


# ── guillotine FAAB strategy (placeholder) ───────────────────────────────────
def render_guillotine():
    gl = [c for c in data["contexts"] if c["format"] == "guillotine"]
    st.markdown(
        '<div class="actionwrap"><div class="actionhd">🪓 Guillotine FAAB Strategy</div>'
        '<div class="actionsub">Coming soon — bid sizing for guillotine formats, where '
        'a team is eliminated each week and their whole roster hits the wire.</div></div>',
        unsafe_allow_html=True)
    if not gl:                                  # tab is hidden in this case
        return
    for ctx in gl:
        me = ctx["my_roster"]
        budget = ctx.get("waiver_budget") or 0
        used = (me or {}).get("waiver_budget_used", 0)
        left = budget - used
        alive = len(ctx["teams"])
        kc = st.columns(4)
        tiles = [(f"{left:,}", "FAAB remaining", "g", True),
                 (f"{budget:,}", "Starting budget", "", False),
                 (alive, "Teams remaining", "c", False),
                 (f"Wk {data['week']}", "Current week", "a", False)]
        for col, (n, lab, cls, on) in zip(kc, tiles):
            col.markdown(f'<div class="kpi{" on" if on else ""}"><div class="n {cls}">{n}</div>'
                         f'<div class="l">{esc(lab)}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="note"><b>{esc(ctx["name"])}</b> · {alive} teams · '
                    f'{esc(ctx["scoring_label"])}. Planned: pace your budget against the '
                    'weeks left, price the eliminated roster hitting the wire, and flag '
                    'the bids worth spending on.</div>', unsafe_allow_html=True)


# ── this week's matchup ticker ───────────────────────────────────────────────
def render_ticker():
    """Your own matchup in every league, scrolling.

    Before kickoff each side shows its projected total; once points are on the
    board it shows the live score with the expected final beside it, so a
    mid-slate refresh reflects games in progress and any projection change for
    the later window. Hovering pauses the scroll.
    """
    items = []
    for ctx in data["contexts"]:
        try:
            rows = S.league_matchups(ctx["league_id"], data["week"])
            games = A.week_matchups(ctx, valuer_for(ctx), players, rows)
        except Exception:
            continue
        for g in games:
            if not g["mine"]:
                continue                       # only the games you're actually in
            # put the user's team first so the eye lands on it
            a, b = (g["a"], g["b"]) if g["a"]["is_mine"] else (g["b"], g["a"])

            def side(sd, other, mine=False):
                me = " me" if mine else ""
                w = "up" if sd["win"] >= other["win"] else "dn"
                if g["live"]:
                    num = (f'<span class="p">{sd["live"]:.1f}</span>'
                           f'<span class="exp">→{sd["expected"]:.0f}</span>')
                else:
                    num = f'<span class="p">{sd["proj"]:.1f}</span>'
                return (f'<span class="t{me}">{esc(sd["name"])}</span>{num}'
                        f'<span class="w {w}">{sd["win"]}%</span>')

            flag = '<span class="lv">LIVE</span>' if g["live"] else ""
            items.append(f'<span class="tk"><span class="lg">{esc(ctx["name"][:20])}</span>'
                         f'{flag}{side(a, b, True)}<span class="vs">vs</span>{side(b, a)}</span>')
    if not items:
        return
    # a handful of items would leave the track shorter than the viewport, so
    # repeat until it fills, then double the whole thing for a seamless loop
    while len(items) < 8:
        items = items * 2
    track = "".join(items)
    st.markdown(f'<div class="ticker"><div class="track">{track}{track}</div></div>',
                unsafe_allow_html=True)


# ── global action center: every move across every league, in one place ────────
def render_action_center():
    ctxs = data["contexts"]
    opts = ["All leagues"] + [c["name"] for c in ctxs]
    pick = st.pills("League", opts, default="All leagues", key="ac_league",
                    label_visibility="collapsed") or "All leagues"
    active = ctxs if pick == "All leagues" else [c for c in ctxs if c["name"] == pick]

    lineup, waivers, trades, close = {}, {}, {}, {}
    for ctx in active:
        d = digest_for(ctx)
        nm = ctx["name"]
        ss = d["start_sit"]
        if ss and ss["swaps"]:
            lineup[nm] = ss["swaps"]
        if ss and ss.get("close_calls"):
            close[nm] = ss["close_calls"][:3]
        w = [x for x in d["waiver_rows"][:3] if x["score"] > 0]
        if w:
            waivers[nm] = w
        t = trades_for(ctx)[:2]
        if t:
            trades[nm] = t

    n_l = sum(len(v) for v in lineup.values())
    n_w = sum(len(v) for v in waivers.values())
    n_t = sum(len(v) for v in trades.values())
    st.markdown(
        f'<div class="actionwrap"><div class="actionhd">⚡ This Week — Every League at Once'
        f'<span class="counts"><b>{n_l}</b> lineup · <b>{n_w}</b> waivers · '
        f'<b>{n_t}</b> trades</span></div></div>', unsafe_allow_html=True)

    def lane_body(groups, item_fn, empty):
        if not groups:
            return f'<div class="none">{empty}</div>'
        parts = []
        for i, (nm, items) in enumerate(groups.items()):
            parts.append(f'<div class="lgh{" first" if i == 0 else ""}">{esc(nm)}</div>')
            parts.extend(item_fn(x) for x in items)
        return "".join(parts)

    def lane(cls, title, groups, item_fn, empty, extra=""):
        """One column. Each league name appears once as a subheader, then its rows."""
        st.markdown(f'<div class="lane"><div class="lh {cls}">{title}</div>'
                    f'{lane_body(groups, item_fn, empty)}{extra}</div>',
                    unsafe_allow_html=True)

    def rank_label(slot, r):
        """For a flex slot the candidates are different positions, so 'WR47 vs
        TE24' compares nothing — show the cross-position rank instead. For a
        dedicated slot everyone is the same position, so the positional rank is
        the readable one."""
        multi = len(FLEX_ELIG.get(slot, set())) > 1
        if multi and r.get("overall"):
            return f'ovr {r["overall"]:.0f}'
        return r.get("pos_rank") or ""

    def rank_tag(slot, r, extra=""):
        lab = rank_label(slot, r)
        inner = " · ".join(x for x in (lab, extra) if x)
        return f' <span class="pr">({esc(inner)})</span>' if inner else ""

    def swap_item(sw):
        slot = sw["slot"]
        # deltas belong to the PRIMARY recommendation, not the whole row — with
        # two alternatives listed it was unclear what "+20 spots" referred to
        bits = []
        if sw.get("rank_delta"):
            bits.append(f'{sw["rank_delta"]:+d} spots')
        if abs(sw["gain"]) >= 0.05:
            bits.append(f'{sw["gain"]:+.1f} proj')
        alt = "".join(f' <span class="alt">or {esc(a["name"])}</span>{rank_tag(slot, a)}'
                      for a in sw["alts"])
        return (f'<span class="ai"><span class="txt"><span class="sl">{esc(slot)}</span>'
                f'Start <b class="g">{esc(sw["in"]["name"])}</b>'
                f'{rank_tag(slot, sw["in"], " · ".join(bits))}{alt} '
                f'over <span class="r">{esc(sw["out"]["name"])}</span>'
                f'{rank_tag(slot, sw["out"])}</span></span>')

    def waiver_item(w):
        return (f'<span class="ai"><span class="txt">Add <b>{esc(w["name"])}</b> '
                f'{esc(w["pos"])}</span>'
                + (f'<span class="why">{esc(w["why"])}</span>' if w.get("why") else "")
                + '</span>')

    def trade_item(t):
        # Every piece, not just the headline one. Showing only give[0]/get[0]
        # rendered a 2-for-1 as a 1-for-1 with a player silently missing, which
        # made correct suggestions look wrong.
        give = " + ".join(esc(r["name"]) for r in t.get("gives", [t["give"]]))
        get = " + ".join(esc(r["name"]) for r in t.get("gets", [t["get"]]))
        # no shape label: listing both players already says it is a 2-for-1
        return (f'<span class="ai"><span class="txt">Give '
                f'<span class="r">{give}</span> → get <b class="g">{get}</b></span>'
                f'<span class="why">vs {esc(t["partner"])} · {t["fairness"]:.0f}% fair</span>'
                f'</span>')

    def close_item(c):
        """A slot the optimiser got right by a hair. Naming the margin matters:
        it's the difference between 'settled' and 'flip a coin'."""
        a, b = c["starter"], c["challenger"]
        ra = rank_tag(c["slot"], a)
        rb = rank_tag(c["slot"], b)
        return (f'<span class="ai"><span class="txt"><span class="sl">{esc(c["slot"])}</span>'
                f'<span class="keep">{esc(a["name"])}</span>{ra} '
                f'<span class="over">over</span> {esc(b["name"])}{rb}</span>'
                f'<span class="why">margin {c["margin"]:.1f}</span></span>')

    close_html = ""
    if close:
        close_html = ('<div class="lh2">⚖️ Close calls'
                      '<span class="sub2">tight enough that a matchup read could '
                      'decide it</span></div>'
                      + lane_body(close, close_item, ""))

    cols = st.columns(3)
    with cols[0]:
        lane("s", "🟢 Lineup changes", lineup, swap_item, "All lineups optimal 🎉",
             extra=close_html)
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
            slot = sw["slot"]
            multi = len(FLEX_ELIG.get(slot, set())) > 1
            def pr(r):
                lab = (f'ovr {r["overall"]:.0f}' if multi and r.get("overall")
                       else (r.get("pos_rank") or ""))
                return f' <span class="pr">({esc(lab)})</span>' if lab else ""
            alt = "".join(
                f'<div class="alt">or {esc(a["name"])}{pr(a)} '
                f'<span class="m">{esc(a["pos"])}·{a["pts"]:.1f}</span></div>'
                for a in sw["alts"])
            gbits = []
            if sw.get("rank_delta"):
                gbits.append(f'{sw["rank_delta"]:+d} spots')
            if abs(sw["gain"]) >= 0.05:
                gbits.append(f'{sw["gain"]:+.1f} proj')
            # states plainly which two players the numbers compare
            gain = (f' · {esc(sw["in"]["name"])} vs {esc(sw["out"]["name"])}: '
                    f'{" · ".join(gbits)}') if gbits else ""
            st.markdown(
                f'<div class="swap"><div class="side"><div class="k in">START · {esc(sw["slot"])}{gain}</div>'
                f'<div class="n">{esc(s_in["name"])}{pr(s_in)} <span class="m">{esc(s_in["pos"])}·{esc(s_in["team"])} '
                f'· {s_in["pts"]:.1f} pts</span></div>{alt}</div><div class="ar">▶</div>'
                f'<div class="side"><div class="k out">SIT</div>'
                f'<div class="n">{esc(s_out["name"])}{pr(s_out)} <span class="m">{esc(s_out["pos"])}·{esc(s_out["team"])} '
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
    """A card states who it helps and by how much. A deal favouring one side is
    still worth seeing — it just has to say so rather than be dressed up."""
    kind = "dynasty asset" if ctx["format"] == "dynasty" else "win-now"

    def imp(pts):
        pc = "g" if pts > 0.05 else ("r" if pts < -0.05 else "")
        return f'<span class="{pc}">{pts:+.1f}</span> pts this week'

    def ros(x):
        c = "g" if x > 0.05 else ("r" if x < -0.05 else "")
        return f'<span class="{c}">{x:+.1f}</span> pts rest of season'

    tp, mr, tr = (t.get("their_pts_delta"), t.get("ros_delta"),
                  t.get("their_ros_delta"))
    impact = ""
    if tp is not None:
        impact = (f'<div class="impact2"><span>You {imp(t.get("pts_delta", 0))}</span>'
                  f'<span class="vs2">vs</span>'
                  f'<span>{esc(t["partner"][:16])} {imp(tp)}</span></div>')
        if mr is not None and tr is not None:
            impact += (f'<div class="impact2 second"><span>You {ros(mr)}</span>'
                       f'<span class="vs2">vs</span>'
                       f'<span>{esc(t["partner"][:16])} {ros(tr)}</span></div>')
    gives, gets = t.get("gives", [t["give"]]), t.get("gets", [t["get"]])
    shape = f'<span class="lg">{esc(t.get("shape", "1-for-1"))}</span>'
    return (f'<div class="trade"><div class="top">'
            f'<div class="p">{shape}vs {esc(t["partner"])} '
            f'<span class="w">· {kind} values</span></div>'
            f'<div class="fair">{t["fairness"]:.0f}% fair</div></div>'
            f'<div class="legs">{trade_leg(gives, "give")}{trade_leg(gets, "get")}</div>'
            f'{impact}{extra}<div class="why">{esc(t["rationale"])}</div></div>')


# ── global trade ideas tab: every league's win-win swaps in one board ─────────
def render_trade_ideas_global():
    pool, blocked = [], []
    for ctx in data["contexts"]:
        if ctx["trades_disabled"]:
            blocked.append(ctx["name"])
            continue
        for t in trades_for(ctx, max_ideas=10):
            pool.append((ctx, t))

    if not pool:
        st.markdown('<div class="empty">No clean win-win surfaced across your leagues right now. '
                    'Ideas appear when one of your surplus positions lines up with a rival\'s need '
                    'at comparable value.</div>', unsafe_allow_html=True)
        if blocked:
            st.markdown(f'<div class="note">🔒 Trades disabled in: <b>{esc(", ".join(blocked))}</b> '
                        '(guillotine/elimination format).</div>', unsafe_allow_html=True)
        return

    best = max(t["fairness"] for _, t in pool)
    packages = sum(1 for _, t in pool if t.get("shape", "1-for-1") != "1-for-1")
    by_lg = {}
    for ctx_, t in pool:
        by_lg.setdefault(ctx_["name"], []).append(t)

    kc = st.columns(4)
    tiles = [(len(pool), "Total ideas", "g", True),
             (len(by_lg), "Leagues with ideas", "c", False),
             (f"{best:.0f}%", "Best fairness", "g", False),
             (packages, "Package deals", "a", False)]
    for col, (n, l, cls, on) in zip(kc, tiles):
        col.markdown(f'<div class="kpi{" on" if on else ""}"><div class="n {cls}">{n}</div>'
                     f'<div class="l">{esc(l)}</div></div>', unsafe_allow_html=True)

    # filter by league — the only cut that matters here
    opts = ["All leagues"] + [f"{n} ({len(v)})" for n, v in by_lg.items()]
    pick = st.pills("League", opts, default="All leagues", key="ti_league",
                    label_visibility="collapsed") or "All leagues"
    if pick == "All leagues":
        rows = pool
    else:
        chosen = pick.rsplit(" (", 1)[0]
        rows = [(c, t) for c, t in pool if c["name"] == chosen]

    # group by league, best idea first within each — mirrors the day-grouped board
    by_league = {}
    for ctx, t in rows:
        by_league.setdefault(ctx["name"], (ctx, []))[1].append(t)
    order = sorted(by_league.values(), key=lambda x: max(t["fairness"] for t in x[1]), reverse=True)

    TOP_PER_LEAGUE = 2
    v_cache = {}
    for ctx, ideas in order:
        kind = "dynasty asset" if ctx["format"] == "dynasty" else "win-now"
        hdr(ctx["name"])
        v = v_cache.setdefault(ctx["league_id"], valuer_for(ctx))
        ranked = sorted(ideas, key=lambda x: (A.trade_edge(x), x["fairness"]),
                        reverse=True)
        for t in ranked[:TOP_PER_LEAGUE]:
            tr = v.trend30(t["get"]["id"]) if hasattr(v, "trend30") else 0
            trend = (f'<div class="why" style="margin-top:6px">30-day trend on '
                     f'{esc(t["gets"][0]["name"] if t.get("gets") else t["get"]["name"])}: '
                     f'<span class="trend {"up" if tr > 0 else "dn"}">'
                     f'{"▲" if tr > 0 else "▼"} {abs(tr):,}</span></div>') if tr else ""
            st.markdown(trade_card(t, ctx, trend), unsafe_allow_html=True)

        rest = ranked[TOP_PER_LEAGUE:]
        if rest:
            with st.expander(f"More ideas — {ctx['name']} ({len(rest)})"):
                for t in rest:
                    st.markdown(trade_card(t, ctx), unsafe_allow_html=True)

    if blocked:
        st.markdown(f'<div class="note" style="margin-top:16px">🔒 Trades disabled in: '
                    f'<b>{esc(", ".join(blocked))}</b> (guillotine/elimination format).</div>',
                    unsafe_allow_html=True)


# ── trade block: shop a specific player ──────────────────────────────────────
def render_trade_block():
    """Ideas built around a player YOU name. The calculator prices a deal you
    already have in mind and the Ideas board picks both sides itself; this sits
    between them — you say who is available and, if you like, what you want back."""
    tradeable = [c for c in data["contexts"] if not c["trades_disabled"] and c["my_roster"]]
    if not tradeable:
        st.markdown('<div class="empty">No leagues with trading enabled.</div>',
                    unsafe_allow_html=True)
        return
    tradeable.sort(key=lambda c: (c["format"] != "dynasty", c["name"]))

    c1, c2 = st.columns([2, 3])
    lname = c1.selectbox("League", [c["name"] for c in tradeable], key="blk_lg")
    ctx = next(c for c in tradeable if c["name"] == lname)
    v = valuer_for(ctx)
    me = ctx["my_roster"]

    rows = sorted(({**pinfo(p, players), "raw": v.raw_value(p), "val": v.value(p)}
                   for p in me["players"] if v.raw_value(p)),
                  key=lambda r: -r["raw"])
    look = {r["id"]: r for r in rows}
    if not rows:
        st.markdown('<div class="empty">Nothing on this roster is priced.</div>',
                    unsafe_allow_html=True)
        return

    want_opts = ["Anything", "QB", "RB", "WR", "TE"]
    if ctx["format"] == "dynasty" and v.pick_scale():
        want_opts.append("Picks")
    with c2:
        st.markdown('<div class="pickerlbl">What you want back</div>',
                    unsafe_allow_html=True)
        want = st.pills("What you want back", want_opts, default="Anything",
                        key="blk_want", label_visibility="collapsed") or "Anything"

    # Dynasty only: whether a worse lineup this year is a cost or the point.
    stance = "Competing"
    if ctx["format"] == "dynasty":
        st.markdown('<div class="pickerlbl">Where your season stands</div>',
                    unsafe_allow_html=True)
        stance = st.pills("Stance", ["Competing", "Tanking"], default="Competing",
                          key="blk_stance", label_visibility="collapsed") or "Competing"

    st.markdown('<div class="pickerlbl">Who you are shopping</div>',
                unsafe_allow_html=True)
    give = st.multiselect("On the block", [r["id"] for r in rows],
                          format_func=lambda i: (f'{look[i]["name"]} · {look[i]["pos"]}-'
                                                 f'{look[i]["team"]} · {look[i]["raw"]:,}'),
                          key="blk_give", label_visibility="collapsed",
                          max_selections=2)
    if not give:
        extra = ('<b>Where your season stands</b> decides whether a deal that '
                 'weakens this year counts against it or for it — tanking ranks '
                 'long-term value and picks, and a worse record means a better '
                 'pick. ' if ctx["format"] == "dynasty" else "")
        st.markdown('<div class="note">Choose a player to shop — two at most, since '
                    'anything larger stops being a trade anyone reads. '
                    '<b>What you want back</b> narrows the return to one position, '
                    f'or to draft picks. {extra}</div>', unsafe_allow_html=True)
        return

    picks_by_team = None
    if ctx["format"] == "dynasty" and v.pick_scale():
        pranks, _ = rankings_for(ctx)
        rank_of = {r["rid"]: r["proj_rank"] for r in pranks}
        name_of = {t["roster_id"]: t["name"] for t in ctx["teams"]}
        cur = int(ctx.get("season") or data["season"])
        inv = A.pick_inventory(ctx, [cur + 1, cur + 2, cur + 3])
        scale = v.pick_scale()
        picks_by_team = {}
        for rid, pks in inv.items():
            out = []
            for pk in pks:
                orig = pk["original_rid"]
                tier = A.pick_tier(rank_of.get(orig, ctx["num_teams"]), ctx["num_teams"])
                raw = v.pick_value(pk["season"], pk["round"], tier)
                if not raw:
                    continue
                suf = VAL.ROUND_SUFFIX.get(pk["round"], f'{pk["round"]}th')
                out.append({"id": f'PICK|{pk["season"]}|{pk["round"]}|{orig}',
                            "name": f'{pk["season"]} {suf} ({tier})', "pos": "PICK",
                            "team": name_of.get(orig, "?"),
                            "val": round(raw * scale, 1), "raw": raw})
            picks_by_team[rid] = out

    with st.spinner("Working the phones…"):
        ideas = A.block_ideas(ctx, v, players, give, want=want, max_ideas=10,
                              picks_by_team=picks_by_team,
                              weekly_maps=weekly_maps_for(ctx), stance=stance)

    shopping = ", ".join(look[i]["name"] for i in give)
    if not ideas:
        st.markdown(f'<div class="empty">No fair return for <b>{esc(shopping)}</b>'
                    + (f' at {esc(want)}' if want != "Anything" else "")
                    + '. Widen what you are looking for, or add a second piece to '
                      'the block.</div>', unsafe_allow_html=True)
        return

    hdr(f'{len(ideas)} ideas for {shopping}'
        + (f" · want {want}" if want != "Anything" else "")
        + (f" · {stance.lower()}" if ctx["format"] == "dynasty" else ""))
    for t in ideas:
        st.markdown(trade_card(t, ctx), unsafe_allow_html=True)


# ── interactive trade calculator ──────────────────────────────────────────────
def render_trade_calc():
    tradeable = [c for c in data["contexts"] if not c["trades_disabled"] and c["my_roster"]]
    if not tradeable:
        st.markdown('<div class="empty">No leagues with trading enabled.</div>',
                    unsafe_allow_html=True)
        return

    # dynasty first: picks, and the deeper roster questions, live there
    tradeable.sort(key=lambda c: (c["format"] != "dynasty", c["name"]))
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

    # ── where each side ranks, position by position ─────────────────────────
    teams_str, avg_str = A.positional_strength(ctx, v, players)
    n_teams = len(teams_str) or 1
    pos_rank = {}
    for pos in ("QB", "RB", "WR", "TE"):
        ordered = sorted(teams_str.items(),
                         key=lambda kv: kv[1]["strength"].get(pos, 0), reverse=True)
        pos_rank[pos] = {rid: i + 1 for i, (rid, _) in enumerate(ordered)}
    pick_rank = {}          # filled in by the pick block below, dynasty only

    def _ord(n):
        return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10, 'th')}"

    def strength_box(team, label):
        """Each position as a league rank rather than a percentage. "3rd of 12 at
        RB" places you immediately; "+56%" needs arithmetic. Where a rival ranks
        near the bottom is where they will pay up."""
        rid = team["roster_id"]
        rows_html = ""
        entries = [(pos, pos_rank[pos].get(rid, n_teams)) for pos in ("QB", "RB", "WR", "TE")]
        if pick_rank:
            entries.append(("PICKS", pick_rank.get(rid, n_teams)))
        for pos, rk in entries:
            share = (n_teams - rk) / max(1, n_teams - 1)      # 1.0 best .. 0.0 worst
            cls = "up" if share >= 0.66 else ("mid" if share >= 0.33 else "dn")
            # last place would otherwise draw an empty track, which reads as "no
            # players here" rather than "worst in the league"
            share = max(share, 0.07)
            rows_html += (
                f'<div class="strrow"><div class="p">{pos}</div>'
                f'<div class="bar"><i class="{cls}" style="left:0;width:{share*100:.0f}%"></i></div>'
                f'<div class="v {cls}">{_ord(rk)}</div></div>')
        return (f'<div class="strbox"><h4><span class="who">{esc(label)}</span>'
                f'<span class="cap">of {n_teams} teams</span></h4>{rows_html}</div>')

    mine_rows, their_rows = rows_for(me), rows_for(partner)

    # ── rookie picks (dynasty only) ──────────────────────────────────────────
    pranks, rec_weight = rankings_for(ctx)
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
        totals = {t["roster_id"]: sum(r["raw"] for r in pick_rows(t)) for t in ctx["teams"]}
        for i, (rid_, _) in enumerate(sorted(totals.items(), key=lambda kv: kv[1],
                                             reverse=True)):
            pick_rank[rid_] = i + 1

    look = {r["id"]: r for r in mine_rows + their_rows}

    def label(pid):
        r = look[pid]
        tag = f'{r["raw"]:,}' if r["raw"] else "unpriced"
        if r["pos"] == "PICK":
            return f'🎟 {r["name"]} · {r["team"]} · {tag}'
        return f'{r["name"]} · {r["pos"]}-{r["team"]} · {tag}'

    st.markdown(f'<div class="strgrid">{strength_box(me, "You")}'
                f'{strength_box(partner, partner["name"])}</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="note">Each position ranked against the rest of the '
                'league. Where a rival sits near the bottom is where they will '
                'pay up.</div>', unsafe_allow_html=True)

    has_picks = any(r["pos"] == "PICK" for r in mine_rows + their_rows)
    filters = ["All", "QB", "RB", "WR", "TE"] + (["Picks"] if has_picks else [])

    def narrow(rows, filter_key, select_key):
        """Position filter over one side's list. Anything already selected stays
        in the options even when it doesn't match — otherwise switching the
        filter would silently drop players you'd already put in the deal."""
        pick = st.pills("Filter", filters, default="All", key=filter_key,
                        label_visibility="collapsed") or "All"
        if pick == "All":
            keep = rows
        elif pick == "Picks":
            keep = [r for r in rows if r["pos"] == "PICK"]
        else:
            keep = [r for r in rows if r["pos"] == pick]
        ids = [r["id"] for r in keep]
        chosen = st.session_state.get(select_key) or []
        ids += [c for c in chosen if c not in ids]
        return ids

    s1, s2 = st.columns(2)
    with s1:
        st.markdown('<div class="pickerlbl">You send</div>', unsafe_allow_html=True)
        send_opts = narrow(mine_rows, "calc_send_f", "calc_send")
        send = st.multiselect("You send", send_opts, format_func=label,
                              key="calc_send", label_visibility="collapsed")
    with s2:
        st.markdown('<div class="pickerlbl">You get</div>', unsafe_allow_html=True)
        recv_opts = narrow(their_rows, "calc_recv_f", "calc_recv")
        recv = st.multiselect("You get", recv_opts, format_func=label,
                              key="calc_recv", label_visibility="collapsed")

    if not send and not recv:
        picks_note = ("Rookie picks are in both lists, priced by their original "
                      "owner's projected finish."
                      if ctx["format"] == "dynasty" and v.pick_scale()
                      else "No rookie picks here — this is a redraft league, so "
                           "there are none to trade.")
        st.markdown('<div class="note">Pick players from each side to price the deal. '
                    f'Values are <b>FantasyCalc {esc(fmt)}</b>, format-adjusted for '
                    f'{ctx["num_teams"]} teams'
                    f'{" · superflex" if ctx["superflex"] else ""}. {picks_note}</div>',
                    unsafe_allow_html=True)
        return

    give_rows = [look[p] for p in send]
    get_rows = [look[p] for p in recv]
    gr = sum(r["raw"] for r in give_rows)
    tr_ = sum(r["raw"] for r in get_rows)

    # The roster-spot charge for an uneven deal — FantasyCalc's own constants,
    # already used when generating ideas but previously missing here, so the
    # calculator was grading packages on a raw sum. It scales with the count
    # difference, so it covers 3-for-1 and beyond, not just 2-for-1.
    adj_g, adj_t = A.package_adjustment(give_rows, get_rows,
                                        ctx["format"] == "dynasty")
    gr_adj, tr_adj = gr + adj_g, tr_ + adj_t
    # Net value stays the plain arithmetic of the two tiles beside it — sending
    # 4,658 for 3,708 is -950, and showing +556 there because a roster-spot
    # credit had been folded in made the three tiles contradict each other.
    # Fairness is where the credit belongs, and the note below explains it.
    diff = tr_ - gr
    adj_diff = tr_adj - gr_adj
    fairness = ((100 - abs(adj_diff) / max(gr_adj, tr_adj) * 100)
                if max(gr_adj, tr_adj) else 0)

    kc = st.columns(4)
    tiles = [(f"{gr:,.0f}", "You send", "", False), (f"{tr_:,.0f}", "You get", "", False),
             (f"{diff:+,.0f}", "Net value", "g" if diff >= 0 else "", diff >= 0),
             (f"{fairness:.0f}%", "Fairness", "g" if fairness >= 85 else "c", False)]
    for col, (n, l, cls, on) in zip(kc, tiles):
        col.markdown(f'<div class="kpi{" on" if on else ""}"><div class="n {cls}">{n}</div>'
                     f'<div class="l">{esc(l)}</div></div>', unsafe_allow_html=True)

    # value over replacement for both rosters — the "does this actually help" test
    my_repl = A._replacement(ctx, v, players, me["roster_id"])
    their_repl = A._replacement(ctx, v, players, partner["roster_id"])
    my_net = (A._surplus_over_replacement(get_rows, my_repl)
              - A._surplus_over_replacement(give_rows, my_repl))
    their_net = (A._surplus_over_replacement(give_rows, their_repl)
                 - A._surplus_over_replacement(get_rows, their_repl))

    real = lambda ids: [x for x in ids if not str(x).startswith("PICK|")]
    my_pids = [str(x) for x in me["players"]]
    their_pids = [str(x) for x in partner["players"]]
    my_after = [x for x in my_pids if x not in set(send)] + real(recv)
    their_after = [x for x in their_pids if x not in set(recv)] + real(send)

    def lp(pids):
        lu, _ = A.optimal_lineup(pids, ctx["roster_positions"], players, v.start_score)
        return sum(v.points(pid) for _, pid in lu if pid)

    def lv(pids):
        return A._lineup_value(pids, ctx, v, players)

    def lvr(pids):                      # same lineup, in FantasyCalc's own units
        return A._lineup_value_raw(pids, ctx, v, players)

    d_pts, t_pts = lp(my_after) - lp(my_pids), lp(their_after) - lp(their_pids)

    # Rest of season, re-picking the best lineup EACH week and summing. Choosing
    # one lineup off summed projections is materially wrong, not just imprecise:
    # on this roster it overstated a trade by 11 points across 14 weeks, because
    # a starter on his bye still held his slot and his replacement scored nothing.
    _w0, _w1 = S.fantasy_weeks(ctx["league"], data["week"])
    _maps = S.weekly_projection_maps(data["season"], _w0, ctx["scoring_key"], _w1)

    def lros(pids):
        return A.lineup_points_over_weeks(pids, ctx, players, _maps)

    d_ros, t_ros = lros(my_after) - lros(my_pids), lros(their_after) - lros(their_pids)
    d_val, t_val = lv(my_after) - lv(my_pids), lv(their_after) - lv(their_pids)
    base_raw, their_base_raw = lvr(my_pids), lvr(their_pids)
    d_raw, t_rawv = lvr(my_after) - base_raw, lvr(their_after) - their_base_raw
    d_pct = (100.0 * d_raw / base_raw) if base_raw else 0.0
    t_pct = (100.0 * t_rawv / their_base_raw) if their_base_raw else 0.0

    # where each team is projected to finish, before and after this deal
    def ranks_with(rosters):
        alt = dict(ctx)
        alt["teams"] = [{**t, "players": rosters.get(t["roster_id"], t["players"])}
                        for t in ctx["teams"]]
        alt["my_roster"] = next(t for t in alt["teams"]
                                if t["roster_id"] == me["roster_id"])
        pr, _ = A.power_rankings(alt, v, players, ros=ros_for(ctx))
        return {r["rid"]: r["proj_rank"] for r in pr}

    before = ranks_with({})
    after_r = ranks_with({me["roster_id"]: my_after, partner["roster_id"]: their_after})
    n_t = ctx["num_teams"] or len(ctx["teams"])

    def _ord2(n):
        return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"

    def move(rid):
        a, b = before.get(rid), after_r.get(rid)
        if not a or not b:
            return "—"
        if a == b:
            return f'{_ord2(a)} (no change)'
        arrow = "▲" if b < a else "▼"
        cls = "g" if b < a else "r"
        return f'{_ord2(a)} → <span class="{cls}">{_ord2(b)} {arrow}</span>'

    # Judge the headline on what the table actually shows. Value over replacement
    # alone called deals win-win that gut the other roster's startable lineup —
    # they receive two players above their own replacement level while losing the
    # best player in the trade. Nobody accepts that, and claiming otherwise makes
    # the verdict useless as something to send a leaguemate.
    if d_val > 0 and t_val > 0:
        cls, head = "win", "Win-win — both rosters come out ahead"
    elif d_val > 0 and t_val > -1.0:
        cls, head = "win", "Good for you, roughly neutral for them"
    elif d_val > 0:
        cls, head = "even", "Better for you — they lose roster value, expect pushback"
    elif t_val > 0 and d_val <= 0:
        cls, head = "lose", "Better for them than for you"
    else:
        cls, head = "even", "Neither side clearly gains"

    def cell(x, unit=""):
        c = "g" if x > 0.05 else ("r" if x < -0.05 else "")
        return f'<span class="{c}">{x:+.1f}{unit}</span>'

    def cellp(pct, raw):                # share of that side's own starting lineup
        c = "g" if raw > 0 else ("r" if raw < 0 else "")
        return f'<span class="{c}">{pct:+.1f}%</span>'

    st.markdown(
        f'<div class="verdict {cls}">{esc(head)}'
        f'<div class="impact">'
        f'<div class="ih"></div><div class="ih">You</div>'
        f'<div class="ih">{esc(partner["name"][:18])}</div>'
        f'<div class="k">Week {data["week"]} lineup</div>'
        f'<div>{cell(d_pts, " pts")}</div><div>{cell(t_pts, " pts")}</div>'
        f'<div class="k">Rest of season (wk {_w0}–{_w1})</div>'
        f'<div>{cell(d_ros, " pts")}</div><div>{cell(t_ros, " pts")}</div>'
        f'<div class="k">Projected finish (of {n_t})</div>'
        f'<div>{move(me["roster_id"])}</div><div>{move(partner["roster_id"])}</div>'
        f'</div></div>', unsafe_allow_html=True)

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
        credit = adj_g or adj_t
        who = "your side" if adj_g else f"{esc(partner['name'])}'s side"
        st.markdown(f'<div class="note">📦 <b>{len(send)}-for-{len(recv)}</b> — the side '
                    'taking on more bodies has to cut someone to fit them, so each extra '
                    f'body counts for less than face value. <b>{credit:,.0f}</b> is credited '
                    f'to {who} for that, which is why the fairness above is not a straight '
                    'sum. FantasyCalc\'s own constants, scaled to the count difference.'
                    '</div>', unsafe_allow_html=True)


# ── header stat rail ──────────────────────────────────────────────────────────
with ticker_slot:
    render_ticker()

# ── top-level board ───────────────────────────────────────────────────────────
# The guillotine tab only exists for accounts that actually play the format —
# Sleeper flags it structurally as settings.type == 3, so this is not a guess.
_has_guillotine = any(c["format"] == "guillotine" for c in data["contexts"])
_labels = ["⚡ This Week", "🏆 Leagues", "📊 This Week's Rankings", "🤝 Trades"]
if _has_guillotine:
    _labels.append("🪓 Guillotine FAAB Strategy (coming soon)")

top = st.tabs(_labels)
with top[0]:
    render_action_center()
with top[1]:
    render_leagues_overview()
with top[2]:
    render_rankings()
with top[3]:
    # both are trade tools: price your own deal, or browse suggestions
    sub = st.tabs(["🧮 Calculator", "💡 Ideas", "📋 Trade Block"])
    with sub[0]:
        render_trade_calc()
    with sub[1]:
        render_trade_ideas_global()
    with sub[2]:
        render_trade_block()
if _has_guillotine:
    with top[4]:
        render_guillotine()

st.markdown('<div class="note" style="margin-top:22px">Data: Sleeper public API · '
            'Projections live · Trade values from FantasyCalc. '
            'Share this dashboard — anyone can enter their own Sleeper username above (or use <b>?u=username</b>).</div>',
            unsafe_allow_html=True)
