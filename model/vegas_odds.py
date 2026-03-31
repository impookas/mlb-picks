#!/usr/bin/env python3
"""Scrape Vegas odds from ESPN API."""

import json
import urllib.request

def american_to_prob(odds_str):
    """Convert American odds to implied probability."""
    odds_str = odds_str.strip()
    if odds_str.startswith('+'):
        odds = int(odds_str[1:])
        return round(100 / (odds + 100), 3)
    elif odds_str.startswith('-'):
        odds = int(odds_str[1:])
        return round(odds / (odds + 100), 3)
    return 0.5

def fetch_vegas_odds():
    """Fetch current Vegas odds from ESPN."""
    url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=10).read())
    except:
        return {}
    
    odds_map = {}
    for event in data.get('events', []):
        comp = event.get('competitions', [{}])[0]
        teams = comp.get('competitors', [])
        away = next((t for t in teams if t.get('homeAway') == 'away'), {})
        home = next((t for t in teams if t.get('homeAway') == 'home'), {})
        
        away_name = away.get('team', {}).get('displayName', '')
        home_name = home.get('team', {}).get('displayName', '')
        
        odds_data = comp.get('odds', [{}])[0] if comp.get('odds') else {}
        moneyline = odds_data.get('moneyline', {})
        
        if moneyline:
            away_ml = moneyline.get('away', {}).get('close', {}).get('odds', '+100')
            home_ml = moneyline.get('home', {}).get('close', {}).get('odds', '+100')
            
            game_key = f"{away_name} @ {home_name}"
            odds_map[game_key] = {
                "away_ml": away_ml,
                "home_ml": home_ml,
                "away_prob": american_to_prob(away_ml),
                "home_prob": american_to_prob(home_ml),
            }
    
    return odds_map

if __name__ == "__main__":
    odds = fetch_vegas_odds()
    for game, data in odds.items():
        print(f"{game}")
        print(f"  Vegas: {data['home_ml']} ({data['home_prob']*100:.1f}%)")
