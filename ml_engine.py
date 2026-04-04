"""
ShieldPay – Machine Learning Inference Engine

Models:
  A. Fraud Detection   – RandomForestClassifier
     P(fraud | X) = sigmoid(wᵀX + b)
     Features: login_variance, claim_interval_std, session_mean,
               income_deviation, claim_velocity

  B. Income Prediction – GradientBoostingRegressor
     ŷ = f(X) where X includes income history + environment
     Output: predicted_income, confidence_band [lower, upper]

Falls back to heuristic rule-based scoring if models are not trained.
"""

import os
import math
import json
import statistics
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import numpy as np

# ──────────────────────────────────────────────
# Model Paths
# ──────────────────────────────────────────────
MODEL_DIR = Path(os.getenv("MODEL_DIR", "./ml/models"))
FRAUD_MODEL_PATH = MODEL_DIR / "fraud_model.pkl"
INCOME_MODEL_PATH = MODEL_DIR / "income_model.pkl"
SCALER_PATH = MODEL_DIR / "scalers.pkl"

# Global model cache
_fraud_model = None
_income_model = None
_scalers = None


def _load_models():
    """Lazy load models from disk."""
    global _fraud_model, _income_model, _scalers

    if FRAUD_MODEL_PATH.exists():
        with open(FRAUD_MODEL_PATH, "rb") as f:
            _fraud_model = pickle.load(f)

    if INCOME_MODEL_PATH.exists():
        with open(INCOME_MODEL_PATH, "rb") as f:
            _income_model = pickle.load(f)

    if SCALER_PATH.exists():
        with open(SCALER_PATH, "rb") as f:
            _scalers = pickle.load(f)


# Load on module import
try:
    _load_models()
except Exception as e:
    pass  # Will fall back to rule-based


# ──────────────────────────────────────────────
# Feature Extraction
# ──────────────────────────────────────────────

def extract_fraud_features(
    login_timestamps: List[str],
    claim_timestamps: List[str],
    session_durations: List[float],
    income_history: List[float],
    declared_income: float,
) -> Dict[str, float]:
    """
    Extract the 5 core features for fraud detection.
    
    Features:
      1. login_variance         – std of inter-login intervals (hours)
      2. claim_interval_std     – std of inter-claim intervals (hours)
      3. session_duration_mean  – mean session length (seconds)
      4. income_deviation       – abs(declared - mean_actual) / declared
      5. claim_velocity_7d      – number of claims in last 7 days
    """
    from datetime import datetime, timedelta

    def parse_ts(ts_list):
        result = []
        for ts in ts_list:
            try:
                result.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                continue
        return sorted(result)

    login_dts = parse_ts(login_timestamps)
    claim_dts = parse_ts(claim_timestamps)

    # 1. Login interval variance
    if len(login_dts) >= 2:
        intervals = [(login_dts[i] - login_dts[i-1]).total_seconds() / 3600
                     for i in range(1, len(login_dts))]
        login_variance = statistics.stdev(intervals) if len(intervals) > 1 else 0
    else:
        login_variance = 0.0

    # 2. Claim interval std
    if len(claim_dts) >= 2:
        c_intervals = [(claim_dts[i] - claim_dts[i-1]).total_seconds() / 3600
                       for i in range(1, len(claim_dts))]
        claim_interval_std = statistics.stdev(c_intervals) if len(c_intervals) > 1 else 0
    else:
        claim_interval_std = 0.0

    # 3. Session duration mean
    session_mean = statistics.mean(session_durations) if session_durations else 300.0

    # 4. Income deviation
    if income_history and declared_income > 0:
        mean_actual = statistics.mean(income_history)
        income_deviation = abs(declared_income - mean_actual) / declared_income
    else:
        income_deviation = 0.0

    # 5. Claim velocity (last 7 days)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    claim_velocity = sum(1 for dt in claim_dts if dt >= week_ago)

    return {
        "login_variance": round(login_variance, 4),
        "claim_interval_std": round(claim_interval_std, 4),
        "session_duration_mean": round(session_mean, 2),
        "income_deviation": round(income_deviation, 4),
        "claim_velocity_7d": float(claim_velocity),
    }


