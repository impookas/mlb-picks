#!/usr/bin/env python3
"""
Extract feature vectors from the full-season backtest for model training.
Outputs a CSV with one row per game, all features + outcome.
Zero look-ahead: same data access rules as backtest.py.
"""

import json
import csv
import sys
import time
import math
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BASE_URL = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "training"

_cache = {}
_req = 0

def api_get(endpoint: str) -> dict:
    global _req
    if endpoint in _cache:
        return _cache[endpoint]
    try:
        _req += 1
        if _req % 50 == 0:
            time.sleep(0.3)
        data = json.loads(urllib.request.urlopen(f"{BASE_URL}{endpoint}", timeout=20).read())
        _cache[endpoint] = data
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

DOMED = {"Tropicana Field", "Globe Life Field", "Chase Field", "loanDepot park",
         "Rogers Centre", "American Family Field", "Daikin Park", "T-Mobile Park"}


# ── Prior season data ──
_prior_standings = {}
_prior_batting = {}
_prior_pitching = {}

def load_prior(year=2024):
    global _prior_standings, _prior_batting, _prior_pitching
    print(f"  Loading {year} team data...")

    data = api_get(f"/standings?leagueId=103,104&season={year}&standingsTypes=regularSeason")
    for rec in data.get("records", []):
        for tr in rec.get("teamRecords", []):
            tid = tr["team"]["id"]
            splits = tr.get("records", {}).get("splitRecords", [])
            home = next((s for s in splits if s.get("type") == "home"), {})
            away = next((s for s in splits if s.get("type") == "away"), {})
            _prior_standings[tid] = {
                "pct": safe_float(tr.get("winningPercentage", ".500"), 0.500),
                "rs": tr.get("runsScored", 700),
                "ra": tr.get("runsAllowed", 700),
                "home_w": home.get("wins", 40), "home_l": home.get("losses", 41),
                "away_w": away.get("wins", 40), "away_l": away.get("losses", 41),
            }

    tdata = api_get(f"/teams?sportId=1&season={year}")
    for team in tdata.get("teams", []):
        tid = team["id"]
        bd = api_get(f"/teams/{tid}/stats?stats=season&season={year}&group=hitting")
        sp = bd.get("stats", [{}])[0].get("splits", [])
        if sp:
            _prior_batting[tid] = sp[0]["stat"]
        pd = api_get(f"/teams/{tid}/stats?stats=season&season={year}&group=pitching")
        sp2 = pd.get("stats", [{}])[0].get("splits", [])
        if sp2:
            _prior_pitching[tid] = sp2[0]["stat"]

    print(f"  ✅ {len(_prior_standings)} teams loaded")


# ── Pitcher helpers (same as backtest — zero look-ahead) ──

def get_pitcher_prior(pid, season=2024):
    try:
        data = api_get(f"/people/{pid}/stats?stats=yearByYear&group=pitching&sportId=1")
        for s in reversed(data.get("stats", [{}])[0].get("splits", [])):
            if int(s["season"]) == season:
                return s["stat"]
    except:
        pass
    return None

def get_pitcher_stats_asof(pid, before_date, season=2025):
    data = api_get(f"/people/{pid}/stats?stats=gameLog&group=pitching&season={season}&sportId=1")
    splits = data.get("stats", [{}])[0].get("splits", [])

    ip = er = h = bb = k = hr = go = ao = 0.0
    games = 0
    for g in splits:
        if g.get("date", "") >= before_date:
            continue
        s = g.get("stat", {})
        gip = safe_float(s.get("inningsPitched", "0"), 0)
        if gip == 0:
            continue
        ip += gip; er += int(s.get("earnedRuns", 0))
        h += int(s.get("hits", 0)); bb += int(s.get("baseOnBalls", 0))
        k += int(s.get("strikeOuts", 0)); hr += int(s.get("homeRuns", 0))
        go += int(s.get("groundOuts", 0)); ao += int(s.get("airOuts", 0))
        games += 1

    if games < 3 or ip < 10:
        prior = get_pitcher_prior(pid, season - 1)
        if prior:
            return prior
        if ip < 1:
            return None

    if ip < 1:
        return None

    return {
        "era": str(round((er/ip)*9, 2)),
        "whip": str(round((bb+h)/ip, 2)),
        "strikeoutsPer9Inn": str(round((k/ip)*9, 2)),
        "walksPer9Inn": str(round((bb/ip)*9, 2)),
        "homeRunsPer9": str(round((hr/ip)*9, 2)),
        "inningsPitched": str(round(ip, 1)),
        "groundOutsToAirouts": str(round(go/max(1,ao), 2)),
        "strikeoutWalkRatio": str(round(k/max(1,bb), 2)),
    }

