#!/usr/bin/env python3
"""
MLB Prediction Model v3 — Learned weights from logistic regression + gradient boosting.
Uses the same feature extraction as training (zero look-ahead compatible).
Ensemble of LR + GB for final probability.
"""

import json
import math
import pickle
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_URL = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).parent.parent
MODEL_DIR = ROOT / "model" / "learned"
PICKS_DIR = ROOT / "picks"

# Need Stump class for pickle deserialization
class Stump:
    def __init__(self):
        self.feature = 0
        self.threshold = 0
        self.left_val = 0
        self.right_val = 0
    def predict_one(self, x):
        if x[self.feature] <= self.threshold:
            return self.left_val
        return self.right_val
    def predict(self, X):
        return [self.predict_one(x) for x in X]

# Load trained model
with open(MODEL_DIR / "model_config.json") as f:
    MODEL = json.load(f)

# Patch pickle to find Stump in this module
sys.modules['train'] = sys.modules[__name__]
with open(MODEL_DIR / "gb_trees.pkl", "rb") as f:
    GB_TREES = pickle.load(f)

FEATURES = MODEL["features"]
MEANS = MODEL["means"]
STDS = MODEL["stds"]
LR_WEIGHTS = MODEL["lr_weights"]
LR_BIAS = MODEL["lr_bias"]
GB_BASE = MODEL["gb_base_pred"]
GB_LR = MODEL["gb_lr"]

# Ensemble weight: LR differentiates better, GB clusters too much with stumps
LR_WEIGHT = 0.6
GB_WEIGHT = 0.4


def api_get(endpoint):
    try:
        data = json.loads(urllib.request.urlopen(f"{BASE_URL}{endpoint}", timeout=20).read())
        return data
    except:
        return {}


def safe_float(val, default):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ── Park factors ──
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


# ── Sigmoid ──
def sigmoid(z):
    z = max(-500, min(500, z))
    return 1.0 / (1.0 + math.exp(-z))


# ── Data fetchers (same as v2, live season data) ──

def get_schedule(date):
    data = api_get(f"/schedule?sportId=1&date={date}&hydrate=probablePitcher(note),team,venue")
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("gameType") == "R":
                games.append(g)
    return games


def get_pitcher_stats(pid, season=2026):
    try:
        data = api_get(f"/people/{pid}/stats?stats=yearByYear&group=pitching&sportId=1")
        for s in reversed(data.get("stats", [{}])[0].get("splits", [])):
            if int(s["season"]) == season:
                return s["stat"]
        for s in reversed(data.get("stats", [{}])[0].get("splits", [])):
            if s.get("sport", {}).get("id") == 1:
                return s["stat"]
    except:
        pass
    return None


def get_pitcher_game_log(pid, season=2026, n=5):
    try:
        data = api_get(f"/people/{pid}/stats?stats=gameLog&group=pitching&season={season}&sportId=1")
        return data.get("stats", [{}])[0].get("splits", [])[-n:]
    except:
        return []


def get_pitcher_vs_team(pid, team_id):
    try:
        data = api_get(f"/people/{pid}/stats?stats=vsTeam&group=pitching&sportId=1&opposingTeamId={team_id}")
        stats = data.get("stats", [])
        if stats and stats[0].get("splits"):
            return stats[0]["splits"][0].get("stat")
    except:
        pass
    return None


def get_team_standings(season=2026):
    try:
        data = api_get(f"/standings?leagueId=103,104&season={season}&standingsTypes=regularSeason")
        teams = {}
        for rec in data.get("records", []):
            for tr in rec.get("teamRecords", []):
                tid = tr["team"]["id"]
                splits = tr.get("records", {}).get("splitRecords", [])
                home = next((s for s in splits if s.get("type") == "home"), {})
                away = next((s for s in splits if s.get("type") == "away"), {})
                teams[tid] = {
                    "pct": safe_float(tr.get("winningPercentage", ".500"), 0.500),
                    "rs": tr.get("runsScored", 0),
                    "ra": tr.get("runsAllowed", 0),
                    "home_w": home.get("wins", 0),
                    "home_l": home.get("losses", 0),
                    "away_w": away.get("wins", 0),
                    "away_l": away.get("losses", 0),
                }
        return teams
    except:
        return {}


def get_team_batting(tid, season=2026):
    try:
        data = api_get(f"/teams/{tid}/stats?stats=season&season={season}&group=hitting")
        return data.get("stats", [{}])[0].get("splits", [{}])[0].get("stat")
    except:
        return None


