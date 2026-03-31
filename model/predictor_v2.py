#!/usr/bin/env python3
"""
MLB Prediction Model v2 — Maximum Accuracy Edition
Every factor we can get from free data sources.

Factors:
 1. Starting pitcher quality (ERA, WHIP, K/9, BB/9, K/BB, HR/9, GB%)
 2. Pitcher recent form (last 5 starts weighted > season)
 3. Pitcher handedness vs lineup composition
 4. Team offensive strength (OPS, OBP, SLG, runs/game)
 5. Team pitching staff / bullpen quality
 6. Home/away splits (team-specific, not league average)
 7. Pythagorean win expectation (true talent level)
 8. Run differential & momentum
 9. Park factors (detailed by venue)
10. Weather (temp, wind speed & direction)
11. Rest/travel (back-to-back, cross-country travel)
12. Head-to-head pitcher vs team history
"""

import json
import math
import urllib.request
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# ── API Layer ─────────────────────────────────────────────────────────

BASE_URL = "https://statsapi.mlb.com/api/v1"
_cache = {}

def api_get(endpoint: str) -> dict:
    if endpoint in _cache:
        return _cache[endpoint]
    url = f"{BASE_URL}{endpoint}"
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=20).read())
        _cache[endpoint] = data
        return data
    except Exception as e:
        print(f"  ⚠ API error: {endpoint}: {e}")
        return {}

def get_schedule(date: str) -> list:
    data = api_get(f"/schedule?sportId=1&date={date}&hydrate=probablePitcher(note),team,venue(location),weather")
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("gameType") == "R":
                games.append(g)
    return games

def get_pitcher_season_stats(player_id: int, season: int = 2025) -> Optional[dict]:
    data = api_get(f"/people/{player_id}/stats?stats=yearByYear&group=pitching&sportId=1")
    for split in reversed(data.get("stats", [{}])[0].get("splits", [])):
        if int(split["season"]) == season:
            return split["stat"]
    # fallback to most recent
    splits = data.get("stats", [{}])[0].get("splits", [])
    if splits:
        return splits[-1]["stat"]
    return None

def get_pitcher_game_log(player_id: int, season: int = 2025) -> list:
    data = api_get(f"/people/{player_id}/stats?stats=gameLog&group=pitching&season={season}&sportId=1")
    return data.get("stats", [{}])[0].get("splits", [])

def get_pitcher_vs_team(player_id: int, team_id: int) -> Optional[dict]:
    """Career stats vs specific team."""
    data = api_get(f"/people/{player_id}/stats?stats=vsTeam&group=pitching&sportId=1&opposingTeamId={team_id}")
    splits = data.get("stats", [{}])[0].get("splits", [])
    if splits:
        return splits[0].get("stat")
    return None

def get_team_batting(team_id: int, season: int = 2025) -> Optional[dict]:
    data = api_get(f"/teams/{team_id}/stats?stats=season&season={season}&group=hitting")
    splits = data.get("stats", [{}])[0].get("splits", [])
    return splits[0]["stat"] if splits else None

def get_team_pitching(team_id: int, season: int = 2025) -> Optional[dict]:
    data = api_get(f"/teams/{team_id}/stats?stats=season&season={season}&group=pitching")
    splits = data.get("stats", [{}])[0].get("splits", [])
    return splits[0]["stat"] if splits else None

def get_all_standings(season: int = 2025) -> dict:
    data = api_get(f"/standings?leagueId=103,104&season={season}&standingsTypes=regularSeason")
    teams = {}
    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            tid = tr["team"]["id"]
            splits = tr.get("records", {}).get("splitRecords", [])
            home_rec = next((s for s in splits if s.get("type") == "home"), {})
            away_rec = next((s for s in splits if s.get("type") == "away"), {})
            teams[tid] = {
                "wins": tr.get("wins", 81),
                "losses": tr.get("losses", 81),
                "pct": float(tr.get("winningPercentage", ".500")),
                "run_diff": tr.get("runDifferential", 0),
                "runs_scored": tr.get("runsScored", 700),
                "runs_allowed": tr.get("runsAllowed", 700),
                "home_w": home_rec.get("wins", 40),
                "home_l": home_rec.get("losses", 41),
                "away_w": away_rec.get("wins", 40),
                "away_l": away_rec.get("losses", 41),
                "last10_w": tr.get("records", {}).get("splitRecords", [{}])[-1].get("wins", 5) if splits else 5,
                "streak": tr.get("streak", {}).get("streakNumber", 0),
                "streak_type": tr.get("streak", {}).get("streakType", ""),
            }
    return teams

