"""Rival Watch: the Market Intelligence dashboard (Streamlit).

The idea: quick commerce runs on order slips, so each day's intelligence
is printed as a dispatch slip. Around it sit three views built for this
project rather than generic charts:
  - the verdict: the latest risk level, said plainly and large
  - the 30-day strip: one tile per day, coloured by that day's risk
    (grey tiles are days the pipeline did not run)
  - the rival board: one square per event that mentions a competitor

Run from the project root:   streamlit run dashboard/app.py
The theme lives in .streamlit/config.toml at the project root.
"""
import html
import os
import re
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------------------- settings
BACKEND = os.getenv("MIS_BACKEND_URL", "http://localhost:8000")

RISK_ORDER = ["LOW", "MEDIUM", "HIGH"]
RISK_SCORE = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
RISK_COLORS = {"LOW": "#43D18A", "MEDIUM": "#FFB224", "HIGH": "#FF5C4D"}
CONFIDENCE_WORDS = {"LOW": "not very sure", "MEDIUM": "fairly sure", "HIGH": "very sure"}
DEFAULT_WATCHLIST = (
    "Blinkit, Swiggy Instamart, BigBasket, Flipkart Minutes, JioMart, Amazon Fresh"
)
STRIP_DAYS = 30          # how many days the strip shows
STALE_AFTER_HOURS = 26   # the pipeline runs daily; longer than this means a missed run
MAX_SQUARES = 40         # rival board: squares per row before showing "+n"

st.set_page_config(page_title="Rival watch", page_icon="🧾", layout="wide")

