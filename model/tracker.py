#!/usr/bin/env python3
"""
MLB Prediction Tracker — Result fetching, scoring, and calibration.

Usage:
    python tracker.py                    # Score all tracked dates
    python tracker.py 2026-03-26         # Score specific date
    python tracker.py --backfill         # Fetch results for all picks files
    python tracker.py --report           # Full season report
"""

import json
import math
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BASE_URL = "https://statsapi.mlb.com/api/v1"
PICKS_DIR = Path(__file__).parent.parent / "picks"
RESULTS_DIR = Path(__file__).parent.parent / "results"
REPORT_DIR = Path(__file__).parent.parent / "reports"


# ── API ───────────────────────────────────────────────────────────────

def api_get(endpoint: str) -> dict:
    url = f"{BASE_URL}{endpoint}"
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=20).read())
        return data
    except Exception as e:
        print(f"  ⚠ API error: {endpoint}: {e}")
        return {}


def fetch_results(date: str) -> dict:
    """Fetch final scores for all games on a date. Returns {game_id: result}."""
    data = api_get(f"/schedule?sportId=1&date={date}&hydrate=linescore,team")
    results = {}
    for d in data.get("dates", []):
        for g in d.get("games", []):
            status = g.get("status", {}).get("abstractGameState", "")
            if status != "Final":
                continue

            game_id = g["gamePk"]
            linescore = g.get("linescore", {})
            away_runs = linescore.get("teams", {}).get("away", {}).get("runs")
            home_runs = linescore.get("teams", {}).get("home", {}).get("runs")

            if away_runs is None or home_runs is None:
                continue

            home_win = home_runs > away_runs
            results[game_id] = {
                "game_id": game_id,
                "date": date,
                "away_team": g["teams"]["away"]["team"]["name"],
                "home_team": g["teams"]["home"]["team"]["name"],
                "away_runs": away_runs,
                "home_runs": home_runs,
                "home_win": home_win,
                "winner": g["teams"]["home"]["team"]["name"] if home_win else g["teams"]["away"]["team"]["name"],
                "final_score": f"{away_runs}-{home_runs}",
                "innings": linescore.get("currentInning", 9),
            }
    return results


# ── Scoring ───────────────────────────────────────────────────────────

def score_prediction(pred: dict, result: dict) -> dict:
    """Score a single prediction against its result."""
    pick = pred["pick"]
    pick_prob = pred["pick_prob"]
    home_prob = pred["home_win_prob"]
    confidence = pred["confidence"]

    actual_winner = result["winner"]
    home_win = result["home_win"]

    correct = (pick == actual_winner)

    # Brier score component: (forecast - outcome)^2
    # Lower = better. Perfect = 0, worst = 1
    brier = (home_prob - (1.0 if home_win else 0.0)) ** 2

    # Log loss component: -[y*log(p) + (1-y)*log(1-p)]
    # Lower = better. Measures calibration quality.
    p = max(0.001, min(0.999, home_prob))
    y = 1.0 if home_win else 0.0
    logloss = -(y * math.log(p) + (1 - y) * math.log(1 - p))

    # How much edge did the pick have?
    edge = pred["edge"]

    return {
        "game_id": pred["game_id"],
        "date": pred["game_date"],
        "matchup": f"{pred['away_team']} @ {pred['home_team']}",
        "pick": pick,
        "pick_prob": pick_prob,
        "home_prob": home_prob,
        "confidence": confidence,
        "edge": edge,
        "actual_winner": actual_winner,
        "score": result["final_score"],
        "correct": correct,
        "brier": round(brier, 4),
        "logloss": round(logloss, 4),
        "home_win": home_win,

        # Pitchers for analysis
        "away_pitcher": pred.get("away_pitcher", "TBD"),
        "home_pitcher": pred.get("home_pitcher", "TBD"),
        "away_pitcher_score": pred.get("away_pitcher_score", 0),
        "home_pitcher_score": pred.get("home_pitcher_score", 0),
    }


