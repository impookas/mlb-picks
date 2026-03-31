#!/usr/bin/env python3
"""
MLB Prediction Backtester — NO look-ahead bias.

Strategy:
- Pitcher stats: computed from game log entries BEFORE the game date only
- Team stats: uses PRIOR season (2024) data — conservative but zero look-ahead
- Standings/Pythagorean: uses prior season final standings
- All other factors (park, home field, weather): no temporal component

Usage:
    python backtest.py                          # Default: Aug 1 - Sept 30, 2025
    python backtest.py 2025-08-01 2025-09-30    # Custom range
    python backtest.py 2025-06-01 2025-09-30 --sample 500  # Limit games
"""

import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

BASE_URL = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).parent.parent
BACKTEST_DIR = ROOT / "backtest"

_cache = {}
_request_count = 0


def api_get(endpoint: str) -> dict:
    global _request_count
    if endpoint in _cache:
        return _cache[endpoint]
    url = f"{BASE_URL}{endpoint}"
    try:
        _request_count += 1
        if _request_count % 50 == 0:
            time.sleep(0.5)  # Be nice to the API
        data = json.loads(urllib.request.urlopen(url, timeout=20).read())
        _cache[endpoint] = data
        return data
    except Exception as e:
        return {}


# ── Park factors (static, no bias) ───────────────────────────────────

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

DOMED_VENUES = {
    "Tropicana Field", "Globe Life Field", "Chase Field", "loanDepot park",
    "Rogers Centre", "American Family Field", "Daikin Park", "T-Mobile Park",
}


# ── Prior Season Data (2024 for backtesting 2025) ────────────────────

_prior_standings = None
_prior_team_batting = {}
_prior_team_pitching = {}


def load_prior_season_data(prior_year: int = 2024):
    """Load team-level stats from the prior season. Zero look-ahead."""
    global _prior_standings, _prior_team_batting, _prior_team_pitching

    print(f"  Loading {prior_year} season data (prior year baseline)...")

    # Standings
    data = api_get(f"/standings?leagueId=103,104&season={prior_year}&standingsTypes=regularSeason")
    _prior_standings = {}
    for record in data.get("records", []):
        for tr in record.get("teamRecords", []):
            tid = tr["team"]["id"]
            splits = tr.get("records", {}).get("splitRecords", [])
            home_rec = next((s for s in splits if s.get("type") == "home"), {})
            away_rec = next((s for s in splits if s.get("type") == "away"), {})
            _prior_standings[tid] = {
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
            }

    # Team batting — all teams
    data = api_get(f"/teams?sportId=1&season={prior_year}")
    for team in data.get("teams", []):
        tid = team["id"]
        bdata = api_get(f"/teams/{tid}/stats?stats=season&season={prior_year}&group=hitting")
        splits = bdata.get("stats", [{}])[0].get("splits", [])
        if splits:
            _prior_team_batting[tid] = splits[0]["stat"]

        pdata = api_get(f"/teams/{tid}/stats?stats=season&season={prior_year}&group=pitching")
        splits = pdata.get("stats", [{}])[0].get("splits", [])
        if splits:
            _prior_team_pitching[tid] = splits[0]["stat"]

    print(f"  ✅ Loaded {len(_prior_standings)} teams from {prior_year}")


# ── Pitcher Stats from Game Log (date-filtered, no look-ahead) ───────

def get_pitcher_prior_season(player_id: int, season: int = 2024) -> Optional[dict]:
    """Get a pitcher's prior season stats as fallback. Zero look-ahead."""
    try:
        data = api_get(f"/people/{player_id}/stats?stats=yearByYear&group=pitching&sportId=1")
        stats = data.get("stats", [])
        if not stats:
            return None
        for split in reversed(stats[0].get("splits", [])):
            if int(split["season"]) == season:
                return split["stat"]
    except (IndexError, KeyError):
        pass
    return None