# ---------------------------------------------------------------- styles
st.html(
    """
<style>
:root {
  --plum: #1A0F24; --panel: #26172F; --ink: #F1ECF6; --muted: #A898B8;
  --lilac: #C9A7FF; --paper: #F7F4EE; --paper-ink: #2A2230;
  --low: #43D18A; --medium: #FFB224; --high: #FF5C4D; --none: #3A2A47;
}
.block-container { padding-top: 4rem; max-width: 1240px; }

/* ---- masthead */
.masthead { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; margin-bottom: 4px; }
.masthead h1 { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; margin: 0; padding: 0; }
.masthead .sub { color: var(--muted); font-size: 1rem; }

/* ---- verdict */
.verdict-kicker { color: var(--muted); font-size: 0.95rem; margin: 18px 0 0; }
.verdict { font-size: clamp(3.2rem, 7vw, 5.6rem); font-weight: 800; line-height: 0.95;
           letter-spacing: -0.045em; margin: 6px 0 14px; }
.verdict-note { font-size: 1.08rem; line-height: 1.55; max-width: 46ch; color: var(--ink); }

/* ---- 30-day strip */
.strip-wrap { margin-top: 34px; }
.strip-title { font-weight: 700; font-size: 1rem; margin-bottom: 8px; }
.strip { display: grid; grid-template-columns: repeat(30, 1fr); gap: 4px; max-width: 640px; }
.strip .d { aspect-ratio: 1 / 1.6; border-radius: 3px; background: var(--none); }
.strip .d.today { outline: 2px solid var(--lilac); outline-offset: 2px; }
.strip-axis { display: flex; justify-content: space-between; max-width: 640px;
              color: var(--muted); font-size: 0.8rem; margin-top: 6px; }
.legend { display: flex; gap: 16px; flex-wrap: wrap; color: var(--muted); font-size: 0.85rem; margin-top: 12px; }
.legend i { display: inline-block; width: 10px; height: 14px; border-radius: 2px; margin-right: 6px;
            vertical-align: -2px; }
.tally { margin-top: 14px; font-size: 1rem; color: var(--ink); }

/* ---- dispatch slip (the receipt) */
.slip-holder { display: flex; justify-content: center; padding: 6px 0 0; }
.slip {
  --edge: 9px;
  width: 100%; max-width: 380px; background: var(--paper); color: var(--paper-ink);
  font-family: 'IBM Plex Mono', ui-monospace, Menlo, Consolas, monospace; font-size: 0.82rem;
  line-height: 1.5; padding: 26px 22px 30px; position: relative;
  transform: rotate(-1.2deg);
  box-shadow: 0 18px 40px rgba(0,0,0,0.45);
  /* torn top and bottom edges */
  -webkit-mask:
    conic-gradient(from -45deg at bottom, #0000, #000 1deg 89deg, #0000 90deg) bottom / calc(2*var(--edge)) var(--edge) repeat-x,
    conic-gradient(from 135deg at top, #0000, #000 1deg 89deg, #0000 90deg) top / calc(2*var(--edge)) var(--edge) repeat-x,
    linear-gradient(#000 0 0) center / 100% calc(100% - 2*var(--edge)) no-repeat;
          mask:
    conic-gradient(from -45deg at bottom, #0000, #000 1deg 89deg, #0000 90deg) bottom / calc(2*var(--edge)) var(--edge) repeat-x,
    conic-gradient(from 135deg at top, #0000, #000 1deg 89deg, #0000 90deg) top / calc(2*var(--edge)) var(--edge) repeat-x,
    linear-gradient(#000 0 0) center / 100% calc(100% - 2*var(--edge)) no-repeat;
}
.slip.flat { transform: none; }
.slip .c { text-align: center; }
.slip .brand { font-weight: 600; font-size: 1rem; letter-spacing: 0.08em; }
.slip .rule { border-top: 1px dashed rgba(42,34,48,0.55); margin: 10px 0; }
.slip .rule.double { border-top: 3px double rgba(42,34,48,0.8); }
.slip .h { font-weight: 600; margin-bottom: 2px; }
.slip .row { display: flex; justify-content: space-between; gap: 12px; }
.slip ol { margin: 0; padding-left: 1.4em; }
.slip ol li { margin: 0 0 2px; font-size: 0.82rem !important; line-height: 1.5 !important; }
.slip ol { margin: 0 !important; }
.slip .total { display: flex; justify-content: space-between; align-items: center;
               font-weight: 600; font-size: 1.05rem; margin-top: 4px; }
.slip .stamp { padding: 3px 12px; color: #fff; font-weight: 600; letter-spacing: 0.06em; }
.slip .barcode { display: flex; justify-content: center; height: 34px; margin: 16px 0 6px; }
.slip .barcode span { display: block; height: 100%; }
.slip .tiny { font-size: 0.72rem; opacity: 0.7; }
.slip .why-rule { display: flex; justify-content: space-between; gap: 10px; }
.slip .why-rule span:first-child { overflow-wrap: anywhere; }
.slip .stamp-review {
  position: absolute; top: 120px; right: 14px; transform: rotate(14deg);
  border: 3px solid #C2382F; color: #C2382F; padding: 4px 10px; border-radius: 4px;
  font-weight: 700; font-size: 0.9rem; letter-spacing: 0.08em; text-align: center;
  line-height: 1.15; opacity: 0.85; background: rgba(247,244,238,0.6);
}
.review-flag { margin-top: 14px; padding: 10px 14px; border-left: 4px solid var(--high);
               background: rgba(255,92,77,0.08); max-width: 46ch; line-height: 1.5; }

/* ---- rival board */
.board-title { font-weight: 800; font-size: 1.6rem; letter-spacing: -0.02em; margin: 6px 0 2px; }
.board-sub { color: var(--muted); margin-bottom: 18px; }
.rival { display: grid; grid-template-columns: 170px 1fr 48px; align-items: center; gap: 14px;
         padding: 9px 0; border-bottom: 1px solid rgba(201,167,255,0.12); }
.rival .name { font-weight: 600; }
.rival .sq { display: flex; flex-wrap: wrap; gap: 4px; }
.rival .sq span { width: 14px; height: 14px; border-radius: 2px; }
.rival .sq em { color: var(--muted); font-style: normal; font-size: 0.85rem; margin-left: 4px; }
.rival .n { text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
.rival.quiet .name { color: var(--muted); font-weight: 400; }

/* ---- small screens */
@media (max-width: 760px) {
  .strip { grid-template-columns: repeat(15, 1fr); }
  .rival { grid-template-columns: 110px 1fr 36px; }
  .slip { transform: none; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
"""
)


