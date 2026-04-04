"""
ShieldPay – Fraud Detection Model Training
RandomForestClassifier with hyperparameter tuning.
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve,
    accuracy_score, f1_score
)
from sklearn.utils.class_weight import compute_class_weight

# ✅ Ensure directories exist (kept your original + enhanced)
os.makedirs("./models", exist_ok=True)
os.makedirs("./results", exist_ok=True)
os.makedirs("ml/models", exist_ok=True)
os.makedirs("ml/results", exist_ok=True)


def load_data():
    path = "./data/fraud_dataset.csv"
    if not os.path.exists(path):
        print("Dataset not found. Generating...")
        import sys
        sys.path.insert(0, ".")
        from generate_dataset import generate_fraud_dataset
        generate_fraud_dataset()

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} samples | Fraud rate: {df['is_fraud'].mean():.1%}")
    return df


def preprocess(df: pd.DataFrame):
    FEATURES = [
        "login_variance",
        "claim_interval_std",
        "session_duration_mean",
        "income_deviation",
        "claim_velocity_7d",
    ]
    TARGET = "is_fraud"

    X = df[FEATURES].values
    y = df[TARGET].values

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=42, stratify=y_trainval
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test)

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    print(f"Fraud in train: {y_train.mean():.1%} | val: {y_val.mean():.1%} | test: {y_test.mean():.1%}")

    return X_train_s, X_val_s, X_test_s, y_train, y_val, y_test, scaler, FEATURES


def train_model(X_train, y_train):
    class_weights = compute_class_weight(
        class_weight="balanced", classes=np.unique(y_train), y=y_train
    )
    cw_dict = {0: class_weights[0], 1: class_weights[1]}
    print(f"Class weights: {cw_dict}")

    rf_model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features="sqrt",
        class_weight=cw_dict,
        n_jobs=-1,
        random_state=42,
    )
    rf_model.fit(X_train, y_train)
    print("✓ RandomForest trained")

    gb_model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    gb_model.fit(X_train, y_train)
    print("✓ GradientBoosting trained")

    return rf_model, gb_model


def evaluate_model(model, X_val, y_val, X_test, y_test, model_name="Model"):
    print(f"\n{'='*50}")
    print(f"Model: {model_name}")
    print(f"{'='*50}")

    y_val_pred = model.predict(X_val)
    y_val_prob = model.predict_proba(X_val)[:, 1]
    y_test_pred = model.predict(X_test)
    y_test_prob = model.predict_proba(X_test)[:, 1]

    val_acc = accuracy_score(y_val, y_val_pred)
    test_acc = accuracy_score(y_test, y_test_pred)
    val_auc = roc_auc_score(y_val, y_val_prob)
    test_auc = roc_auc_score(y_test, y_test_prob)
    val_f1 = f1_score(y_val, y_val_pred)
    test_f1 = f1_score(y_test, y_test_pred)

    print(f"\nValidation: Acc={val_acc:.4f} | AUC={val_auc:.4f} | F1={val_f1:.4f}")
    print(f"Test:       Acc={test_acc:.4f} | AUC={test_auc:.4f} | F1={test_f1:.4f}")

    print(classification_report(y_test, y_test_pred))
    print(confusion_matrix(y_test, y_test_pred))

    return {
        "model_name": model_name,
        "val_accuracy": round(val_acc, 4),
        "test_accuracy": round(test_acc, 4),
        "val_auc_roc": round(val_auc, 4),
        "test_auc_roc": round(test_auc, 4),
        "val_f1": round(val_f1, 4),
        "test_f1": round(test_f1, 4),
    }, y_test_prob


def plot_results(rf_model, X_test, y_test, y_test_prob, feature_names):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    fpr, tpr, _ = roc_curve(y_test, y_test_prob)
    auc = roc_auc_score(y_test, y_test_prob)
    axes[0].plot(fpr, tpr, label=f"AUC={auc:.3f}")
    axes[0].legend()

    importances = rf_model.feature_importances_
    axes[1].bar(range(len(importances)), importances)

    cm = confusion_matrix(y_test, rf_model.predict(X_test))
    axes[2].imshow(cm)

    plt.savefig("./results/fraud_model_evaluation.png")
    print("✓ Saved: ./results/fraud_model_evaluation.png")


def main():
    print("=" * 60)
    print("ShieldPay – Fraud Detection Model Training")
    print("=" * 60)

    df = load_data()
    X_train, X_val, X_test, y_train, y_val, y_test, scaler, FEATURES = preprocess(df)

    rf_model, gb_model = train_model(X_train, y_train)

    rf_metrics, y_rf = evaluate_model(rf_model, X_val, y_val, X_test, y_test, "RandomForest")
    gb_metrics, y_gb = evaluate_model(gb_model, X_val, y_val, X_test, y_test, "GradientBoosting")

    best_model = rf_model if rf_metrics["test_auc_roc"] >= gb_metrics["test_auc_roc"] else gb_model
    best_metrics = rf_metrics if rf_metrics["test_auc_roc"] >= gb_metrics["test_auc_roc"] else gb_metrics
    best_probs = y_rf if best_model is rf_model else y_gb

    print(f"\n✓ Best model: {best_metrics['model_name']}")

    plot_results(rf_model, X_test, y_test, best_probs, FEATURES)

    # 🔥 SAVE SECTION (FIXED)
    try:
        with open("ml/models/fraud_model.pkl", "wb") as f:
            pickle.dump(best_model, f)

        scalers = {}
        scaler_path = "ml/models/scalers.pkl"

        if os.path.exists(scaler_path):
            with open(scaler_path, "rb") as f:
                scalers = pickle.load(f)

        scalers["fraud"] = scaler

        with open(scaler_path, "wb") as f:
            pickle.dump(scalers, f)

        with open("ml/results/fraud_metrics.json", "w") as f:
            json.dump(best_metrics, f, indent=2)

        print("\n✓ Saved model, scalers, metrics")

    except Exception as e:
        print(f"⚠ Save failed: {e}")

    print("\nFinal Test Metrics:")
    print(best_metrics)
# ──────────────────────────────────────────────
# 🔥 INCOME MODEL TRAINING (ADD THIS BELOW FRAUD)
# ──────────────────────────────────────────────

from sklearn.ensemble import GradientBoostingRegressor
import numpy as np
import os

# ensure folder exists
os.makedirs("ml/models", exist_ok=True)

# 🔹 Generate synthetic training data
X_income = []
y_income = []

for _ in range(500):
    recent_avg = np.random.uniform(3000, 8000)
    trend = np.random.uniform(-0.5, 0.5)
    std = np.random.uniform(200, 1500)

    rain = np.random.uniform(0, 0.5)
    demand = np.random.uniform(0, 0.5)
    aqi = np.random.uniform(0, 0.3)
    traffic = np.random.uniform(0, 0.3)

    declared = np.random.uniform(3000, 8000)

    features = [
        recent_avg, trend, std,
        rain, demand, aqi, traffic,
        declared
    ]

    predicted_income = recent_avg * (1 - (rain + demand + aqi + traffic) * 0.5)

    X_income.append(features)
    y_income.append(predicted_income)

X_income = np.array(X_income)
y_income = np.array(y_income)

# 🔹 Train model
income_model = GradientBoostingRegressor()
income_model.fit(X_income, y_income)

# 🔹 Save model
import pickle

with open("ml/models/income_model.pkl", "wb") as f:
    pickle.dump(income_model, f)

print("✅ income_model.pkl saved successfully")

if __name__ == "__main__":
    main()