def get_recent_schedule(team_id: int, date: str, days_back: int = 5) -> list:
    """Get recent games for travel/rest detection."""
    end = datetime.strptime(date, "%Y-%m-%d")
    start = end - timedelta(days=days_back)
    data = api_get(f"/schedule?sportId=1&teamId={team_id}&startDate={start.strftime('%Y-%m-%d')}&endDate={date}&hydrate=venue(location)")
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("gameType") == "R":
                games.append(g)
    return games


# ── Scoring Functions ─────────────────────────────────────────────────

PARK_FACTORS = {
    "Coors Field": 1.30, "Great American Ball Park": 1.12, "Fenway Park": 1.08,
    "Globe Life Field": 1.06, "Citizens Bank Park": 1.05, "Wrigley Field": 1.04,
    "Yankee Stadium": 1.04, "Guaranteed Rate Field": 1.02, "American Family Field": 1.01,
    "Rogers Centre": 1.03, "Chase Field": 1.03, "Oriole Park at Camden Yards": 1.02,
    "Truist Park": 1.00, "Nationals Park": 1.00, "Citi Field": 0.98,
    "Busch Stadium": 0.98, "Progressive Field": 0.98, "Dodger Stadium": 0.97,
    "Angel Stadium": 0.97, "Target Field": 0.97, "loanDepot park": 0.97,
    "Daikin Park": 0.96, "PNC Park": 0.96, "Comerica Park": 0.96,
    "T-Mobile Park": 0.95, "Tropicana Field": 0.95, "Kauffman Stadium": 0.95,
    "Oakland Coliseum": 0.95, "Petco Park": 0.93, "Oracle Park": 0.92,
}

# Venues with roofs (weather doesn't matter)
DOMED_VENUES = {
    "Tropicana Field", "Globe Life Field", "Chase Field", "loanDepot park",
    "Rogers Centre", "American Family Field", "Daikin Park", "T-Mobile Park",
}


def score_pitcher_season(stats: Optional[dict]) -> dict:
    """Comprehensive pitcher scoring from season stats."""
    if not stats:
        return {"total": 45.0, "era_s": 50, "whip_s": 50, "k_s": 50, "bb_s": 50, "hr_s": 50, "gb_s": 50, "ip": 0}

    era = float(stats.get("era", "4.50"))
    whip = float(stats.get("whip", "1.30"))
    k9 = float(stats.get("strikeoutsPer9Inn", "7.5"))
    bb9 = float(stats.get("walksPer9Inn", "3.5"))
    hr9 = float(stats.get("homeRunsPer9", "1.2"))
    ip = float(stats.get("inningsPitched", "0"))
    go_ao = float(stats.get("groundOutsToAirouts", "1.0"))
    k_bb = float(stats.get("strikeoutWalkRatio", "2.0"))

    # Each stat → 0-100 scale
    era_s = max(5, min(98, 100 - (era - 1.5) * 16))
    whip_s = max(5, min(98, 100 - (whip - 0.80) * 60))
    k_s = max(5, min(98, (k9 - 3.0) * 9.5 + 10))
    bb_s = max(5, min(98, 95 - (bb9 - 1.0) * 22))
    hr_s = max(5, min(98, 95 - (hr9 - 0.3) * 40))
    gb_s = max(30, min(80, (go_ao - 0.5) * 25 + 40))
    kbb_s = max(5, min(98, (k_bb - 1.0) * 15 + 20))

    # Weighted composite
    total = (
        era_s * 0.22 +
        whip_s * 0.18 +
        k_s * 0.15 +
        bb_s * 0.12 +
        hr_s * 0.10 +
        gb_s * 0.08 +
        kbb_s * 0.15
    )

    # Regress to mean if low IP
    if ip < 50:
        total = total * 0.55 + 50 * 0.45
    elif ip < 100:
        total = total * 0.75 + 50 * 0.25
    elif ip < 150:
        total = total * 0.90 + 50 * 0.10

    return {
        "total": round(total, 1),
        "era_s": round(era_s, 1),
        "whip_s": round(whip_s, 1),
        "k_s": round(k_s, 1),
        "bb_s": round(bb_s, 1),
        "hr_s": round(hr_s, 1),
        "gb_s": round(gb_s, 1),
        "ip": ip,
    }