# ---------------------------------------------------------------- data access
@st.cache_data(ttl=30, show_spinner=False)
def fetch(path):
    """GET a backend path. Returns (json_data, error) where error is None on success."""
    try:
        r = requests.get(f"{BACKEND}{path}", timeout=10)
    except requests.exceptions.ConnectionError:
        return None, "offline"
    except requests.exceptions.Timeout:
        return None, "timeout"
    if r.status_code == 404:
        return None, "not_found"
    if r.status_code != 200:
        return None, f"http_{r.status_code}"
    return r.json(), None


def load_events():
    """All events as a DataFrame, newest first, with helper columns added."""
    data, err = fetch("/api/events/all?limit=1000")
    if err:
        return None, err
    df = pd.DataFrame(data.get("events", []))
    if df.empty:
        return df, None

    # Older backend versions don't send these from /all
    for col in ["top_reasons", "impact_areas", "recommended_actions"]:
        if col not in df.columns:
            df[col] = ""

    # format="mixed": timestamps may or may not include microseconds
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", format="mixed")
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    df["day"] = df["date_parsed"].fillna(df["created_at"]).dt.normalize()
    df["risk_level"] = df["risk_level"].astype(str).str.upper()
    df["confidence"] = df["confidence"].astype(str).str.upper()
    df["risk_score"] = df["risk_level"].map(RISK_SCORE)
    return df.sort_values("created_at", ascending=False), None


# ---------------------------------------------------------------- text helpers
def clean(text):
    """Strip Markdown symbols the AI adds (** and #) so text reads cleanly on the slip."""
    text = text if isinstance(text, str) else ""
    text = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def as_items(text):
    """Turn '1. a\\n2. b' into ['a', 'b'] for a numbered list."""
    lines = [l.strip() for l in clean(text).splitlines() if l.strip()]
    return [re.sub(r"^(\d+[.)]|[-*•])\s*", "", l) for l in lines]


def ol(text, empty="Not recorded"):
    items = as_items(text)
    if not items:
        return f"<div>{empty}</div>"
    return "<ol>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ol>"


def short(text, limit=420):
    text = clean(text).replace("\n", " ")
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def rivals_in(event, watchlist):
    """Watched competitor names that this event mentions."""
    hay = f'{event.get("competitors", "")} {event.get("summary", "")}'.lower()
    return [n for n in watchlist if n.lower() in hay]


def barcode(seed):
    """Decorative barcode drawn from the event id, so each slip's is different."""
    bars = []
    for i, ch in enumerate(f"{seed:06d}RIVALWATCH{seed * 7919}"):
        w = 1 + (ord(ch) + i) % 3
        color = "#2A2230" if i % 2 == 0 else "transparent"
        bars.append(f'<span style="width:{w * 2}px;background:{color}"></span>')
    return f'<div class="barcode" aria-hidden="true">{"".join(bars)}</div>'


RULE_NAMES = {
    "regulatory_action": "Regulatory action",
    "funding_or_ipo": "Funding or IPO",
    "large_amount": "Large amount",
    "market_expansion": "Expansion",
    "price_war": "Price war",
    "multiple_sources": "Several sources",
}


def has_hybrid(event):
    """True if this event was scored by the hybrid engine (older events were not)."""
    level = event.get("llm_risk_level")
    return isinstance(level, str) and level != ""


def needs_review(event):
    """True only when the backend flagged this event (works for missing/NaN values too)."""
    value = event.get("needs_review")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(value)