def score_date(date: str) -> Optional[dict]:
    """Score all predictions for a date. Returns summary + individual results."""
    picks_file = PICKS_DIR / f"{date}.json"
    if not picks_file.exists():
        print(f"  No picks file for {date}")
        return None

    with open(picks_file) as f:
        predictions = json.load(f)

    if not predictions:
        return None

    print(f"  Fetching results for {date}...")
    results = fetch_results(date)

    if not results:
        print(f"  No final results yet for {date}")
        return None

    scored = []
    for pred in predictions:
        gid = pred["game_id"]
        if gid not in results:
            print(f"    ⚠ No result for game {gid} ({pred['away_team']} @ {pred['home_team']})")
            continue
        scored.append(score_prediction(pred, results[gid]))

    if not scored:
        return None

    # Aggregate stats
    total = len(scored)
    correct = sum(1 for s in scored if s["correct"])
    avg_brier = sum(s["brier"] for s in scored) / total
    avg_logloss = sum(s["logloss"] for s in scored) / total

    # By confidence tier
    tiers = {}
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        tier_picks = [s for s in scored if s["confidence"] == tier]
        if tier_picks:
            tiers[tier] = {
                "total": len(tier_picks),
                "correct": sum(1 for s in tier_picks if s["correct"]),
                "pct": round(sum(1 for s in tier_picks if s["correct"]) / len(tier_picks), 3),
                "avg_brier": round(sum(s["brier"] for s in tier_picks) / len(tier_picks), 4),
            }

    # Calibration buckets (group by predicted probability)
    cal_buckets = {}
    for s in scored:
        bucket = round(s["pick_prob"] * 10) / 10  # Round to nearest 10%
        bucket_key = f"{bucket:.1f}"
        if bucket_key not in cal_buckets:
            cal_buckets[bucket_key] = {"predicted": [], "actual": []}
        cal_buckets[bucket_key]["predicted"].append(s["pick_prob"])
        cal_buckets[bucket_key]["actual"].append(1 if s["correct"] else 0)

    calibration = {}
    for k, v in sorted(cal_buckets.items()):
        avg_pred = sum(v["predicted"]) / len(v["predicted"])
        avg_actual = sum(v["actual"]) / len(v["actual"])
        calibration[k] = {
            "n": len(v["predicted"]),
            "avg_predicted": round(avg_pred, 3),
            "avg_actual": round(avg_actual, 3),
            "gap": round(avg_actual - avg_pred, 3),
        }

    summary = {
        "date": date,
        "total_games": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy": round(correct / total, 3),
        "avg_brier": round(avg_brier, 4),
        "avg_logloss": round(avg_logloss, 4),
        "by_confidence": tiers,
        "calibration": calibration,
        "baseline_brier": 0.25,  # What you'd get always predicting 50/50
        "picks": scored,
    }

    return summary


# ── Reporting ─────────────────────────────────────────────────────────

