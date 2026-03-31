#!/usr/bin/env python3
"""
MLB Prediction Model v1
Pitcher-heavy win probability model for daily game predictions.
"""

import json
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

# ── MLB Stats API helpers ─────────────────────────────────────────────

BASE_URL = "https://statsapi.mlb.com/api/v1"

def api_get(endpoint: str) -> dict:
    url = f"{BASE_URL}{endpoint}"
    data = urllib.request.urlopen(url, timeout=15).read()
    return json.loads(data)

def get_schedule(date: str) -> list:
    """Get games for a date (YYYY-MM-DD) with probable pitchers."""
    data = api_get(f"/schedule?sportId=1&date={date}&hydrate=probablePitcher(note),team,venue")
    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            if game.get("gameType") != "R":
                continue
            games.append(game)
    return games

def get_pitcher_stats(player_id: int, season: int = 2025) -> Optional[dict]:
    """Get a pitcher's season stats. Falls back to most recent available season."""
    try:
        data = api_get(f"/people/{player_id}/stats?stats=yearByYear&group=pitching&sportId=1")
        splits = data["stats"][0]["splits"]
        # Try requested season first, then fall back to most recent
        for s in reversed(splits):
            if int(s["season"]) == season:
                return s["stat"]
        # Fall back to most recent MLB season
        for s in reversed(splits):
            if s.get("sport", {}).get("id") == 1:
                return s["stat"]
    except Exception:
        pass
    return None

def get_team_record(team_id: int, season: int = 2025) -> Optional[dict]:
    """Get team W-L record and run differential."""
    try:
        data = api_get(f"/teams/{team_id}/stats?stats=season&season={season}&group=hitting")
        if data["stats"] and data["stats"][0]["splits"]:
            return data["stats"][0]["splits"][0]["stat"]
    except Exception:
        pass
    return None

def get_team_standings(season: int = 2025) -> dict:
    """Get team standings with win percentages."""
    try:
        data = api_get(f"/standings?leagueId=103,104&season={season}&standingsTypes=regularSeason")
        teams = {}
        for record in data.get("records", []):
            for team_record in record.get("teamRecords", []):
                team_id = team_record["team"]["id"]
                teams[team_id] = {
                    "wins": team_record.get("wins", 0),
                    "losses": team_record.get("losses", 0),
                    "pct": float(team_record.get("winningPercentage", ".500")),
                    "run_diff": team_record.get("runDifferential", 0),
                    "home_wins": team_record.get("records", {}).get("splitRecords", [{}])[0].get("wins", 0) if team_record.get("records") else 0,
                    "home_losses": team_record.get("records", {}).get("splitRecords", [{}])[0].get("losses", 0) if team_record.get("records") else 0,
                }
        return teams
    except Exception:
        return {}


# ── Prediction Model ──────────────────────────────────────────────────

# Park factors (runs relative to average — 1.0 = neutral)
PARK_FACTORS = {
    "Coors Field": 1.30,
    "Great American Ball Park": 1.12,
    "Fenway Park": 1.08,
    "Globe Life Field": 1.06,
    "Citizens Bank Park": 1.05,
    "Wrigley Field": 1.04,
    "Yankee Stadium": 1.04,
    "Guaranteed Rate Field": 1.02,
    "American Family Field": 1.01,
    "Citi Field": 0.98,
    "Busch Stadium": 0.98,
    "Angel Stadium": 0.97,
    "Dodger Stadium": 0.97,
    "Target Field": 0.97,
    "Daikin Park": 0.96,  # formerly Minute Maid
    "T-Mobile Park": 0.95,
    "Tropicana Field": 0.95,
    "Petco Park": 0.93,
    "Oracle Park": 0.92,
    "Kauffman Stadium": 0.95,
    "Oriole Park at Camden Yards": 1.02,
    "PNC Park": 0.96,
    "Nationals Park": 1.00,
    "Progressive Field": 0.98,
    "Rogers Centre": 1.03,
    "Truist Park": 1.00,
    "Chase Field": 1.03,
    "loanDepot park": 0.97,
    "Oakland Coliseum": 0.95,
    "Comerica Park": 0.96,
}

# Home field advantage in MLB is roughly 54% historically
HOME_ADVANTAGE = 0.04  # +4% to home team base probability