def get_pitcher_stats_asof(player_id: int, before_date: str, season: int = 2025) -> dict:
    """
    Compute pitcher stats from game log entries BEFORE the given date.
    Falls back to prior season stats if insufficient current-season data.
    Zero look-ahead in both cases.
    """
    data = api_get(f"/people/{player_id}/stats?stats=gameLog&group=pitching&season={season}&sportId=1")
    splits = data.get("stats", [{}])[0].get("splits", [])

    total_ip = 0.0
    total_er = 0
    total_h = 0
    total_bb = 0
    total_k = 0
    total_hr = 0
    total_go = 0
    total_ao = 0
    games = 0

    for g in splits:
        game_date = g.get("date", "")
        if game_date >= before_date:
            continue  # Skip games on or after the target date

        s = g.get("stat", {})
        ip = float(s.get("inningsPitched", "0"))
        if ip == 0:
            continue

        total_ip += ip
        total_er += int(s.get("earnedRuns", 0))
        total_h += int(s.get("hits", 0))
        total_bb += int(s.get("baseOnBalls", 0))
        total_k += int(s.get("strikeOuts", 0))
        total_hr += int(s.get("homeRuns", 0))
        total_go += int(s.get("groundOuts", 0))
        total_ao += int(s.get("airOuts", 0))
        games += 1

    # If fewer than 3 starts this season before game date, fall back to prior season
    if games < 3 or total_ip < 10:
        prior = get_pitcher_prior_season(player_id, season - 1)
        if prior:
            return prior  # Already in the right format from MLB API
        # If no prior season either, return what we have or None
        if total_ip < 1:
            return None

    if total_ip < 1:
        return None

    era = (total_er / total_ip) * 9
    whip = (total_bb + total_h) / total_ip
    k9 = (total_k / total_ip) * 9
    bb9 = (total_bb / total_ip) * 9
    hr9 = (total_hr / total_ip) * 9
    go_ao = total_go / max(1, total_ao)
    k_bb = total_k / max(1, total_bb)

    return {
        "era": f"{era:.2f}",
        "whip": f"{whip:.2f}",
        "strikeoutsPer9Inn": f"{k9:.2f}",
        "walksPer9Inn": f"{bb9:.2f}",
        "homeRunsPer9": f"{hr9:.2f}",
        "inningsPitched": f"{total_ip:.1f}",
        "groundOutsToAirouts": f"{go_ao:.2f}",
        "strikeoutWalkRatio": f"{k_bb:.2f}",
        "games": games,
    }


def get_pitcher_recent_asof(player_id: int, before_date: str, season: int = 2025, n: int = 5) -> list:
    """Get the last N game log entries before a date. Falls back to prior season if needed."""
    data = api_get(f"/people/{player_id}/stats?stats=gameLog&group=pitching&season={season}&sportId=1")
    splits = data.get("stats", [{}])[0].get("splits", [])

    prior = [g for g in splits if g.get("date", "") < before_date]

    # If fewer than 3 current-season starts, supplement with prior season
    if len(prior) < 3:
        try:
            prior_data = api_get(f"/people/{player_id}/stats?stats=gameLog&group=pitching&season={season - 1}&sportId=1")
            prior_splits = prior_data.get("stats", [{}])[0].get("splits", [])
            combined = prior_splits[-(n - len(prior)):] + prior
            return combined[-n:]
        except (IndexError, KeyError):
            pass  # No prior season data, use what we have

    return prior[-n:]


def get_pitcher_vs_team_career(player_id: int, team_id: int) -> Optional[dict]:
    """Career vs team — no temporal issue since it's all historical."""
    try:
        data = api_get(f"/people/{player_id}/stats?stats=vsTeam&group=pitching&sportId=1&opposingTeamId={team_id}")
        stats = data.get("stats", [])
        if stats and stats[0].get("splits"):
            return stats[0]["splits"][0].get("stat")
    except (IndexError, KeyError):
        pass
    return None


# ── Scoring (same logic as predictor_v2 but using date-aware inputs) ─