def extract_income_features(
    income_history: List[float],
    declared_income: float,
    environment: Dict[str, Any],
) -> Dict[str, float]:
    """
    Extract features for income prediction.
    
    Features:
      - recent_avg_4w   – mean of last 4 weeks income
      - income_trend    – slope of income over last 8 weeks
      - income_std      – volatility measure
      - rain_impact     – rain income impact %
      - demand_impact   – demand income impact %
      - aqi_impact      – AQI income impact %
      - traffic_impact  – traffic income impact %
      - declared        – declared weekly income
    """
    n = len(income_history)

    if n == 0:
        recent_avg = declared_income
        income_trend = 0.0
        income_std = 0.0
    elif n < 4:
        recent_avg = statistics.mean(income_history)
        income_trend = 0.0
        income_std = statistics.stdev(income_history) if n > 1 else 0.0
    else:
        recent_avg = statistics.mean(income_history[-4:])
        # Trend: linear regression slope approximation
        y = income_history[-8:] if n >= 8 else income_history
        x = list(range(len(y)))
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
        den = sum((xi - x_mean) ** 2 for xi in x)
        income_trend = num / den if den > 0 else 0.0
        income_std = statistics.stdev(income_history[-8:]) if len(income_history) >= 2 else 0.0

    # Extract environmental impacts
    rain_impact = environment.get("weather", {}).get("income_impact_pct", 0) / 100.0
    demand_impact = environment.get("demand", {}).get("income_impact_pct", 0) / 100.0
    aqi_impact = environment.get("aqi", {}).get("income_impact_pct", 0) / 100.0
    traffic_impact = environment.get("traffic", {}).get("income_impact_pct", 0) / 100.0

    return {
        "recent_avg_4w": round(recent_avg, 2),
        "income_trend": round(income_trend, 4),
        "income_std": round(income_std, 2),
        "rain_impact": round(rain_impact, 3),
        "demand_impact": round(demand_impact, 3),
        "aqi_impact": round(aqi_impact, 3),
        "traffic_impact": round(traffic_impact, 3),
        "declared_income": round(declared_income, 2),
    }


# ──────────────────────────────────────────────
# Rule-Based Fallbacks (when models not trained)
# ──────────────────────────────────────────────

def _rule_based_fraud_score(features: Dict[str, float]) -> Dict[str, Any]:
    """
    Heuristic fraud scoring using feature thresholds.
    P(fraud | X) ≈ sigmoid(weighted_sum)
    """
    score = 0.0

    # Login variance: high = irregular = suspicious
    if features["login_variance"] > 48:
        score += 0.25
    elif features["login_variance"] > 24:
        score += 0.10

    # Claim interval std: near-zero = scripted
    if 0 < features["claim_interval_std"] < 2:
        score += 0.30
    elif features["claim_interval_std"] == 0 and features["claim_velocity_7d"] > 1:
        score += 0.20

    # Session duration: very short = automated
    if features["session_duration_mean"] < 15:
        score += 0.20
    elif features["session_duration_mean"] < 60:
        score += 0.08

    # Income deviation
    if features["income_deviation"] > 0.40:
        score += 0.20
    elif features["income_deviation"] > 0.20:
        score += 0.10

    # Claim velocity
    if features["claim_velocity_7d"] >= 3:
        score += 0.25
    elif features["claim_velocity_7d"] >= 2:
        score += 0.10

    # Convert to 0–100
    fraud_score = round(min(100, score * 100), 2)

    # Sigmoid-like probability
    logit = (fraud_score - 50) / 20
    probability = 1 / (1 + math.exp(-logit))

    signals = []
    if features["login_variance"] > 48:
        signals.append("high_login_irregularity")
    if 0 < features["claim_interval_std"] < 2:
        signals.append("scripted_claim_intervals")
    if features["session_duration_mean"] < 15:
        signals.append("automated_sessions_detected")
    if features["income_deviation"] > 0.40:
        signals.append("significant_income_inflation")
    if features["claim_velocity_7d"] >= 3:
        signals.append("high_claim_velocity")

    return {
        "fraud_score": fraud_score,
        "probability": round(probability, 4),
        "signals": signals,
        "model_type": "rule_based_heuristic",
        "confidence": 0.70,
    }


def _rule_based_income_prediction(
    features: Dict[str, float],
    income_history: List[float],
) -> Dict[str, Any]:
    """
    Heuristic income prediction.
    ŷ = recent_avg × (1 - combined_env_impact) × trend_adjustment
    L = Σ(y - ŷ)²  [used for confidence estimation]
    """
    recent_avg = features["recent_avg_4w"]
    trend_adj = 1 + (features["income_trend"] * 0.05)  # Cap trend effect
    trend_adj = max(0.5, min(1.5, trend_adj))

    # Combined environmental impact
    env_impact = (
        features["rain_impact"] * 0.40 +
        features["demand_impact"] * 0.35 +
        features["aqi_impact"] * 0.10 +
        features["traffic_impact"] * 0.15
    )

    predicted = recent_avg * trend_adj * (1 - env_impact)
    predicted = max(0, predicted)

    # Confidence band: use historical std
    std = features["income_std"]
    conf_band_pct = max(0.10, min(0.30, std / max(recent_avg, 1)))
    lower = max(0, predicted * (1 - conf_band_pct))
    upper = predicted * (1 + conf_band_pct)

    # R² approximation from historical data
    if len(income_history) >= 3:
        mean_y = statistics.mean(income_history)
        ss_tot = sum((y - mean_y) ** 2 for y in income_history)
        ss_res = sum((y - predicted) ** 2 for y in income_history[-3:])
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.5
        r2 = max(0.0, min(1.0, r2))
    else:
        r2 = 0.65

    return {
        "predicted_income": round(predicted, 2),
        "confidence_lower": round(lower, 2),
        "confidence_upper": round(upper, 2),
        "confidence_band_pct": round(conf_band_pct * 100, 1),
        "trend_direction": "up" if features["income_trend"] > 0 else "down",
        "env_impact_pct": round(env_impact * 100, 1),
        "r2_score": round(r2, 4),
        "model_type": "rule_based_regression",
        "feature_importance": {
            "recent_history": 0.40,
            "rain": 0.25,
            "demand": 0.20,
            "aqi": 0.08,
            "traffic": 0.07,
        }
    }