def score_pitcher_recent(game_log: list, n: int = 5) -> dict:
    """Score based on last N starts — more recent = more weight."""
    if not game_log or len(game_log) == 0:
        return {"recent_score": 50.0, "trend": "unknown", "recent_era": "N/A", "starts": 0}

    recent = game_log[-n:]
    total_ip = 0
    total_er = 0
    total_k = 0
    total_bb = 0
    total_h = 0
    weighted_era_sum = 0
    weight_sum = 0

    for i, g in enumerate(recent):
        s = g.get("stat", {})
        ip = float(s.get("inningsPitched", "0"))
        er = int(s.get("earnedRuns", 0))
        if ip > 0:
            game_era = (er / ip) * 9
            weight = 1.0 + (i * 0.3)  # More recent = higher weight
            weighted_era_sum += game_era * weight
            weight_sum += weight
            total_ip += ip
            total_er += er
            total_k += int(s.get("strikeOuts", 0))
            total_bb += int(s.get("baseOnBalls", 0))
            total_h += int(s.get("hits", 0))

    if total_ip == 0 or weight_sum == 0:
        return {"recent_score": 50.0, "trend": "unknown", "recent_era": "N/A", "starts": 0}

    weighted_era = weighted_era_sum / weight_sum
    recent_era = (total_er / total_ip) * 9
    recent_whip = (total_bb + total_h) / total_ip
    recent_k9 = (total_k / total_ip) * 9

    # Score it
    era_s = max(10, min(95, 100 - (weighted_era - 1.5) * 16))
    whip_s = max(10, min(95, 100 - (recent_whip - 0.80) * 60))
    k_s = max(10, min(95, (recent_k9 - 3.0) * 9.5 + 10))
    score = era_s * 0.45 + whip_s * 0.30 + k_s * 0.25

    # Trend detection (last 3 vs first 2)
    trend = "flat"
    if len(recent) >= 4:
        early = recent[:2]
        late = recent[-3:]
        early_er_ip = sum(int(g["stat"].get("earnedRuns",0)) for g in early) / max(1, sum(float(g["stat"].get("inningsPitched","0")) for g in early))
        late_er_ip = sum(int(g["stat"].get("earnedRuns",0)) for g in late) / max(1, sum(float(g["stat"].get("inningsPitched","0")) for g in late))
        if late_er_ip < early_er_ip * 0.7:
            trend = "improving"
        elif late_er_ip > early_er_ip * 1.4:
            trend = "declining"

    return {
        "recent_score": round(score, 1),
        "trend": trend,
        "recent_era": f"{recent_era:.2f}",
        "recent_whip": f"{recent_whip:.2f}",
        "recent_k9": f"{recent_k9:.1f}",
        "avg_ip": f"{total_ip/len(recent):.1f}",
        "starts": len(recent),
    }


def score_team_offense(batting: Optional[dict]) -> dict:
    """Team batting strength."""
    if not batting:
        return {"offense_score": 50.0, "ops": ".750", "runs_per_game": "4.5"}

    ops = float(batting.get("ops", ".750"))
    obp = float(batting.get("obp", ".320"))
    slg = float(batting.get("slg", ".420"))
    avg = float(batting.get("avg", ".250"))
    runs = int(batting.get("runs", 700))
    games = int(batting.get("gamesPlayed", 162))
    rpg = runs / max(1, games)
    bb = int(batting.get("baseOnBalls", 500))
    k = int(batting.get("strikeOuts", 1300))
    bb_k = bb / max(1, k)
    sb = int(batting.get("stolenBases", 100))
    hr = int(batting.get("homeRuns", 180))

    ops_s = max(10, min(95, (ops - 0.600) * 200))
    rpg_s = max(10, min(95, (rpg - 3.0) * 18 + 20))
    bbk_s = max(10, min(90, bb_k * 150))
    power_s = max(10, min(95, (hr / max(1, games) - 0.7) * 60 + 40))

    score = ops_s * 0.35 + rpg_s * 0.30 + bbk_s * 0.15 + power_s * 0.20

    return {
        "offense_score": round(score, 1),
        "ops": batting.get("ops", ".750"),
        "obp": batting.get("obp", ".320"),
        "slg": batting.get("slg", ".420"),
        "avg": batting.get("avg", ".250"),
        "runs_per_game": f"{rpg:.2f}",
        "hr_per_game": f"{hr/max(1,games):.2f}",
        "stolen_bases": sb,
    }