def rules_list(event):
    rules = event.get("rules_fired")
    return rules if isinstance(rules, list) else []


def scoring_html(event):
    """The 'how it was scored' block on the slip."""
    if not has_hybrid(event):
        return '<div class="tiny">Scored by the AI only (saved before hybrid scoring).</div>'
    rules = rules_list(event)
    rule_rows = "".join(
        f'<div class="why-rule"><span>{html.escape(RULE_NAMES.get(r.get("rule"), r.get("rule", "")))}'
        f' ({html.escape(", ".join(map(str, r.get("matched", [])))[:60])})</span>'
        f'<span>+{int(r.get("points", 0))}</span></div>'
        for r in rules
    ) or "<div>No warning signs found</div>"
    score = event.get("final_score")
    score_txt = f"{float(score):.1f} of 3" if score is not None and pd.notna(score) else "-"
    return f"""
  <div class="h">HOW IT WAS SCORED</div>
  <div class="row"><span>AI said</span><span>{html.escape(str(event["llm_risk_level"]).title())}</span></div>
  <div class="row"><span>Rules</span><span>{int(event.get("rule_points") or 0)} points</span></div>
  {rule_rows}
  <div class="row"><span>Combined score</span><span>{score_txt}</span></div>"""


# ---------------------------------------------------------------- building blocks
def slip(event, watchlist, flat=False):
    """The dispatch slip for one event."""
    level = event["risk_level"]
    color = RISK_COLORS.get(level, "#777")
    saved = pd.to_datetime(event.get("created_at"), errors="coerce", format="mixed")
    saved_txt = saved.strftime("%d %b %Y  %H:%M") if pd.notna(saved) else event.get("date", "")
    spotted = rivals_in(event, watchlist)
    rivals_html = (
        html.escape(", ".join(spotted)) if spotted else html.escape(short(event.get("competitors", ""), 140))
    )
    return f"""
<div class="slip-holder"><div class="slip {'flat' if flat else ''}">
  {'<div class="stamp-review">CHECK<br>BY HAND</div>' if needs_review(event) else ''}
  <div class="c brand">RIVAL WATCH</div>
  <div class="c">Daily dispatch for Zepto</div>
  <div class="rule"></div>
  <div class="row"><span>Run #{int(event["id"])}</span><span>{html.escape(saved_txt)}</span></div>
  <div class="rule"></div>
  <div class="h">RIVALS SPOTTED</div>
  <div>{rivals_html or "None named"}</div>
  <div class="rule"></div>
  <div class="h">WHAT HAPPENED</div>
  <div>{html.escape(short(event.get("summary", "")))}</div>
  <div class="rule"></div>
  <div class="h">WHY</div>{ol(event.get("top_reasons"))}
  <div class="h" style="margin-top:8px">AFFECTED</div>{ol(event.get("impact_areas"))}
  <div class="h" style="margin-top:8px">DO NEXT</div>{ol(event.get("recommended_actions"))}
  <div class="rule"></div>
  {scoring_html(event)}
  <div class="rule"></div>
  <div class="row"><span>AI confidence</span><span>{html.escape(str(event.get("confidence", "")).title())}</span></div>
  <div class="row"><span>Sources</span><span>{int(event.get("source_count") or 1)}</span></div>
  <div class="rule double"></div>
  <div class="total"><span>RISK</span><span class="stamp" style="background:{color}">{level}</span></div>
  {barcode(int(event["id"]))}
  <div class="c tiny">Printed by the n8n pipeline. Keep for your records.</div>
</div></div>"""