def season_report(results: list) -> dict:
    """Aggregate season-level stats from multiple date results.
    
    Main stats count ONLY HIGH confidence picks (premium picks).
    Breakdown by tier shows all levels.
    """
    all_picks = []
    for r in results:
        all_picks.extend(r["picks"])

    if not all_picks:
        return {"error": "No scored picks"}

    # Main stats: HIGH confidence only (premium picks for track record)
    high_picks = [p for p in all_picks if p["confidence"] == "HIGH"]
    
    if not high_picks:
        return {"error": "No HIGH confidence picks to track"}
    
    total = len(high_picks)
    correct = sum(1 for p in high_picks if p["correct"])
    avg_brier = sum(p["brier"] for p in high_picks) / total
    avg_logloss = sum(p["logloss"] for p in high_picks) / total

    # By confidence
    tiers = {}
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        tp = [p for p in all_picks if p["confidence"] == tier]
        if tp:
            c = sum(1 for p in tp if p["correct"])
            tiers[tier] = {
                "total": len(tp),
                "correct": c,
                "pct": round(c / len(tp), 3),
                "avg_brier": round(sum(p["brier"] for p in tp) / len(tp), 4),
                "avg_edge": round(sum(p["edge"] for p in tp) / len(tp), 3),
            }

    # Calibration across HIGH picks only
    cal_buckets = {}
    for p in high_picks:
        bucket = round(p["pick_prob"] * 20) / 20  # 5% buckets for more granularity
        bucket_key = f"{bucket:.2f}"
        if bucket_key not in cal_buckets:
            cal_buckets[bucket_key] = {"predicted": [], "actual": []}
        cal_buckets[bucket_key]["predicted"].append(p["pick_prob"])
        cal_buckets[bucket_key]["actual"].append(1 if p["correct"] else 0)

    calibration = {}
    for k, v in sorted(cal_buckets.items()):
        avg_pred = sum(v["predicted"]) / len(v["predicted"])
        avg_actual = sum(v["actual"]) / len(v["actual"])
        calibration[k] = {
            "n": len(v["predicted"]),
            "avg_predicted": round(avg_pred, 3),
            "avg_actual": round(avg_actual, 3),
            "gap": round(avg_actual - avg_pred, 3),
        }

    # Biggest wins and losses (by edge) - HIGH picks only
    correct_picks = sorted([p for p in high_picks if p["correct"]], key=lambda x: x["edge"], reverse=True)
    wrong_picks = sorted([p for p in high_picks if not p["correct"]], key=lambda x: x["edge"], reverse=True)

    # ROI simulation: flat bet on HIGH picks only
    # If pick_prob > implied odds (50%), calculate profit at -110 juice
    roi_units = 0
    for p in high_picks:
        if p["correct"]:
            roi_units += 0.909  # Win at -110 odds
        else:
            roi_units -= 1.0

    return {
        "dates_tracked": len(results),
        "total_picks": total,
        "correct": correct,
        "wrong": total - correct,
        "accuracy": round(correct / total, 3),
        "avg_brier": round(avg_brier, 4),
        "avg_logloss": round(avg_logloss, 4),
        "baseline_brier": 0.25,
        "brier_skill": round(1 - (avg_brier / 0.25), 4),  # >0 = beating coin flip
        "by_confidence": tiers,
        "calibration": calibration,
        "roi_units": round(roi_units, 2),
        "roi_pct": round((roi_units / total) * 100, 1) if total > 0 else 0,
        "best_wins": [{"matchup": p["matchup"], "pick": p["pick"], "prob": p["pick_prob"], "score": p["score"]} for p in correct_picks[:5]],
        "worst_misses": [{"matchup": p["matchup"], "pick": p["pick"], "prob": p["pick_prob"], "score": p["score"]} for p in wrong_picks[:5]],
    }