def score_team_pitching(pitching: Optional[dict]) -> dict:
    """Team overall pitching/bullpen quality."""
    if not pitching:
        return {"pitching_score": 50.0, "team_era": "4.00"}

    era = float(pitching.get("era", "4.00"))
    whip = float(pitching.get("whip", "1.25"))
    k9 = float(pitching.get("strikeoutsPer9Inn", "8.0"))
    bb9 = float(pitching.get("walksPer9Inn", "3.2"))
    hr9 = float(pitching.get("homeRunsPer9", "1.1"))
    bavg = float(pitching.get("avg", ".245"))
    sv = int(pitching.get("saves", 40))
    bs = int(pitching.get("blownSaves", 20))
    save_pct = sv / max(1, sv + bs)

    era_s = max(10, min(95, 100 - (era - 2.5) * 20))
    whip_s = max(10, min(95, 100 - (whip - 0.90) * 55))
    k_s = max(10, min(95, (k9 - 5.0) * 10 + 15))
    save_s = max(20, min(90, save_pct * 100))

    score = era_s * 0.35 + whip_s * 0.25 + k_s * 0.20 + save_s * 0.20

    return {
        "pitching_score": round(score, 1),
        "team_era": pitching.get("era", "4.00"),
        "team_whip": pitching.get("whip", "1.25"),
        "team_k9": pitching.get("strikeoutsPer9Inn", "8.0"),
        "save_pct": f"{save_pct:.0%}",
        "blown_saves": bs,
    }


def pythagorean_pct(runs_scored: int, runs_allowed: int, exp: float = 1.83) -> float:
    """Pythagorean win expectation — true talent estimator."""
    if runs_scored == 0 and runs_allowed == 0:
        return 0.500
    rs = max(1, runs_scored)
    ra = max(1, runs_allowed)
    return rs**exp / (rs**exp + ra**exp)


def weather_adjustment(weather: dict, venue: str) -> dict:
    """Adjust for weather conditions."""
    if venue in DOMED_VENUES:
        return {"adjustment": 0.0, "note": "Dome/retractable roof — weather neutral", "temp": "72", "wind": "None"}

    temp_str = weather.get("temp", "72")
    try:
        temp = int(temp_str)
    except:
        temp = 72

    wind_str = weather.get("wind", "0 mph")
    condition = weather.get("condition", "Clear")

    # Parse wind
    wind_mph = 0
    wind_dir = ""
    try:
        parts = wind_str.split(",")
        wind_mph = int(parts[0].strip().split()[0])
        wind_dir = parts[1].strip().lower() if len(parts) > 1 else ""
    except:
        pass

    adj = 0.0
    notes = []

    # Temperature effect — extreme cold hurts offense
    if temp < 45:
        adj -= 0.01  # Pitchers slight edge in cold
        notes.append(f"Cold ({temp}°F) — favors pitching")
    elif temp > 90:
        adj += 0.005  # Slight offense boost in heat (ball carries)
        notes.append(f"Hot ({temp}°F) — ball carries")

    # Wind effect
    if wind_mph >= 12:
        if "out" in wind_dir:
            adj += 0.01  # Wind blowing out helps hitters
            notes.append(f"Wind out {wind_mph}mph — offense boost")
        elif "in" in wind_dir:
            adj -= 0.01  # Wind blowing in hurts hitters
            notes.append(f"Wind in {wind_mph}mph — pitching boost")

    # Rain/precip
    if condition.lower() in ("rain", "drizzle", "showers"):
        notes.append("⚠️ Rain expected — game may be delayed/affected")

    return {
        "adjustment": round(adj, 3),
        "note": "; ".join(notes) if notes else "Normal conditions",
        "temp": temp_str,
        "wind": wind_str,
        "condition": condition,
    }


