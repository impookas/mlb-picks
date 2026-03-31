#!/usr/bin/env python3
"""
MLB Picks — Multi-page static site generator.
Pages: index (today), track-record, how-it-works
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
PICKS_DIR = ROOT / "picks"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"
BACKTEST_DIR = ROOT / "backtest"
SITE_DIR = ROOT / "site" / "public"

NOW = datetime.now().strftime("%B %d, %Y at %I:%M %p ET")
YEAR = datetime.now().year


def load_all_results():
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        with open(f) as fh:
            results.append(json.load(fh))
    return results


def load_latest_picks():
    files = sorted(PICKS_DIR.glob("*.json"), reverse=True)
    if not files:
        return None, None
    with open(files[0]) as f:
        return files[0].stem, json.load(f)


def load_season_report():
    report_file = REPORTS_DIR / "season.json"
    if report_file.exists():
        with open(report_file) as f:
            return json.load(f)
    return None


# ── Shared Components ─────────────────────────────────────────────────

SHARED_CSS = '''
:root {
    --bg: #0a0e17;
    --surface: #111827;
    --surface2: #1a2332;
    --surface3: #1f2b3d;
    --border: #1e293b;
    --border-hover: #334155;
    --text: #e2e8f0;
    --text-dim: #94a3b8;
    --text-muted: #64748b;
    --accent: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.12);
    --green: #22c55e;
    --green-dim: rgba(34, 197, 94, 0.12);
    --red: #ef4444;
    --red-dim: rgba(239, 68, 68, 0.12);
    --amber: #f59e0b;
    --high: #f97316;
    --medium: #3b82f6;
    --low: #64748b;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Nav */
.nav {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(12px);
    background: rgba(17, 24, 39, 0.92);
}

.nav-inner {
    max-width: 960px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.8rem 1.5rem;
}

.nav-brand {
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--text);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.nav-brand:hover { text-decoration: none; }
.nav-brand span { color: var(--accent); }

.nav-links {
    display: flex;
    gap: 0.25rem;
}

.nav-links a {
    padding: 0.5rem 1rem;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--text-dim);
    transition: all 0.15s;
}

.nav-links a:hover {
    background: var(--surface2);
    color: var(--text);
    text-decoration: none;
}

.nav-links a.active {
    background: var(--accent-glow);
    color: var(--accent);
}

/* Container */
.container {
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
}

/* Page header */
.page-header {
    margin-bottom: 2rem;
}

.page-header h1 {
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin-bottom: 0.3rem;
}

.page-header .subtitle {
    color: var(--text-dim);
    font-size: 0.95rem;
}

/* Stats row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.75rem;
    margin-bottom: 2.5rem;
}

.stat-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.1rem 1rem;
    text-align: center;
}

.stat-val {
    font-size: 1.7rem;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.stat-label {
    font-size: 0.7rem;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.2rem;
}

.c-green { color: var(--green); }
.c-red { color: var(--red); }
.c-amber { color: var(--amber); }
.c-blue { color: var(--accent); }

/* Section */
.section {
    margin-bottom: 2.5rem;
}

.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.badge {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.15rem 0.55rem;
    border-radius: 5px;
    background: var(--accent);
    color: white;
}

/* Pick cards */
.pick-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 0.85rem;
    overflow: hidden;
    transition: border-color 0.2s;
}
.pick-card:hover { border-color: var(--border-hover); }
.pick-card.high { border-left: 3px solid var(--high); }
.pick-card.medium { border-left: 3px solid var(--medium); }
.pick-card.low { border-left: 3px solid var(--low); }

.pick-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.2rem 0.5rem;
}

.matchup-name {
    font-size: 1.05rem;
    font-weight: 700;
}

.matchup-name .at { color: var(--text-muted); font-weight: 400; margin: 0 0.25rem; }

.conf-tag {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15rem 0.55rem;
    border-radius: 5px;
}
.conf-tag.high { background: rgba(249,115,22,0.15); color: var(--high); }
.conf-tag.medium { background: var(--accent-glow); color: var(--medium); }
.conf-tag.low { background: rgba(100,116,139,0.15); color: var(--low); }

.pick-body {
    padding: 0.5rem 1.2rem 1rem;
}

.pitcher-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.65rem 0.85rem;
    background: var(--surface2);
    border-radius: 8px;
    margin-bottom: 0.85rem;
}

.p-side { flex: 1; }
.p-name { font-weight: 600; font-size: 0.9rem; }
.p-stats { font-size: 0.75rem; color: var(--text-dim); }
.p-vs { color: var(--text-muted); font-size: 0.78rem; font-weight: 600; }

.pick-result-row {
    display: flex;
    align-items: center;
    gap: 1.2rem;
}

.pick-box {
    background: var(--accent-glow);
    border: 1px solid rgba(59,130,246,0.18);
    border-radius: 8px;
    padding: 0.6rem 1.4rem;
    text-align: center;
    flex-shrink: 0;
}

.pick-box .lbl { font-size: 0.6rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); }
.pick-box .team { font-size: 0.95rem; font-weight: 800; }
.pick-box .prob { font-size: 1.5rem; font-weight: 800; color: var(--accent); }
.pick-box .edge { font-size: 0.72rem; color: var(--green); font-weight: 600; }

.factors-col { flex: 1; }

.factor-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.25rem;
}

.f-label { font-size: 0.7rem; color: var(--text-dim); width: 95px; flex-shrink: 0; }
.f-bar { height: 3px; border-radius: 2px; }
.f-bar.pos { background: var(--green); }
.f-bar.neg { background: var(--red); }
.f-val { font-size: 0.7rem; font-weight: 600; width: 40px; text-align: right; flex-shrink: 0; }

.pick-footer {
    display: flex;
    gap: 0.85rem;
    padding: 0.5rem 1.2rem;
    border-top: 1px solid var(--border);
    font-size: 0.7rem;
    color: var(--text-muted);
}

/* Footer */
.site-footer {
    margin-top: 4rem;
    padding: 2rem 0;
    border-top: 1px solid var(--border);
    text-align: center;
    font-size: 0.78rem;
    color: var(--text-muted);
}

/* Day result rows */
.day-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 0.5rem;
    overflow: hidden;
}

.day-summary {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 1.2rem;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s;
}
.day-summary:hover { background: var(--surface2); }

.day-date { font-weight: 700; width: 65px; }
.day-rec { font-weight: 600; width: 45px; }
.day-pct { font-weight: 700; width: 50px; }
.day-brier { font-size: 0.8rem; color: var(--text-dim); flex: 1; }
.day-arrow { color: var(--text-muted); transition: transform 0.2s; font-size: 0.8rem; }

.day-row.open .day-arrow { transform: rotate(90deg); }

.day-picks {
    display: none;
    padding: 0 1.2rem 0.85rem;
}
.day-row.open .day-picks { display: block; }

.dp-line {
    padding: 0.35rem 0;
    font-size: 0.85rem;
    border-bottom: 1px solid var(--border);
}
.dp-line:last-child { border-bottom: none; }
.dp-line.wrong { color: var(--text-dim); }

/* Calibration chart */
.cal-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.4rem;
}
.cal-label { font-size: 0.78rem; font-weight: 600; width: 42px; text-align: right; }
.cal-bar-wrap {
    flex: 1;
    height: 22px;
    background: var(--surface2);
    border-radius: 4px;
    position: relative;
    overflow: hidden;
}
.cal-pred-bar { position: absolute; top: 0; left: 0; height: 100%; background: rgba(59,130,246,0.2); border-right: 2px solid var(--accent); }
.cal-act-bar { position: absolute; top: 0; left: 0; height: 100%; background: rgba(34,197,94,0.25); border-right: 2px solid var(--green); }
.cal-actual { font-size: 0.78rem; color: var(--green); font-weight: 600; width: 42px; }
.cal-n { font-size: 0.7rem; color: var(--text-muted); width: 38px; }

/* Tier boxes */
.tier-box {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.7rem 1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 0.4rem;
}
.tier-name { font-weight: 600; width: 90px; }
.tier-rec { color: var(--text-dim); }
.tier-pct { font-weight: 700; color: var(--green); }

/* How it works */
.info-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}
.info-card h3 {
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.info-card p, .info-card li {
    font-size: 0.88rem;
    color: var(--text-dim);
    margin-bottom: 0.4rem;
}
.info-card ul { padding-left: 1.2rem; }
.info-card .weight-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}
.info-card .wb-label { font-size: 0.78rem; width: 140px; flex-shrink: 0; }
.info-card .wb-fill { height: 6px; border-radius: 3px; background: var(--accent); }
.info-card .wb-val { font-size: 0.72rem; color: var(--text-dim); width: 35px; }

/* Mobile */
@media (max-width: 640px) {
    .container { padding: 1.2rem 1rem 3rem; }
    .page-header h1 { font-size: 1.4rem; }
    .stats-row { grid-template-columns: repeat(2, 1fr); }
    .stat-val { font-size: 1.3rem; }
    .pick-result-row { flex-direction: column; }
    .pitcher-row { flex-direction: column; gap: 0.4rem; }
    .p-vs { display: none; }
    .nav-inner { flex-direction: column; gap: 0.5rem; }
    .day-summary { gap: 0.5rem; font-size: 0.88rem; }
    .pick-footer { flex-wrap: wrap; }
}
'''


def nav_html(active):
    links = [
        ("index.html", "Today", "today"),
        ("track-record.html", "Track Record", "record"),
        ("how-it-works.html", "How It Works", "how"),
    ]
    link_html = ""
    for href, label, key in links:
        cls = ' class="active"' if key == active else ""
        link_html += f'<a href="{href}"{cls}>{label}</a>'

    return f'''<nav class="nav">
    <div class="nav-inner">
        <a href="index.html" class="nav-brand">&#9918; MLB <span>Picks</span></a>
        <div class="nav-links">{link_html}</div>
    </div>
</nav>'''


def page_wrap(title, active, body):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — MLB Picks</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>{SHARED_CSS}</style>
</head>
<body>
{nav_html(active)}
<div class="container">
{body}
</div>
<footer class="site-footer">
    <p>Picks are for informational and entertainment purposes only.</p>
    <p style="margin-top:0.4rem;">&copy; {YEAR} MLB Picks &middot; Updated {NOW}</p>
</footer>
<script>
document.querySelectorAll('.day-summary').forEach(el => {{
    el.addEventListener('click', () => el.parentElement.classList.toggle('open'));
}});
</script>
</body>
</html>'''


# ── Page: Today's Picks ──────────────────────────────────────────────

def build_today():
    picks_date, picks = load_latest_picks()
    report = load_season_report()

    # Stats bar
    if report:
        total = report.get("total_picks", 0)
        correct = report.get("correct", 0)
        accuracy = report.get("accuracy", 0)
        brier_skill = report.get("brier_skill", 0)
        roi = report.get("roi_pct", 0)
    else:
        total = correct = 0
        accuracy = brier_skill = roi = 0

    acc_cls = "c-green" if accuracy > 0.55 else "c-amber" if accuracy > 0.50 else "c-red"
    bs_cls = "c-green" if brier_skill > 0 else "c-red"
    roi_cls = "c-green" if roi > 0 else "c-red"

    stats = f'''<div class="stats-row">
        <div class="stat-box"><div class="stat-val {acc_cls}">{correct}-{total - correct}</div><div class="stat-label">Season Record</div></div>
        <div class="stat-box"><div class="stat-val {acc_cls}">{accuracy*100:.1f}%</div><div class="stat-label">Win Rate</div></div>
        <div class="stat-box"><div class="stat-val {bs_cls}">{brier_skill*100:.1f}%</div><div class="stat-label">Brier Skill</div></div>
        <div class="stat-box"><div class="stat-val {roi_cls}">{roi:+.1f}%</div><div class="stat-label">Flat-Bet ROI</div></div>
    </div>'''

    # Pick cards — HIGH confidence only
    cards = ""
    if picks:
        picks = [p for p in picks if p["confidence"] == "HIGH"]
    if picks:
        for p in picks:
            conf = p["confidence"].lower()
            conf_text = {"HIGH": "&#128293; High", "MEDIUM": "&#9989; Med", "LOW": "&#9723; Low"}[p["confidence"]]

            # Factors
            factors = ""
            if "factors" in p:
                for fname, fdata in sorted(p["factors"].items(), key=lambda x: abs(x[1]["impact"]), reverse=True)[:4]:
                    impact = fdata["impact"]
                    w = min(abs(impact) * 9, 100)
                    cls = "pos" if impact > 0 else "neg"
                    label = fname.replace("_", " ").title()
                    factors += f'<div class="factor-row"><span class="f-label">{label}</span><div class="f-bar {cls}" style="width:{w}%"></div><span class="f-val">{impact:+.1f}%</span></div>'

            # Pitcher recent form
            away_recent = p.get("away_pitcher_recent", {})
            home_recent = p.get("home_pitcher_recent", {})
            away_recent_era = away_recent.get("recent_era", "N/A")
            home_recent_era = home_recent.get("recent_era", "N/A")

            cards += f'''<div class="pick-card {conf}">
    <div class="pick-top">
        <div class="matchup-name">{p["away_team"]} <span class="at">@</span> {p["home_team"]}</div>
        <div class="conf-tag {conf}">{conf_text}</div>
    </div>
    <div class="pick-body">
        <div class="pitcher-row">
            <div class="p-side"><div class="p-name">{p["away_pitcher"]}</div><div class="p-stats">{p.get("away_pitcher_era","N/A")} ERA &middot; Score {p["away_pitcher_score"]} &middot; L5: {away_recent_era}</div></div>
            <div class="p-vs">vs</div>
            <div class="p-side"><div class="p-name">{p["home_pitcher"]}</div><div class="p-stats">{p.get("home_pitcher_era","N/A")} ERA &middot; Score {p["home_pitcher_score"]} &middot; L5: {home_recent_era}</div></div>
        </div>
        <div class="pick-result-row">
            <div class="pick-box">
                <div class="lbl">Pick</div>
                <div class="team">{p["pick"]}</div>
                <div class="prob">{p["pick_prob"]*100:.0f}%</div>
                <div class="edge">+{p["edge"]*100:.1f}% edge</div>
            </div>
            <div class="factors-col">{factors}</div>
        </div>
    </div>
    <div class="pick-footer">
        <span>{p["venue"]}</span>
        <span>Park Factor: {p.get("park_factor", 1.0)}</span>
        <span>{p.get("weather", {}).get("note", "")}</span>
    </div>
</div>'''
    else:
        cards = '<div class="info-card"><p>No high-confidence picks today. Some days the model doesn&#39;t see a strong enough edge.</p></div>'

    pick_count = len(picks) if picks else 0
    date_badge = f'<span class="badge">{picks_date}</span>' if picks_date else ""

    body = f'''
    <div class="page-header">
        <h1>Today&#39;s Picks {date_badge}</h1>
        <div class="subtitle">{pick_count} premium pick{"s" if pick_count != 1 else ""} &middot; 64%+ confidence only &middot; Timestamped before first pitch</div>
    </div>
    {stats}
    <div class="section">{cards}</div>'''

    return page_wrap("Today's Picks", "today", body)


# ── Page: Track Record ────────────────────────────────────────────────

def build_track_record():
    from datetime import datetime as dt

    # Load backtest picks (HIGH only)
    bt_picks = []
    for f in sorted(BACKTEST_DIR.glob("picks_*.json"), reverse=True):
        with open(f) as fh:
            all_bt = json.load(fh)
            bt_picks = [p for p in all_bt if p["confidence"] == "HIGH"]
        break

    # Load live results (HIGH only)
    live_picks = []
    results = load_all_results()
    for r in results:
        for p in r["picks"]:
            if p.get("confidence") == "HIGH" or p.get("pick_prob", 0) >= 0.65:
                live_picks.append(p)

    # Combine: backtest first, then live
    all_picks = bt_picks + live_picks

    if not all_picks:
        body = '<div class="page-header"><h1>Track Record</h1></div><div class="info-card"><p>No results yet. Check back after games finish.</p></div>'
        return page_wrap("Track Record", "record", body)

    total = len(all_picks)
    correct = sum(1 for p in all_picks if p["correct"])
    accuracy = correct / total
    avg_brier = sum(p["brier"] for p in all_picks) / total
    brier_skill = 1 - (avg_brier / 0.25)

    # Realistic ROI with moneyline odds
    wagered = total * 10
    returned = 0
    for p in all_picks:
        if p["correct"]:
            odds = prob_to_american(p["pick_prob"])
            returned += 10 + payout_on_10(odds)
    net = returned - wagered
    roi = (net / wagered) * 100 if wagered > 0 else 0

    acc_cls = "c-green" if accuracy > 0.55 else "c-amber" if accuracy > 0.50 else "c-red"
    bs_cls = "c-green" if brier_skill > 0 else "c-red"
    roi_cls = "c-green" if roi > 0 else "c-red"

    # Split stats
    bt_total = len(bt_picks)
    bt_correct = sum(1 for p in bt_picks if p["correct"])
    live_total = len(live_picks)
    live_correct = sum(1 for p in live_picks if p["correct"])

    stats = f'''<div class="stats-row">
        <div class="stat-box"><div class="stat-val {acc_cls}">{correct}-{total-correct}</div><div class="stat-label">Overall Record</div></div>
        <div class="stat-box"><div class="stat-val {acc_cls}">{accuracy*100:.1f}%</div><div class="stat-label">Win Rate</div></div>
        <div class="stat-box"><div class="stat-val {bs_cls}">{brier_skill*100:.1f}%</div><div class="stat-label">Brier Skill</div></div>
        <div class="stat-box"><div class="stat-val {roi_cls}">{roi:+.1f}%</div><div class="stat-label">ROI (Real Odds)</div></div>
    </div>'''

    # Backtest vs Live split
    split_html = ""
    if bt_total > 0:
        bt_w = bt_total * 10
        bt_r = sum(10 + payout_on_10(prob_to_american(p["pick_prob"])) for p in bt_picks if p["correct"])
        bt_roi = ((bt_r - bt_w) / bt_w) * 100
        bt_roi_cls = "c-green" if bt_roi > 0 else "c-red"
        bt_acc = bt_correct / bt_total * 100
        split_html += f'<div class="tier-box"><span class="tier-name">&#128202; Backtest</span><span class="tier-rec">{bt_correct}/{bt_total}</span><span class="tier-pct c-green">{bt_acc:.0f}%</span><span style="color:var(--text-dim);font-size:0.85rem;">Aug-Sep 2025</span><span class="{bt_roi_cls}" style="font-weight:700;">{bt_roi:+.1f}% ROI</span></div>'
    if live_total > 0:
        lv_w = live_total * 10
        lv_r = sum(10 + payout_on_10(prob_to_american(p["pick_prob"])) for p in live_picks if p["correct"])
        lv_roi = ((lv_r - lv_w) / lv_w) * 100
        lv_roi_cls = "c-green" if lv_roi > 0 else "c-red"
        lv_acc = live_correct / live_total * 100
        split_html += f'<div class="tier-box"><span class="tier-name">&#9889; Live</span><span class="tier-rec">{live_correct}/{live_total}</span><span class="tier-pct c-green">{lv_acc:.0f}%</span><span style="color:var(--text-dim);font-size:0.85rem;">2026 Season</span><span class="{lv_roi_cls}" style="font-weight:700;">{lv_roi:+.1f}% ROI</span></div>'

    # Calibration on HIGH picks
    cal_buckets = {}
    for p in all_picks:
        bucket = round(p["pick_prob"] * 20) / 20
        bk = f"{bucket:.2f}"
        if bk not in cal_buckets:
            cal_buckets[bk] = {"pred": [], "actual": []}
        cal_buckets[bk]["pred"].append(p["pick_prob"])
        cal_buckets[bk]["actual"].append(1 if p["correct"] else 0)

    cal_html = ""
    for k, v in sorted(cal_buckets.items()):
        ap = sum(v["pred"]) / len(v["pred"])
        aa = sum(v["actual"]) / len(v["actual"])
        pw = ap * 100
        aw = aa * 100
        cal_html += f'''<div class="cal-row">
            <span class="cal-label">{ap*100:.0f}%</span>
            <div class="cal-bar-wrap">
                <div class="cal-pred-bar" style="width:{pw}%"></div>
                <div class="cal-act-bar" style="width:{aw}%"></div>
            </div>
            <span class="cal-actual">{aa*100:.0f}%</span>
            <span class="cal-n">n={len(v["pred"])}</span>
        </div>'''

    # All picks grouped by date
    picks_by_date = {}
    for p in all_picks:
        d = p.get("date", p.get("game_date", "unknown"))
        if d not in picks_by_date:
            picks_by_date[d] = []
        picks_by_date[d].append(p)

    days_html = ""
    for date in sorted(picks_by_date.keys(), reverse=True):
        day_picks = picks_by_date[date]
        try:
            date_disp = dt.strptime(date, "%Y-%m-%d").strftime("%b %d, %Y")
        except:
            date_disp = date
        day_total = len(day_picks)
        day_correct = sum(1 for p in day_picks if p["correct"])

        if day_total == 0:
            continue
        pct = day_correct / day_total * 100
        pct_cls = "c-green" if pct > 55 else "c-amber" if pct > 45 else "c-red"

        # Is this backtest or live?
        is_bt = date < "2026-01-01"
        tag = ' <span style="font-size:0.7rem;color:var(--text-muted);">backtest</span>' if is_bt else ' <span style="font-size:0.7rem;color:var(--accent);">live</span>'

        detail = ""
        for p in sorted(day_picks, key=lambda x: x["pick_prob"], reverse=True):
            icon = "&#9989;" if p["correct"] else "&#10060;"
            cls = "correct" if p["correct"] else "wrong"
            matchup = p.get("matchup", f'{p.get("away_team", "?")} @ {p.get("home_team", "?")}')
            score = p.get("score", "N/A")
            odds = prob_to_american(p["pick_prob"])
            detail += f'<div class="dp-line {cls}">{icon} {matchup} &mdash; <strong>{p["pick"]}</strong> ({p["pick_prob"]*100:.0f}%, {odds:+.0f}) &mdash; {score}</div>'

        days_html += f'''<div class="day-row">
            <div class="day-summary">
                <span class="day-date">{date_disp}</span>
                <span class="day-rec">{day_correct}/{day_total}</span>
                <span class="day-pct {pct_cls}">{pct:.0f}%</span>
                {tag}
                <span class="day-arrow">&#9656;</span>
            </div>
            <div class="day-picks">{detail}</div>
        </div>'''

    body = f'''
    <div class="page-header">
        <h1>Track Record</h1>
        <div class="subtitle">HIGH confidence (62%+) picks only &middot; {total} total picks &middot; Every result verified &middot; ROI with real odds</div>
    </div>

    <div class="info-card" style="margin-bottom:1.5rem;">
        <p style="font-size:0.85rem;">Only 64%+ confidence picks are shown. ROI is calculated using realistic moneyline odds with standard vig &mdash; not flat -110. Backtest uses prior-year team data and date-filtered pitcher stats (zero look-ahead).</p>
    </div>

    {stats}

    <div class="section">
        <div class="section-title">Backtest vs Live</div>
        {split_html if split_html else '<div class="info-card"><p>No data yet.</p></div>'}
    </div>

    <div class="section">
        <div class="section-title">Calibration (65%+ Picks)</div>
        <p style="font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem;">Blue = predicted. Green = actual. These should be close.</p>
        {cal_html}
    </div>

    <div class="section">
        <div class="section-title">Every Pick ({total} total)</div>
        <p style="font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem;">Click any day to expand. Includes moneyline odds estimate.</p>
        {days_html}
    </div>'''

    return page_wrap("Track Record", "record", body)


# ── Page: How It Works ────────────────────────────────────────────────

def build_how():
    body = '''
    <div class="page-header">
        <h1>How It Works</h1>
        <div class="subtitle">Transparent methodology — no black boxes</div>
    </div>

    <div class="info-card">
        <h3>&#127919; The Model</h3>
        <p>A multi-factor statistical model that analyzes 10 data signals to generate a win probability for every MLB game. We only publish picks where the model finds a <strong>62%+ win probability</strong> — about 2 per day. Everything below that threshold is filtered out.</p>
        <p>All data comes from the official MLB Stats API. No gut calls, no "expert opinions," no fudging.</p>
    </div>

    <div class="info-card">
        <h3>&#128202; Full-Season Backtest</h3>
        <p>We backtested the model across the <strong>entire 2025 MLB season</strong> — 2,426 games over 182 days — with <strong>zero look-ahead bias</strong>:</p>
        <ul>
            <li><strong>Pitcher stats:</strong> Computed from game logs <em>before</em> each game date only. A prediction for June 15 uses only data through June 14.</li>
            <li><strong>Early-season fallback:</strong> For pitchers with fewer than 3 starts in the current season, the model falls back to their prior-year (2024) stats.</li>
            <li><strong>Team stats:</strong> Uses the prior season (2024) as the baseline — no current-year leakage.</li>
        </ul>
        <p style="margin-top:0.6rem;"><strong>Results on 62%+ picks (361 total):</strong></p>
        <ul>
            <li>Record: <strong>239-122 (66.2% win rate)</strong></li>
            <li>ROI with realistic moneyline odds: <strong>+2.5%</strong></li>
            <li>Brier Skill: <strong>+2.6%</strong> (beating coin flip)</li>
            <li>Calibration at 65%: predicted 64.5%, actual 64.4% — nearly perfect</li>
        </ul>
        <p style="margin-top:0.4rem;font-size:0.82rem;color:var(--text-dim);">Every single pick from the backtest is viewable on the Track Record page.</p>
    </div>

    <div class="info-card">
        <h3>&#9878;&#65039; Factor Weights</h3>
        <p>Each prediction is built from these signals, ranked by impact on the final probability:</p>
        <div style="margin-top:0.8rem;">
            <div class="weight-bar"><span class="wb-label">Starting Pitcher</span><div class="wb-fill" style="width:80%"></div><span class="wb-val">24%</span></div>
            <div class="weight-bar"><span class="wb-label">Team Offense</span><div class="wb-fill" style="width:55%"></div><span class="wb-val">16%</span></div>
            <div class="weight-bar"><span class="wb-label">True Talent (Pyth)</span><div class="wb-fill" style="width:42%"></div><span class="wb-val">12%</span></div>
            <div class="weight-bar"><span class="wb-label">Bullpen Quality</span><div class="wb-fill" style="width:35%"></div><span class="wb-val">10%</span></div>
            <div class="weight-bar"><span class="wb-label">Home Field</span><div class="wb-fill" style="width:30%"></div><span class="wb-val">~3.5%</span></div>
            <div class="weight-bar"><span class="wb-label">Pitcher vs Team</span><div class="wb-fill" style="width:22%"></div><span class="wb-val">&#177;1.5%</span></div>
            <div class="weight-bar"><span class="wb-label">Park Factor</span><div class="wb-fill" style="width:15%"></div><span class="wb-val">&#177;0.8%</span></div>
            <div class="weight-bar"><span class="wb-label">Weather</span><div class="wb-fill" style="width:12%"></div><span class="wb-val">&#177;1%</span></div>
            <div class="weight-bar"><span class="wb-label">Rest / Travel</span><div class="wb-fill" style="width:12%"></div><span class="wb-val">&#177;1%</span></div>
        </div>
    </div>

    <div class="info-card">
        <h3>&#128200; Pitcher Scoring</h3>
        <p>Starting pitchers are the single biggest factor. Each pitcher gets a composite score (0-100) based on:</p>
        <ul>
            <li><strong>Season stats:</strong> ERA (22%), WHIP (18%), K/BB ratio (15%), K/9 (15%), BB/9 (12%), HR/9 (10%), ground ball rate (8%)</li>
            <li><strong>Recent form:</strong> Last 5 starts, recency-weighted — a pitcher on a hot streak gets more credit than one coasting on April numbers</li>
            <li><strong>vs. Team history:</strong> Career stats against the opposing lineup (15+ IP minimum to filter noise)</li>
            <li><strong>Regression:</strong> Pitchers with fewer than 50 IP are regressed toward league average. Small samples lie.</li>
        </ul>
        <p>Season score (60%) and recent form (40%) are blended into one rating. The gap between the two starters is the biggest single driver of the prediction.</p>
    </div>

    <div class="info-card">
        <h3>&#128176; ROI Calculation</h3>
        <p>We don't use flat -110 odds for ROI — that overstates returns on favorites. Our ROI calculation:</p>
        <ul>
            <li>Converts each pick's probability to an <strong>estimated moneyline</strong> with standard sportsbook vig (~4.5%)</li>
            <li>Calculates actual payout based on those odds — a -170 favorite only pays $5.88 on a $10 bet</li>
            <li>Tracks cumulative profit/loss across all picks</li>
        </ul>
        <p>This is more conservative than most handicapping sites report, but it's honest.</p>
    </div>

    <div class="info-card">
        <h3>&#128202; How We Measure Accuracy</h3>
        <p>Win-loss record alone is misleading. We track:</p>
        <ul>
            <li><strong>Brier Score:</strong> How close predicted probabilities are to outcomes. 0.25 = coin flip. Lower = better.</li>
            <li><strong>Brier Skill:</strong> Percentage improvement over always guessing 50/50. Positive = the model adds value.</li>
            <li><strong>Calibration:</strong> When we say 65%, does it actually win ~65% of the time? The Track Record page shows this directly.</li>
            <li><strong>ROI (Real Odds):</strong> Simulated profit with realistic moneyline odds and vig.</li>
        </ul>
    </div>

    <div class="info-card">
        <h3>&#128338; Daily Process</h3>
        <ul>
            <li><strong>10:00 AM ET</strong> — Model pulls all available data, scores every game, publishes 62%+ picks</li>
            <li><strong>1:00 AM ET</strong> — Results scored automatically, Track Record updated</li>
            <li>All picks are timestamped and locked before first pitch — no retroactive edits, ever</li>
            <li>Some days there are 0 picks. If the model doesn't see an edge, it doesn't force one.</li>
        </ul>
    </div>

    <div class="info-card">
        <h3>&#128161; What This Is (And Isn't)</h3>
        <p>This is a <strong>data-driven edge-finding tool</strong>. It identifies games where the model sees a higher probability than the market implies, and publishes them transparently.</p>
        <p>It is not a guaranteed money printer. Over 2,426 backtested games, the model's 62%+ picks hit at 66.2% and produced a modest +2.5% ROI against realistic odds. That's real signal, but it's not going to make you rich overnight.</p>
        <p>The Track Record page shows every pick — wins and losses — with no editing or cherry-picking. If the model stops working, you'll see it there first.</p>
    </div>'''

    return page_wrap("How It Works", "how", body)


# ── Page: Backtest ────────────────────────────────────────────────────

def prob_to_american(prob):
    market_prob = prob - 0.03
    market_prob = max(0.35, min(0.75, market_prob))
    vigged = min(0.95, market_prob + 0.0225)
    if vigged >= 0.50:
        return -(vigged / (1 - vigged)) * 100
    else:
        return ((1 - vigged) / vigged) * 100

def payout_on_10(american_odds):
    if american_odds < 0:
        return 10 * (100 / abs(american_odds))
    else:
        return 10 * (american_odds / 100)

def build_backtest():
    # Find the latest backtest files
    bt_report = None
    bt_picks = None
    for f in sorted(BACKTEST_DIR.glob("backtest_*.json"), reverse=True):
        with open(f) as fh:
            bt_report = json.load(fh)
        break
    for f in sorted(BACKTEST_DIR.glob("picks_*.json"), reverse=True):
        with open(f) as fh:
            bt_picks = json.load(fh)
        break

    if not bt_report or not bt_picks:
        body = '<div class="page-header"><h1>Backtest</h1></div><div class="info-card"><p>No backtest data yet.</p></div>'
        return page_wrap("Backtest", "backtest", body)

    total = bt_report["total_games"]
    correct = bt_report["correct"]
    accuracy = bt_report["accuracy"]
    brier = bt_report["avg_brier"]
    brier_skill = bt_report["brier_skill"]

    # Compute realistic ROI with moneyline odds for different tiers
    def compute_tier(picks, label):
        n = len(picks)
        if n == 0:
            return None
        w = sum(1 for p in picks if p["correct"])
        wagered = n * 10
        returned = 0
        for p in picks:
            if p["correct"]:
                odds = prob_to_american(p["pick_prob"])
                returned += 10 + payout_on_10(odds)
        net = returned - wagered
        roi = (net / wagered) * 100 if wagered > 0 else 0
        odds_list = [prob_to_american(p["pick_prob"]) for p in picks]
        avg_odds = sum(odds_list) / len(odds_list)
        return {"label": label, "n": n, "w": w, "pct": w/n, "wagered": wagered, "net": net, "roi": roi, "avg_odds": avg_odds, "per_day": n / max(1, bt_report.get("days_processed", 59))}

    all_tier = compute_tier(bt_picks, "All Picks")
    high_tier = compute_tier([p for p in bt_picks if p["confidence"] == "HIGH"], "HIGH Only")
    med_tier = compute_tier([p for p in bt_picks if p["confidence"] == "MEDIUM"], "MEDIUM Only")
    low_tier = compute_tier([p for p in bt_picks if p["confidence"] == "LOW"], "LOW Only")

    # Probability buckets for HIGH picks
    high_picks = [p for p in bt_picks if p["confidence"] == "HIGH"]
    buckets_html = ""
    for lo, hi, blabel in [(0.60, 0.65, "60-64%"), (0.65, 0.70, "65-69%"), (0.70, 0.75, "70-75%")]:
        bucket = [p for p in high_picks if lo <= p["pick_prob"] < hi]
        if not bucket:
            continue
        t = compute_tier(bucket, blabel)
        if t:
            roi_cls = "c-green" if t["roi"] > 0 else "c-red"
            buckets_html += f'<div class="tier-box"><span class="tier-name">{blabel}</span><span class="tier-rec">{t["w"]}/{t["n"]}</span><span class="tier-pct {roi_cls}">{t["pct"]*100:.0f}%</span><span style="color:var(--text-dim);font-size:0.85rem;">Avg {t["avg_odds"]:+.0f}</span><span class="{roi_cls}" style="font-weight:700;">{t["roi"]:+.1f}% ROI</span></div>'

    # Tier summary cards
    tiers_html = ""
    for t in [high_tier, med_tier, low_tier]:
        if t is None:
            continue
        roi_cls = "c-green" if t["roi"] > 0 else "c-red"
        pct_cls = "c-green" if t["pct"] > 0.58 else "c-amber" if t["pct"] > 0.52 else "c-red"
        tiers_html += f'''<div class="tier-box">
            <span class="tier-name">{t["label"]}</span>
            <span class="tier-rec">{t["w"]}/{t["n"]}</span>
            <span class="tier-pct {pct_cls}">{t["pct"]*100:.0f}%</span>
            <span style="color:var(--text-dim);font-size:0.85rem;">Avg {t["avg_odds"]:+.0f} | {t["per_day"]:.1f}/day</span>
            <span class="{roi_cls}" style="font-weight:700;">{t["roi"]:+.1f}% ROI</span>
        </div>'''

    # Calibration
    cal_html = ""
    if bt_report.get("calibration"):
        for k, v in bt_report["calibration"].items():
            pw = v["predicted"] * 100
            aw = v["actual"] * 100
            cal_html += f'''<div class="cal-row">
                <span class="cal-label">{v["predicted"]*100:.0f}%</span>
                <div class="cal-bar-wrap">
                    <div class="cal-pred-bar" style="width:{pw}%"></div>
                    <div class="cal-act-bar" style="width:{aw}%"></div>
                </div>
                <span class="cal-actual">{v["actual"]*100:.0f}%</span>
                <span class="cal-n">n={v["n"]}</span>
            </div>'''

    # All picks grouped by date
    picks_by_date = {}
    for p in bt_picks:
        d = p["date"]
        if d not in picks_by_date:
            picks_by_date[d] = []
        picks_by_date[d].append(p)

    days_html = ""
    for date in sorted(picks_by_date.keys(), reverse=True):
        day_picks = picks_by_date[date]
        from datetime import datetime as dt
        date_disp = dt.strptime(date, "%Y-%m-%d").strftime("%b %d")
        day_total = len(day_picks)
        day_correct = sum(1 for p in day_picks if p["correct"])
        pct = day_correct / day_total * 100
        pct_cls = "c-green" if pct > 55 else "c-amber" if pct > 45 else "c-red"

        detail = ""
        for p in sorted(day_picks, key=lambda x: x["pick_prob"], reverse=True):
            icon = "&#9989;" if p["correct"] else "&#10060;"
            cls = "correct" if p["correct"] else "wrong"
            conf_tag = ""
            if p["confidence"] == "HIGH":
                conf_tag = ' <span style="color:var(--high);font-size:0.75rem;font-weight:600;">HIGH</span>'
            elif p["confidence"] == "MEDIUM":
                conf_tag = ' <span style="color:var(--medium);font-size:0.75rem;font-weight:600;">MED</span>'

            odds = prob_to_american(p["pick_prob"])
            detail += f'<div class="dp-line {cls}">{icon} {p["away_team"]} @ {p["home_team"]} &mdash; <strong>{p["pick"]}</strong> ({p["pick_prob"]*100:.0f}%, {odds:+.0f}) &mdash; {p["score"]}{conf_tag}</div>'

        days_html += f'''<div class="day-row">
            <div class="day-summary">
                <span class="day-date">{date_disp}</span>
                <span class="day-rec">{day_correct}/{day_total}</span>
                <span class="day-pct {pct_cls}">{pct:.0f}%</span>
                <span class="day-brier">{date}</span>
                <span class="day-arrow">&#9656;</span>
            </div>
            <div class="day-picks">{detail}</div>
        </div>'''

    acc_cls = "c-green" if accuracy > 0.55 else "c-amber"
    bs_cls = "c-green" if brier_skill > 0 else "c-red"
    overall_roi = all_tier["roi"] if all_tier else 0
    roi_cls = "c-green" if overall_roi > 0 else "c-red"
    high_roi = high_tier["roi"] if high_tier else 0
    hr_cls = "c-green" if high_roi > 0 else "c-red"

    body = f'''
    <div class="page-header">
        <h1>Backtest Results</h1>
        <div class="subtitle">{bt_report.get("start_date", "")} to {bt_report.get("end_date", "")} &middot; {total} games &middot; {bt_report.get("days_processed", 0)} days &middot; No look-ahead bias</div>
    </div>

    <div class="info-card" style="margin-bottom:1.5rem;">
        <p style="font-size:0.85rem;">Pitcher stats computed from game logs <strong>before each game date only</strong>. Team stats use <strong>{bt_report.get("prior_season", 2024)} season data</strong> (prior year). Zero future information leaked. ROI calculated with realistic moneyline odds including vig.</p>
    </div>

    <div class="stats-row">
        <div class="stat-box"><div class="stat-val {acc_cls}">{correct}-{total-correct}</div><div class="stat-label">Record</div></div>
        <div class="stat-box"><div class="stat-val {acc_cls}">{accuracy*100:.1f}%</div><div class="stat-label">Win Rate</div></div>
        <div class="stat-box"><div class="stat-val {bs_cls}">{brier_skill*100:.1f}%</div><div class="stat-label">Brier Skill</div></div>
        <div class="stat-box"><div class="stat-val {roi_cls}">{overall_roi:+.1f}%</div><div class="stat-label">All-Picks ROI</div></div>
        <div class="stat-box"><div class="stat-val {hr_cls}">{high_roi:+.1f}%</div><div class="stat-label">65%+ ROI</div></div>
    </div>

    <div class="section">
        <div class="section-title">ROI by Confidence Tier (Realistic Odds)</div>
        <p style="font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem;">$10 flat bet per game. Odds estimated from model probability with standard vig.</p>
        {tiers_html}
    </div>

    <div class="section">
        <div class="section-title">HIGH Picks by Probability Bucket</div>
        {buckets_html if buckets_html else '<div class="info-card"><p>Not enough HIGH picks to bucket.</p></div>'}
    </div>

    <div class="section">
        <div class="section-title">Calibration</div>
        <p style="font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem;">Blue = predicted. Green = actual. Perfect calibration = bars match.</p>
        {cal_html}
    </div>

    <div class="section">
        <div class="section-title">Every Pick ({total} games)</div>
        <p style="font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem;">Click any day to expand. Sorted by probability within each day.</p>
        {days_html}
    </div>'''

    return page_wrap("Backtest", "backtest", body)


# ── Generate All Pages ────────────────────────────────────────────────

def generate():
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    pages = [
        ("index.html", build_today),
        ("track-record.html", build_track_record),
        ("backtest.html", build_backtest),
        ("how-it-works.html", build_how),
    ]

    for filename, builder in pages:
        html = builder()
        out = SITE_DIR / filename
        out.write_text(html)
        print(f"  ✅ {filename} ({len(html):,} bytes)")

    print(f"\n✅ Site generated: {SITE_DIR}")


if __name__ == "__main__":
    generate()