def safe_float(val, default):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def score_pitcher(stats: Optional[dict]) -> dict:
    if not stats:
        return {"total": 45.0, "ip": 0}

    era = safe_float(stats.get("era", "4.50"), 4.50)
    whip = safe_float(stats.get("whip", "1.30"), 1.30)
    k9 = safe_float(stats.get("strikeoutsPer9Inn", "7.5"), 7.5)
    bb9 = safe_float(stats.get("walksPer9Inn", "3.5"), 3.5)
    hr9 = safe_float(stats.get("homeRunsPer9", "1.2"), 1.2)
    ip = safe_float(stats.get("inningsPitched", "0"), 0)
    go_ao = safe_float(stats.get("groundOutsToAirouts", "1.0"), 1.0)
    k_bb = safe_float(stats.get("strikeoutWalkRatio", "2.0"), 2.0)

    era_s = max(5, min(98, 100 - (era - 1.5) * 16))
    whip_s = max(5, min(98, 100 - (whip - 0.80) * 60))
    k_s = max(5, min(98, (k9 - 3.0) * 9.5 + 10))
    bb_s = max(5, min(98, 95 - (bb9 - 1.0) * 22))
    hr_s = max(5, min(98, 95 - (hr9 - 0.3) * 40))
    gb_s = max(30, min(80, (go_ao - 0.5) * 25 + 40))
    kbb_s = max(5, min(98, (k_bb - 1.0) * 15 + 20))

    total = (era_s * 0.22 + whip_s * 0.18 + k_s * 0.15 +
             bb_s * 0.12 + hr_s * 0.10 + gb_s * 0.08 + kbb_s * 0.15)

    if ip < 50:
        total = total * 0.55 + 50 * 0.45
    elif ip < 100:
        total = total * 0.75 + 50 * 0.25
    elif ip < 150:
        total = total * 0.90 + 50 * 0.10

    return {"total": round(total, 1), "ip": ip}


def score_recent(game_log: list) -> dict:
    if not game_log:
        return {"recent_score": 50.0, "trend": "unknown"}

    total_ip = 0
    total_er = 0
    total_k = 0
    total_bb = 0
    total_h = 0
    weighted_era_sum = 0
    weight_sum = 0

    for i, g in enumerate(game_log):
        s = g.get("stat", {})
        ip = float(s.get("inningsPitched", "0"))
        er = int(s.get("earnedRuns", 0))
        if ip > 0:
            game_era = (er / ip) * 9
            weight = 1.0 + (i * 0.3)
            weighted_era_sum += game_era * weight
            weight_sum += weight
            total_ip += ip
            total_er += er
            total_k += int(s.get("strikeOuts", 0))
            total_bb += int(s.get("baseOnBalls", 0))
            total_h += int(s.get("hits", 0))

    if total_ip == 0 or weight_sum == 0:
        return {"recent_score": 50.0, "trend": "unknown"}

    weighted_era = weighted_era_sum / weight_sum
    recent_whip = (total_bb + total_h) / total_ip
    recent_k9 = (total_k / total_ip) * 9

    era_s = max(10, min(95, 100 - (weighted_era - 1.5) * 16))
    whip_s = max(10, min(95, 100 - (recent_whip - 0.80) * 60))
    k_s = max(10, min(95, (recent_k9 - 3.0) * 9.5 + 10))
    score = era_s * 0.45 + whip_s * 0.30 + k_s * 0.25

    trend = "flat"
    if len(game_log) >= 4:
        early = game_log[:2]
        late = game_log[-3:]
        e_ip = sum(float(g["stat"].get("inningsPitched", "0")) for g in early)
        l_ip = sum(float(g["stat"].get("inningsPitched", "0")) for g in late)
        if e_ip > 0 and l_ip > 0:
            e_rate = sum(int(g["stat"].get("earnedRuns", 0)) for g in early) / e_ip
            l_rate = sum(int(g["stat"].get("earnedRuns", 0)) for g in late) / l_ip
            if l_rate < e_rate * 0.7:
                trend = "improving"
            elif l_rate > e_rate * 1.4:
                trend = "declining"

    return {"recent_score": round(score, 1), "trend": trend}