def pitcher_score(stats: Optional[dict]) -> float:
    """
    Rate a pitcher 0-100 based on key stats.
    Higher = better pitcher.
    """
    if not stats:
        return 45.0  # Unknown pitcher = slightly below average

    era = float(stats.get("era", "4.50"))
    whip = float(stats.get("whip", "1.30"))
    k_per_9 = float(stats.get("strikeoutsPer9Inn", "7.5"))
    bb_per_9 = float(stats.get("walksPer9Inn", "3.0"))
    ip = float(stats.get("inningsPitched", "0"))

    # Normalize each stat to 0-100 scale
    # ERA: 2.0 = elite (95), 4.50 = avg (50), 6.0 = bad (20)
    era_score = max(10, min(95, 100 - (era - 2.0) * 18.75))

    # WHIP: 0.90 = elite (95), 1.30 = avg (50), 1.60 = bad (20)
    whip_score = max(10, min(95, 100 - (whip - 0.90) * 64.3))

    # K/9: 12+ = elite (95), 7.5 = avg (50), 5.0 = bad (20)
    k_score = max(10, min(95, 20 + (k_per_9 - 5.0) * 10.7))

    # BB/9: 1.5 = elite (90), 3.0 = avg (55), 5.0 = bad (20)
    bb_score = max(10, min(90, 90 - (bb_per_9 - 1.5) * 20))

    # Weight: ERA matters most, then WHIP, then K rate, then walks
    score = (era_score * 0.35) + (whip_score * 0.25) + (k_score * 0.20) + (bb_score * 0.20)

    # Discount for low innings (less reliable data)
    if ip < 50:
        score = score * 0.7 + 45 * 0.3  # Regress toward average
    elif ip < 100:
        score = score * 0.85 + 45 * 0.15

    return round(score, 1)


def predict_game(game: dict, standings: dict) -> dict:
    """
    Generate a win probability prediction for a game.
    Returns prediction dict with all the details.
    """
    away_team = game["teams"]["away"]["team"]
    home_team = game["teams"]["home"]["team"]
    venue = game.get("venue", {}).get("name", "Unknown")

    # Get probable pitchers
    away_pitcher = game["teams"]["away"].get("probablePitcher", {})
    home_pitcher = game["teams"]["home"].get("probablePitcher", {})

    away_pitcher_name = away_pitcher.get("fullName", "TBD")
    home_pitcher_name = home_pitcher.get("fullName", "TBD")

    # Get pitcher stats (use 2025 season)
    away_p_stats = get_pitcher_stats(away_pitcher["id"]) if away_pitcher.get("id") else None
    home_p_stats = get_pitcher_stats(home_pitcher["id"]) if home_pitcher.get("id") else None

    # Score pitchers
    away_p_score = pitcher_score(away_p_stats)
    home_p_score = pitcher_score(home_p_stats)

    # Team strength from standings
    away_standing = standings.get(away_team["id"], {})
    home_standing = standings.get(home_team["id"], {})
    away_team_pct = away_standing.get("pct", 0.500)
    home_team_pct = home_standing.get("pct", 0.500)

    # ── Build win probability ──

    # Start with 50/50
    home_prob = 0.50

    # Pitcher differential (biggest factor — up to ±15%)
    pitcher_diff = (home_p_score - away_p_score) / 100.0
    home_prob += pitcher_diff * 0.30  # Scale: 30-point diff = ~9% swing

    # Team quality differential (up to ±10%)
    team_diff = home_team_pct - away_team_pct
    home_prob += team_diff * 0.20  # A .600 vs .400 team = ~4% swing

    # Home field advantage
    home_prob += HOME_ADVANTAGE

    # Park factor (slight adjustment — pitchers parks favor pitching-strong teams)
    park = PARK_FACTORS.get(venue, 1.0)
    # In pitcher-friendly parks, good pitchers get a slight boost
    if park < 0.97 and home_p_score > 60:
        home_prob += 0.01
    elif park > 1.05 and home_p_score < 50:
        home_prob -= 0.01

    # Clamp to reasonable range
    home_prob = max(0.25, min(0.75, home_prob))
    away_prob = 1.0 - home_prob

    # Determine pick
    if home_prob >= 0.55:
        pick = home_team["name"]
        confidence = "HIGH" if home_prob >= 0.60 else "MEDIUM"
    elif away_prob >= 0.55:
        pick = away_team["name"]
        confidence = "HIGH" if away_prob >= 0.60 else "MEDIUM"
    else:
        pick = home_team["name"] if home_prob > away_prob else away_team["name"]
        confidence = "LOW"

    # Edge vs implied 50/50 market
    pick_prob = max(home_prob, away_prob)
    edge = pick_prob - 0.50

    return {
        "game_id": game["gamePk"],
        "game_date": game.get("officialDate", ""),
        "game_time": game.get("gameDate", ""),
        "away_team": away_team["name"],
        "home_team": home_team["name"],
        "away_pitcher": away_pitcher_name,
        "home_pitcher": home_pitcher_name,
        "away_pitcher_score": away_p_score,
        "home_pitcher_score": home_p_score,
        "away_pitcher_era": away_p_stats.get("era", "N/A") if away_p_stats else "N/A",
        "home_pitcher_era": home_p_stats.get("era", "N/A") if home_p_stats else "N/A",
        "away_pitcher_whip": away_p_stats.get("whip", "N/A") if away_p_stats else "N/A",
        "home_pitcher_whip": home_p_stats.get("whip", "N/A") if home_p_stats else "N/A",
        "away_team_pct": away_team_pct,
        "home_team_pct": home_team_pct,
        "venue": venue,
        "park_factor": PARK_FACTORS.get(venue, 1.0),
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(away_prob, 3),
        "pick": pick,
        "pick_prob": round(pick_prob, 3),
        "confidence": confidence,
        "edge": round(edge, 3),
    }


