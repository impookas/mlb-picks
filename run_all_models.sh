#!/bin/bash
# Today's date
TODAY=$(date +%Y-%m-%d)

echo "Running MLB prediction models for $TODAY..."
echo "============================================"

# Run v2
echo "Running v2 model..."
python3 model/predictor_v2.py $TODAY

# Run v3  
echo "Running v3 model..."
python3 model/predictor_v3.py $TODAY

# Run v4 ensemble
echo "Running v4 ensemble model..."
python3 model/predictor_v4.py $TODAY