# ──────────────────────────────────────────────
# ML Model Inference
# ──────────────────────────────────────────────

def predict_fraud(
    login_timestamps: List[str],
    claim_timestamps: List[str],
    session_durations: List[float],
    income_history: List[float],
    declared_income: float,
) -> Dict[str, Any]:
    """
    Run fraud detection inference.
    Uses trained ML model if available, falls back to rule-based.
    
    Formula: P(fraud | X) = sigmoid(wᵀX + b)
    """
    features = extract_fraud_features(
        login_timestamps, claim_timestamps, session_durations,
        income_history, declared_income
    )

    result = None

    if _fraud_model is not None:
        try:
            feature_vec = np.array([[
                features["login_variance"],
                features["claim_interval_std"],
                features["session_duration_mean"],
                features["income_deviation"],
                features["claim_velocity_7d"],
            ]])

            # Scale if scaler available
            if _scalers and "fraud" in _scalers:
                feature_vec = _scalers["fraud"].transform(feature_vec)

            prob = _fraud_model.predict_proba(feature_vec)[0]
            fraud_prob = float(prob[1]) if len(prob) > 1 else float(prob[0])
            fraud_score = round(fraud_prob * 100, 2)

            # Get feature importances
            importances = {}
            if hasattr(_fraud_model, "feature_importances_"):
                feat_names = ["login_variance", "claim_interval_std",
                              "session_duration_mean", "income_deviation", "claim_velocity_7d"]
                importances = {n: round(float(v), 4)
                               for n, v in zip(feat_names, _fraud_model.feature_importances_)}

            signals = []
            if features["claim_velocity_7d"] >= 3: signals.append("high_claim_velocity")
            if features["income_deviation"] > 0.30: signals.append("income_inflation")
            if features["session_duration_mean"] < 30: signals.append("short_sessions")

            result = {
                "fraud_score": fraud_score,
                "probability": round(fraud_prob, 4),
                "signals": signals,
                "model_type": "random_forest_classifier",
                "confidence": 0.88,
                "feature_importances": importances,
            }
        except Exception:
            result = None

    if result is None:
        result = _rule_based_fraud_score(features)

    result["features_used"] = features
    return result