def strip_html(events):
    """One tile per day for the last STRIP_DAYS days, coloured by that day's highest risk."""
    today = pd.Timestamp.now().normalize()
    days = pd.date_range(end=today, periods=STRIP_DAYS, freq="D")
    daily = events.groupby("day")["risk_score"].max()
    names = {v: k for k, v in RISK_SCORE.items()}
    tiles = []
    for d in days:
        score = daily.get(d)
        if pd.notna(score):
            level = names[int(score)]
            style = f'style="background:{RISK_COLORS[level]}"'
            label = f"{d:%d %b}: {level.title()} risk"
        else:
            style, label = "", f"{d:%d %b}: no run"
        today_cls = " today" if d == today else ""
        tiles.append(f'<div class="d{today_cls}" {style} title="{label}" aria-label="{label}"></div>')
    window = events[events["day"] >= days[0]]
    counts = window["risk_level"].value_counts()
    ran = window["day"].nunique()
    tally = (
        f'In the last {STRIP_DAYS} days the pipeline ran on {ran} '
        f'{"day" if ran == 1 else "days"}: '
        f'{counts.get("HIGH", 0)} high, {counts.get("MEDIUM", 0)} medium and {counts.get("LOW", 0)} low risk.'
    )
    legend = "".join(
        f'<span><i style="background:{RISK_COLORS[r]}"></i>{r.title()}</span>' for r in RISK_ORDER
    ) + '<span><i style="background:var(--none)"></i>No run</span>'
    return f"""
<div class="strip-wrap">
  <div class="strip-title">The last {STRIP_DAYS} days</div>
  <div class="strip">{''.join(tiles)}</div>
  <div class="strip-axis"><span>{days[0]:%d %b}</span><span>Today</span></div>
  <div class="legend">{legend}</div>
  <div class="tally">{tally}</div>
</div>"""


def board_html(events, watchlist):
    """Rival board: one square per event mentioning each competitor, oldest to newest."""
    oldest_first = events.sort_values("created_at")
    rows = []
    for name in watchlist:
        hits = oldest_first[
            (oldest_first["competitors"].fillna("") + " " + oldest_first["summary"].fillna(""))
            .str.lower().str.contains(name.lower(), regex=False)
        ]
        rows.append((name, hits))
    rows.sort(key=lambda r: (-(r[1]["risk_level"] == "HIGH").sum(), -len(r[1])))

    out = []
    for name, hits in rows:
        squares = "".join(
            f'<span style="background:{RISK_COLORS[r.risk_level]}" '
            f'title="{r.date}: {r.risk_level.title()} risk"></span>'
            for r in hits.tail(MAX_SQUARES).itertuples()
        )
        extra = f"<em>+{len(hits) - MAX_SQUARES} earlier</em>" if len(hits) > MAX_SQUARES else ""
        quiet = " quiet" if hits.empty else ""
        body = squares + extra if not hits.empty else '<em>Not mentioned</em>'
        out.append(
            f'<div class="rival{quiet}"><div class="name">{html.escape(name)}</div>'
            f'<div class="sq">{body}</div><div class="n">{len(hits)}</div></div>'
        )
    return "".join(out)


def connection_error(err):
    if err in ("offline", "timeout"):
        st.error(
            f"The dashboard can't reach the backend at `{BACKEND}`.\n\n"
            "Start it in its own terminal:\n\n"
            "```\nvenv\\Scripts\\activate\ncd backend\nuvicorn app.main:app --reload\n```\n"
            "Then select **Refresh data** in the sidebar."
        )
    else:
        st.error(
            f"The backend answered with an error ({err}). This usually means Supabase is "
            "paused. Open your project on supabase.com, select **Restore project**, "
            "restart uvicorn, then select **Refresh data**."
        )
    st.stop()


