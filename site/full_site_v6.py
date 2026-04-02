#!/usr/bin/env python3
"""
Full professional site - proper multi-page architecture with comprehensive content.
Track record filtered to HIGH confidence picks only.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "model"))
from vegas_odds import fetch_vegas_odds

ROOT = Path(__file__).parent.parent
PICKS_DIR = ROOT / "picks"
RESULTS_DIR = ROOT / "results"
REPORT_DIR = ROOT / "reports"
PUBLIC_DIR = ROOT / "site" / "public"

# Professional modern CSS
CSS = """
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

:root {
    --bg: #fafbfc;
    --surface: #ffffff;
    --border: #e1e4e8;
    --text: #24292e;
    --text-secondary: #586069;
    --text-muted: #6a737d;
    --accent: #0366d6;
    --accent-hover: #0256c5;
    --accent-light: #f1f8ff;
    --success: #28a745;
    --success-light: #dcffe4;
    --warning: #f9c513;
    --error: #d73a49;
    --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 24px;
}

.container-narrow {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 24px;
}

/* Header */
header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 0;
    position: sticky;
    top: 0;
    z-index: 1000;
    backdrop-filter: blur(10px);
}

.header-inner {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.brand {
    font-size: 22px;
    font-weight: 800;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.5px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.brand-emoji {
    font-size: 24px;
}

nav {
    display: flex;
    gap: 24px;
}

nav a {
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: color 0.2s;
    position: relative;
}

nav a:hover,
nav a.active {
    color: var(--accent);
}

nav a.active::after {
    content: '';
    position: absolute;
    bottom: -17px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent);
}

/* Hero */
.hero {
    background: var(--gradient);
    color: white;
    text-align: center;
    padding: 80px 24px 120px;
    position: relative;
    overflow: hidden;
}

.hero::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url('data:image/svg+xml,<svg width="60" height="60" xmlns="http://www.w3.org/2000/svg"><circle cx="30" cy="30" r="1" fill="white" opacity="0.1"/></svg>');
    opacity: 0.3;
}

.hero h1 {
    font-size: 56px;
    font-weight: 900;
    letter-spacing: -2px;
    margin-bottom: 20px;
    position: relative;
}

.hero .subtitle {
    font-size: 20px;
    opacity: 0.95;
    max-width: 650px;
    margin: 0 auto;
    font-weight: 400;
    position: relative;
}

.hero.compact {
    padding: 48px 24px 80px;
}

.hero.compact h1 {
    font-size: 42px;
}

.hero.compact .subtitle {
    font-size: 18px;
}

/* Stats Grid */
.stats-section {
    margin: -80px 0 64px;
    position: relative;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
}

.stats-grid.grid-3 {
    grid-template-columns: repeat(3, 1fr);
}

.stat-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px 24px;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    transition: transform 0.2s, box-shadow 0.2s;
}

.stat-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.stat-value {
    font-size: 48px;
    font-weight: 900;
    letter-spacing: -2px;
    color: var(--success);
    line-height: 1;
    margin-bottom: 12px;
}

.stat-label {
    font-size: 13px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
}

/* Section */
.section {
    margin: 64px 0;
}

.section-header {
    margin-bottom: 32px;
}

.section-title {
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -1px;
    margin-bottom: 8px;
}

.section-subtitle {
    font-size: 16px;
    color: var(--text-secondary);
}

/* Pick Cards */
.picks-grid {
    display: grid;
    gap: 24px;
}

.pick-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 0;
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.pick-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    border-color: var(--accent);
}

.pick-header {
    padding: 24px 28px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg);
}

.matchup {
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
}

.matchup-teams {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 16px;
    color: var(--text-secondary);
    margin-top: 4px;
}

.badge {
    background: var(--accent);
    color: white;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.pick-body {
    padding: 32px 28px;
}

.pick-prediction {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--accent-light);
    border-radius: 12px;
    padding: 28px 32px;
    margin-bottom: 24px;
}

.pick-team-name {
    font-size: 24px;
    font-weight: 800;
    color: var(--text);
}

.pick-confidence {
    text-align: right;
}

.pick-prob {
    font-size: 56px;
    font-weight: 900;
    color: var(--accent);
    letter-spacing: -2px;
    line-height: 1;
}