def predict_income(
    income_history: List[float],
    declared_income: float,
    environment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run income prediction inference.
    Uses trained ML model if available, falls back to rule-based.
    
    Formula: ŷ = f(X); Loss: L = Σ(y - ŷ)²
    """
    features = extract_income_features(income_history, declared_income, environment)
    result = None

    if _income_model is not None:
        try:
            feature_vec = np.array([[
                features["recent_avg_4w"],
                features["income_trend"],
                features["income_std"],
                features["rain_impact"],
                features["demand_impact"],
                features["aqi_impact"],
                features["traffic_impact"],
                features["declared_income"],
            ]])

            if _scalers and "income" in _scalers:
                feature_vec = _scalers["income"].transform(feature_vec)

            predicted = float(_income_model.predict(feature_vec)[0])

            # Confidence band from model's staged predictions if GBM
            std_estimate = features["income_std"] if features["income_std"] > 0 else predicted * 0.15
            lower = max(0, predicted - 1.5 * std_estimate)
            upper = predicted + 1.5 * std_estimate

            importances = {}
            if hasattr(_income_model, "feature_importances_"):
                feat_names = ["recent_avg", "trend", "std", "rain",
                              "demand", "aqi", "traffic", "declared"]
                importances = {n: round(float(v), 4)
                               for n, v in zip(feat_names, _income_model.feature_importances_)}

            result = {
                "predicted_income": round(max(0, predicted), 2),
                "confidence_lower": round(lower, 2),
                "confidence_upper": round(upper, 2),
                "confidence_band_pct": round((upper - lower) / max(predicted, 1) * 50, 1),
                "trend_direction": "up" if features["income_trend"] > 0 else "down",
                "env_impact_pct": round(
                    (features["rain_impact"] + features["demand_impact"] +
                     features["aqi_impact"] + features["traffic_impact"]) * 25, 1
                ),
                "model_type": "gradient_boosting_regressor",
                "feature_importances": importances,
            }
        except Exception:
            result = None

    if result is None:
        result = _rule_based_income_prediction(features, income_history)

    result["features_used"] = features
    return result


def reload_models():
    """Reload models from disk (call after retraining)."""
    _load_models()
    return {"status": "models_reloaded", "fraud_loaded": _fraud_model is not None,
            "income_loaded": _income_model is not None}
# ──────────────────────────────────────────────
# 🔥 ML TRIGGER DECISION ENGINE (NEW)
# ──────────────────────────────────────────────
import logging
logger = logging.getLogger(__name__)
def predict_trigger_probability(
    environment: Dict[str, Any],
    user
) -> Dict[str, Any]:
    """
    Decide whether a claim should be auto-triggered using ML.

    Logic:
    - Use income prediction drop
    - Combine with environment severity
    - Output trigger decision
    """

    try:
        # 🔥 1. Predict income
        income_pred = predict_income(
            user.get_income_history(),
            user.declared_weekly_income,
            environment
        )

        predicted_income = income_pred.get(
            "predicted_income",
            user.declared_weekly_income
        )

        declared_income = user.declared_weekly_income

        # 🔥 2. Compute income drop %
        if declared_income > 0:
            income_drop_pct = max(
                0,
                (declared_income - predicted_income) / declared_income * 100
            )
        else:
            income_drop_pct = 0

        # 🔥 3. FIXED: Convert severity/category → numeric scores

        severity_map = {
            # Weather
            "clear": 0,
            "light": 20,
            "moderate": 50,
            "heavy": 75,
            "severe": 100,

            # Traffic
            "free_flow": 0,
            "light": 20,
            "moderate": 50,
            "heavy": 75,
            "gridlock": 100,

            # AQI
            "good": 0,
            "satisfactory": 10,
            "moderate": 30,
            "poor": 60,
            "very_poor": 80,
            "severe": 100,

            # Demand
            "high": 0,
            "normal": 20,
            "low": 60,
            "very_low": 100
        }

        rain = severity_map.get(
            environment.get("weather", {}).get("severity", "clear"),
            0
        )

        traffic = severity_map.get(
            environment.get("traffic", {}).get("category", "free_flow"),
            0
        )

        aqi = severity_map.get(
            environment.get("aqi", {}).get("category", "good"),
            0
        )

        demand = severity_map.get(
            environment.get("demand", {}).get("category", "normal"),
            0
        )

        env_score = (
            rain * 0.35 +
            traffic * 0.25 +
            aqi * 0.15 +
            demand * 0.25
        )

        # 🔥 DEBUG (VERY IMPORTANT)
        logger.info({
            "ml_debug": {
                "rain_score": rain,
                "traffic_score": traffic,
                "aqi_score": aqi,
                "demand_score": demand,
                "env_score": env_score,
                "income_drop_pct": income_drop_pct
            }
        })

        # 🔥 4. Combine into probability
        prob = min(
            1.0,
            0.6 * (income_drop_pct / 100) + 0.4 * (env_score / 100)
        )

        # 🔥 5. Decide trigger type
        trigger_type = None
        reason = ""

        if prob > 0.8:
            trigger_type = "high_risk_event"
            reason = "Severe disruption predicted"
        elif prob > 0.65:
            trigger_type = "ml_auto"
            reason = "Moderate disruption predicted"
        else:
            return {
                "probability": round(prob, 4),
                "should_trigger": False,
                "trigger_type": None,
                "reason": "Conditions not severe enough",
                "income_drop_pct": round(income_drop_pct, 2),
                "env_score": round(env_score, 2)
            }

        # 🔥 6. Additional safety
        if income_drop_pct < 10:
            return {
                "probability": round(prob, 4),
                "should_trigger": False,
                "trigger_type": None,
                "reason": "Low income impact",
                "income_drop_pct": round(income_drop_pct, 2),
                "env_score": round(env_score, 2)
            }

        return {
            "probability": round(prob, 4),
            "should_trigger": True,
            "trigger_type": trigger_type,
            "reason": reason,
            "income_drop_pct": round(income_drop_pct, 2),
            "env_score": round(env_score, 2)
        }

    except Exception as e:
        print("❌ ML TRIGGER ERROR:", e)

        return {
            "probability": 0.0,
            "should_trigger": False,
            "trigger_type": None,
            "reason": "ML failure fallback"
        }