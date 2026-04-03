#!/usr/bin/env python3
"""
Injury tracking and lineup analysis.

Sources:
1. MLB Stats API: /teams/{id}/roster (check IL status)
2. Lineup comparison: missing regulars = likely injured
3. Team stats impact: compare with/without key players
"""

import json
import urllib.request
from typing import Dict, List, Optional

BASE_URL = "https://statsapi.mlb.com/api/v1"

def get_team_roster(team_id: int, roster_type: str = "active") -> List[dict]:
    """
    Get team roster with injury list status.
    
    roster_type: "active", "40Man", "fullSeason", etc.
    """
    url = f"{BASE_URL}/teams/{team_id}/roster/{roster_type}?hydrate=person(stats(type=season,season=2026))"
    
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        return data.get("roster", [])
    except Exception as e:
        print(f"Error fetching roster for team {team_id}: {e}")
        return []


def get_injured_list(team_id: int) -> List[dict]:
    """Get players on injured list."""
    # IL can be fetched via transactions or by checking status in roster
    url = f"{BASE_URL}/teams/{team_id}/roster/depthChart"
    
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
        # Parse depth chart for IL players
        # (This endpoint structure varies, may need adjustment)
        return []
    except Exception as e:
        print(f"Error fetching IL for team {team_id}: {e}")
        return []


def identify_key_players(roster: List[dict], min_games: int = 30) -> List[dict]:
    """
    Identify key players (regulars) based on games played and stats.
    
    Returns list of players who are critical to team performance.
    """
    key_players = []
    
    for player_entry in roster:
        player = player_entry.get("person", {})
        position = player_entry.get("position", {}).get("abbreviation", "")
        status = player_entry.get("status", {}).get("code", "A")
        
        # Check if player has stats for current season
        stats_data = player.get("stats", [])
        if not stats_data:
            continue
        
        # Get season stats
        season_stats = None
        for stat_group in stats_data:
            for split in stat_group.get("splits", []):
                if split.get("season") == "2026":
                    season_stats = split.get("stat", {})
                    break
        
        if not season_stats:
            continue
        
        games_played = season_stats.get("gamesPlayed", 0)
        
        # Define "key player" criteria
        is_regular = games_played >= min_games
        
        # Position players
        if position in ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]:
            ops = season_stats.get("ops", "0")
            try:
                ops_val = float(ops)
                is_productive = ops_val >= 0.750  # Above-average hitter
            except:
                is_productive = False
            
            if is_regular and is_productive:
                key_players.append({
                    "name": player.get("fullName"),
                    "id": player.get("id"),
                    "position": position,
                    "games": games_played,
                    "ops": ops,
                    "status": status
                })
        
        # Pitchers
        elif position == "P":
            era = season_stats.get("era", "9.99")
            ip = season_stats.get("inningsPitched", "0")
            
            try:
                era_val = float(era)
                ip_val = float(ip)
                is_key_pitcher = (era_val <= 4.50 and ip_val >= 30)
            except:
                is_key_pitcher = False
            
            if is_key_pitcher:
                key_players.append({
                    "name": player.get("fullName"),
                    "id": player.get("id"),
                    "position": "P",
                    "era": era,
                    "ip": ip,
                    "status": status
                })
    
    return key_players


def calculate_injury_impact(team_id: int) -> dict:
    """
    Calculate overall injury impact on team.
    
    Returns:
    - missing_key_players: List of injured key players
    - impact_score: 0-100 (0 = no impact, 100 = catastrophic)
    - position_gaps: Which positions are weakened
    """
    roster = get_team_roster(team_id, roster_type="active")
    
    if not roster:
        return {
            "missing_key_players": [],
            "impact_score": 0,
            "position_gaps": [],
            "team_strength_adjustment": 0
        }
    
    key_players = identify_key_players(roster)
    
    # Check for players on IL (status != "A" for Active)
    injured_key_players = []
    for player in key_players:
        if player["status"] != "A":
            injured_key_players.append(player)
    
    # Calculate impact
    # Each key player missing = ~10-15 point impact
    # Multiple stars missing = compounding effect
    base_impact = len(injured_key_players) * 12
    
    # Compounding: 3+ injuries = crisis
    if len(injured_key_players) >= 3:
        base_impact *= 1.3
    
    impact_score = min(100, base_impact)
    
    # Identify weakened positions
    position_gaps = list(set(p["position"] for p in injured_key_players))
    
    # Team strength adjustment for prediction model
    # Loss of key players = reduce team strength
    # -5 to -15 points per key injury
    adjustment = -len(injured_key_players) * 8
    
    return {
        "missing_key_players": injured_key_players,
        "impact_score": impact_score,
        "position_gaps": position_gaps,
        "team_strength_adjustment": adjustment
    }


def quick_injury_check(home_id: int, away_id: int) -> dict:
    """
    Quick check for both teams' injury situations.
    Returns relative advantage.
    """
    home_injuries = calculate_injury_impact(home_id)
    away_injuries = calculate_injury_impact(away_id)
    
    # Net advantage
    # If home has fewer injuries, they get a boost
    home_adj = home_injuries["team_strength_adjustment"]
    away_adj = away_injuries["team_strength_adjustment"]
    
    net_advantage = away_adj - home_adj  # Positive = home advantage
    
    return {
        "home_injuries": home_injuries,
        "away_injuries": away_injuries,
        "net_advantage_home": net_advantage,
        "summary": {
            "home_missing": len(home_injuries["missing_key_players"]),
            "away_missing": len(away_injuries["missing_key_players"]),
            "advantage": "home" if net_advantage > 5 else ("away" if net_advantage < -5 else "neutral")
        }
    }


if __name__ == "__main__":
    # Test with a real team
    print("Testing injury tracking...")
    
    # Example: Yankees (147) vs Red Sox (111)
    result = quick_injury_check(147, 111)
    
    print(f"\nHome (Yankees) missing: {result['summary']['home_missing']} key players")
    print(f"Away (Red Sox) missing: {result['summary']['away_missing']} key players")
    print(f"Advantage: {result['summary']['advantage']}")
    
    if result['home_injuries']['missing_key_players']:
        print("\nHome injuries:")
        for player in result['home_injuries']['missing_key_players']:
            print(f"  - {player['name']} ({player['position']})")
    
    if result['away_injuries']['missing_key_players']:
        print("\nAway injuries:")
        for player in result['away_injuries']['missing_key_players']:
            print(f"  - {player['name']} ({player['position']})")
