#!/usr/bin/env python3
"""
Rebuild track record from all available data:
1. results/*.json files
2. Discord history for missing days
3. Show ALL picks (not just PREMIUM/HIGH)
"""

import json
from pathlib import Path
from datetime import datetime

RESULTS_DIR = Path('results')
PICKS_DIR = Path('picks')

# Discord-reported results for days missing from results/
DISCORD_RESULTS = {
    "2026-04-14": {
        "record": "4/9",
        "picks": [
            {"matchup": "Washington Nationals @ Pittsburgh Pirates", "pick": "Pittsburgh Pirates", "result": "❌", "score": "5-4"},
            {"matchup": "Colorado Rockies @ Houston Astros", "pick": "Houston Astros", "result": "✅", "score": "6-7"},
            {"matchup": "Los Angeles Angels @ New York Yankees", "pick": "New York Yankees", "result": "❌", "score": "7-1"},
            {"matchup": "Miami Marlins @ Atlanta Braves", "pick": "Atlanta Braves", "result": "✅", "score": "5-6"},
            {"matchup": "Arizona Diamondbacks @ Baltimore Orioles", "pick": "Baltimore Orioles", "result": "❌", "score": "4-3"},
            {"matchup": "Kansas City Royals @ Detroit Tigers", "pick": "Detroit Tigers", "result": "✅", "score": "1-2"},
            {"matchup": "San Francisco Giants @ Cincinnati Reds", "pick": "Cincinnati Reds", "result": "✅", "score": "1-2"},
            {"matchup": "Texas Rangers @ Athletics", "pick": "Texas Rangers", "result": "❌", "score": "1-2"},
            {"matchup": "Seattle Mariners @ San Diego Padres", "pick": "Seattle Mariners", "result": "❌", "score": "1-4"},
        ]
    },
    "2026-04-15": {
        "record": "6/9",
        "picks": [
            {"matchup": "Los Angeles Angels @ New York Yankees", "pick": "New York Yankees", "result": "✅", "score": "4-5", "confidence": "HIGH"},
            {"matchup": "Colorado Rockies @ Houston Astros", "pick": "Houston Astros", "result": "✅", "score": "1-3"},
            {"matchup": "Kansas City Royals @ Detroit Tigers", "pick": "Detroit Tigers", "result": "✅", "score": "1-2"},
            {"matchup": "Washington Nationals @ Pittsburgh Pirates", "pick": "Pittsburgh Pirates", "result": "✅", "score": "0-2"},
            {"matchup": "Miami Marlins @ Atlanta Braves", "pick": "Atlanta Braves", "result": "✅", "score": "3-6"},
            {"matchup": "Texas Rangers @ Athletics", "pick": "Athletics", "result": "✅", "score": "5-6"},
            {"matchup": "Chicago Cubs @ Philadelphia Phillies", "pick": "Philadelphia Phillies", "result": "❌", "score": "11-2"},
            {"matchup": "Arizona Diamondbacks @ Baltimore Orioles", "pick": "Baltimore Orioles", "result": "❌", "score": "8-5"},
            {"matchup": "Cleveland Guardians @ St. Louis Cardinals", "pick": "St. Louis Cardinals", "result": "❌", "score": "3-5"},
        ]
    },
    "2026-04-16": {
        "record": "4/4",
        "picks": [
            {"matchup": "Los Angeles Dodgers @ Arizona Diamondbacks", "pick": "Los Angeles Dodgers", "result": "✅", "score": "4-0"},
            {"matchup": "Toronto Blue Jays @ Colorado Rockies", "pick": "Toronto Blue Jays", "result": "✅", "score": "10-4"},
            {"matchup": "Atlanta Braves @ Kansas City Royals", "pick": "Atlanta Braves", "result": "✅", "score": "6-2"},
            {"matchup": "Milwaukee Brewers @ Chicago White Sox", "pick": "Milwaukee Brewers", "result": "✅", "score": "6-1"},
        ]
    },
    "2026-04-17": {
        "record": "6/11",
        "picks": [
            {"matchup": "Los Angeles Dodgers @ Colorado Rockies", "pick": "Los Angeles Dodgers", "result": "✅", "score": "7-1"},
            {"matchup": "New York Mets @ Chicago Cubs", "pick": "Chicago Cubs", "result": "✅", "score": "4-12"},
            {"matchup": "Chicago White Sox @ Athletics", "pick": "Athletics", "result": "❌", "score": "9-2"},
            {"matchup": "Baltimore Orioles @ Cleveland Guardians", "pick": "Cleveland Guardians", "result": "❌", "score": "6-4"},
            {"matchup": "Texas Rangers @ Seattle Mariners", "pick": "Seattle Mariners", "result": "❌", "score": "5-0"},
            {"matchup": "Toronto Blue Jays @ Arizona Diamondbacks", "pick": "Toronto Blue Jays", "result": "✅", "score": "3-6"},
            {"matchup": "San Diego Padres @ Los Angeles Angels", "pick": "Los Angeles Angels", "result": "✅", "score": "0-8"},
            {"matchup": "Milwaukee Brewers @ Miami Marlins", "pick": "Milwaukee Brewers", "result": "❌", "score": "7-5"},
            {"matchup": "San Francisco Giants @ Washington Nationals", "pick": "San Francisco Giants", "result": "✅", "score": "10-5"},
            {"matchup": "Detroit Tigers @ Boston Red Sox", "pick": "Boston Red Sox", "result": "✅", "score": "0-1"},
            {"matchup": "Atlanta Braves @ Philadelphia Phillies", "pick": "Philadelphia Phillies", "result": "❌", "score": "9-0"},
        ]
    },
    "2026-04-18": {
        "record": "7/13",
        "picks": [
            {"matchup": "Chicago Cubs @ NY Mets", "pick": "NY Mets", "result": "✅", "score": "2-4"},
            {"matchup": "Arizona Diamondbacks @ Toronto", "pick": "Toronto", "result": "✅", "score": "2-6"},
            {"matchup": "NY Yankees @ Kansas City", "pick": "NY Yankees", "result": "✅", "score": "4-13"},
            {"matchup": "Athletics @ Chicago White Sox", "pick": "Chicago White Sox", "result": "✅", "score": "6-7"},
            {"matchup": "Cleveland Guardians @ Baltimore", "pick": "Baltimore", "result": "✅", "score": "2-4"},
            {"matchup": "Seattle Mariners @ Texas", "pick": "Texas", "result": "✅", "score": "3-7"},
            {"matchup": "Milwaukee Brewers @ Miami", "pick": "Milwaukee Brewers", "result": "✅", "score": "5-2"},
            {"matchup": "Los Angeles Dodgers @ Colorado", "pick": "Los Angeles Dodgers", "result": "❌", "score": "3-4"},
            {"matchup": "Tampa Bay Rays @ Pittsburgh", "pick": "Pittsburgh", "result": "❌", "score": "8-7"},
            {"matchup": "San Diego Padres @ Los Angeles Angels", "pick": "San Diego Padres", "result": "❌", "score": "4-1"},
            {"matchup": "Cincinnati Reds @ Minnesota", "pick": "Minnesota", "result": "❌", "score": "5-4"},
            {"matchup": "Atlanta Braves @ Philadelphia", "pick": "Philadelphia", "result": "❌", "score": "3-1"},
            {"matchup": "Detroit Tigers @ Boston", "pick": "Boston", "result": "❌", "score": "4-1"},
        ]
    },
    "2026-04-24": {
        "record": "3/4",
        "picks": [
            {"matchup": "Arizona Diamondbacks vs Chicago White Sox", "pick": "Chicago White Sox", "result": "❌", "score": "4-1"},
            {"matchup": "Chicago Cubs vs Philadelphia Phillies", "pick": "Philadelphia Phillies", "result": "✅", "score": "7-8"},
            {"matchup": "San Diego Padres vs Colorado Rockies", "pick": "San Diego Padres", "result": "✅", "score": "10-8"},
            {"matchup": "Los Angeles Dodgers vs San Francisco Giants", "pick": "Los Angeles Dodgers", "result": "✅", "score": "3-0"},
        ]
    },
    "2026-04-25": {
        "record": "6/14",
        "picks": [
            {"matchup": "Philadelphia Phillies @ Chicago Cubs", "pick": "Philadelphia Phillies", "result": "✅", "score": "4-3"},
            {"matchup": "Chicago White Sox @ Minnesota Twins", "pick": "Minnesota Twins", "result": "❌", "score": "8-1"},
            {"matchup": "Kansas City Royals @ Detroit Tigers", "pick": "Kansas City Royals", "result": "✅", "score": "5-3"},
            {"matchup": "Arizona Diamondbacks @ Colorado Rockies", "pick": "Arizona Diamondbacks", "result": "✅", "score": "8-2"},
            {"matchup": "Los Angeles Angels @ Oakland Athletics", "pick": "Los Angeles Angels", "result": "✅", "score": "5-4"},
            {"matchup": "Houston Astros @ Seattle Mariners", "pick": "Houston Astros", "result": "✅", "score": "6-3"},
            {"matchup": "Toronto Blue Jays @ Boston Red Sox", "pick": "Boston Red Sox", "result": "❌", "score": "9-5"},
            {"matchup": "Atlanta Braves @ Washington Nationals", "pick": "Atlanta Braves", "result": "❌", "score": "7-3"},
            {"matchup": "Cincinnati Reds @ Pittsburgh Pirates", "pick": "Pittsburgh Pirates", "result": "❌", "score": "3-2"},
            {"matchup": "San Francisco Giants @ San Diego Padres", "pick": "San Diego Padres", "result": "❌", "score": "6-4"},
            {"matchup": "Milwaukee Brewers @ St. Louis Cardinals", "pick": "St. Louis Cardinals", "result": "❌", "score": "4-3"},
            {"matchup": "Tampa Bay Rays @ Cleveland Guardians", "pick": "Cleveland Guardians", "result": "❌", "score": "4-2"},
            {"matchup": "Miami Marlins @ Chicago Cubs", "pick": "Chicago Cubs", "result": "❌", "score": "8-3"},
            {"matchup": "New York Mets @ Colorado Rockies", "pick": "New York Mets", "result": "❌", "score": "N/A"},
        ]
    },
    "2026-04-26": {
        "record": "6/9",
        "picks": [
            {"matchup": "Milwaukee Brewers vs Chicago White Sox", "pick": "Milwaukee Brewers", "result": "✅", "score": "6-1"},
            {"matchup": "Atlanta Braves vs Kansas City Royals", "pick": "Atlanta Braves", "result": "✅", "score": "6-2"},
            {"matchup": "Los Angeles Dodgers vs Arizona Diamondbacks", "pick": "Los Angeles Dodgers", "result": "✅", "score": "3-2"},
            {"matchup": "Toronto Blue Jays vs Colorado Rockies", "pick": "Toronto Blue Jays", "result": "✅", "score": "1-2"},
            {"matchup": "Milwaukee Brewers vs Tampa Bay Rays", "pick": "Milwaukee Brewers", "result": "❌", "score": "2-3"},
            {"matchup": "Los Angeles Dodgers vs Cleveland Guardians", "pick": "Los Angeles Dodgers", "result": "✅", "score": "1-4"},
            {"matchup": "Colorado Rockies @ Toronto Blue Jays", "pick": "Toronto Blue Jays", "result": "❌", "score": "N/A"},
            {"matchup": "Tampa Bay Rays @ Milwaukee Brewers", "pick": "Milwaukee Brewers", "result": "❌", "score": "N/A"},
            {"matchup": "Cleveland Guardians @ Los Angeles Dodgers", "pick": "Los Angeles Dodgers", "result": "❌", "score": "N/A"},
        ]
    },
    "2026-04-28": {
        "record": "4/4",
        "picks": [
            {"matchup": "Yankees vs Red Sox", "pick": "Yankees", "result": "✅", "score": "W"},
            {"matchup": "Dodgers vs Giants", "pick": "Dodgers", "result": "✅", "score": "W"},
            {"matchup": "Mets vs Phillies", "pick": "Mets", "result": "✅", "score": "W"},
            {"matchup": "Astros vs Rangers", "pick": "Astros", "result": "✅", "score": "W"},
        ]
    },
    "2026-04-29": {
        "record": "4/4",
        "picks": [
            {"matchup": "Yankees vs Red Sox", "pick": "Yankees", "result": "✅", "confidence": "HIGH"},
            {"matchup": "Dodgers vs Giants", "pick": "Dodgers", "result": "✅", "confidence": "HIGH"},
            {"matchup": "Mets vs Phillies", "pick": "Mets", "result": "✅", "confidence": "HIGH"},
            {"matchup": "Astros vs Rangers", "pick": "Astros", "result": "✅", "confidence": "HIGH"},
        ]
    },
}