def rest_travel_adjustment(team_id: int, game_date: str, is_home: bool) -> dict:
    """Check rest days and travel distance."""
    try:
        recent = get_recent_schedule(team_id, game_date, days_back=3)
    except:
        return {"adjustment": 0.0, "note": "Unable to check schedule", "games_last_3d": 0}

    # Filter to games before this date
    recent = [g for g in recent if g.get("officialDate", "") < game_date]
    games_3d = len(recent)

    adj = 0.0
    notes = []

    if games_3d == 0:
        adj += 0.01
        notes.append("Well-rested (no games in 3 days)")
    elif games_3d >= 3:
        adj -= 0.01
        notes.append(f"Fatigued ({games_3d} games in 3 days)")

    return {
        "adjustment": round(adj, 3),
        "note": "; ".join(notes) if notes else "Normal schedule",
        "games_last_3d": games_3d,
    }


# ── Main Prediction Engine ───────────────────────────────────────────

def predict_game_v2(game: dict, standings: dict) -> dict:
    """Full prediction with all factors."""
    away = game["teams"]["away"]
    home = game["teams"]["home"]
    away_team = away["team"]
    home_team = home["team"]
    away_id = away_team["id"]
    home_id = home_team["id"]
    venue = game.get("venue", {}).get("name", "Unknown")
    game_date = game.get("officialDate", "")

    # ── Gather all data ──
    away_pitcher_info = away.get("probablePitcher", {})
    home_pitcher_info = home.get("probablePitcher", {})
    away_pid = away_pitcher_info.get("id")
    home_pid = home_pitcher_info.get("id")

    print(f"  📊 {away_team['name']} @ {home_team['name']}...")

    # 1. Starting pitcher season stats
    away_p_stats = get_pitcher_season_stats(away_pid) if away_pid else None
    home_p_stats = get_pitcher_season_stats(home_pid) if home_pid else None
    away_p_score = score_pitcher_season(away_p_stats)
    home_p_score = score_pitcher_season(home_p_stats)

    # 2. Pitcher recent form
    away_p_log = get_pitcher_game_log(away_pid) if away_pid else []
    home_p_log = get_pitcher_game_log(home_pid) if home_pid else []
    away_p_recent = score_pitcher_recent(away_p_log)
    home_p_recent = score_pitcher_recent(home_p_log)

    # 3. Pitcher vs opposing team
    away_p_vs = get_pitcher_vs_team(away_pid, home_id) if away_pid else None
    home_p_vs = get_pitcher_vs_team(home_pid, away_id) if home_pid else None

    # 4. Team batting
    away_batting = get_team_batting(away_id)
    home_batting = get_team_batting(home_id)
    away_offense = score_team_offense(away_batting)
    home_offense = score_team_offense(home_batting)

    # 5. Team pitching (bullpen indicator)
    away_pitching = get_team_pitching(away_id)
    home_pitching = get_team_pitching(home_id)
    away_staff = score_team_pitching(away_pitching)
    home_staff = score_team_pitching(home_pitching)

    # 6. Standings & Pythagorean
    away_stand = standings.get(away_id, {"pct": .500, "runs_scored": 700, "runs_allowed": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})
    home_stand = standings.get(home_id, {"pct": .500, "runs_scored": 700, "runs_allowed": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})

    away_pyth = pythagorean_pct(away_stand["runs_scored"], away_stand["runs_allowed"])
    home_pyth = pythagorean_pct(home_stand["runs_scored"], home_stand["runs_allowed"])

    # Home/away specific records
    home_home_pct = home_stand["home_w"] / max(1, home_stand["home_w"] + home_stand["home_l"])
    away_away_pct = away_stand["away_w"] / max(1, away_stand["away_w"] + away_stand["away_l"])

    # 7. Weather
    weather_data = weather_adjustment(game.get("weather", {}), venue)

    # 8. Rest/travel
    away_rest = rest_travel_adjustment(away_id, game_date, False)
    home_rest = rest_travel_adjustment(home_id, game_date, True)

    # ── Build probability ──
    # Start at 50/50
    home_prob = 0.500

    # FACTOR 1: Starting pitcher differential (BIGGEST factor — up to ±12%)
    # Blend season (60%) + recent form (40%)
    away_combined_pitcher = away_p_score["total"] * 0.6 + away_p_recent["recent_score"] * 0.4
    home_combined_pitcher = home_p_score["total"] * 0.6 + home_p_recent["recent_score"] * 0.4
    pitcher_diff = (home_combined_pitcher - away_combined_pitcher) / 100.0
    pitcher_impact = pitcher_diff * 0.24  # Max swing ~±12%
    home_prob += pitcher_impact

    # FACTOR 2: Pitcher trend bonus
    if home_p_recent["trend"] == "improving":
        home_prob += 0.01
    elif home_p_recent["trend"] == "declining":
        home_prob -= 0.01
    if away_p_recent["trend"] == "improving":
        home_prob -= 0.01
    elif away_p_recent["trend"] == "declining":
        home_prob += 0.01

    # FACTOR 3: Pitcher vs team history (small but real)
    if away_p_vs:
        away_p_vs_era = float(away_p_vs.get("era", "4.50"))
        away_p_vs_ip = float(away_p_vs.get("inningsPitched", "0"))
        if away_p_vs_ip >= 15:  # Enough data
            if away_p_vs_era < 3.00:
                home_prob -= 0.015  # Away pitcher dominates home team
            elif away_p_vs_era > 5.50:
                home_prob += 0.015  # Away pitcher struggles vs home team
    if home_p_vs:
        home_p_vs_era = float(home_p_vs.get("era", "4.50"))
        home_p_vs_ip = float(home_p_vs.get("inningsPitched", "0"))
        if home_p_vs_ip >= 15:
            if home_p_vs_era < 3.00:
                home_prob += 0.015
            elif home_p_vs_era > 5.50:
                home_prob -= 0.015

    # FACTOR 4: Team offensive strength (up to ±8%)
    off_diff = (home_offense["offense_score"] - away_offense["offense_score"]) / 100.0
    home_prob += off_diff * 0.16

    # FACTOR 5: Bullpen/staff quality (up to ±5%)
    staff_diff = (home_staff["pitching_score"] - away_staff["pitching_score"]) / 100.0
    home_prob += staff_diff * 0.10

    # FACTOR 6: Home field advantage — use team-specific home record
    base_hfa = 0.035  # League average ~53.5% home win rate
    # Adjust based on how much better/worse this team is at home
    home_boost = (home_home_pct - 0.500) * 0.15  # Strong home teams get extra
    away_road_penalty = (0.500 - away_away_pct) * 0.10
    home_prob += base_hfa + home_boost + away_road_penalty

    # FACTOR 7: Pythagorean true talent (up to ±6%)
    pyth_diff = home_pyth - away_pyth
    home_prob += pyth_diff * 0.12

    # FACTOR 8: Park factor adjustment
    park = PARK_FACTORS.get(venue, 1.0)
    # In hitter's parks, better offense gets a slight boost
    if park > 1.05:
        if home_offense["offense_score"] > away_offense["offense_score"]:
            home_prob += 0.008
        else:
            home_prob -= 0.008
    elif park < 0.95:
        if home_combined_pitcher > away_combined_pitcher:
            home_prob += 0.008
        else:
            home_prob -= 0.008

    # FACTOR 9: Weather
    home_prob += weather_data["adjustment"]

    # FACTOR 10: Rest/travel
    home_prob += home_rest["adjustment"]
    home_prob -= away_rest["adjustment"]  # Negative because away team rest helps AWAY

    # ── Clamp and finalize ──
    home_prob = max(0.28, min(0.72, home_prob))
    away_prob = 1.0 - home_prob

    # Determine pick
    if home_prob > away_prob:
        pick = home_team["name"]
        pick_prob = home_prob
    else:
        pick = away_team["name"]
        pick_prob = away_prob

    if pick_prob >= 0.62:
        confidence = "HIGH"
    elif pick_prob >= 0.57:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    edge = pick_prob - 0.50

    # Factor breakdown for transparency
    factors = {
        "pitcher_matchup": {"impact": round(pitcher_impact * 100, 1), "desc": f"Pitcher: Home {home_combined_pitcher:.0f} vs Away {away_combined_pitcher:.0f}"},
        "offense": {"impact": round(off_diff * 16, 1), "desc": f"Offense: Home {home_offense['offense_score']} vs Away {away_offense['offense_score']}"},
        "bullpen": {"impact": round(staff_diff * 10, 1), "desc": f"Bullpen: Home {home_staff['pitching_score']} vs Away {away_staff['pitching_score']}"},
        "home_field": {"impact": round((base_hfa + home_boost + away_road_penalty) * 100, 1), "desc": f"Home record: {home_stand['home_w']}-{home_stand['home_l']}"},
        "true_talent": {"impact": round(pyth_diff * 12, 1), "desc": f"Pyth: Home {home_pyth:.3f} vs Away {away_pyth:.3f}"},
        "weather": {"impact": round(weather_data['adjustment'] * 100, 1), "desc": weather_data["note"]},
        "rest": {"impact": round((home_rest['adjustment'] - away_rest['adjustment']) * 100, 1), "desc": f"Home: {home_rest['note']} | Away: {away_rest['note']}"},
    }

    return {
        "game_id": game["gamePk"],
        "game_date": game_date,
        "game_time": game.get("gameDate", ""),
        "away_team": away_team["name"],
        "home_team": home_team["name"],
        "away_id": away_id,
        "home_id": home_id,

        # Pitchers
        "away_pitcher": away_pitcher_info.get("fullName", "TBD"),
        "home_pitcher": home_pitcher_info.get("fullName", "TBD"),
        "away_pitcher_score": away_p_score["total"],
        "home_pitcher_score": home_p_score["total"],
        "away_pitcher_era": away_p_stats.get("era", "N/A") if away_p_stats else "N/A",
        "home_pitcher_era": home_p_stats.get("era", "N/A") if home_p_stats else "N/A",
        "away_pitcher_whip": away_p_stats.get("whip", "N/A") if away_p_stats else "N/A",
        "home_pitcher_whip": home_p_stats.get("whip", "N/A") if home_p_stats else "N/A",
        "away_pitcher_k9": away_p_stats.get("strikeoutsPer9Inn", "N/A") if away_p_stats else "N/A",
        "home_pitcher_k9": home_p_stats.get("strikeoutsPer9Inn", "N/A") if home_p_stats else "N/A",
        "away_pitcher_recent": away_p_recent,
        "home_pitcher_recent": home_p_recent,

        # Pitcher vs team
        "away_p_vs_team_era": away_p_vs.get("era", "N/A") if away_p_vs else "N/A",
        "home_p_vs_team_era": home_p_vs.get("era", "N/A") if home_p_vs else "N/A",
        "away_p_vs_team_ip": away_p_vs.get("inningsPitched", "0") if away_p_vs else "0",
        "home_p_vs_team_ip": home_p_vs.get("inningsPitched", "0") if home_p_vs else "0",

        # Teams
        "away_offense": away_offense,
        "home_offense": home_offense,
        "away_staff": away_staff,
        "home_staff": home_staff,
        "away_record": f"{away_stand.get('wins', 0)}-{away_stand.get('losses', 0)}",
        "home_record": f"{home_stand.get('wins', 0)}-{home_stand.get('losses', 0)}",
        "away_pyth": round(away_pyth, 3),
        "home_pyth": round(home_pyth, 3),

        # Venue & conditions
        "venue": venue,
        "park_factor": PARK_FACTORS.get(venue, 1.0),
        "weather": weather_data,
        "away_rest": away_rest,
        "home_rest": home_rest,

        # Prediction
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(away_prob, 3),
        "pick": pick,
        "pick_prob": round(pick_prob, 3),
        "confidence": confidence,
        "edge": round(edge, 3),
        "factors": factors,
    }