# ---------------------------------------------------------------- sidebar (refresh first, so it works when offline)
with st.sidebar:
    if st.button("Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

events, err = load_events()

st.html(
    '<div class="masthead"><h1>Rival watch</h1>'
    '<span class="sub">What Zepto\'s quick-commerce competitors did, read every morning</span></div>'
)

if err:
    connection_error(err)

with st.sidebar:
    st.header("Rivals to watch")
    watch_text = st.text_area("Names, separated by commas", value=DEFAULT_WATCHLIST, height=100)
    watchlist = [w.strip() for w in watch_text.split(",") if w.strip()]

    if not events.empty:
        st.header("Narrow the board and log")
        risk_pick = st.multiselect("Risk level", RISK_ORDER, default=RISK_ORDER,
                                   format_func=str.title)
        first_day, last_day = events["day"].min().date(), events["day"].max().date()
        date_pick = st.date_input("Dates", value=(first_day, last_day),
                                  min_value=first_day, max_value=last_day)
        search = st.text_input("Search summaries", placeholder="funding, dark stores, pricing")
    st.caption(f"Reading from `{BACKEND}`")

if events.empty:
    st.info(
        "Nothing printed yet. Run the n8n workflow and approve the email; "
        "the first dispatch slip will appear here."
    )
    st.stop()

# Filters apply to the rival board and the event log. The verdict, slip and
# strip always show the real latest picture.
filtered = events[events["risk_level"].isin(risk_pick)]
if isinstance(date_pick, (list, tuple)) and len(date_pick) == 2:
    start, end = pd.Timestamp(date_pick[0]), pd.Timestamp(date_pick[1])
    filtered = filtered[(filtered["day"] >= start) & (filtered["day"] <= end)]
if search:
    filtered = filtered[filtered["summary"].str.contains(search, case=False, na=False)]

# ---------------------------------------------------------------- verdict + slip
latest = events.iloc[0].to_dict()
latest_detail, latest_err = fetch("/api/events/latest")
if latest_err is None and latest_detail and latest_detail.get("id") == latest["id"]:
    latest.update({k: latest_detail.get(k, latest.get(k)) for k in
                   ["top_reasons", "impact_areas", "recommended_actions"]})

level = latest["risk_level"]
saved = latest["created_at"]
hours_ago = (pd.Timestamp.now() - saved).total_seconds() / 3600 if pd.notna(saved) else None
when = (
    "this morning's run" if hours_ago is not None and hours_ago < 18
    else f"the run on {saved:%d %b}" if pd.notna(saved) else "the latest run"
)
spotted = rivals_in(latest, watchlist)
who = (
    ", ".join(spotted[:-1]) + f" and {spotted[-1]}" if len(spotted) > 1
    else spotted[0] if spotted else "the competitors it found"
)
note = (
    f"From {when}. The AI looked at news about {html.escape(who)} and is "
    f"{CONFIDENCE_WORDS.get(latest['confidence'], 'unsure')} about this call, "
    f"based on {int(latest.get('source_count') or 1)} "
    f"{'source' if int(latest.get('source_count') or 1) == 1 else 'sources'}."
)

if has_hybrid(latest) and str(latest["llm_risk_level"]).upper() != level:
    note += (f" The AI alone said {str(latest['llm_risk_level']).title()}; the rule check "
             f"moved it to {level.title()}.")
review_html = (
    '<div class="review-flag"><b>Check this one by hand.</b> The AI and the rule check '
    'strongly disagree, which can mean the AI guessed without evidence.</div>'
    if needs_review(latest) else ""
)

left, right = st.columns([1.35, 1], gap="large")
with left:
    st.html(
        f'<div class="verdict-kicker">Latest verdict</div>'
        f'<div class="verdict" style="color:{RISK_COLORS[level]}">{level.title()} risk</div>'
        f'<div class="verdict-note">{note}</div>'
        + review_html
        + strip_html(events)
    )
    if hours_ago is not None and hours_ago > STALE_AFTER_HOURS:
        st.warning(
            f"No new dispatch for {hours_ago / 24:.0f} days. Check the Pipeline health tab below."
        )
with right:
    st.html(slip(latest, watchlist))

st.divider()

# ---------------------------------------------------------------- rival board
st.html(
    '<div class="board-title">Rival board</div>'
    '<div class="board-sub">Each square is one day a competitor was in the news, '
    'coloured by how risky that day was for Zepto. Busiest and riskiest rivals rise to the top.</div>'
)
if filtered.empty:
    st.info("No events match the sidebar filters. Widen the dates or risk levels.")
elif not watchlist:
    st.info("Add competitor names in the sidebar to fill the board.")
else:
    st.html(board_html(filtered, watchlist))

st.divider()

# ---------------------------------------------------------------- log + health
tab_log, tab_health = st.tabs(["Dispatch log", "Pipeline health"])

with tab_log:
    if filtered.empty:
        st.info("No events match the sidebar filters.")
    else:
        pick_col, slip_col = st.columns([1.35, 1], gap="large")
        with pick_col:
            for col in ["llm_risk_level", "needs_review"]:
                if col not in filtered.columns:
                    filtered[col] = None
            table = filtered[["id", "day", "risk_level", "llm_risk_level", "needs_review",
                              "confidence", "source_count", "summary"]].copy()
            table["llm_risk_level"] = table["llm_risk_level"].fillna("").astype(str).str.title()
            table["needs_review"] = table["needs_review"].fillna(False).astype(bool)
            table["risk_level"] = table["risk_level"].str.title()
            table["confidence"] = table["confidence"].str.title()
            table["summary"] = table["summary"].map(clean)
            st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                height=min(420, 38 + 35 * len(table)),
                column_config={
                    "id": st.column_config.NumberColumn("Run", width="small"),
                    "day": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                    "risk_level": st.column_config.TextColumn("Final risk", width="small"),
                    "llm_risk_level": st.column_config.TextColumn("AI said", width="small"),
                    "needs_review": st.column_config.CheckboxColumn("Check by hand", width="small"),
                    "confidence": st.column_config.TextColumn("Confidence", width="small"),
                    "source_count": st.column_config.NumberColumn("Sources", width="small"),
                    "summary": st.column_config.TextColumn("What happened", width="large"),
                },
            )
            export = filtered.drop(columns=["date_parsed", "day", "risk_score"], errors="ignore")
            st.download_button(
                "Download these runs as CSV",
                data=export.to_csv(index=False).encode("utf-8"),
                file_name=f"rival_watch_{datetime.now():%Y%m%d}.csv",
                mime="text/csv",
            )
            labels = {
                int(r.id): f"Run #{r.id}, {r.date}, {r.risk_level.title()} risk"
                for r in filtered.itertuples()
            }
            chosen = st.selectbox("Print the slip for", list(labels), format_func=labels.get)
            row = filtered[filtered["id"] == chosen].iloc[0].to_dict()
            with st.expander("Read the full summary"):
                st.markdown(row["summary"])
        with slip_col:
            st.html(slip(row, watchlist, flat=True))

with tab_health:
    health, health_err = fetch("/health")
    checks = [
        ("Backend", health_err is None,
         f"Running, version {health.get('version', '?')}" if health_err is None else "Not responding"),
        ("Database", True, f"Connected, {len(events)} runs stored"),
        ("Daily pipeline", hours_ago is not None and hours_ago <= STALE_AFTER_HOURS,
         f"Last run {hours_ago:.0f} hours ago" if hours_ago is not None else "No runs yet"),
    ]
    for name, ok, text in checks:
        (st.success if ok else st.warning)(f"**{name}.** {text}")

    if hours_ago is None or hours_ago > STALE_AFTER_HOURS:
        st.markdown(
            "The pipeline should print one slip a day. If it hasn't, check these in order:\n\n"
            "1. **n8n is running** (`n8n start`) and the workflow is **active**.\n"
            "2. **Gmail is connected.** Open the Gmail node and reconnect if it asks.\n"
            "3. **The approval email was answered.** The run waits until you approve.\n"
            "4. **Gemini limits.** Too many runs in one day can hit the free-tier limit.\n"
            "5. **Supabase is awake.** Free projects pause after a week without use."
        )