def get_team_pitching(tid, season=2026):
    try:
        data = api_get(f"/teams/{tid}/stats?stats=season&season={season}&group=pitching")
        return data.get("stats", [{}])[0].get("splits", [{}])[0].get("stat")
    except:
        return None


# ── Scoring functions (same as extract_features.py) ──

def score_pitcher_raw(stats):
    if not stats:
        return 45.0, 0.0
    era = safe_float(stats.get("era"), 4.50)
    whip = safe_float(stats.get("whip"), 1.30)
    k9 = safe_float(stats.get("strikeoutsPer9Inn"), 7.5)
    bb9 = safe_float(stats.get("walksPer9Inn"), 3.5)
    hr9 = safe_float(stats.get("homeRunsPer9"), 1.2)
    ip = safe_float(stats.get("inningsPitched"), 0)
    go_ao = safe_float(stats.get("groundOutsToAirouts"), 1.0)
    k_bb = safe_float(stats.get("strikeoutWalkRatio"), 2.0)

    era_s = max(5, min(98, 100 - (era - 1.5) * 16))
    whip_s = max(5, min(98, 100 - (whip - 0.80) * 60))
    k_s = max(5, min(98, (k9 - 3.0) * 9.5 + 10))
    bb_s = max(5, min(98, 95 - (bb9 - 1.0) * 22))
    hr_s = max(5, min(98, 95 - (hr9 - 0.3) * 40))
    gb_s = max(30, min(80, (go_ao - 0.5) * 25 + 40))
    kbb_s = max(5, min(98, (k_bb - 1.0) * 15 + 20))

    total = (era_s*0.22 + whip_s*0.18 + k_s*0.15 + bb_s*0.12 + hr_s*0.10 + gb_s*0.08 + kbb_s*0.15)
    if ip < 50: total = total*0.55 + 50*0.45
    elif ip < 100: total = total*0.75 + 50*0.25
    elif ip < 150: total = total*0.90 + 50*0.10
    return round(total, 2), ip


def score_recent_raw(game_log):
    if not game_log:
        return 50.0, 0
    ip = er = k = bb = h = 0.0
    ws = we = 0.0
    for i, g in enumerate(game_log):
        s = g.get("stat", {})
        gip = safe_float(s.get("inningsPitched", "0"), 0)
        ger = int(s.get("earnedRuns", 0))
        if gip > 0:
            w = 1.0 + i*0.3
            ws += (ger/gip)*9 * w; we += w
            ip += gip; er += ger; k += int(s.get("strikeOuts", 0))
            bb += int(s.get("baseOnBalls", 0)); h += int(s.get("hits", 0))
    if ip == 0 or we == 0:
        return 50.0, 0
    wera = ws/we
    rwhip = (bb+h)/ip
    rk9 = (k/ip)*9
    es = max(10, min(95, 100-(wera-1.5)*16))
    ws2 = max(10, min(95, 100-(rwhip-0.80)*60))
    ks = max(10, min(95, (rk9-3.0)*9.5+10))
    return round(es*0.45+ws2*0.30+ks*0.25, 2), len(game_log)


def score_offense_raw(batting):
    if not batting:
        return 50.0
    ops = safe_float(batting.get("ops", ".750"), 0.750)
    runs = int(batting.get("runs", 700))
    games = max(1, int(batting.get("gamesPlayed", 162)))
    rpg = runs / games
    hr = int(batting.get("homeRuns", 180))
    bb = int(batting.get("baseOnBalls", 500))
    k = max(1, int(batting.get("strikeOuts", 1300)))
    bbk = bb / k
    ops_s = max(10, min(95, (ops-0.600)*200))
    rpg_s = max(10, min(95, (rpg-3.0)*18+20))
    bbk_s = max(10, min(90, bbk*150))
    pow_s = max(10, min(95, (hr/games-0.7)*60+40))
    return round(ops_s*0.35+rpg_s*0.30+bbk_s*0.15+pow_s*0.20, 2)


def score_pitching_raw(pitching):
    if not pitching:
        return 50.0
    era = safe_float(pitching.get("era"), 4.00)
    whip = safe_float(pitching.get("whip"), 1.25)
    k9 = safe_float(pitching.get("strikeoutsPer9Inn"), 8.0)
    sv = int(pitching.get("saves", 40))
    bs = int(pitching.get("blownSaves", 20))
    sp = sv/max(1,sv+bs)
    es = max(10, min(95, 100-(era-2.5)*20))
    ws = max(10, min(95, 100-(whip-0.90)*55))
    ks = max(10, min(95, (k9-5.0)*10+15))
    ss = max(20, min(90, sp*100))
    return round(es*0.35+ws*0.25+ks*0.20+ss*0.20, 2)


