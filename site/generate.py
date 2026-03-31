#!/usr/bin/env python3
"""
Static site generator for MLB Predictor.
Reads picks/ and results/ data, outputs a clean public-facing index.html.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
PICKS_DIR = ROOT / "picks"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"
SITE_DIR = ROOT / "site"
OUT_FILE = SITE_DIR / "index.html"


def load_all_results():
    """Load all scored results, sorted by date desc."""
    results = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        with open(f) as fh:
            results.append(json.load(fh))
    return results


def load_today_picks():
    """Load most recent picks file."""
    files = sorted(PICKS_DIR.glob("*.json"), reverse=True)
    if not files:
        return None, None
    with open(files[0]) as f:
        return files[0].stem, json.load(f)


def load_season_report():
    """Load season report if it exists."""
    report_file = REPORTS_DIR / "season.json"
    if report_file.exists():
        with open(report_file) as f:
            return json.load(f)
    return None


def generate_html():
    picks_date, picks = load_today_picks()
    results = load_all_results()
    report = load_season_report()
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p ET")

    # Calculate season stats
    total_picks = report.get("total_picks", 0) if report else 0
    correct = report.get("correct", 0) if report else 0
    accuracy = report.get("accuracy", 0) if report else 0
    brier = report.get("avg_brier", 0.25) if report else 0.25
    brier_skill = report.get("brier_skill", 0) if report else 0
    roi = report.get("roi_pct", 0) if report else 0
    roi_units = report.get("roi_units", 0) if report else 0

    # Build picks HTML
    picks_html = ""
    if picks:
        for p in picks:
            conf_class = p["confidence"].lower()
            conf_label = {"HIGH": "🔥 High", "MEDIUM": "✅ Med", "LOW": "◽ Low"}[p["confidence"]]

            # Factor bars
            factors_html = ""
            if "factors" in p:
                sorted_factors = sorted(p["factors"].items(), key=lambda x: abs(x[1]["impact"]), reverse=True)
                for fname, fdata in sorted_factors[:3]:
                    impact = fdata["impact"]
                    bar_width = min(abs(impact) * 8, 100)
                    bar_class = "positive" if impact > 0 else "negative"
                    factors_html += f'<div class="factor"><span class="factor-label">{fname.replace("_", " ").title()}</span><div class="factor-bar {bar_class}" style="width:{bar_width}%"></div><span class="factor-val">{impact:+.1f}%</span></div>'

            picks_html += f'''
            <div class="pick-card {conf_class}">
                <div class="pick-header">
                    <div class="matchup">{p["away_team"]} <span class="at">@</span> {p["home_team"]}</div>
                    <div class="confidence {conf_class}">{conf_label}</div>
                </div>
                <div class="pick-details">
                    <div class="pitchers">
                        <div class="pitcher away">
                            <span class="pitcher-name">{p["away_pitcher"]}</span>
                            <span class="pitcher-stat">{p.get("away_pitcher_era", "N/A")} ERA</span>
                            <span class="pitcher-score">Score: {p["away_pitcher_score"]}</span>
                        </div>
                        <div class="vs">vs</div>
                        <div class="pitcher home">
                            <span class="pitcher-name">{p["home_pitcher"]}</span>
                            <span class="pitcher-stat">{p.get("home_pitcher_era", "N/A")} ERA</span>
                            <span class="pitcher-score">Score: {p["home_pitcher_score"]}</span>
                        </div>
                    </div>
                    <div class="prediction">
                        <div class="pick-label">PICK</div>
                        <div class="pick-team">{p["pick"]}</div>
                        <div class="pick-prob">{p["pick_prob"]*100:.0f}%</div>
                        <div class="pick-edge">+{p["edge"]*100:.1f}% edge</div>
                    </div>
                    <div class="factors">{factors_html}</div>
                </div>
                <div class="pick-meta">
                    <span>{p["venue"]}</span>
                    <span>Park: {p.get("park_factor", 1.0)}</span>
                    <span>{p.get("weather", {}).get("note", "")}</span>
                </div>
            </div>'''
    else:
        picks_html = '<div class="no-picks">No picks yet today. Check back before first pitch.</div>'

    # Build results history HTML
    history_html = ""
    for r in results[:14]:  # Last 2 weeks
        date_display = datetime.strptime(r["date"], "%Y-%m-%d").strftime("%b %d")
        pct = r["accuracy"] * 100

        picks_detail = ""
        for p in r["picks"]:
            icon = "✅" if p["correct"] else "❌"
            picks_detail += f'<div class="result-pick {("correct" if p["correct"] else "wrong")}">{icon} {p["matchup"]} → <strong>{p["pick"]}</strong> ({p["pick_prob"]*100:.0f}%) — Final: {p["score"]}</div>'

        history_html += f'''
        <div class="day-result">
            <div class="day-header" onclick="this.parentElement.classList.toggle('open')">
                <span class="day-date">{date_display}</span>
                <span class="day-record">{r["correct"]}/{r["total_games"]}</span>
                <span class="day-pct">{pct:.0f}%</span>
                <span class="day-brier">Brier: {r["avg_brier"]:.4f}</span>
                <span class="expand-icon">▸</span>
            </div>
            <div class="day-detail">{picks_detail}</div>
        </div>'''

    # Calibration table
    cal_html = ""
    if report and report.get("calibration"):
        for k, v in report["calibration"].items():
            bar_w = v["avg_actual"] * 100
            pred_w = v["avg_predicted"] * 100
            cal_html += f'''
            <div class="cal-row">
                <span class="cal-pred">{v["avg_predicted"]*100:.0f}%</span>
                <div class="cal-bar-container">
                    <div class="cal-bar-predicted" style="width:{pred_w}%"></div>
                    <div class="cal-bar-actual" style="width:{bar_w}%"></div>
                </div>
                <span class="cal-actual">{v["avg_actual"]*100:.0f}%</span>
                <span class="cal-n">n={v["n"]}</span>
            </div>'''

    # Confidence tier breakdown
    tiers_html = ""
    if report and report.get("by_confidence"):
        for tier in ["HIGH", "MEDIUM", "LOW"]:
            t = report["by_confidence"].get(tier)
            if t:
                emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "◽"}[tier]
                tiers_html += f'''
                <div class="tier-row">
                    <span class="tier-label">{emoji} {tier}</span>
                    <span class="tier-record">{t["correct"]}/{t["total"]}</span>
                    <span class="tier-pct">{t["pct"]*100:.0f}%</span>
                </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MLB Picks — AI-Powered Daily Predictions</title>
    <meta name="description" content="Free daily MLB predictions powered by a multi-factor AI model. Verified track record, transparent methodology.">
    <style>
        :root {{
            --bg: #0a0e17;
            --surface: #111827;
            --surface2: #1a2332;
            --border: #1e293b;
            --text: #e2e8f0;
            --text-dim: #94a3b8;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.15);
            --green: #22c55e;
            --red: #ef4444;
            --amber: #f59e0b;
            --high: #f97316;
            --medium: #3b82f6;
            --low: #64748b;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            min-height: 100vh;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        /* Header */
        .header {{
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}

        .header h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-bottom: 0.5rem;
        }}

        .header h1 span {{
            color: var(--accent);
        }}

        .header .tagline {{
            color: var(--text-dim);
            font-size: 1.05rem;
        }}

        .header .updated {{
            color: var(--text-dim);
            font-size: 0.8rem;
            margin-top: 0.75rem;
        }}

        /* Stats bar */
        .stats-bar {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
            margin-bottom: 2.5rem;
        }}

        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
        }}

        .stat-card .stat-value {{
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }}

        .stat-card .stat-label {{
            font-size: 0.75rem;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-top: 0.25rem;
        }}

        .stat-green {{ color: var(--green); }}
        .stat-red {{ color: var(--red); }}
        .stat-amber {{ color: var(--amber); }}
        .stat-blue {{ color: var(--accent); }}

        /* Section headers */
        .section-header {{
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 1.2rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .section-header .date-badge {{
            background: var(--accent);
            color: white;
            font-size: 0.75rem;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
            font-weight: 600;
        }}

        /* Pick cards */
        .pick-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 1rem;
            overflow: hidden;
            transition: border-color 0.2s;
        }}

        .pick-card:hover {{
            border-color: var(--accent);
        }}

        .pick-card.high {{ border-left: 3px solid var(--high); }}
        .pick-card.medium {{ border-left: 3px solid var(--medium); }}
        .pick-card.low {{ border-left: 3px solid var(--low); }}

        .pick-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
        }}

        .matchup {{
            font-size: 1.1rem;
            font-weight: 700;
        }}

        .matchup .at {{
            color: var(--text-dim);
            font-weight: 400;
            margin: 0 0.3rem;
        }}

        .confidence {{
            font-size: 0.8rem;
            font-weight: 600;
            padding: 0.2rem 0.6rem;
            border-radius: 6px;
        }}
        .confidence.high {{ background: rgba(249,115,22,0.15); color: var(--high); }}
        .confidence.medium {{ background: var(--accent-glow); color: var(--medium); }}
        .confidence.low {{ background: rgba(100,116,139,0.15); color: var(--low); }}

        .pick-details {{
            padding: 0 1.25rem 1rem;
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 1rem;
        }}

        .pitchers {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            grid-column: 1 / -1;
            padding: 0.75rem;
            background: var(--surface2);
            border-radius: 8px;
        }}

        .pitcher {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }}

        .pitcher-name {{
            font-weight: 600;
            font-size: 0.95rem;
        }}

        .pitcher-stat, .pitcher-score {{
            font-size: 0.78rem;
            color: var(--text-dim);
        }}

        .vs {{
            color: var(--text-dim);
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .prediction {{
            text-align: center;
            padding: 0.75rem 1.5rem;
            background: var(--accent-glow);
            border-radius: 8px;
            border: 1px solid rgba(59,130,246,0.2);
        }}

        .pick-label {{
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--accent);
        }}

        .pick-team {{
            font-size: 1.05rem;
            font-weight: 800;
        }}

        .pick-prob {{
            font-size: 1.6rem;
            font-weight: 800;
            color: var(--accent);
        }}

        .pick-edge {{
            font-size: 0.75rem;
            color: var(--green);
            font-weight: 600;
        }}

        .factors {{
            grid-column: 1 / -1;
        }}

        .factor {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.3rem;
        }}

        .factor-label {{
            font-size: 0.72rem;
            color: var(--text-dim);
            width: 100px;
            flex-shrink: 0;
        }}

        .factor-bar {{
            height: 4px;
            border-radius: 2px;
            transition: width 0.5s;
        }}
        .factor-bar.positive {{ background: var(--green); }}
        .factor-bar.negative {{ background: var(--red); }}

        .factor-val {{
            font-size: 0.72rem;
            font-weight: 600;
            width: 45px;
            text-align: right;
            flex-shrink: 0;
        }}

        .pick-meta {{
            display: flex;
            gap: 1rem;
            padding: 0.6rem 1.25rem;
            border-top: 1px solid var(--border);
            font-size: 0.72rem;
            color: var(--text-dim);
        }}

        .no-picks {{
            text-align: center;
            padding: 3rem;
            color: var(--text-dim);
            background: var(--surface);
            border-radius: 12px;
            border: 1px solid var(--border);
        }}

        /* History */
        .history {{ margin-top: 3rem; }}

        .day-result {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 0.5rem;
            overflow: hidden;
        }}

        .day-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 0.8rem 1.25rem;
            cursor: pointer;
            user-select: none;
        }}

        .day-header:hover {{ background: var(--surface2); }}

        .day-date {{
            font-weight: 700;
            width: 60px;
        }}

        .day-record {{
            font-weight: 600;
            width: 40px;
        }}

        .day-pct {{
            font-weight: 700;
            width: 45px;
            color: var(--green);
        }}

        .day-brier {{
            font-size: 0.8rem;
            color: var(--text-dim);
            flex: 1;
        }}

        .expand-icon {{
            color: var(--text-dim);
            transition: transform 0.2s;
        }}

        .day-result.open .expand-icon {{ transform: rotate(90deg); }}

        .day-detail {{
            display: none;
            padding: 0 1.25rem 1rem;
        }}

        .day-result.open .day-detail {{ display: block; }}

        .result-pick {{
            padding: 0.4rem 0;
            font-size: 0.85rem;
            border-bottom: 1px solid var(--border);
        }}

        .result-pick:last-child {{ border-bottom: none; }}
        .result-pick.wrong {{ color: var(--text-dim); }}

        /* Calibration */
        .calibration {{ margin-top: 3rem; }}

        .cal-row {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
        }}

        .cal-pred, .cal-actual {{
            font-size: 0.8rem;
            font-weight: 600;
            width: 40px;
            text-align: right;
        }}

        .cal-actual {{ color: var(--green); }}

        .cal-n {{
            font-size: 0.72rem;
            color: var(--text-dim);
            width: 40px;
        }}

        .cal-bar-container {{
            flex: 1;
            height: 20px;
            background: var(--surface2);
            border-radius: 4px;
            position: relative;
            overflow: hidden;
        }}

        .cal-bar-predicted {{
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            background: rgba(59,130,246,0.25);
            border-right: 2px solid var(--accent);
        }}

        .cal-bar-actual {{
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            background: rgba(34,197,94,0.3);
            border-right: 2px solid var(--green);
        }}

        /* Tiers */
        .tiers {{ margin-top: 2rem; }}

        .tier-row {{
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 0.6rem 1rem;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 0.5rem;
        }}

        .tier-label {{ font-weight: 600; width: 100px; }}
        .tier-record {{ color: var(--text-dim); }}
        .tier-pct {{ font-weight: 700; color: var(--green); }}

        /* Footer */
        .footer {{
            margin-top: 4rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-dim);
            font-size: 0.8rem;
        }}

        .footer a {{ color: var(--accent); text-decoration: none; }}

        .methodology {{
            margin-top: 3rem;
            padding: 1.5rem;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
        }}

        .methodology h3 {{
            font-size: 1rem;
            margin-bottom: 0.75rem;
        }}

        .methodology p {{
            font-size: 0.85rem;
            color: var(--text-dim);
            margin-bottom: 0.5rem;
        }}

        /* Mobile */
        @media (max-width: 640px) {{
            .container {{ padding: 1rem; }}
            .header h1 {{ font-size: 1.6rem; }}
            .stats-bar {{ grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }}
            .stat-card .stat-value {{ font-size: 1.4rem; }}
            .pick-details {{ grid-template-columns: 1fr; }}
            .pitchers {{ flex-direction: column; }}
            .vs {{ display: none; }}
            .pick-meta {{ flex-wrap: wrap; }}
            .day-header {{ gap: 0.5rem; font-size: 0.9rem; }}
        }}
    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>⚾ MLB <span>Picks</span></h1>
            <p class="tagline">AI-powered daily predictions — every pick timestamped and tracked</p>
            <p class="updated">Last updated: {now}</p>
        </header>

        <div class="stats-bar">
            <div class="stat-card">
                <div class="stat-value {"stat-green" if accuracy > 0.55 else "stat-amber" if accuracy > 0.50 else "stat-red"}">{correct}-{total_picks - correct}</div>
                <div class="stat-label">Season Record</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {"stat-green" if accuracy > 0.55 else "stat-amber"}">{accuracy*100:.1f}%</div>
                <div class="stat-label">Win Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {"stat-green" if brier_skill > 0 else "stat-red"}">{brier_skill*100:.1f}%</div>
                <div class="stat-label">Brier Skill</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {"stat-green" if roi > 0 else "stat-red"}">{roi:+.1f}%</div>
                <div class="stat-label">Flat-bet ROI</div>
            </div>
        </div>

        <div class="picks-section">
            <div class="section-header">
                Today's Picks
                <span class="date-badge">{picks_date or "—"}</span>
            </div>
            {picks_html}
        </div>

        <div class="history">
            <div class="section-header">Results History</div>
            {history_html if history_html else '<div class="no-picks">No scored results yet. Check back after games finish.</div>'}
        </div>

        {f"""<div class="calibration">
            <div class="section-header">Calibration</div>
            <p style="font-size:0.82rem;color:var(--text-dim);margin-bottom:1rem;">
                Blue = predicted win probability. Green = actual win rate. Perfect calibration = bars match.
            </p>
            {cal_html}
        </div>""" if cal_html else ""}

        {f"""<div class="tiers">
            <div class="section-header">By Confidence Tier</div>
            {tiers_html}
        </div>""" if tiers_html else ""}

        <div class="methodology">
            <h3>Methodology</h3>
            <p>Multi-factor model analyzing starting pitcher quality (season + last 5 starts + vs-team history), team offense (OPS, runs/game, power), bullpen quality, home/away splits, Pythagorean win expectation, park factors, weather, and rest/travel.</p>
            <p>All picks are generated and timestamped before first pitch. Results are scored automatically using Brier score and log loss — industry-standard probability calibration metrics.</p>
            <p>Data source: MLB Stats API. Model version: v2.</p>
        </div>

        <footer class="footer">
            <p>Picks are for informational and entertainment purposes only.</p>
            <p style="margin-top:0.5rem;">© {datetime.now().year} MLB Picks</p>
        </footer>
    </div>
</body>
</html>'''

    OUT_FILE.write_text(html)
    print(f"✅ Generated {OUT_FILE} ({len(html):,} bytes)")
    return str(OUT_FILE)


if __name__ == "__main__":
    generate_html()