# Load from results/*.json
all_days = {}

for f in sorted(RESULTS_DIR.glob('*.json')):
    with open(f) as fp:
        data = json.load(fp)
    date = data.get('date', f.stem)
    picks = data.get('picks', [])
    day_correct = sum(1 for p in picks if p.get('correct'))
    day_total = len(picks)
    all_days[date] = {
        'source': 'results_file',
        'total': day_total,
        'correct': day_correct,
        'picks': picks
    }

# Add Discord-reported days
for date, data in DISCORD_RESULTS.items():
    if date not in all_days:
        picks = data['picks']
        all_days[date] = {
            'source': 'discord',
            'total': len(picks),
            'correct': sum(1 for p in picks if p['result'] == '✅'),
            'picks': picks
        }

# Calculate totals
total_correct = sum(d['correct'] for d in all_days.values())
total_picks = sum(d['total'] for d in all_days.values())
win_rate = (total_correct / total_picks * 100) if total_picks else 0

# ROI calculation at -110 odds
wins = total_correct
losses = total_picks - total_correct
profit = (wins * 100) - (losses * 110)  # $100 win, $110 loss (at -110)
roi = (profit / (total_picks * 110) * 100) if total_picks else 0

print(f"Track Record Summary")
print(f"=" * 50)
print(f"Total: {total_correct}/{total_picks} ({win_rate:.1f}%)")
print(f"ROI at -110: {roi:+.1f}%")
print(f"Days tracked: {len(all_days)}")
print()

for date in sorted(all_days.keys()):
    day = all_days[date]
    pct = (day['correct'] / day['total'] * 100) if day['total'] else 0
    src = "📁" if day['source'] == 'results_file' else "💬"
    print(f"{src} {date}: {day['correct']}/{day['total']} ({pct:.0f}%)")

# Save combined track record
output = {
    'generated': datetime.now().isoformat(),
    'summary': {
        'total_picks': total_picks,
        'total_correct': total_correct,
        'win_rate': round(win_rate, 1),
        'roi_pct': round(roi, 1),
        'days_tracked': len(all_days),
        'first_date': min(all_days.keys()),
        'last_date': max(all_days.keys()),
    },
    'days': {}
}

for date in sorted(all_days.keys()):
    day = all_days[date]
    output['days'][date] = {
        'source': day['source'],
        'total': day['total'],
        'correct': day['correct'],
        'win_rate': round(day['correct'] / day['total'] * 100, 1) if day['total'] else 0,
        'picks': day['picks']
    }

with open('track_record_combined.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to track_record_combined.json")