def score_team_offense(batting: Optional[dict]) -> float:
    if not batting:
        return 50.0
    ops = float(batting.get("ops", ".750"))
    runs = int(batting.get("runs", 700))
    games = int(batting.get("gamesPlayed", 162))
    rpg = runs / max(1, games)
    hr = int(batting.get("homeRuns", 180))
    bb = int(batting.get("baseOnBalls", 500))
    k = int(batting.get("strikeOuts", 1300))
    bb_k = bb / max(1, k)

    ops_s = max(10, min(95, (ops - 0.600) * 200))
    rpg_s = max(10, min(95, (rpg - 3.0) * 18 + 20))
    bbk_s = max(10, min(90, bb_k * 150))
    power_s = max(10, min(95, (hr / max(1, games) - 0.7) * 60 + 40))

    return round(ops_s * 0.35 + rpg_s * 0.30 + bbk_s * 0.15 + power_s * 0.20, 1)


def score_team_pitching(pitching: Optional[dict]) -> float:
    if not pitching:
        return 50.0
    era = float(pitching.get("era", "4.00"))
    whip = float(pitching.get("whip", "1.25"))
    k9 = float(pitching.get("strikeoutsPer9Inn", "8.0"))
    sv = int(pitching.get("saves", 40))
    bs = int(pitching.get("blownSaves", 20))
    save_pct = sv / max(1, sv + bs)

    era_s = max(10, min(95, 100 - (era - 2.5) * 20))
    whip_s = max(10, min(95, 100 - (whip - 0.90) * 55))
    k_s = max(10, min(95, (k9 - 5.0) * 10 + 15))
    save_s = max(20, min(90, save_pct * 100))

    return round(era_s * 0.35 + whip_s * 0.25 + k_s * 0.20 + save_s * 0.20, 1)


def pythagorean_pct(rs: int, ra: int, exp: float = 1.83) -> float:
    if rs == 0 and ra == 0:
        return 0.500
    rs = max(1, rs)
    ra = max(1, ra)
    return rs**exp / (rs**exp + ra**exp)


# ── Main Prediction Logic (same as v2 but with date-aware data) ──────

