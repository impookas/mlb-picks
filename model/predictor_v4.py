#!/usr/bin/env python3
"""
MLB Prediction Model v4 — Ensemble of v2 (hand-tuned) + v3 (learned weights).
Blends conservative v2 calibration with v3's data-driven feature importance.

Usage: First run v2 and v3, then run this to blend their outputs.
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
PICKS_DIR = ROOT / "picks"
MODEL_DIR = ROOT / "model"

# Ensemble weights: favor v2 early season, shift toward v3 as season progresses
V2_WEIGHT = 0.6  # Conservative hand-tuned
V3_WEIGHT = 0.4  # Data-driven learned weights


def blend_predictions(v2_pred, v3_pred):
    """Combine v2 and v3 predictions with weighted average."""
    # Get probabilities from both models
    v2_home = v2_pred["home_win_prob"]
    v3_home = v3_pred["home_win_prob"]
    
    # Weighted blend
    blended_home = V2_WEIGHT * v2_home + V3_WEIGHT * v3_home
    blended_away = 1.0 - blended_home
    
    # Determine pick
    if blended_home > blended_away:
        pick = v2_pred["home_team"]
        pick_prob = blended_home
    else:
        pick = v2_pred["away_team"]
        pick_prob = blended_away
    
    # Optimized threshold (62%+ for best balance of volume + ROI)
    if pick_prob >= 0.62:
        confidence = "HIGH"
    elif pick_prob >= 0.56:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    return {
        "game_id": v2_pred["game_id"],
        "game_date": v2_pred["game_date"],
        "game_time": v2_pred["game_time"],
        "away_team": v2_pred["away_team"],
        "home_team": v2_pred["home_team"],
        "away_id": v2_pred["away_id"],
        "home_id": v2_pred["home_id"],
        "away_pitcher": v2_pred["away_pitcher"],
        "home_pitcher": v2_pred["home_pitcher"],
        "away_pitcher_score": v2_pred["away_pitcher_score"],
        "home_pitcher_score": v2_pred["home_pitcher_score"],
        "away_pitcher_era": v2_pred["away_pitcher_era"],
        "home_pitcher_era": v2_pred["home_pitcher_era"],
        "away_pitcher_recent": v2_pred["away_pitcher_recent"],
        "home_pitcher_recent": v2_pred["home_pitcher_recent"],
        "venue": v2_pred["venue"],
        "park_factor": v2_pred["park_factor"],
        "home_win_prob": round(blended_home, 3),
        "away_win_prob": round(blended_away, 3),
        "pick": pick,
        "pick_prob": round(pick_prob, 3),
        "confidence": confidence,
        "edge": round(pick_prob - 0.50, 3),
        "model_detail": {
            "v2_home_prob": round(v2_home, 3),
            "v3_home_prob": round(v3_home, 3),
            "v2_pick_prob": round(v2_pred["pick_prob"], 3),
            "v3_pick_prob": round(v3_pred["pick_prob"], 3),
            "blend": round(pick_prob, 3),
            "v2_confidence": v2_pred["confidence"],
            "v3_confidence": v3_pred["confidence"],
        },
        "factors": v2_pred["factors"],
    }


def run_predictions(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"🔍 Running ensemble prediction for {date}...")
    print(f"   v2 weight: {V2_WEIGHT*100:.0f}% | v3 weight: {V3_WEIGHT*100:.0f}%\n")
    
    # Run v2
    print("📊 Running v2 (hand-tuned)...")
    result = subprocess.run([sys.executable, str(MODEL_DIR / "predictor_v2.py"), date],
                          capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"v2 error: {result.stderr}")
        return []
    
    # Save v2 output to temp file
    v2_temp = PICKS_DIR / f"{date}_v2_temp.json"
    picks_file = PICKS_DIR / f"{date}.json"
    if picks_file.exists():
        picks_file.rename(v2_temp)
    
    # Run v3
    print("📊 Running v3 (learned)...")
    result = subprocess.run([sys.executable, str(MODEL_DIR / "predictor_v3.py"), date],
                          capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"v3 error: {result.stderr}")
        return []
    
    # Now we have v2 in v2_temp and v3 in date.json
    v3_file = picks_file
    v2_file = v2_temp
    
    # Load both
    try:
        with open(v2_file) as f:
            v2_preds = json.load(f)
        print(f"   ✅ Loaded {len(v2_preds)} v2 predictions")
    except Exception as e:
        print(f"Could not load v2: {e}")
        return []
    
    try:
        with open(v3_file) as f:
            v3_preds = json.load(f)
        print(f"   ✅ Loaded {len(v3_preds)} v3 predictions")
    except Exception as e:
        print(f"Could not load v3: {e}")
        return []
    
    # Match games by game_id and blend
    v3_by_id = {p["game_id"]: p for p in v3_preds}
    blended = []
    
    for v2_pred in v2_preds:
        gid = v2_pred["game_id"]
        if gid in v3_by_id:
            blended.append(blend_predictions(v2_pred, v3_by_id[gid]))
    
    blended.sort(key=lambda x: x["edge"], reverse=True)
    
    # Save
    if blended:
        outfile = PICKS_DIR / f"{date}.json"
        with open(outfile, "w") as f:
            json.dump(blended, f, indent=2)
        print(f"\n💾 Saved {len(blended)} ensemble predictions to {outfile}")
    
    # Clean up temp files
    if v2_file.exists():
        v2_file.unlink()
    
    # Print summary
    high = [p for p in blended if p["confidence"] == "HIGH"]
    med = [p for p in blended if p["confidence"] == "MEDIUM"]
    print(f"\n⚾ {date}: {len(blended)} games | 🔥 {len(high)} HIGH | ✅ {len(med)} MEDIUM")
    
    for p in high:
        v2_conf = p["model_detail"]["v2_confidence"]
        v3_conf = p["model_detail"]["v3_confidence"]
        v2_prob = p["model_detail"]["v2_pick_prob"]
        v3_prob = p["model_detail"]["v3_pick_prob"]
        print(f"  🔥 {p['away_team']} @ {p['home_team']} → {p['pick']} ({p['pick_prob']*100:.0f}%)")
        print(f"     v2: {v2_prob*100:.0f}% ({v2_conf}) | v3: {v3_prob*100:.0f}% ({v3_conf})")
    
    return blended


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    run_predictions(date)
