"""
ShieldPay – Income Prediction Model Training
GradientBoostingRegressor with confidence band estimation.

Mathematical formulation:
  ŷ = f(X)  where f = ensemble of decision trees
  Loss: L = Σ(y - ŷ)² / N  (MSE)
  
  Confidence band:
    lower = ŷ - 1.5 × σ_residual
    upper = ŷ + 1.5 × σ_residual

Training:
  - Load income_dataset.csv
  - Split: 60% train / 20% validation / 20% test
  - Train GradientBoostingRegressor
  - Evaluate: MAE, RMSE, R² score
  - Save model to ml/models/

Usage:
  python train_income.py
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score
)

os.makedirs("./models", exist_ok=True)
os.makedirs("./results", exist_ok=True)


def load_data():
    """Load and validate income dataset."""
    path = "./data/income_dataset.csv"
    if not os.path.exists(path):
        print("Dataset not found. Generating...")
        import sys
        sys.path.insert(0, ".")
        from generate_dataset import generate_income_dataset
        generate_income_dataset()

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} samples")
    print(f"Income range: ₹{df['actual_income'].min():.0f} – ₹{df['actual_income'].max():.0f}")
    return df


def preprocess(df: pd.DataFrame):
    """Prepare features. Split 60/20/20."""
    FEATURES = [
        "recent_avg_4w",
        "income_trend",
        "income_std",
        "rain_impact",
        "demand_impact",
        "aqi_impact",
        "traffic_impact",
        "declared_income",
    ]
    TARGET = "actual_income"

    X = df[FEATURES].values
    y = df[TARGET].values

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=42
    )

    # Scale
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test)

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    return X_train_s, X_val_s, X_test_s, y_train, y_val, y_test, scaler, FEATURES


def train_models(X_train, y_train):
    """Train GBM and RF regressors."""

    # ── GradientBoosting ──
    gbm = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        min_samples_leaf=10,
        random_state=42,
    )
    gbm.fit(X_train, y_train)
    print("✓ GradientBoosting trained")

    # ── RandomForest (comparison) ──
    rf = RandomForestRegressor(
        n_estimators=150,
        max_depth=8,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)
    print("✓ RandomForest trained")

    return gbm, rf


def evaluate_model(model, X_val, y_val, X_test, y_test, name="GBM"):
    """Evaluate with MAE, RMSE, R²."""
    print(f"\n{'='*50}")
    print(f"Model: {name}")
    print(f"{'='*50}")

    y_val_pred = model.predict(X_val)
    y_test_pred = model.predict(X_test)

    # Validation
    val_mae = mean_absolute_error(y_val, y_val_pred)
    val_rmse = np.sqrt(mean_squared_error(y_val, y_val_pred))
    val_r2 = r2_score(y_val, y_val_pred)

    # Test
    test_mae = mean_absolute_error(y_test, y_test_pred)
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    test_r2 = r2_score(y_test, y_test_pred)

    print(f"\nValidation: MAE=₹{val_mae:.2f} | RMSE=₹{val_rmse:.2f} | R²={val_r2:.4f}")
    print(f"Test:       MAE=₹{test_mae:.2f} | RMSE=₹{test_rmse:.2f} | R²={test_r2:.4f}")

    # MAPE
    mape = np.mean(np.abs((y_test - y_test_pred) / np.maximum(y_test, 1))) * 100
    print(f"Test MAPE:  {mape:.2f}%")

    return {
        "model_name": name,
        "val_mae": round(val_mae, 2),
        "val_rmse": round(val_rmse, 2),
        "val_r2": round(val_r2, 4),
        "test_mae": round(test_mae, 2),
        "test_rmse": round(test_rmse, 2),
        "test_r2": round(test_r2, 4),
        "test_mape": round(mape, 2),
    }, y_test_pred


def estimate_confidence_bands(model, X_test, y_test, y_test_pred):
    """
    Estimate prediction confidence bands using residual std.
    lower = ŷ - 1.5σ, upper = ŷ + 1.5σ
    """
    residuals = y_test - y_test_pred
    sigma = np.std(residuals)
    lower = y_test_pred - 1.5 * sigma
    upper = y_test_pred + 1.5 * sigma

    # Coverage: % of actuals within band
    coverage = np.mean((y_test >= lower) & (y_test <= upper))
    print(f"\nConfidence Band (1.5σ): Coverage={coverage:.1%} | σ=₹{sigma:.2f}")

    return lower, upper, sigma, coverage


def plot_results(model, X_test, y_test, y_pred, lower, upper, feature_names, model_name):
    """Generate evaluation plots."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"ShieldPay Income Prediction – {model_name}", fontsize=14)

    # ── Predicted vs Actual ──
    axes[0].scatter(y_test, y_pred, alpha=0.4, s=10, c="steelblue")
    line = [min(y_test), max(y_test)]
    axes[0].plot(line, line, "r--", linewidth=2, label="Perfect")
    axes[0].set_xlabel("Actual Income (₹)")
    axes[0].set_ylabel("Predicted Income (₹)")
    axes[0].set_title("Predicted vs Actual")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # ── Confidence Band on Sorted Samples ──
    n_show = min(100, len(y_test))
    idx = np.argsort(y_test)[:n_show]
    x_axis = range(n_show)
    axes[1].fill_between(x_axis, lower[idx], upper[idx], alpha=0.25, color="blue", label="Confidence Band")
    axes[1].plot(x_axis, y_test[idx], "g-", linewidth=1.5, label="Actual", alpha=0.8)
    axes[1].plot(x_axis, y_pred[idx], "r--", linewidth=1.5, label="Predicted", alpha=0.8)
    axes[1].set_title("Prediction with Confidence Band")
    axes[1].set_xlabel("Sorted Sample Index")
    axes[1].set_ylabel("Income (₹)")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # ── Feature Importance ──
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]
        axes[2].bar(range(len(importances)), importances[sorted_idx],
                   color=["#e74c3c" if importances[i] > importances.mean() else "#3498db"
                          for i in sorted_idx])
        axes[2].set_xticks(range(len(importances)))
        axes[2].set_xticklabels([feature_names[i] for i in sorted_idx], rotation=35, ha="right")
        axes[2].set_title("Feature Importances")
        axes[2].set_ylabel("Importance")
        axes[2].grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig("./results/income_model_evaluation.png", dpi=150, bbox_inches="tight")
    print("✓ Saved: ./results/income_model_evaluation.png")


