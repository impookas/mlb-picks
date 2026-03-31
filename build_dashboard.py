#!/usr/bin/env python3
"""Build the dashboard HTML with embedded prediction data."""

import json
import os
import glob

PICKS_DIR = os.path.join(os.path.dirname(__file__), "picks")
TRACKER_FILE = os.path.join(os.path.dirname(__file__), "tracker", "results.json")
TEMPLATE = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
OUTPUT = os.path.join(os.path.dirname(__file__), "dashboard", "live.html")


def build():
    # Load all pick files
    picks_by_date = {}
    for f in sorted(glob.glob(os.path.join(PICKS_DIR, "*.json"))):
        date = os.path.basename(f).replace(".json", "")
        with open(f) as fh:
            picks_by_date[date] = json.load(fh)

    # Load results tracker
    results = []
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE) as f:
            results = json.load(f)

    # Read template
    with open(TEMPLATE) as f:
        html = f.read()

    # Inject data
    html = html.replace(
        "/*PICKS_JSON*/null/*END_PICKS_JSON*/",
        json.dumps(picks_by_date)
    )
    html = html.replace(
        "/*RESULTS_JSON*/null/*END_RESULTS_JSON*/",
        json.dumps(results)
    )

    # Write output
    with open(OUTPUT, "w") as f:
        f.write(html)

    print(f"✅ Dashboard built: {OUTPUT}")
    print(f"   {len(picks_by_date)} days of picks, {len(results)} tracked results")


if __name__ == "__main__":
    build()