def pyth(rs, ra):
    rs, ra = max(1, rs), max(1, ra)
    return round(rs**1.83 / (rs**1.83 + ra**1.83), 4)


# ── Model prediction ──

def predict_lr(features_normalized):
    z = sum(w * x for w, x in zip(LR_WEIGHTS, features_normalized)) + LR_BIAS
    return sigmoid(z)


def predict_gb(features_normalized):
    pred = GB_BASE
    for tree in GB_TREES:
        pred += GB_LR * tree.predict_one(features_normalized)
    return sigmoid(pred)


def predict_ensemble(features_raw):
    """Normalize features and run ensemble prediction."""
    normalized = [(features_raw[i] - MEANS[i]) / STDS[i] for i in range(len(FEATURES))]
    lr_prob = predict_lr(normalized)
    gb_prob = predict_gb(normalized)
    return LR_WEIGHT * lr_prob + GB_WEIGHT * gb_prob, lr_prob, gb_prob


# ── Main prediction pipeline ──

def predict_game(game, standings, season=2026):
    away = game["teams"]["away"]
    home = game["teams"]["home"]
    aid, hid = away["team"]["id"], home["team"]["id"]
    venue = game.get("venue", {}).get("name", "Unknown")

    ap_info = away.get("probablePitcher", {})
    hp_info = home.get("probablePitcher", {})
    apid, hpid = ap_info.get("id"), hp_info.get("id")

    # Pitcher stats
    ap_stats = get_pitcher_stats(apid, season) if apid else None
    hp_stats = get_pitcher_stats(hpid, season) if hpid else None
    ap_score, ap_ip = score_pitcher_raw(ap_stats)
    hp_score, hp_ip = score_pitcher_raw(hp_stats)

    # Recent form
    ap_recent = get_pitcher_game_log(apid, season) if apid else []
    hp_recent = get_pitcher_game_log(hpid, season) if hpid else []
    ap_rec, _ = score_recent_raw(ap_recent)
    hp_rec, _ = score_recent_raw(hp_recent)

    # Combined pitcher (80/20 as the data suggests season matters more)
    ap_combined = ap_score * 0.8 + ap_rec * 0.2
    hp_combined = hp_score * 0.8 + hp_rec * 0.2

    # Team stats
    a_bat = get_team_batting(aid, season)
    h_bat = get_team_batting(hid, season)
    a_pit = get_team_pitching(aid, season)
    h_pit = get_team_pitching(hid, season)
    a_off = score_offense_raw(a_bat)
    h_off = score_offense_raw(h_bat)
    a_staff = score_pitching_raw(a_pit)
    h_staff = score_pitching_raw(h_pit)

    # Standings
    a_stand = standings.get(aid, {"pct": .5, "rs": 700, "ra": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})
    h_stand = standings.get(hid, {"pct": .5, "rs": 700, "ra": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})
    a_pyth = pyth(a_stand.get("rs", 700), a_stand.get("ra", 700))
    h_pyth = pyth(h_stand.get("rs", 700), h_stand.get("ra", 700))
    h_home_pct = h_stand.get("home_w", 40) / max(1, h_stand.get("home_w", 40) + h_stand.get("home_l", 41))
    a_away_pct = a_stand.get("away_w", 40) / max(1, a_stand.get("away_w", 40) + a_stand.get("away_l", 41))

    park = PARK_FACTORS.get(venue, 1.0)

    # Build feature vector (same order as training)
    features_raw = [
        hp_combined - ap_combined,       # pitcher_diff
        hp_score - ap_score,             # pitcher_season_diff
        hp_rec - ap_rec,                 # pitcher_recent_diff
        h_off - a_off,                   # offense_diff
        h_staff - a_staff,               # bullpen_diff
        h_pyth - a_pyth,                 # pyth_diff
        h_home_pct,                      # home_home_pct
        a_away_pct,                      # away_road_pct
        park,                            # park_factor
        hp_combined,                     # home_pitcher_combined
        ap_combined,                     # away_pitcher_combined
        h_off,                           # home_offense
        a_off,                           # away_offense
        h_staff,                         # home_bullpen
        a_staff,                         # away_bullpen
        h_pyth,                          # home_pyth
        a_pyth,                          # away_pyth
        hp_ip,                           # home_pitcher_ip
        ap_ip,                           # away_pitcher_ip
    ]

    # Run ensemble
    home_prob, lr_prob, gb_prob = predict_ensemble(features_raw)

    # Soft clamp — allow wider range since model is trained on real data
    home_prob = max(0.20, min(0.80, home_prob))
    away_prob = 1.0 - home_prob

    if home_prob > away_prob:
        pick = home["team"]["name"]
        pick_prob = home_prob
    else:
        pick = away["team"]["name"]
        pick_prob = away_prob

    if pick_prob >= 0.68: confidence = "HIGH"
    elif pick_prob >= 0.60: confidence = "MEDIUM"
    else: confidence = "LOW"

    return {
        "game_id": game["gamePk"],
        "game_date": game.get("officialDate", ""),
        "game_time": game.get("gameDate", ""),
        "away_team": away["team"]["name"],
        "home_team": home["team"]["name"],
        "away_id": aid,
        "home_id": hid,
        "away_pitcher": ap_info.get("fullName", "TBD"),
        "home_pitcher": hp_info.get("fullName", "TBD"),
        "away_pitcher_score": ap_score,
        "home_pitcher_score": hp_score,
        "away_pitcher_era": ap_stats.get("era", "N/A") if ap_stats else "N/A",
        "home_pitcher_era": hp_stats.get("era", "N/A") if hp_stats else "N/A",
        "away_pitcher_recent": {"recent_score": ap_rec, "recent_era": "N/A"},
        "home_pitcher_recent": {"recent_score": hp_rec, "recent_era": "N/A"},
        "venue": venue,
        "park_factor": park,
        "home_win_prob": round(home_prob, 3),
        "away_win_prob": round(away_prob, 3),
        "pick": pick,
        "pick_prob": round(pick_prob, 3),
        "confidence": confidence,
        "edge": round(pick_prob - 0.50, 3),
        "model_detail": {
            "lr_prob": round(lr_prob, 3),
            "gb_prob": round(gb_prob, 3),
            "ensemble": round(home_prob, 3),
        },
        "factors": {
            "pitcher_matchup": {"impact": round((hp_combined - ap_combined) * 0.24, 1), "desc": f"Pitcher: Home {hp_score} vs Away {ap_score}"},
            "bullpen": {"impact": round((h_staff - a_staff) * 0.10, 1), "desc": f"Bullpen: Home {h_staff} vs Away {a_staff}"},
            "offense": {"impact": round((h_off - a_off) * 0.16, 1), "desc": f"Offense: Home {h_off} vs Away {a_off}"},
            "true_talent": {"impact": round((h_pyth - a_pyth) * 100, 1), "desc": f"Pyth: Home {h_pyth} vs Away {a_pyth}"},
            "home_field": {"impact": round((h_home_pct - 0.5) * 10, 1), "desc": f"Home record: {h_stand.get('home_w',0)}-{h_stand.get('home_l',0)}"},
        },
    }