def get_recent_asof(pid, before_date, season=2025, n=5):
    data = api_get(f"/people/{pid}/stats?stats=gameLog&group=pitching&season={season}&sportId=1")
    try:
        splits = data.get("stats", [{}])[0].get("splits", [])
    except:
        return []
    prior = [g for g in splits if g.get("date", "") < before_date]
    if len(prior) < 3:
        try:
            pd = api_get(f"/people/{pid}/stats?stats=gameLog&group=pitching&season={season-1}&sportId=1")
            ps = pd.get("stats", [{}])[0].get("splits", [])
            combined = ps[-(n-len(prior)):] + prior
            return combined[-n:]
        except:
            pass
    return prior[-n:]

def get_vs_team(pid, team_id):
    try:
        data = api_get(f"/people/{pid}/stats?stats=vsTeam&group=pitching&sportId=1&opposingTeamId={team_id}")
        stats = data.get("stats", [])
        if stats and stats[0].get("splits"):
            return stats[0]["splits"][0].get("stat")
    except:
        pass
    return None


# ── Scoring functions (raw scores, not combined into probability) ──

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
            ip += gip; er += ger; k += int(s.get("strikeOuts",0))
            bb += int(s.get("baseOnBalls",0)); h += int(s.get("hits",0))
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
    games = int(batting.get("gamesPlayed", 162))
    rpg = runs / max(1, games)
    hr = int(batting.get("homeRuns", 180))
    bb = int(batting.get("baseOnBalls", 500))
    k = int(batting.get("strikeOuts", 1300))
    bbk = bb / max(1, k)
    ops_s = max(10, min(95, (ops-0.600)*200))
    rpg_s = max(10, min(95, (rpg-3.0)*18+20))
    bbk_s = max(10, min(90, bbk*150))
    pow_s = max(10, min(95, (hr/max(1,games)-0.7)*60+40))
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
    return rs**1.83 / (rs**1.83 + ra**1.83)


# ── Extract features for one game ──

def extract_game_features(game, game_date, season=2025):
    away = game["teams"]["away"]
    home = game["teams"]["home"]
    aid, hid = away["team"]["id"], home["team"]["id"]
    venue = game.get("venue", {}).get("name", "Unknown")

    ap = away.get("probablePitcher", {})
    hp = home.get("probablePitcher", {})
    apid, hpid = ap.get("id"), hp.get("id")
    if not apid or not hpid:
        return None

    # Pitcher season (date-aware)
    ap_stats = get_pitcher_stats_asof(apid, game_date, season)
    hp_stats = get_pitcher_stats_asof(hpid, game_date, season)
    ap_score, ap_ip = score_pitcher_raw(ap_stats)
    hp_score, hp_ip = score_pitcher_raw(hp_stats)

    # Pitcher recent (date-aware)
    ap_recent = get_recent_asof(apid, game_date, season)
    hp_recent = get_recent_asof(hpid, game_date, season)
    ap_rec_score, ap_rec_n = score_recent_raw(ap_recent)
    hp_rec_score, hp_rec_n = score_recent_raw(hp_recent)

    # Combined pitcher
    ap_combined = ap_score * 0.6 + ap_rec_score * 0.4
    hp_combined = hp_score * 0.6 + hp_rec_score * 0.4

    # Pitcher vs team (career)
    ap_vs = get_vs_team(apid, hid)
    hp_vs = get_vs_team(hpid, aid)
    ap_vs_era = safe_float(ap_vs.get("era", "4.50"), 4.50) if ap_vs else 4.50
    hp_vs_era = safe_float(hp_vs.get("era", "4.50"), 4.50) if hp_vs else 4.50
    ap_vs_ip = safe_float(ap_vs.get("inningsPitched", "0"), 0) if ap_vs else 0
    hp_vs_ip = safe_float(hp_vs.get("inningsPitched", "0"), 0) if hp_vs else 0

    # Team offense (prior year)
    a_off = score_offense_raw(_prior_batting.get(aid))
    h_off = score_offense_raw(_prior_batting.get(hid))

    # Team pitching/bullpen (prior year)
    a_staff = score_pitching_raw(_prior_pitching.get(aid))
    h_staff = score_pitching_raw(_prior_pitching.get(hid))

    # Standings (prior year)
    a_stand = _prior_standings.get(aid, {"pct": .5, "rs": 700, "ra": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})
    h_stand = _prior_standings.get(hid, {"pct": .5, "rs": 700, "ra": 700, "home_w": 40, "home_l": 41, "away_w": 40, "away_l": 41})

    a_pyth = pyth(a_stand["rs"], a_stand["ra"])
    h_pyth = pyth(h_stand["rs"], h_stand["ra"])
    h_home_pct = h_stand["home_w"] / max(1, h_stand["home_w"] + h_stand["home_l"])
    a_away_pct = a_stand["away_w"] / max(1, a_stand["away_w"] + a_stand["away_l"])

    park = PARK_FACTORS.get(venue, 1.0)

    return {
        # Differentials (home - away perspective)
        "pitcher_diff": hp_combined - ap_combined,
        "pitcher_season_diff": hp_score - ap_score,
        "pitcher_recent_diff": hp_rec_score - ap_rec_score,
        "offense_diff": h_off - a_off,
        "bullpen_diff": h_staff - a_staff,
        "pyth_diff": h_pyth - a_pyth,

        # Raw scores
        "home_pitcher_combined": hp_combined,
        "away_pitcher_combined": ap_combined,
        "home_pitcher_season": hp_score,
        "away_pitcher_season": ap_score,
        "home_pitcher_recent": hp_rec_score,
        "away_pitcher_recent": ap_rec_score,
        "home_pitcher_ip": hp_ip,
        "away_pitcher_ip": ap_ip,
        "home_offense": h_off,
        "away_offense": a_off,
        "home_bullpen": h_staff,
        "away_bullpen": a_staff,
        "home_pyth": round(h_pyth, 4),
        "away_pyth": round(a_pyth, 4),

        # Home/away context
        "home_home_pct": round(h_home_pct, 3),
        "away_road_pct": round(a_away_pct, 3),
        "is_home": 1,  # Always from home perspective
        "park_factor": park,

        # Pitcher vs team
        "home_p_vs_era": hp_vs_era,
        "away_p_vs_era": ap_vs_era,
        "home_p_vs_ip": hp_vs_ip,
        "away_p_vs_ip": ap_vs_ip,

        # Meta
        "game_id": game["gamePk"],
        "date": game_date,
        "away_team": away["team"]["name"],
        "home_team": home["team"]["name"],
        "venue": venue,
    }


