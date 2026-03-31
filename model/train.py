#!/usr/bin/env python3
"""
Train prediction models on extracted feature data.
Uses time-based cross-validation (no future leakage).

Models:
1. Logistic Regression (interpretable, baseline)
2. Gradient Boosting (more powerful, handles interactions)
3. Ensemble (blend of both)

Outputs:
- Learned weights / model coefficients
- Cross-validated accuracy, Brier score, calibration
- Saved model for use in predictor_v3
"""

import json
import math
import csv
import pickle
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
TRAINING_DIR = ROOT / "training"
MODEL_DIR = ROOT / "model" / "learned"

# Feature columns used for prediction (differentials + context)
FEATURE_COLS = [
    "pitcher_diff",
    "pitcher_season_diff",
    "pitcher_recent_diff",
    "offense_diff",
    "bullpen_diff",
    "pyth_diff",
    "home_home_pct",
    "away_road_pct",
    "park_factor",
    "home_pitcher_combined",
    "away_pitcher_combined",
    "home_offense",
    "away_offense",
    "home_bullpen",
    "away_bullpen",
    "home_pyth",
    "away_pyth",
    "home_pitcher_ip",
    "away_pitcher_ip",
]


def load_data(filepath):
    with open(filepath) as f:
        rows = json.load(f)
    print(f"  Loaded {len(rows)} games")
    return rows


def extract_xy(rows, features=FEATURE_COLS):
    X = []
    y = []
    meta = []
    for r in rows:
        try:
            x = [float(r[f]) for f in features]
            X.append(x)
            y.append(r["home_win"])
            meta.append({"date": r["date"], "game_id": r["game_id"],
                         "away_team": r["away_team"], "home_team": r["home_team"]})
        except (KeyError, ValueError, TypeError):
            continue
    return X, y, meta


# ── Logistic Regression (from scratch, no sklearn needed) ──

def sigmoid(z):
    z = max(-500, min(500, z))
    return 1.0 / (1.0 + math.exp(-z))


def logistic_regression_train(X, y, lr=0.001, epochs=2000, l2=0.01):
    """Train logistic regression with gradient descent + L2 regularization."""
    n_features = len(X[0])
    n_samples = len(X)
    weights = [0.0] * n_features
    bias = 0.0

    for epoch in range(epochs):
        dw = [0.0] * n_features
        db = 0.0

        for i in range(n_samples):
            z = sum(w * x for w, x in zip(weights, X[i])) + bias
            pred = sigmoid(z)
            error = pred - y[i]
            for j in range(n_features):
                dw[j] += error * X[i][j]
            db += error

        for j in range(n_features):
            weights[j] -= lr * (dw[j] / n_samples + l2 * weights[j])
        bias -= lr * (db / n_samples)

        if epoch % 500 == 0:
            loss = 0
            for i in range(n_samples):
                z = sum(w * x for w, x in zip(weights, X[i])) + bias
                p = sigmoid(z)
                p = max(1e-7, min(1-1e-7, p))
                loss += -(y[i] * math.log(p) + (1-y[i]) * math.log(1-p))
            loss /= n_samples
            print(f"    Epoch {epoch}: loss={loss:.4f}")

    return weights, bias


def logistic_regression_predict(X, weights, bias):
    preds = []
    for x in X:
        z = sum(w * xi for w, xi in zip(weights, x)) + bias
        preds.append(sigmoid(z))
    return preds


# ── Gradient Boosting (simple decision stumps, no sklearn) ──

class Stump:
    def __init__(self):
        self.feature = 0
        self.threshold = 0
        self.left_val = 0
        self.right_val = 0

    def predict_one(self, x):
        if x[self.feature] <= self.threshold:
            return self.left_val
        return self.right_val

    def predict(self, X):
        return [self.predict_one(x) for x in X]