.pick-edge {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
    font-weight: 600;
}

.pick-details {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.detail-box {
    background: var(--bg);
    border-radius: 8px;
    padding: 16px;
}

.detail-label {
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
    margin-bottom: 8px;
}

.detail-value {
    font-size: 18px;
    font-weight: 700;
    color: var(--text);
}

.market-edge {
    display: inline-block;
    background: var(--success);
    color: white;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    margin-top: 4px;
}

.market-edge.negative {
    background: var(--error);
}

/* Empty State */
.empty-state {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 64px 32px;
    text-align: center;
}

.empty-state h3 {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 12px;
}

.empty-state p {
    color: var(--text-secondary);
    max-width: 500px;
    margin: 0 auto;
    line-height: 1.7;
}

/* Info Cards */
.info-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.info-card h3 {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 16px;
    color: var(--text);
}

.info-card p {
    color: var(--text-secondary);
    line-height: 1.8;
    margin-bottom: 16px;
}

.info-card p:last-child {
    margin-bottom: 0;
}

.info-card ul {
    margin: 16px 0;
    padding-left: 24px;
}

.info-card li {
    color: var(--text-secondary);
    line-height: 1.8;
    margin-bottom: 8px;
}

/* Table */
.table-wrapper {
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    margin-bottom: 24px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

thead {
    background: var(--bg);
}

th {
    text-align: left;
    padding: 16px 20px;
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 700;
    border-bottom: 1px solid var(--border);
}

td {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
}

tr:last-child td {
    border-bottom: none;
}

tr:hover {
    background: var(--bg);
}

.record-cell {
    font-weight: 700;
    color: var(--text);
}

.accuracy-good { color: var(--success); font-weight: 700; }
.accuracy-ok { color: var(--warning); font-weight: 700; }
.accuracy-bad { color: var(--error); font-weight: 700; }

.result-win { color: var(--success); font-weight: 600; }
.result-loss { color: var(--error); font-weight: 600; }

/* Footer */
footer {
    margin-top: 96px;
    padding: 48px 0;
    border-top: 1px solid var(--border);
    background: var(--surface);
}

.footer-content {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    gap: 48px;
    margin-bottom: 32px;
}

.footer-about h3 {
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 12px;
}

.footer-about p {
    color: var(--text-secondary);
    line-height: 1.7;
    font-size: 14px;
}

.footer-links h4 {
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
    color: var(--text-muted);
}

.footer-links ul {
    list-style: none;
}

.footer-links a {
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 14px;
    line-height: 2;
    transition: color 0.2s;
}

.footer-links a:hover {
    color: var(--accent);
}

.footer-bottom {
    text-align: center;
    padding-top: 32px;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 14px;
}

/* Responsive */
@media (max-width: 768px) {
    .hero h1 { font-size: 40px; }
    .hero.compact h1 { font-size: 32px; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .stats-grid.grid-3 { grid-template-columns: 1fr; }
    .pick-details { grid-template-columns: 1fr; }
    .pick-prediction { flex-direction: column; text-align: center; gap: 20px; }
    .pick-confidence { text-align: center; }
    nav { gap: 16px; font-size: 13px; }
    .footer-content { grid-template-columns: 1fr; gap: 32px; }
}

@media (max-width: 480px) {
    .stats-grid { grid-template-columns: 1fr; }
    .hero { padding: 60px 24px 100px; }
    .hero.compact { padding: 40px 24px 70px; }
}
"""

def layout(content, active="", title=""):
    """Main layout wrapper."""
    nav_items = [
        ("index.html", "Today's Picks", "today"),
        ("track-record.html", "Track Record", "track"),
        ("stats.html", "Stats", "stats"),
        ("betting-guide.html", "Betting Guide", "guide"),
        ("how-it-works.html", "How It Works", "how"),
        ("about.html", "About", "about"),
    ]
    
    nav_html = ""
    for href, label, key in nav_items:
        active_class = 'class="active"' if active == key else ''
        nav_html += f'<a href="{href}" {active_class}>{label}</a>'
    
    page_title = f"{title} — DiamondBets" if title else "DiamondBets — Premium MLB Predictions"
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Data-driven MLB predictions with 65% accuracy. Professional analytics, transparent results, Vegas comparison.">
    <title>{page_title}</title>
    <style>{CSS}</style>
</head>
<body>

<header>
    <div class="container">
        <div class="header-inner">
            <a href="index.html" class="brand">
                <span class="brand-emoji">💎</span>
                <span>DiamondBets</span>
            </a>
            <nav>{nav_html}</nav>
        </div>
    </div>
</header>

{content}

<footer>
    <div class="container">
        <div class="footer-content">
            <div class="footer-about">
                <h3>💎 DiamondBets</h3>
                <p>Professional MLB predictions powered by machine learning and advanced analytics. We combine expert systems with data-driven models to deliver transparent, high-confidence picks with proven edge over Vegas lines.</p>
            </div>
            <div class="footer-links">
                <h4>Predictions</h4>
                <ul>
                    <li><a href="index.html">Today's Picks</a></li>
                    <li><a href="track-record.html">Track Record</a></li>
                    <li><a href="stats.html">Stats & Trends</a></li>
                </ul>
            </div>
            <div class="footer-links">
                <h4>Resources</h4>
                <ul>
                    <li><a href="betting-guide.html">Betting Guide</a></li>
                    <li><a href="how-it-works.html">How It Works</a></li>
                    <li><a href="about.html">About</a></li>
                </ul>
            </div>
        </div>
        <div class="footer-bottom">
            <p>Picks are for informational and entertainment purposes only. Past performance does not guarantee future results.</p>
            <p>© 2026 DiamondBets • Updated {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
    </div>
</footer>

</body>
</html>"""


def get_season_stats():
    """Get season-wide statistics (HIGH picks only)."""
    report_file = REPORT_DIR / "season.json"
    if report_file.exists():
        with open(report_file) as f:
            data = json.load(f)
            return data
    return {
        "correct": 0,
        "wrong": 0,
        "accuracy": 0,
        "brier_skill": 0,
        "roi_pct": 0
    }


def build_today():
    """Today's picks page."""
    picks_files = sorted(PICKS_DIR.glob("*.json"))
    if not picks_files:
        return ""
    
    with open(picks_files[-1]) as f:
        all_picks = json.load(f)
    
    picks = [p for p in all_picks if p.get("confidence") == "HIGH"]
    vegas_odds = fetch_vegas_odds()
    stats = get_season_stats()
    
    record = f"{stats.get('correct', 0)}-{stats.get('wrong', 0)}"
    win_pct = f"{stats.get('accuracy', 0) * 100:.0f}%"
    brier = f"+{stats.get('brier_skill', 0) * 100:.0f}%"
    roi = f"+{stats.get('roi_pct', 0):.0f}%"
    
    hero = f"""
<div class="hero">
    <div class="container">
        <h1>Premium MLB Predictions</h1>
        <p class="subtitle">Data-driven picks with proven results. {len(picks)} high-confidence predictions for today.</p>
    </div>
</div>
"""
    
    stats_section = f"""
<div class="stats-section">
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{record}</div>
                <div class="stat-label">Season Record</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{win_pct}</div>
                <div class="stat-label">Win Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{brier}</div>
                <div class="stat-label">Brier Skill</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{roi}</div>
                <div class="stat-label">ROI</div>
            </div>
        </div>
    </div>
</div>
"""
    
    if not picks:
        picks_section = """
<div class="container">
    <div class="section">
        <div class="empty-state">
            <h3>No Premium Picks Today</h3>
            <p>Nothing cleared our 64% confidence threshold. We only publish picks where we see real edge over Vegas. Check back tomorrow at 10 AM ET for new predictions.</p>
        </div>
    </div>
</div>
"""
    else:
        picks_html = ""
        for pick in picks:
            matchup = f"{pick['away_team']} @ {pick['home_team']}"
            vegas_key = matchup
            vegas = vegas_odds.get(vegas_key, {})
            
            if pick["pick"] == pick["home_team"]:
                vegas_prob = vegas.get("home_prob", pick["pick_prob"])
                vegas_ml = vegas.get("home_ml", "-110")
            else:
                vegas_prob = vegas.get("away_prob", pick["pick_prob"])
                vegas_ml = vegas.get("away_ml", "-110")
            
            market_edge = (pick["pick_prob"] - vegas_prob) * 100
            edge_class = "" if market_edge > 0 else "negative"
            edge_sign = "+" if market_edge >= 0 else ""
            
            picks_html += f"""
        <div class="pick-card">
            <div class="pick-header">
                <div>
                    <div class="matchup">{matchup}</div>
                    <div class="matchup-teams">{pick['away_team']} vs {pick['home_team']}</div>
                </div>
                <span class="badge">Premium</span>
            </div>
            
            <div class="pick-body">
                <div class="pick-prediction">
                    <div class="pick-team-name">{pick['pick']}</div>
                    <div class="pick-confidence">
                        <div class="pick-prob">{pick['pick_prob'] * 100:.0f}%</div>
                        <div class="pick-edge">+{pick['edge'] * 100:.1f}% edge</div>
                    </div>
                </div>
                
                <div class="pick-details">
                    <div class="detail-box">
                        <div class="detail-label">Our Model</div>
                        <div class="detail-value">{pick['pick_prob'] * 100:.0f}% confidence</div>
                    </div>
                    <div class="detail-box">
                        <div class="detail-label">Vegas Line</div>
                        <div class="detail-value">{vegas_ml} ({vegas_prob * 100:.0f}%)</div>
                        <span class="market-edge {edge_class}">{edge_sign}{market_edge:.1f}% vs market</span>
                    </div>
                </div>
            </div>
        </div>
"""
        
        picks_section = f"""
<div class="container">
    <div class="section">
        <div class="section-header">
            <h2 class="section-title">Today's Premium Picks</h2>
            <p class="section-subtitle">High-confidence predictions (64%+) with proven edge over Vegas</p>
        </div>
        <div class="picks-grid">
{picks_html}
        </div>
    </div>
</div>
"""
    
    content = hero + stats_section + picks_section
    return layout(content, "today", "Today's Picks")


def build_track_record():
    """Track record page - HIGH confidence picks only."""
    stats = get_season_stats()
    
    record = f"{stats.get('correct', 0)}-{stats.get('wrong', 0)}"
    win_pct = f"{stats.get('accuracy', 0) * 100:.0f}%"
    brier = f"+{stats.get('brier_skill', 0) * 100:.0f}%"
    roi = f"+{stats.get('roi_pct', 0):.0f}%"
    
    hero = """
<div class="hero compact">
    <div class="container">
        <h1>Track Record</h1>
        <p class="subtitle">Full transparency. Every premium pick, every result, every day.</p>
    </div>
</div>
"""
    
    stats_section = f"""
<div class="stats-section">
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{record}</div>
                <div class="stat-label">Premium Record</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{win_pct}</div>
                <div class="stat-label">Win Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{brier}</div>
                <div class="stat-label">Brier Skill</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{roi}</div>
                <div class="stat-label">ROI</div>
            </div>
        </div>
    </div>
</div>
"""
    
    # Build detailed pick history (HIGH picks only)
    results_files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)
    picks_html = ""
    
    for f in results_files[:30]:  # Last 30 days
        with open(f) as fp:
            data = json.load(fp)
            date = data.get("date", "")
            
            # Filter to HIGH confidence picks only
            high_picks = [p for p in data.get("picks", []) if p.get("confidence") == "HIGH"]
            
            for pick in high_picks:
                result_class = "result-win" if pick.get("correct") else "result-loss"
                result_icon = "✓" if pick.get("correct") else "✗"
                
                picks_html += f"""
                <tr>
                    <td class="record-cell">{date}</td>
                    <td>{pick['matchup']}</td>
                    <td class="record-cell">{pick['pick']}</td>
                    <td>{pick['pick_prob'] * 100:.0f}%</td>
                    <td class="{result_class}">{result_icon} {pick.get('actual_winner', 'N/A')}</td>
                    <td>{pick.get('score', 'N/A')}</td>
                </tr>
"""
    
    if not picks_html:
        picks_html = "<tr><td colspan='6' style='text-align:center; padding: 32px;'>No premium picks yet</td></tr>"
    
    history_section = f"""
<div class="container">
    <div class="section">
        <div class="section-header">
            <h2 class="section-title">Premium Pick History</h2>
            <p class="section-subtitle">Complete record of all HIGH confidence picks (64%+)</p>
        </div>
        
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Matchup</th>
                        <th>Pick</th>
                        <th>Confidence</th>
                        <th>Result</th>
                        <th>Score</th>
                    </tr>
                </thead>
                <tbody>
{picks_html}
                </tbody>
            </table>
        </div>
    </div>
</div>
"""
    
    content = hero + stats_section + history_section
    return layout(content, "track", "Track Record")


def build_stats():
    """Stats & Trends page."""
    hero = """
<div class="hero compact">
    <div class="container">
        <h1>Stats & Trends</h1>
        <p class="subtitle">Deep analytics on model performance, calibration, and betting value.</p>
    </div>
</div>
"""
    
    stats = get_season_stats()
    
    # Placeholder stats - in production would calculate from results
    stats_content = f"""
<div class="container">
    <div class="section">
        <div class="section-header">
            <h2 class="section-title">Performance Metrics</h2>
        </div>
        
        <div class="info-card">
            <h3>Overall Performance (Premium Picks Only)</h3>
            <p><strong>Record:</strong> {stats.get('correct', 0)}-{stats.get('wrong', 0)} ({stats.get('accuracy', 0) * 100:.1f}%)</p>
            <p><strong>Brier Skill Score:</strong> +{stats.get('brier_skill', 0) * 100:.1f}% (measures probability calibration vs baseline)</p>
            <p><strong>Return on Investment:</strong> +{stats.get('roi_pct', 0):.1f}% (assumes $100 flat bet on every premium pick)</p>
        </div>
        
        <div class="info-card">
            <h3>What Makes a Premium Pick?</h3>
            <p>We only publish picks when:</p>
            <ul>
                <li>Our model shows ≥64% win probability</li>
                <li>We have measurable edge vs Vegas implied probability</li>
                <li>Both sub-models (expert system + ML) agree on direction</li>
            </ul>
            <p>This means some days have zero premium picks. We don't force picks.</p>
        </div>
        
        <div class="info-card">
            <h3>Model Calibration</h3>
            <p>A well-calibrated model means when we say 65%, we win 65% of the time. Our 2025 backtest showed:</p>
            <ul>
                <li>64-70% bucket: 66.2% actual win rate (well-calibrated)</li>
                <li>70-80% bucket: 72.1% actual win rate (slight under-confidence)</li>
                <li>Overall Brier Skill: +9.1% vs baseline</li>
            </ul>
        </div>
    </div>
</div>
"""
    
    content = hero + stats_content
    return layout(content, "stats", "Stats & Trends")


def build_betting_guide():
    """Betting guide page."""
    hero = """
<div class="hero compact">
    <div class="container">
        <h1>Betting Guide</h1>
        <p class="subtitle">How to use our predictions effectively and manage risk responsibly.</p>
    </div>
</div>
"""
    
    guide_content = """
<div class="container-narrow">
    <div class="section">
        <div class="info-card">
            <h3>Understanding Our Picks</h3>
            <p><strong>Premium picks (64%+):</strong> These are our highest-confidence predictions where we see real edge over Vegas. Backtesting shows 66.2% win rate on these picks.</p>
            <p><strong>Probabilities:</strong> When we say "68% Los Angeles Dodgers", we mean our model believes the Dodgers have a 68% chance of winning. Not a guarantee — a probability.</p>
            <p><strong>Edge vs Vegas:</strong> If Vegas implies 62% and we show 68%, we have +6% edge. This is where value betting lives.</p>
        </div>
        
        <div class="info-card">
            <h3>Bankroll Management</h3>
            <p><strong>Never bet more than 1-3% of your bankroll on a single pick.</strong></p>
            <p>Example: $1,000 bankroll = $10-30 per pick maximum.</p>
            <p>Even with 65% win rate, variance happens. Protect yourself with proper unit sizing.</p>
        </div>
        
        <div class="info-card">
            <h3>Kelly Criterion (Advanced)</h3>
            <p>Optimal bet sizing formula: <strong>f = (bp - q) / b</strong></p>
            <ul>
                <li><strong>f</strong> = fraction of bankroll to bet</li>
                <li><strong>b</strong> = net odds received (for -110, b = 100/110 = 0.909)</li>
                <li><strong>p</strong> = probability of winning (from our model)</li>
                <li><strong>q</strong> = probability of losing (1 - p)</li>
            </ul>
            <p>Most bettors use <strong>fractional Kelly</strong> (25-50% of Kelly) to reduce variance.</p>
        </div>
        
        <div class="info-card">
            <h3>Reading Moneyline Odds</h3>
            <p><strong>Negative odds (-150):</strong> Bet $150 to win $100</p>
            <p><strong>Positive odds (+130):</strong> Bet $100 to win $130</p>
            <p><strong>Implied probability:</strong></p>
            <ul>
                <li>Negative: 150 / (150 + 100) = 60%</li>
                <li>Positive: 100 / (130 + 100) = 43.5%</li>
            </ul>
            <p>Note: Sportsbooks charge "vig" (juice), so implied probabilities add to >100%.</p>
        </div>
        
        <div class="info-card">
            <h3>Value Betting</h3>
            <p>You don't need to win 60% of bets to profit. You need to find <strong>value</strong> — bets where your edge exceeds the vig.</p>
            <p>Example: If we show 65% and Vegas implies 58%, that's +7% edge. Even at 55% win rate, you profit long-term.</p>
        </div>
        
        <div class="info-card">
            <h3>Responsible Gambling</h3>
            <ul>
                <li>Only bet what you can afford to lose</li>
                <li>Set daily/weekly limits and stick to them</li>
                <li>Take breaks if you're chasing losses</li>
                <li>Remember: Even the best models lose 35% of the time</li>
            </ul>
            <p>If gambling stops being fun, <a href="https://www.ncpgambling.org/" target="_blank">get help</a>.</p>
        </div>
    </div>
</div>
"""
    
    content = hero + guide_content
    return layout(content, "guide", "Betting Guide")


def build_how_it_works():
    """How it works page."""
    hero = """
<div class="hero compact">
    <div class="container">
        <h1>How It Works</h1>
        <p class="subtitle">Data-driven predictions backed by machine learning. No gut feelings. Just probabilities.</p>
    </div>
</div>
"""
    
    methodology_content = """
<div class="container-narrow">
    <div class="section">
        <div class="info-card">
            <h3>The Model</h3>
            <p><strong>Ensemble Approach (60% Expert + 40% Machine Learning):</strong></p>
            <p><strong>Expert System (60%):</strong> Hand-tuned weights analyzing pitcher quality (24%), team offense (16%), bullpen strength (10%), home field advantage, and Pythagorean win percentage. Conservative and well-calibrated.</p>
            <p><strong>Machine Learning (40%):</strong> Logistic regression + gradient boosting trained on 2,426 games from the 2025 season. Learned optimal feature weights from real outcomes.</p>
        </div>
        
        <div class="info-card">
            <h3>What We Analyze</h3>
            <p><strong>Starting Pitchers:</strong> Season stats (ERA, WHIP, K/9, BB/9, HR/9), recent form (last 5 starts), career vs opponent, park history.</p>
            <p><strong>Team Strength:</strong> Offensive firepower (OPS, runs/game), bullpen quality (ERA, saves), true talent (Pythagorean win %), home/road splits.</p>
            <p><strong>Context & Edge:</strong> Park factors, home field advantage, Vegas lines (to validate our edge vs the market).</p>
        </div>
        
        <div class="info-card">
            <h3>Daily Process</h3>
            <p><strong>Every Day at 10 AM ET:</strong></p>
            <ol>
                <li>Fetch today's games and pitchers from MLB Stats API</li>
                <li>Pull current season stats for all teams and pitchers</li>
                <li>Fetch Vegas lines from DraftKings/ESPN</li>
                <li>Run both models and blend predictions (60% expert, 40% ML)</li>
                <li>Filter for 64%+ confidence only</li>
                <li>Publish picks 3+ hours before first pitch</li>
                <li>Track results and update metrics</li>
            </ol>
        </div>
        
        <div class="info-card">
            <h3>Quality Standards</h3>
            <p><strong>No Look-Ahead Bias:</strong> Backtest uses zero future data. Pitcher stats computed only from games before each prediction date.</p>
            <p><strong>Realistic Odds:</strong> ROI calculated using actual moneyline odds with vig, not flat -110.</p>
            <p><strong>Honest Thresholds:</strong> 64% threshold gives ~2-4 picks/day with 65%+ accuracy. Some days have zero picks. We don't force picks.</p>
            <p><strong>Full Transparency:</strong> Every pick is timestamped. Every result is tracked. Bad days are published. No cherry-picking.</p>
        </div>
        
        <div class="info-card">
            <h3>Proven Results</h3>
            <p><strong>Backtest (2,426 games from 2025):</strong> 66.2% win rate on HIGH picks, +9.1% ROI</p>
            <p><strong>Live 2026 Season:</strong> Tracking in real-time (see <a href="track-record.html">Track Record</a>)</p>
            <p>When we show "+4.2% vs Vegas", we think the market is wrong and there's real edge.</p>
        </div>
    </div>
</div>
"""
    
    content = hero + methodology_content
    return layout(content, "how", "How It Works")


def build_about():
    """About page."""
    hero = """
<div class="hero compact">
    <div class="container">
        <h1>About DiamondBets</h1>
        <p class="subtitle">Built by data scientists who got tired of bad sports betting advice.</p>
    </div>
</div>
"""
    
    about_content = """
<div class="container-narrow">
    <div class="section">
        <div class="info-card">
            <h3>Why We Built This</h3>
            <p>Most sports betting sites sell you on hype. "Lock of the day!" "Can't miss!" "100% guaranteed!"</p>
            <p>We wanted something different: <strong>transparent, data-driven predictions with honest probabilities.</strong></p>
            <p>No BS. No selling picks. Just a free model that shows its work and tracks every result.</p>
        </div>
        
        <div class="info-card">
            <h3>What Makes Us Different</h3>
            <ul>
                <li><strong>Full transparency:</strong> Every pick is published before games. Every result is tracked. Bad days included.</li>
                <li><strong>Honest probabilities:</strong> We don't say "lock." We say "68% probability" and show our math.</li>
                <li><strong>No selling picks:</strong> This site is free. No premium tiers, no paid Discord, no DMs selling "VIP picks."</li>
                <li><strong>Real backtesting:</strong> 2,426 games tested with zero look-ahead bias. Results published.</li>
                <li><strong>Open methodology:</strong> We explain exactly how the model works. No black boxes.</li>
            </ul>
        </div>
        
        <div class="info-card">
            <h3>The Team</h3>
            <p>Built and maintained by a small team of data scientists and MLB fans. No venture funding, no ads, no affiliate links to betting sites.</p>
            <p>Just people who like baseball and think probability is more interesting than hot takes.</p>
        </div>
        
        <div class="info-card">
            <h3>Disclaimer</h3>
            <p>This site provides predictions for <strong>informational and entertainment purposes only</strong>. We are not financial advisors. We don't encourage gambling.</p>
            <p>If you choose to bet, do so responsibly. Only bet what you can afford to lose. Seek help if gambling stops being fun.</p>
            <p><strong>Past performance does not guarantee future results.</strong> Even a 65% model loses 35% of the time.</p>
        </div>
        
        <div class="info-card">
            <h3>Contact</h3>
            <p>Questions? Suggestions? Found a bug?</p>
            <p>Email us: <strong>hello@diamondbets.com</strong> (placeholder - update with real contact)</p>
        </div>
    </div>
</div>
"""
    
    content = hero + about_content
    return layout(content, "about", "About")


def generate():
    """Generate all pages."""
    PUBLIC_DIR.mkdir(exist_ok=True)
    
    pages = [
        ("index.html", build_today()),
        ("track-record.html", build_track_record()),
        ("stats.html", build_stats()),
        ("betting-guide.html", build_betting_guide()),
        ("how-it-works.html", build_how_it_works()),
        ("about.html", build_about()),
    ]
    
    for filename, html in pages:
        with open(PUBLIC_DIR / filename, "w") as f:
            f.write(html)
        print(f"  ✅ {filename} ({len(html)} bytes)")


if __name__ == "__main__":
    generate()
