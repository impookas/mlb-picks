#!/bin/bash
set -e
cd "$(dirname "$0")"

# Generate today's picks with v4 model (ensemble of v2 + v3)
python3 model/predictor_v4.py
python3 site/generate_v2.py

# Deploy to bloguin.com/picks/ (free, unlimited bandwidth)
rsync -avz -e "ssh -i ~/.ssh/id_franny" site/public/ bloguin@104.236.69.169:files/public/picks/ 2>&1 | tail -5
echo "✅ Deployed to https://bloguin.com/picks/"