# ── Fetch results ──

def fetch_results(date):
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
            if ar is not None and hr is not None:
                results[gid] = {"home_win": 1 if hr > ar else 0, "away_runs": ar, "home_runs": hr}
    return results


# ── Main ──

def run(start="2025-03-27", end="2025-09-28", season=2025):
    print(f"\n{'='*60}")
    print(f"  FEATURE EXTRACTION — {start} to {end}")
    print(f"{'='*60}\n")

    load_prior(season - 1)
    OUT_DIR.mkdir(exist_ok=True)

    rows = []
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    day_count = 0

    while current <= end_dt:
        ds = current.strftime("%Y-%m-%d")
        current += timedelta(days=1)

        data = api_get(f"/schedule?sportId=1&date={ds}&hydrate=probablePitcher(note),team,venue")
        games = [g for d in data.get("dates", []) for g in d.get("games", []) if g.get("gameType") == "R"]
        if not games:
            continue

        results = fetch_results(ds)
        if not results:
            continue

        day_count += 1
        day_added = 0

        for game in games:
            gid = game["gamePk"]
            if gid not in results:
                continue
            try:
                features = extract_game_features(game, ds, season)
            except:
                continue
            if features is None:
                continue

            features["home_win"] = results[gid]["home_win"]
            features["home_runs"] = results[gid]["home_runs"]
            features["away_runs"] = results[gid]["away_runs"]
            rows.append(features)
            day_added += 1

        if day_added > 0:
            print(f"  {ds}: {day_added} games — Total: {len(rows)}")

    # Save as CSV
    if rows:
        outfile = OUT_DIR / f"features_{start}_{end}.csv"
        keys = rows[0].keys()
        with open(outfile, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"\n✅ Saved {len(rows)} games to {outfile}")
        print(f"   {day_count} days, {_req} API requests")

        # Also save as JSON for convenience
        jfile = OUT_DIR / f"features_{start}_{end}.json"
        with open(jfile, "w") as f:
            json.dump(rows, f, indent=2)
        print(f"   Also saved to {jfile}")
    else:
        print("No data extracted.")

    return rows


if __name__ == "__main__":
    s = sys.argv[1] if len(sys.argv) > 1 else "2025-03-27"
    e = sys.argv[2] if len(sys.argv) > 2 else "2025-09-28"
    run(s, e)