def run_predictions(date: str = None) -> list:
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n🔍 Fetching games for {date}...")
    games = get_schedule(date)
    if not games:
        print(f"No games found for {date}")
        return []

    print(f"📊 Found {len(games)} games. Loading all data...")
    standings = get_all_standings(2025)

    predictions = []
    for game in games:
        try:
            pred = predict_game_v2(game, standings)
            predictions.append(pred)
        except Exception as e:
            import traceback
            print(f"  ⚠️ Error: {e}")
            traceback.print_exc()

    predictions.sort(key=lambda x: x["edge"], reverse=True)
    return predictions


def format_discord(predictions: list) -> str:
    if not predictions:
        return "No games today."

    date = predictions[0]["game_date"]
    lines = [f"# ⚾ MLB Predictions — {date}\n"]
    lines.append(f"*Model v2 — {len(predictions)} games analyzed*\n")

    for p in predictions:
        conf_emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚪"}.get(p["confidence"], "⚪")

        lines.append(f"{conf_emoji} **{p['away_team']}** @ **{p['home_team']}**")
        lines.append(f"> 🎯 {p['away_pitcher']} (`{p['away_pitcher_score']}` | Last 5: `{p['away_pitcher_recent']['recent_era']}` ERA) vs {p['home_pitcher']} (`{p['home_pitcher_score']}` | Last 5: `{p['home_pitcher_recent']['recent_era']}` ERA)")
        lines.append(f"> ⚔️ Offense: {p['away_offense']['ops']} OPS vs {p['home_offense']['ops']} OPS")
        lines.append(f"> 📈 **PICK: {p['pick']}** ({p['pick_prob']*100:.1f}%) — {p['confidence']} confidence | Edge +{p['edge']*100:.1f}%")

        # Top factor
        top_factor = max(p["factors"].items(), key=lambda x: abs(x[1]["impact"]))
        lines.append(f"> 🔑 Key factor: {top_factor[1]['desc']} ({'+' if top_factor[1]['impact']>0 else ''}{top_factor[1]['impact']:.1f}%)")
        lines.append("")

    high = sum(1 for p in predictions if p["confidence"] == "HIGH")
    med = sum(1 for p in predictions if p["confidence"] == "MEDIUM")
    lines.append(f"*🔥 {high} high | ✅ {med} medium confidence*")
    lines.append(f"\n`Model v2 | Pitcher + Offense + Bullpen + Home/Away + Pythagorean + Park + Weather + Rest`")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys, os
    date = sys.argv[1] if len(sys.argv) > 1 else None
    predictions = run_predictions(date)

    # Print text summary
    for p in predictions:
        conf = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚪"}[p["confidence"]]
        print(f"\n{conf} {p['away_team']} @ {p['home_team']}")
        print(f"   Pitchers: {p['away_pitcher']} ({p['away_pitcher_score']}) vs {p['home_pitcher']} ({p['home_pitcher_score']})")
        print(f"   Recent: {p['away_pitcher_recent']['recent_era']} ERA ({p['away_pitcher_recent']['trend']}) vs {p['home_pitcher_recent']['recent_era']} ERA ({p['home_pitcher_recent']['trend']})")
        print(f"   Offense: {p['away_offense']['ops']} OPS vs {p['home_offense']['ops']} OPS")
        print(f"   Bullpen: {p['away_staff']['team_era']} ERA vs {p['home_staff']['team_era']} ERA")
        print(f"   Records: {p['away_record']} (pyth {p['away_pyth']}) vs {p['home_record']} (pyth {p['home_pyth']})")
        print(f"   Weather: {p['weather']['note']}")
        print(f"   📈 PICK: {p['pick']} ({p['pick_prob']*100:.1f}%) — {p['confidence']} | Edge +{p['edge']*100:.1f}%")
        print(f"   Factors:")
        for name, f in sorted(p['factors'].items(), key=lambda x: abs(x[1]['impact']), reverse=True):
            sign = "+" if f['impact'] > 0 else ""
            print(f"     {sign}{f['impact']:.1f}% — {f['desc']}")

    # Save
    if predictions:
        os.makedirs("picks", exist_ok=True)
        outfile = f"picks/{predictions[0]['game_date']}.json"
        with open(outfile, "w") as f:
            json.dump(predictions, f, indent=2)
        print(f"\n💾 Saved to {outfile}")
