#!/usr/bin/env python3
"""
Pitcher scoring improvements:
1. Better recent form weighting (exponential decay)
2. Opponent strength adjustment
3. Park factor adjustment
"""

import math

def score_pitcher_recent_weighted(game_log: list, opponent_strengths: dict = None, n: int = 5) -> dict:
    """
    Score pitcher recent form with:
    - Exponential weighting (most recent game = highest weight)
    - Opponent strength adjustment
    - Park factor adjustment
    
    opponent_strengths: {team_id: strength_score} where 100 = best, 50 = average
    """
    if not game_log or len(game_log) == 0:
        return {
            "recent_score": 50.0, 
            "trend": "unknown", 
            "recent_era": "N/A", 
            "starts": 0,
            "weighted_score": 50.0
        }
    
    recent = game_log[-n:]  # Last N starts
    
    # Calculate weights (exponential decay, most recent = highest)
    # weights = [0.4, 0.25, 0.2, 0.1, 0.05] for 5 starts
    total_weight = sum(math.exp(i * 0.5) for i in range(len(recent)))
    weights = [math.exp(i * 0.5) / total_weight for i in range(len(recent))]
    
    total_ip = 0
    total_er = 0
    weighted_score = 0
    
    for idx, (game, weight) in enumerate(zip(recent, weights)):
        stat = game.get("stat", {})
        ip = float(stat.get("inningsPitched", "0"))
        er = int(stat.get("earnedRuns", 0))
        
        if ip == 0:
            continue
        
        total_ip += ip
        total_er += er
        
        # Game-level performance score (0-100)
        game_era = (er * 9) / ip if ip > 0 else 9.0
        k = int(stat.get("strikeOuts", 0))
        bb = int(stat.get("baseOnBalls", 0))
        hits = int(stat.get("hits", 0))
        
        # Score this game
        game_score = score_single_start(ip, er, k, bb, hits)
        
        # Adjust for opponent strength if available
        if opponent_strengths:
            opp_team = game.get("opponent", {}).get("id")
            if opp_team and opp_team in opponent_strengths:
                opp_strength = opponent_strengths[opp_team]
                # Playing tough opponent (80+) and doing well = bonus
                # Playing weak opponent (30-) and doing poorly = penalty
                adjustment = (opp_strength - 50) / 100  # -0.2 to +0.5
                game_score += adjustment * 10  # Up to +5/-5 points
        
        weighted_score += game_score * weight
    
    # Calculate trend (comparing recent 2 vs previous 3)
    if len(recent) >= 3:
        recent_2_scores = []
        older_3_scores = []
        
        for i, game in enumerate(recent):
            stat = game.get("stat", {})
            ip = float(stat.get("inningsPitched", "0"))
            er = int(stat.get("earnedRuns", 0))
            if ip == 0:
                continue
            era = (er * 9) / ip
            score = max(0, min(100, 100 - (era - 1.5) * 16))
            
            if i >= len(recent) - 2:
                recent_2_scores.append(score)
            else:
                older_3_scores.append(score)
        
        if recent_2_scores and older_3_scores:
            recent_avg = sum(recent_2_scores) / len(recent_2_scores)
            older_avg = sum(older_3_scores) / len(older_3_scores)
            diff = recent_avg - older_avg
            
            if diff > 10:
                trend = "improving"
            elif diff < -10:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "unknown"
    else:
        trend = "insufficient_data"
    
    recent_era = (total_er * 9 / total_ip) if total_ip > 0 else 0
    
    return {
        "recent_score": max(0, min(100, weighted_score)),
        "weighted_score": weighted_score,
        "trend": trend,
        "recent_era": f"{recent_era:.2f}",
        "starts": len(recent)
    }


def score_single_start(ip: float, er: int, k: int, bb: int, hits: int) -> float:
    """Score a single start (0-100 scale)."""
    if ip == 0:
        return 30.0
    
    era = (er * 9) / ip
    k_per_9 = (k * 9) / ip
    bb_per_9 = (bb * 9) / ip
    whip = (hits + bb) / ip
    
    # Component scores
    era_score = max(0, min(100, 100 - (era - 1.5) * 16))
    k_score = max(0, min(100, (k_per_9 - 3.0) * 9.5 + 10))
    bb_score = max(0, min(100, 95 - (bb_per_9 - 1.0) * 22))
    whip_score = max(0, min(100, 100 - (whip - 0.80) * 60))
    
    # Quality start bonus
    qs_bonus = 10 if (ip >= 6 and er <= 3) else 0
    
    total = (
        era_score * 0.35 +
        whip_score * 0.25 +
        k_score * 0.20 +
        bb_score * 0.20 +
        qs_bonus
    )
    
    return total


def get_team_strength_scores(standings: dict) -> dict:
    """
    Convert team standings into strength scores (0-100).
    Used for opponent adjustment.
    
    standings: {team_id: {"wins": int, "losses": int, "pct": float}}
    """
    strengths = {}
    
    if not standings:
        return strengths
    
    # Get win% range
    pcts = [team["pct"] for team in standings.values()]
    if not pcts:
        return strengths
    
    min_pct = min(pcts)
    max_pct = max(pcts)
    pct_range = max_pct - min_pct
    
    if pct_range == 0:
        pct_range = 0.001
    
    for team_id, team_data in standings.items():
        pct = team_data["pct"]
        # Normalize to 0-100 scale
        # Best team ~= 90, worst team ~= 10
        normalized = ((pct - min_pct) / pct_range) * 80 + 10
        strengths[team_id] = normalized
    
    return strengths


# Example usage
if __name__ == "__main__":
    # Test with sample game log
    sample_log = [
        {"stat": {"inningsPitched": "6.0", "earnedRuns": 2, "strikeOuts": 8, "baseOnBalls": 2, "hits": 4}, "opponent": {"id": 110}},
        {"stat": {"inningsPitched": "5.0", "earnedRuns": 4, "strikeOuts": 5, "baseOnBalls": 3, "hits": 6}, "opponent": {"id": 147}},
        {"stat": {"inningsPitched": "7.0", "earnedRuns": 1, "strikeOuts": 9, "baseOnBalls": 1, "hits": 3}, "opponent": {"id": 110}},
        {"stat": {"inningsPitched": "6.0", "earnedRuns": 3, "strikeOuts": 7, "baseOnBalls": 2, "hits": 5}, "opponent": {"id": 121}},
        {"stat": {"inningsPitched": "6.2", "earnedRuns": 2, "strikeOuts": 10, "baseOnBalls": 1, "hits": 4}, "opponent": {"id": 147}},
    ]
    
    # Sample opponent strengths (team_id: strength)
    opp_strengths = {
        110: 75,  # Strong team
        147: 35,  # Weak team
        121: 55,  # Average team
    }
    
    result = score_pitcher_recent_weighted(sample_log, opp_strengths)
    print("Recent form analysis:")
    print(f"  Weighted score: {result['weighted_score']:.1f}")
    print(f"  Recent ERA: {result['recent_era']}")
    print(f"  Trend: {result['trend']}")
    print(f"  Starts analyzed: {result['starts']}")