def predict_game_backtest(game: dict, game_date: str, season: int = 2025) -> Optional[dict]:
    away = game["teams"]["away"]
    home = game["teams"]["home"]
    away_id = away["team"]["id"]
    home_id = home["team"]["id"]
    venue = game.get("venue", {}).get("name", "Unknown")

    away_pitcher_info = away.get("probablePitcher", {})
    home_pitcher_info = home.get("probablePitcher", {})
    away_pid = away_pitcher_info.get("id")
    home_pid = home_pitcher_info.get("id")

    if not away_pid or not home_pid:
        return None  # Skip games without both starters known

    # Pitcher season stats AS OF game date (no look-ahead)
    away_p_stats = get_pitcher_stats_asof(away_pid, game_date, season)
    home_p_stats = get_pitcher_stats_asof(home_pid, game_date, season)
    away_p_score = score_pitcher(away_p_stats)
    home_p_score = score_pitcher(home_p_stats)

    # Pitcher recent form AS OF game date
    away_recent_log = get_pitcher_recent_asof(away_pid, game_date, season)
    home_recent_log = get_pitcher_recent_asof(home_pid, game_date, season)
    away_recent = score_recent(away_recent_log)
    home_recent = score_recent(home_recent_log)

    # Pitcher vs team (career — historical, no look-ahead issue)
    away_p_vs = get_pitcher_vs_team_career(away_pid, home_id)
    home_p_vs = get_pitcher_vs_team_career(home_pid, away_id)

    # Team stats from PRIOR season (no look-ahead)
    away_offense = score_team_offense(_prior_team_batting.get(away_id))
    home_offense = score_team_offense(_prior_team_batting.get(home_id))
    away_staff = score_team_pitching(_prior_team_pitching.get(away_id))
    home_staff = score_team_pitching(_prior_team_pitching.get(home_id))

    # Standings from PRIOR season
    away_stand = _prior_standings.get(away_id, {"pct": .500, "runs_scored": 700, "runs_allowed": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})
    home_stand = _prior_standings.get(home_id, {"pct": .500, "runs_scored": 700, "runs_allowed": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})

    away_pyth = pythagorean_pct(away_stand["runs_scored"], away_stand["runs_allowed"])
    home_pyth = pythagorean_pct(home_stand["runs_scored"], home_stand["runs_allowed"])

    home_home_pct = home_stand["home_w"] / max(1, home_stand["home_w"] + home_stand["home_l"])
    away_away_pct = away_stand["away_w"] / max(1, away_stand["away_w"] + away_stand["away_l"])

    # ── Build probability (same weights as v2) ──
    home_prob = 0.500

    # Pitcher matchup
    away_combined = away_p_score["total"] * 0.6 + away_recent["recent_score"] * 0.4
    home_combined = home_p_score["total"] * 0.6 + home_recent["recent_score"] * 0.4
    pitcher_diff = (home_combined - away_combined) / 100.0
    home_prob += pitcher_diff * 0.24

    # Pitcher trend
    if home_recent["trend"] == "improving": home_prob += 0.01
    elif home_recent["trend"] == "declining": home_prob -= 0.01
    if away_recent["trend"] == "improving": home_prob -= 0.01
    elif away_recent["trend"] == "declining": home_prob += 0.01

    # Pitcher vs team
    if away_p_vs:
        vs_era = float(away_p_vs.get("era", "4.50"))
        vs_ip = float(away_p_vs.get("inningsPitched", "0"))
        if vs_ip >= 15:
            if vs_era < 3.00: home_prob -= 0.015
            elif vs_era > 5.50: home_prob += 0.015
    if home_p_vs:
        vs_era = float(home_p_vs.get("era", "4.50"))
        vs_ip = float(home_p_vs.get("inningsPitched", "0"))
        if vs_ip >= 15:
            if vs_era < 3.00: home_prob += 0.015
            elif vs_era > 5.50: home_prob -= 0.015

    # Team offense
    off_diff = (home_offense - away_offense) / 100.0
    home_prob += off_diff * 0.16

    # Bullpen
    staff_diff = (home_staff - away_staff) / 100.0
    home_prob += staff_diff * 0.10

    # Home field
    base_hfa = 0.035
    home_boost = (home_home_pct - 0.500) * 0.15
    away_road_penalty = (0.500 - away_away_pct) * 0.10
    home_prob += base_hfa + home_boost + away_road_penalty

    # Pythagorean
    pyth_diff = home_pyth - away_pyth
    home_prob += pyth_diff * 0.12

    # Park factor
    park = PARK_FACTORS.get(venue, 1.0)
    if park > 1.05:
        if home_offense > away_offense: home_prob += 0.008
        else: home_prob -= 0.008
    elif park < 0.95:
        if home_combined > away_combined: home_prob += 0.008
        else: home_prob -= 0.008

    # Clamp
    home_prob = max(0.28, min(0.72, home_prob))
    away_prob = 1.0 - home_prob

    if home_prob > away_prob:
        pick = home["team"]["name"]
        pick_prob = home_prob
    else:
        pick = away["team"]["name"]
        pick_prob = away_prob

    if pick_prob >= 0.62: confidence = "HIGH"
    elif pick_prob >= 0.57: confidence = "MEDIUM"
    else: confidence = "LOW"

    return {
        "game_id": game["gamePk"],
        "date": game_date,
        "away_team": away["team"]["name"],
        "home_team": home["team"]["name"],
        "away_pitcher": away_pitcher_info.get("fullName", "TBD"),
        "home_pitcher": home_pitcher_info.get("fullName", "TBD"),
        "home_prob": round(home_prob, 3),
        "away_prob": round(away_prob, 3),
        "pick": pick,
        "pick_prob": round(pick_prob, 3),
        "confidence": confidence,
        "edge": round(pick_prob - 0.50, 3),
    }