def format_report_discord(report: dict) -> str:
    """Format season report for Discord."""
    lines = []
    lines.append("# 📊 MLB Predictor — Season Report\n")
    lines.append(f"**{report['dates_tracked']}** days tracked | **{report['total_picks']}** total picks\n")

    # Record
    lines.append(f"## Record: {report['correct']}-{report['wrong']} ({report['accuracy']*100:.1f}%)")

    # Key metrics
    lines.append(f"> **Brier Score:** {report['avg_brier']:.4f} (baseline .2500 — {'✅ beating' if report['avg_brier'] < 0.25 else '❌ losing to'} coin flip)")
    lines.append(f"> **Brier Skill:** {report['brier_skill']:.2%} {'📈' if report['brier_skill'] > 0 else '📉'}")
    lines.append(f"> **Log Loss:** {report['avg_logloss']:.4f}")
    lines.append(f"> **Flat-bet ROI:** {report['roi_pct']:+.1f}% ({report['roi_units']:+.2f} units)\n")

    # By confidence
    lines.append("## By Confidence Tier")
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        t = report["by_confidence"].get(tier)
        if t:
            emoji = {"HIGH": "🔥", "MEDIUM": "✅", "LOW": "⚪"}[tier]
            lines.append(f"{emoji} **{tier}:** {t['correct']}/{t['total']} ({t['pct']*100:.0f}%) — Brier {t['avg_brier']:.4f} — Avg edge {t['avg_edge']*100:.1f}%")

    # Calibration
    lines.append("\n## Calibration")
    lines.append("```")
    lines.append("Predicted  | Actual  | N   | Gap")
    lines.append("-----------|---------|-----|-------")
    for k, v in report["calibration"].items():
        bar = "█" * max(0, round(v["avg_actual"] * 20))
        lines.append(f"  {v['avg_predicted']*100:5.1f}%   | {v['avg_actual']*100:5.1f}% | {v['n']:3d} | {v['gap']*100:+5.1f}%  {bar}")
    lines.append("```")

    # Best/worst
    if report.get("best_wins"):
        lines.append("\n**Best calls:**")
        for w in report["best_wins"][:3]:
            lines.append(f"> ✅ {w['matchup']} — {w['pick']} ({w['prob']*100:.0f}%) — {w['score']}")
    if report.get("worst_misses"):
        lines.append("\n**Worst misses:**")
        for m in report["worst_misses"][:3]:
            lines.append(f"> ❌ {m['matchup']} — {m['pick']} ({m['prob']*100:.0f}%) — {m['score']}")

    return "\n".join(lines)


def format_date_discord(summary: dict) -> str:
    """Format single-day results for Discord."""
    lines = []
    date = summary["date"]
    lines.append(f"# 📋 Results — {date}\n")
    lines.append(f"**{summary['correct']}/{summary['total_games']}** correct ({summary['accuracy']*100:.0f}%) | Brier: {summary['avg_brier']:.4f}\n")

    for p in summary["picks"]:
        emoji = "✅" if p["correct"] else "❌"
        lines.append(f"{emoji} {p['matchup']} — Picked **{p['pick']}** ({p['pick_prob']*100:.0f}%) → {p['actual_winner']} wins {p['score']}")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────

def backfill_all():
    """Score all existing picks files."""
    RESULTS_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    all_results = []
    for picks_file in sorted(PICKS_DIR.glob("*.json")):
        date = picks_file.stem
        print(f"\n📅 {date}...")
        summary = score_date(date)
        if summary:
            all_results.append(summary)
            # Save individual results
            with open(RESULTS_DIR / f"{date}.json", "w") as f:
                json.dump(summary, f, indent=2)
            print(f"   → {summary['correct']}/{summary['total_games']} correct ({summary['accuracy']*100:.0f}%)")

    if all_results:
        report = season_report(all_results)
        with open(REPORT_DIR / "season.json", "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*50}")
        print(f"SEASON: {report['correct']}/{report['total_picks']} ({report['accuracy']*100:.1f}%)")
        print(f"Brier: {report['avg_brier']:.4f} (skill: {report['brier_skill']:.2%})")
        print(f"Log Loss: {report['avg_logloss']:.4f}")
        print(f"ROI: {report['roi_pct']:+.1f}%")

        return report, all_results
    return None, []


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--backfill":
            report, results = backfill_all()
            if report:
                print("\n" + format_report_discord(report))
        elif arg == "--report":
            # Load existing results
            RESULTS_DIR.mkdir(exist_ok=True)
            results = []
            for f in sorted(RESULTS_DIR.glob("*.json")):
                with open(f) as fh:
                    results.append(json.load(fh))
            if results:
                report = season_report(results)
                print(format_report_discord(report))
            else:
                print("No results yet. Run with --backfill first.")
        else:
            # Specific date
            summary = score_date(arg)
            if summary:
                RESULTS_DIR.mkdir(exist_ok=True)
                with open(RESULTS_DIR / f"{arg}.json", "w") as f:
                    json.dump(summary, f, indent=2)
                print(format_date_discord(summary))
    else:
        # Default: backfill everything
        backfill_all()