def run_predictions(date=None, season=2026):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    print(f"🔍 Fetching games for {date}...")
    games = get_schedule(date)
    if not games:
        print(f"No games found for {date}")
        return []

    print(f"📊 Found {len(games)} games. Loading data...")
    standings = get_team_standings(season)

    predictions = []
    for game in games:
        try:
            pred = predict_game(game, standings, season)
            predictions.append(pred)
        except Exception as e:
            print(f"  ⚠️ Error: {e}")

    predictions.sort(key=lambda x: x["edge"], reverse=True)

    # Save
    PICKS_DIR.mkdir(exist_ok=True)
    if predictions:
        outfile = PICKS_DIR / f"{predictions[0]['game_date']}.json"
        with open(outfile, "w") as f:
            json.dump(predictions, f, indent=2)
        print(f"💾 Saved {len(predictions)} predictions to {outfile}")

    # Print summary
    high = [p for p in predictions if p["confidence"] == "HIGH"]
    med = [p for p in predictions if p["confidence"] == "MEDIUM"]
    print(f"\n⚾ {date}: {len(predictions)} games | 🔥 {len(high)} HIGH | ✅ {len(med)} MEDIUM")
    for p in high:
        print(f"  🔥 {p['away_team']} @ {p['home_team']} → {p['pick']} ({p['pick_prob']*100:.0f}%)")
        print(f"     LR: {p['model_detail']['lr_prob']*100:.0f}% | GB: {p['model_detail']['gb_prob']*100:.0f}%")

    return predictions


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    run_predictions(date)