def cross_validate(model, X_train, y_train):
    """5-fold cross-validation."""
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train, cv=kf, scoring="r2")
    print(f"\n5-Fold CV R²: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    return cv_scores


def main():
    print("=" * 60)
    print("ShieldPay – Income Prediction Model Training")
    print("=" * 60)

    df = load_data()
    X_train, X_val, X_test, y_train, y_val, y_test, scaler, FEATURES = preprocess(df)

    gbm, rf = train_models(X_train, y_train)

    # Evaluate
    gbm_metrics, y_pred_gbm = evaluate_model(gbm, X_val, y_val, X_test, y_test, "GradientBoosting")
    rf_metrics, y_pred_rf = evaluate_model(rf, X_val, y_val, X_test, y_test, "RandomForest")

    # Cross-validate best
    print("\nCross-validating GBM:")
    cv_scores = cross_validate(gbm, X_train, y_train)

    # Pick best by R²
    best_model = gbm if gbm_metrics["test_r2"] >= rf_metrics["test_r2"] else rf
    best_metrics = gbm_metrics if best_model is gbm else rf_metrics
    best_pred = y_pred_gbm if best_model is gbm else y_pred_rf
    print(f"\n✓ Best model: {best_metrics['model_name']} (R²={best_metrics['test_r2']:.4f})")

    # Confidence bands
    lower, upper, sigma, coverage = estimate_confidence_bands(best_model, X_test, y_test, best_pred)

    # Feature importances
    print("\nFeature Importances:")
    for name, imp in zip(FEATURES, gbm.feature_importances_):
        print(f"  {name:<20} {imp:.4f} {'█' * int(imp * 40)}")

    # Plots
    plot_results(gbm, X_test, y_test, best_pred, lower, upper, FEATURES, best_metrics["model_name"])

    # Save model
    with open("./models/income_model.pkl", "wb") as f:
        pickle.dump(best_model, f)

    # Update scalers
    scalers = {}
    scaler_path = "./models/scalers.pkl"
    if os.path.exists(scaler_path):
        with open(scaler_path, "rb") as f:
            scalers = pickle.load(f)
    scalers["income"] = scaler
    with open(scaler_path, "wb") as f:
        pickle.dump(scalers, f)

    # Save metrics
    best_metrics["cv_r2_mean"] = round(cv_scores.mean(), 4)
    best_metrics["cv_r2_std"] = round(cv_scores.std(), 4)
    best_metrics["confidence_band_sigma"] = round(float(sigma), 2)
    best_metrics["confidence_band_coverage"] = round(float(coverage), 4)
    with open("./results/income_metrics.json", "w") as f:
        json.dump(best_metrics, f, indent=2)

    print("\n✓ Saved: ./models/income_model.pkl")
    print("✓ Saved: ./models/scalers.pkl")
    print("✓ Saved: ./results/income_metrics.json")
    print(f"\nFinal Test Metrics:")
    print(f"  MAE       : ₹{best_metrics['test_mae']:.2f}")
    print(f"  RMSE      : ₹{best_metrics['test_rmse']:.2f}")
    print(f"  R² Score  : {best_metrics['test_r2']:.4f}")
    print(f"  MAPE      : {best_metrics['test_mape']:.2f}%")


if __name__ == "__main__":
    main()