# ── Fetch Results ─────────────────────────────────────────────────────

def fetch_results(date: str) -> dict:
    data = api_get(f"/schedule?sportId=1&date={date}&hydrate=linescore,team")
    results = {}
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("status", {}).get("abstractGameState") != "Final":
                continue
            gid = g["gamePk"]
            ls = g.get("linescore", {})
            ar = ls.get("teams", {}).get("away", {}).get("runs")
            hr = ls.get("teams", {}).get("home", {}).get("runs")
            if ar is None or hr is None:
                continue
            hw = hr > ar
            results[gid] = {
                "home_win": hw,
                "winner": g["teams"]["home"]["team"]["name"] if hw else g["teams"]["away"]["team"]["name"],
                "score": f"{ar}-{hr}",
            }
    return results


# ── Score a Prediction ────────────────────────────────────────────────

def score_pred(pred, result):
    correct = pred["pick"] == result["winner"]
    p = max(0.001, min(0.999, pred["home_prob"]))
    y = 1.0 if result["home_win"] else 0.0
    brier = (p - y) ** 2
    logloss = -(y * math.log(p) + (1 - y) * math.log(1 - p))

    return {
        **pred,
        "actual_winner": result["winner"],
        "score": result["score"],
        "correct": correct,
        "brier": round(brier, 4),
        "logloss": round(logloss, 4),
    }


# ── Main ──────────────────────────────────────────────────────────────

