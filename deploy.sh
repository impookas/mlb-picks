#!/bin/bash
set -e
cd "$(dirname "$0")"

source ~/.openclaw/credentials/github.env

# Generate today's picks with v4 model (ensemble of v2 + v3)
python3 model/predictor_v4.py
python3 site/generate_v3.py

# Deploy to GitHub Pages
git checkout main
git add site/public/*.html picks/*.json results/*.json reports/*.json
git commit -m "Update picks $(date +%Y-%m-%d)" || true
git push origin main

# Update gh-pages branch
git checkout gh-pages
cp site/public/*.html .
git add *.html
git commit -m "Deploy $(date +%Y-%m-%d)" || true
git push origin gh-pages
git checkout main

echo "✅ Deployed to https://impookas.github.io/mlb-picks/"
