#!/bin/bash
set -e
cd "$(dirname "$0")"
source ~/.openclaw/credentials/github.env
python3 model/predictor_v4.py
python3 site/premium_design.py
git checkout main
git add site/public/*.html
git commit -m "Update picks $(date +%Y-%m-%d)" || true
git push origin main
git checkout gh-pages
cp -f site/public/*.html .
git add index.html track-record.html how-it-works.html
git commit -m "Deploy $(date +%Y-%m-%d)" || true
git push origin gh-pages
git checkout main
echo "✅ Deployed to https://impookas.github.io/mlb-picks/"