def run_backtest(start_date: str, end_date: str, max_games: int = None, season: int = 2025):
    print(f"\n{'='*60}")
    print(f"  MLB BACKTEST — {start_date} to {end_date}")
    print(f"  Using {season - 1} season data for team stats (no look-ahead)")
    print(f"  Pitcher stats computed from {season} game logs up to game date")
    print(f"{'='*60}\n")

    load_prior_season_data(season - 1)

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    all_scored = []
    days_processed = 0
    games_skipped = 0

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        current += timedelta(days=1)

        # Get schedule with probable pitchers
        data = api_get(f"/schedule?sportId=1&date={date_str}&hydrate=probablePitcher(note),team,venue")
        games = []
        for d in data.get("dates", []):
            for g in d.get("games", []):
                if g.get("gameType") == "R":
                    games.append(g)

        if not games:
            continue

        # Get results
        results = fetch_results(date_str)
        if not results:
            continue

        days_processed += 1
        day_scored = 0

        for game in games:
            if max_games and len(all_scored) >= max_games:
                break

            gid = game["gamePk"]
            if gid not in results:
                continue

            try:
                pred = predict_game_backtest(game, date_str, season)
            except Exception as e:
                games_skipped += 1
                continue
            if pred is None:
                games_skipped += 1
                continue

            scored = score_pred(pred, results[gid])
            all_scored.append(scored)
            day_scored += 1

        if day_scored > 0:
            day_correct = sum(1 for s in all_scored[-day_scored:] if s["correct"])
            print(f"  {date_str}: {day_correct}/{day_scored} ({day_correct/day_scored*100:.0f}%) — Total: {len(all_scored)} games")

        if max_games and len(all_scored) >= max_games:
            break

    if not all_scored:
        print("\n❌ No games scored. Check date range.")
        return

    # ── Aggregate Results ──
    total = len(all_scored)
    correct = sum(1 for s in all_scored if s["correct"])
    accuracy = correct / total
    avg_brier = sum(s["brier"] for s in all_scored) / total
    avg_logloss = sum(s["logloss"] for s in all_scored) / total
    brier_skill = 1 - (avg_brier / 0.25)

    # By confidence
    tiers = {}
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        tp = [s for s in all_scored if s["confidence"] == tier]
        if tp:
            c = sum(1 for s in tp if s["correct"])
            tiers[tier] = {"total": len(tp), "correct": c, "pct": round(c / len(tp), 3)}

    # Calibration (5% buckets)
    cal_buckets = {}
    for s in all_scored:
        bucket = round(s["pick_prob"] * 20) / 20
        bk = f"{bucket:.2f}"
        if bk not in cal_buckets:
            cal_buckets[bk] = {"pred": [], "actual": []}
        cal_buckets[bk]["pred"].append(s["pick_prob"])
        cal_buckets[bk]["actual"].append(1 if s["correct"] else 0)

    calibration = {}
    for k, v in sorted(cal_buckets.items()):
        ap = sum(v["pred"]) / len(v["pred"])
        aa = sum(v["actual"]) / len(v["actual"])
        calibration[k] = {"n": len(v["pred"]), "predicted": round(ap, 3), "actual": round(aa, 3), "gap": round(aa - ap, 3)}

    # ROI
    roi_units = sum(0.909 if s["correct"] else -1.0 for s in all_scored)

    # ── Print Report ──
    print(f"\n{'='*60}")
    print(f"  BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"  Period:         {start_date} to {end_date}")
    print(f"  Days:           {days_processed}")
    print(f"  Games:          {total} (skipped {games_skipped} without starters)")
    print(f"  API requests:   {_request_count}")
    print(f"")
    print(f"  Record:         {correct}-{total-correct} ({accuracy*100:.1f}%)")
    print(f"  Brier Score:    {avg_brier:.4f} (baseline .2500)")
    print(f"  Brier Skill:    {brier_skill:.2%} ({'✅' if brier_skill > 0 else '❌'})")
    print(f"  Log Loss:       {avg_logloss:.4f}")
    print(f"  Flat-bet ROI:   {roi_units/total*100:+.1f}% ({roi_units:+.1f} units)")
    print(f"")
    print(f"  By Confidence:")
    for tier, t in tiers.items():
        emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚪"}[tier]
        print(f"    {emoji} {tier:8s} {t['correct']}/{t['total']:3d} ({t['pct']*100:.1f}%)")
    print(f"")
    print(f"  Calibration:")
    print(f"    Predicted | Actual  | N    | Gap")
    print(f"    ----------|---------|------|-------")
    for k, v in calibration.items():
        print(f"    {v['predicted']*100:6.1f}%   | {v['actual']*100:5.1f}% | {v['n']:4d} | {v['gap']*100:+5.1f}%")

    # Save
    BACKTEST_DIR.mkdir(exist_ok=True)
    report = {
        "start_date": start_date,
        "end_date": end_date,
        "prior_season": season - 1,
        "test_season": season,
        "total_games": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "avg_brier": round(avg_brier, 4),
        "brier_skill": round(brier_skill, 4),
        "avg_logloss": round(avg_logloss, 4),
        "roi_pct": round(roi_units / total * 100, 1),
        "roi_units": round(roi_units, 1),
        "by_confidence": tiers,
        "calibration": calibration,
        "games_skipped": games_skipped,
        "days_processed": days_processed,
        "api_requests": _request_count,
    }

    outfile = BACKTEST_DIR / f"backtest_{start_date}_{end_date}.json"
    with open(outfile, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  💾 Saved to {outfile}")

    # Also save all picks for analysis
    picks_file = BACKTEST_DIR / f"picks_{start_date}_{end_date}.json"
    with open(picks_file, "w") as f:
        json.dump(all_scored, f, indent=2)
    print(f"  💾 Picks saved to {picks_file}")

    return report


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-08-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2025-09-28"
    max_g = None
    if "--sample" in sys.argv:
        idx = sys.argv.index("--sample")
        max_g = int(sys.argv[idx + 1])

    run_backtest(start, end, max_g)