def fit_stump(X, residuals, feature_indices):
    """Find best split across all features with more threshold candidates."""
    best_stump = Stump()
    best_loss = float('inf')
    n = len(X)

    for fi in feature_indices:
        vals = sorted(set(x[fi] for x in X))
        # More threshold candidates for better resolution
        if len(vals) <= 50:
            thresholds = [(vals[i] + vals[i+1]) / 2 for i in range(len(vals)-1)]
        else:
            step = max(1, len(vals) // 50)
            thresholds = [(vals[i] + vals[min(i+step, len(vals)-1)]) / 2 for i in range(0, len(vals)-1, step)]

        for t in thresholds:
            left_idx = [i for i in range(n) if X[i][fi] <= t]
            right_idx = [i for i in range(n) if X[i][fi] > t]
            if len(left_idx) < 5 or len(right_idx) < 5:
                continue
            left = [residuals[i] for i in left_idx]
            right = [residuals[i] for i in right_idx]
            left_mean = sum(left) / len(left)
            right_mean = sum(right) / len(right)
            loss = sum((r - left_mean)**2 for r in left) + sum((r - right_mean)**2 for r in right)
            if loss < best_loss:
                best_loss = loss
                best_stump.feature = fi
                best_stump.threshold = t
                best_stump.left_val = left_mean
                best_stump.right_val = right_mean

    return best_stump


def gradient_boosting_train(X, y, n_trees=200, lr=0.05, max_features=None):
    """Simple gradient boosting with decision stumps."""
    n = len(X)
    n_feat = len(X[0])
    feature_indices = list(range(n_feat))

    # Initialize with log-odds of base rate
    base_rate = sum(y) / len(y)
    base_pred = math.log(base_rate / (1 - base_rate))
    preds = [base_pred] * n
    trees = []

    for t in range(n_trees):
        # Compute residuals (negative gradient of log loss)
        residuals = []
        for i in range(n):
            p = sigmoid(preds[i])
            residuals.append(y[i] - p)

        # Fit stump to residuals
        stump = fit_stump(X, residuals, feature_indices)
        trees.append(stump)

        # Update predictions
        stump_preds = stump.predict(X)
        for i in range(n):
            preds[i] += lr * stump_preds[i]

        if t % 50 == 0:
            loss = 0
            for i in range(n):
                p = sigmoid(preds[i])
                p = max(1e-7, min(1-1e-7, p))
                loss += -(y[i]*math.log(p) + (1-y[i])*math.log(1-p))
            loss /= n
            print(f"    Tree {t}: loss={loss:.4f}")

    return trees, base_pred, lr


def gradient_boosting_predict(X, trees, base_pred, lr):
    n = len(X)
    preds = [base_pred] * n
    for tree in trees:
        tp = tree.predict(X)
        for i in range(n):
            preds[i] += lr * tp[i]
    return [sigmoid(p) for p in preds]


# ── Evaluation ──

def evaluate(y_true, y_pred, label=""):
    n = len(y_true)
    # Accuracy (at 0.5 threshold)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if (yp >= 0.5) == (yt == 1))
    acc = correct / n

    # Brier score
    brier = sum((yp - yt)**2 for yt, yp in zip(y_true, y_pred)) / n
    skill = 1 - brier / 0.25

    # Log loss
    ll = 0
    for yt, yp in zip(y_true, y_pred):
        yp = max(1e-7, min(1-1e-7, yp))
        ll += -(yt*math.log(yp) + (1-yt)*math.log(1-yp))
    ll /= n

    # Calibration (5% buckets)
    cal = defaultdict(lambda: {"pred": [], "actual": []})
    for yt, yp in zip(y_true, y_pred):
        b = round(yp * 20) / 20
        cal[f"{b:.2f}"]["pred"].append(yp)
        cal[f"{b:.2f}"]["actual"].append(yt)

    print(f"\n  {label}")
    print(f"  {'='*40}")
    print(f"  Accuracy: {acc*100:.1f}% ({correct}/{n})")
    print(f"  Brier:    {brier:.4f} (skill: {skill:.2%})")
    print(f"  Log Loss: {ll:.4f}")
    print(f"  Calibration:")
    for k in sorted(cal.keys()):
        v = cal[k]
        ap = sum(v["pred"])/len(v["pred"])
        aa = sum(v["actual"])/len(v["actual"])
        print(f"    {ap*100:5.1f}% → {aa*100:5.1f}% (n={len(v['pred']):4d}, gap={aa-ap:+.3f})")

    return {"accuracy": acc, "brier": brier, "skill": skill, "logloss": ll}


# ── Time-based Cross-Validation ──

def time_cv(rows, features=FEATURE_COLS, n_folds=4):
    """Split by time: train on earlier months, test on later."""
    sorted_rows = sorted(rows, key=lambda r: r["date"])
    n = len(sorted_rows)
    fold_size = n // n_folds

    all_lr_results = []
    all_gb_results = []

    for fold in range(1, n_folds):
        train_end = fold * fold_size
        test_end = min((fold + 1) * fold_size, n)

        train_rows = sorted_rows[:train_end]
        test_rows = sorted_rows[train_end:test_end]

        train_dates = f"{train_rows[0]['date']} to {train_rows[-1]['date']}"
        test_dates = f"{test_rows[0]['date']} to {test_rows[-1]['date']}"
        print(f"\n  Fold {fold}: Train {len(train_rows)} ({train_dates}) → Test {len(test_rows)} ({test_dates})")

        X_train, y_train, _ = extract_xy(train_rows, features)
        X_test, y_test, _ = extract_xy(test_rows, features)

        # Normalize features
        means = [sum(x[j] for x in X_train)/len(X_train) for j in range(len(features))]
        stds = [max(1e-8, (sum((x[j]-means[j])**2 for x in X_train)/len(X_train))**0.5) for j in range(len(features))]

        X_train_n = [[(x[j]-means[j])/stds[j] for j in range(len(features))] for x in X_train]
        X_test_n = [[(x[j]-means[j])/stds[j] for j in range(len(features))] for x in X_test]

        # Logistic Regression
        print(f"\n  Training Logistic Regression...")
        weights, bias = logistic_regression_train(X_train_n, y_train, lr=0.01, epochs=3000, l2=0.1)
        lr_preds = logistic_regression_predict(X_test_n, weights, bias)
        lr_res = evaluate(y_test, lr_preds, f"Logistic Regression (Fold {fold})")
        all_lr_results.append(lr_res)

        # Gradient Boosting
        print(f"\n  Training Gradient Boosting...")
        trees, base, lr_gb = gradient_boosting_train(X_train_n, y_train, n_trees=150, lr=0.05)
        gb_preds = gradient_boosting_predict(X_test_n, trees, base, lr_gb)
        gb_res = evaluate(y_test, gb_preds, f"Gradient Boosting (Fold {fold})")
        all_gb_results.append(gb_res)

    # Average results
    print(f"\n{'='*50}")
    print(f"  CROSS-VALIDATION SUMMARY")
    print(f"{'='*50}")
    for label, results in [("Logistic Regression", all_lr_results), ("Gradient Boosting", all_gb_results)]:
        avg_acc = sum(r["accuracy"] for r in results) / len(results)
        avg_brier = sum(r["brier"] for r in results) / len(results)
        avg_skill = sum(r["skill"] for r in results) / len(results)
        avg_ll = sum(r["logloss"] for r in results) / len(results)
        print(f"\n  {label}:")
        print(f"    Accuracy:    {avg_acc*100:.1f}%")
        print(f"    Brier Score: {avg_brier:.4f}")
        print(f"    Brier Skill: {avg_skill:.2%}")
        print(f"    Log Loss:    {avg_ll:.4f}")


def train_final(rows, features=FEATURE_COLS):
    """Train final models on ALL data and save."""
    X, y, meta = extract_xy(rows, features)
    n = len(X)

    # Normalize
    means = [sum(x[j] for x in X)/n for j in range(len(features))]
    stds = [max(1e-8, (sum((x[j]-means[j])**2 for x in X)/n)**0.5) for j in range(len(features))]
    X_n = [[(x[j]-means[j])/stds[j] for j in range(len(features))] for x in X]

    # Train Logistic Regression
    print(f"\n  Training final Logistic Regression on {n} games...")
    weights, bias = logistic_regression_train(X_n, y, lr=0.01, epochs=5000, l2=0.1)

    # Print learned weights
    print(f"\n  Learned Weights:")
    weight_pairs = sorted(zip(features, weights), key=lambda x: abs(x[1]), reverse=True)
    for feat, w in weight_pairs:
        print(f"    {feat:30s}: {w:+.4f}")
    print(f"    {'bias':30s}: {bias:+.4f}")

    # Evaluate on training data (for reference)
    lr_preds = logistic_regression_predict(X_n, weights, bias)
    evaluate(y, lr_preds, "Logistic Regression (Full Training Set)")

    # Train Gradient Boosting
    print(f"\n  Training final Gradient Boosting on {n} games...")
    trees, base, lr_gb = gradient_boosting_train(X_n, y, n_trees=400, lr=0.03)
    gb_preds = gradient_boosting_predict(X_n, trees, base, lr_gb)
    evaluate(y, gb_preds, "Gradient Boosting (Full Training Set)")

    # Ensemble
    ens_preds = [(l + g) / 2 for l, g in zip(lr_preds, gb_preds)]
    evaluate(y, ens_preds, "Ensemble (Full Training Set)")

    # Save models
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_data = {
        "features": features,
        "means": means,
        "stds": stds,
        "lr_weights": weights,
        "lr_bias": bias,
        "gb_trees_count": len(trees),
        "gb_base_pred": base,
        "gb_lr": lr_gb,
    }
    with open(MODEL_DIR / "model_config.json", "w") as f:
        json.dump(model_data, f, indent=2)

    # Save GB trees with pickle
    with open(MODEL_DIR / "gb_trees.pkl", "wb") as f:
        pickle.dump(trees, f)

    print(f"\n  ✅ Models saved to {MODEL_DIR}")
    return model_data


# ── Main ──

if __name__ == "__main__":
    import sys

    # Find latest features file
    feature_files = sorted(TRAINING_DIR.glob("features_*.json"))
    if not feature_files:
        print("No feature data found. Run extract_features.py first.")
        sys.exit(1)

    latest = feature_files[-1]
    print(f"\n  Loading {latest}...")
    rows = load_data(latest)

    if "--cv" in sys.argv or len(sys.argv) == 1:
        print("\n  Running time-based cross-validation...")
        time_cv(rows)

    if "--train" in sys.argv or len(sys.argv) == 1:
        print("\n  Training final models...")
        train_final(rows)