def run_predictions(date: str = None) -> list:
    """Run predictions for all games on a given date."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 Fetching games for {date}...")
    games = get_schedule(date)

    if not games:
        print(f"No games found for {date}")
        return []

    print(f"📊 Found {len(games)} games. Loading standings + pitcher data...")
    standings = get_team_standings(2025)

    predictions = []
    for game in games:
        try:
            pred = predict_game(game, standings)
            predictions.append(pred)
        except Exception as e:
            print(f"  ⚠️ Error predicting game {game.get('gamePk')}: {e}")

    # Sort by edge (best picks first)
    predictions.sort(key=lambda x: x["edge"], reverse=True)
    return predictions


def format_predictions_text(predictions: list) -> str:
    """Format predictions as clean text output."""
    if not predictions:
        return "No predictions available."

    date = predictions[0]["game_date"]
    lines = [f"⚾ MLB PREDICTIONS — {date}", "=" * 50, ""]

    for i, p in enumerate(predictions, 1):
        conf_emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚪"}.get(p["confidence"], "⚪")

        lines.append(f"{conf_emoji} {p['away_team']} @ {p['home_team']}")
        lines.append(f"   Pitchers: {p['away_pitcher']} (Score: {p['away_pitcher_score']}) vs {p['home_pitcher']} (Score: {p['home_pitcher_score']})")
        lines.append(f"   Venue: {p['venue']} (Park factor: {p['park_factor']})")
        lines.append(f"   📈 PICK: {p['pick']} ({p['pick_prob']*100:.1f}%) — Confidence: {p['confidence']}")
        lines.append(f"   Edge: +{p['edge']*100:.1f}%")
        lines.append("")

    # Summary
    high = sum(1 for p in predictions if p["confidence"] == "HIGH")
    med = sum(1 for p in predictions if p["confidence"] == "MEDIUM")
    low = sum(1 for p in predictions if p["confidence"] == "LOW")
    lines.append(f"Summary: {len(predictions)} games | 🔥 {high} high | ✅ {med} medium | ⚪ {low} low confidence")

    return "\n".join(lines)


def format_predictions_discord(predictions: list) -> str:
    """Format predictions for Discord posting."""
    if not predictions:
        return "No games today."

    date = predictions[0]["game_date"]
    lines = [f"# ⚾ MLB Predictions — {date}\n"]

    for p in predictions:
        conf_emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚪"}.get(p["confidence"], "⚪")
        lines.append(f"{conf_emoji} **{p['away_team']}** @ **{p['home_team']}**")
        lines.append(f"> 🎯 {p['away_pitcher']} (`{p['away_pitcher_score']}`) vs {p['home_pitcher']} (`{p['home_pitcher_score']}`)")
        lines.append(f"> 📈 **PICK: {p['pick']}** ({p['pick_prob']*100:.1f}%) — {p['confidence']} confidence")
        lines.append("")

    high = sum(1 for p in predictions if p["confidence"] == "HIGH")
    med = sum(1 for p in predictions if p["confidence"] == "MEDIUM")
    lines.append(f"*{len(predictions)} games | 🔥 {high} high | ✅ {med} medium conf*")
    lines.append(f"\n`Model: Pitcher-weighted v1 | Data: MLB Stats API`")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else None
    predictions = run_predictions(date)
    print(format_predictions_text(predictions))

    # Save to JSON
    if predictions:
        outfile = f"picks/{predictions[0]['game_date']}.json"
        with open(outfile, "w") as f:
            json.dump(predictions, f, indent=2)
        print(f"\n💾 Saved to {outfile}")
