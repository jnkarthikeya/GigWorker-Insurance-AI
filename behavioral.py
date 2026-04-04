"""
ShieldPay – Behavioral Analytics Engine
Analyzes user behavior patterns to compute trust/risk scores.

Dimensions:
  1. Login Frequency Analysis     – How often and consistently user logs in
  2. Claim Timing Analysis        – Suspicious patterns in when claims are filed
  3. Session Consistency          – Variance in session lengths
  4. Income Consistency           – How stable declared vs actual income is
  5. Claim Velocity               – Rate of claims per week/month

Each dimension returns a score (0–100) and anomaly signals.
Final behavior_score = weighted combination.
"""

import math
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from models import User, Claim

# ──────────────────────────────────────────────
# Scoring Weights
# ──────────────────────────────────────────────
WEIGHTS = {
    "login_frequency": 0.20,
    "claim_timing": 0.30,
    "session_consistency": 0.15,
    "income_consistency": 0.20,
    "claim_velocity": 0.15,
}

RISK_THRESHOLDS = {
    "low": 70,
    "moderate": 45,
    "high": 25,
}


def _parse_timestamps(ts_list: List[str]) -> List[datetime]:
    """Parse ISO timestamp strings to datetime objects."""
    result = []
    for ts in ts_list:
        try:
            result.append(datetime.fromisoformat(ts))
        except (ValueError, TypeError):
            continue
    return sorted(result)


def analyze_login_frequency(login_timestamps: List[str]) -> Dict[str, Any]:
    """
    Analyzes login patterns.
    Healthy pattern: regular logins without extreme bursts.
    
    Anomaly signals:
      - Sudden burst of logins in short window
      - Extremely long gaps (inactive then sudden activity)
      - Login times only at odd hours (potential bot)
    """
    dts = _parse_timestamps(login_timestamps)
    if len(dts) < 2:
        return {
            "score": 60.0,
            "anomaly_signals": ["insufficient_data"],
            "details": {"count": len(dts), "avg_interval_hours": None}
        }

    # Compute inter-login intervals in hours
    intervals = [(dts[i] - dts[i-1]).total_seconds() / 3600 for i in range(1, len(dts))]
    avg_interval = statistics.mean(intervals)
    std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0

    anomaly_signals = []
    score = 85.0

    # Check for login bursts (< 5 min apart → suspicious)
    burst_count = sum(1 for iv in intervals if iv < 0.083)  # 5 min
    if burst_count > 2:
        score -= 25
        anomaly_signals.append("login_burst_detected")

    # Check coefficient of variation
    cv = std_interval / avg_interval if avg_interval > 0 else 0
    if cv > 2.0:
        score -= 15
        anomaly_signals.append("high_login_irregularity")

    # Check for exclusively off-hours logins (midnight–5am)
    off_hour_count = sum(1 for dt in dts if 0 <= dt.hour < 5)
    if len(dts) > 0 and off_hour_count / len(dts) > 0.6:
        score -= 10
        anomaly_signals.append("unusual_login_hours")

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "anomaly_signals": anomaly_signals,
        "details": {
            "total_logins": len(dts),
            "avg_interval_hours": round(avg_interval, 2),
            "interval_std": round(std_interval, 2),
            "burst_logins": burst_count,
        }
    }


def analyze_claim_timing(claim_timestamps: List[str]) -> Dict[str, Any]:
    """
    Analyzes claim timing patterns.
    
    Anomaly signals:
      - Claims filed exactly 24h apart (scripted behavior)
      - Multiple claims in same day
      - Claims always on specific day-of-week
      - Claims only within first minute of a storm trigger
    """
    dts = _parse_timestamps(claim_timestamps)
    anomaly_signals = []
    score = 90.0

    if len(dts) < 2:
        return {
            "score": 80.0,
            "anomaly_signals": [],
            "details": {"claim_count": len(dts)}
        }

    intervals = [(dts[i] - dts[i-1]).total_seconds() / 3600 for i in range(1, len(dts))]
    avg_interval = statistics.mean(intervals)

    # Same-day claims
    same_day = sum(1 for iv in intervals if iv < 1.0)
    if same_day > 1:
        score -= 20
        anomaly_signals.append("multiple_same_day_claims")

    # Suspiciously regular intervals (~24h apart with <1h variance)
    near_24h = sum(1 for iv in intervals if 23 <= iv <= 25)
    if near_24h >= 3:
        score -= 25
        anomaly_signals.append("scripted_24h_claim_pattern")

    # All claims on same day of week
    if len(dts) >= 4:
        weekdays = [dt.weekday() for dt in dts]
        unique_days = len(set(weekdays))
        if unique_days == 1:
            score -= 15
            anomaly_signals.append("single_weekday_pattern")

    # Very rapid consecutive claims
    rapid = sum(1 for iv in intervals if iv < 0.5)  # < 30 min
    if rapid > 0:
        score -= 30
        anomaly_signals.append("rapid_consecutive_claims")

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "anomaly_signals": anomaly_signals,
        "details": {
            "claim_count": len(dts),
            "avg_interval_hours": round(avg_interval, 2),
            "same_day_claims": same_day,
            "rapid_claims": rapid,
        }
    }


def analyze_session_consistency(session_durations: List[float]) -> Dict[str, Any]:
    """
    Analyzes session durations for consistency.
    Extremely short sessions (< 10s) or exactly-equal sessions are suspicious.
    
    Anomaly signals:
      - All sessions exactly same duration (bot-like)
      - Very short sessions (<10s) indicating automated access
      - Wild variance suggesting multiple device types
    """
    anomaly_signals = []
    score = 85.0

    if len(session_durations) < 3:
        return {
            "score": 70.0,
            "anomaly_signals": ["insufficient_session_data"],
            "details": {"session_count": len(session_durations)}
        }

    mean_dur = statistics.mean(session_durations)
    std_dur = statistics.stdev(session_durations) if len(session_durations) > 1 else 0

    # Very short sessions
    short_sessions = sum(1 for d in session_durations if d < 10)
    if short_sessions / len(session_durations) > 0.5:
        score -= 20
        anomaly_signals.append("automated_short_sessions")

    # Zero variance (bot-like exactly equal sessions)
    if std_dur < 1.0 and mean_dur > 0:
        score -= 25
        anomaly_signals.append("bot_like_session_uniformity")

    # High CV
    cv = std_dur / mean_dur if mean_dur > 0 else 0
    if cv > 3.0:
        score -= 10
        anomaly_signals.append("high_session_variance")

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "anomaly_signals": anomaly_signals,
        "details": {
            "mean_duration_s": round(mean_dur, 2),
            "std_duration_s": round(std_dur, 2),
            "short_session_count": short_sessions,
        }
    }


def analyze_income_consistency(
    income_history: List[float],
    declared_income: float
) -> Dict[str, Any]:
    """
    Compares declared income to historical actuals.
    
    Anomaly signals:
      - Declared income >> actual income consistently
      - High week-to-week variance (unstable earner or manipulation)
      - Sudden income spike just before enrollment
    """
    anomaly_signals = []
    score = 85.0

    if len(income_history) < 3:
        return {
            "score": 70.0,
            "anomaly_signals": ["insufficient_income_data"],
            "details": {"weeks_recorded": len(income_history)}
        }

    mean_actual = statistics.mean(income_history)
    std_actual = statistics.stdev(income_history) if len(income_history) > 1 else 0

    # Inflation ratio: declared / actual
    if mean_actual > 0:
        inflation_ratio = declared_income / mean_actual
        if inflation_ratio > 1.5:
            score -= 25
            anomaly_signals.append("income_over_declared")
        elif inflation_ratio > 1.25:
            score -= 10
            anomaly_signals.append("income_slightly_inflated")
    else:
        score -= 20
        anomaly_signals.append("zero_income_history")
        inflation_ratio = 1.0

    # Volatility (CV of actual income)
    cv = std_actual / mean_actual if mean_actual > 0 else 0
    if cv > 0.5:
        score -= 15
        anomaly_signals.append("high_income_volatility")

    # Sudden spike in last recorded (fraud before claim)
    if len(income_history) >= 3 and income_history[-1] < mean_actual * 0.5:
        # Actually legitimate – recent drop
        pass
    elif len(income_history) >= 2:
        recent_avg = statistics.mean(income_history[-3:]) if len(income_history) >= 3 else income_history[-1]
        historical_avg = statistics.mean(income_history[:-3]) if len(income_history) > 3 else mean_actual
        if historical_avg > 0 and recent_avg / historical_avg > 1.4:
            score -= 10
            anomaly_signals.append("suspicious_income_spike")

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "anomaly_signals": anomaly_signals,
        "details": {
            "declared_income": declared_income,
            "mean_actual_income": round(mean_actual, 2),
            "inflation_ratio": round(inflation_ratio, 3),
            "income_cv": round(cv, 3),
        }
    }


def analyze_claim_velocity(claim_timestamps: List[str], max_week: int = 3, max_month: int = 12) -> Dict[str, Any]:
    """
    Measures rate of claims in recent windows.
    
    Anomaly signals:
      - Claims exceeding weekly limit
      - Claims exceeding monthly limit
      - Accelerating claim rate over time
    """
    dts = _parse_timestamps(claim_timestamps)
    now = datetime.utcnow()
    anomaly_signals = []
    score = 90.0

    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    claims_last_week = sum(1 for dt in dts if dt >= week_ago)
    claims_last_month = sum(1 for dt in dts if dt >= month_ago)

    if claims_last_week > max_week:
        excess = claims_last_week - max_week
        score -= min(40, excess * 15)
        anomaly_signals.append(f"weekly_claim_limit_exceeded_by_{excess}")

    if claims_last_month > max_month:
        excess = claims_last_month - max_month
        score -= min(30, excess * 8)
        anomaly_signals.append(f"monthly_claim_limit_exceeded_by_{excess}")

    # Velocity acceleration: compare rate in last 2 weeks vs prior 2 weeks
    two_weeks_ago = now - timedelta(days=14)
    recent_rate = claims_last_week
    prior_rate = sum(1 for dt in dts if two_weeks_ago <= dt < week_ago)

    if prior_rate > 0 and recent_rate / prior_rate > 2.0:
        score -= 15
        anomaly_signals.append("accelerating_claim_velocity")

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 2),
        "anomaly_signals": anomaly_signals,
        "details": {
            "claims_last_7_days": claims_last_week,
            "claims_last_30_days": claims_last_month,
            "weekly_limit": max_week,
            "monthly_limit": max_month,
        }
    }


# ──────────────────────────────────────────────
# Main Behavioral Analysis Entry Point
# ──────────────────────────────────────────────
def run_behavioral_analysis(user: User) -> Dict[str, Any]:
    """
    Run all 5 behavioral dimensions and compute composite score.
    
    Returns full breakdown including:
      - Individual dimension scores
      - All anomaly signals
      - Composite behavior_score (0–100)
      - Risk level (low/moderate/high/critical)
    """
    login_result = analyze_login_frequency(user.get_login_timestamps())
    claim_timing_result = analyze_claim_timing(user.get_claim_timestamps())
    session_result = analyze_session_consistency(user.get_session_durations())
    income_result = analyze_income_consistency(
        user.get_income_history(), user.declared_weekly_income
    )
    velocity_result = analyze_claim_velocity(user.get_claim_timestamps())

    # Weighted composite score
    composite = (
        WEIGHTS["login_frequency"] * login_result["score"] +
        WEIGHTS["claim_timing"] * claim_timing_result["score"] +
        WEIGHTS["session_consistency"] * session_result["score"] +
        WEIGHTS["income_consistency"] * income_result["score"] +
        WEIGHTS["claim_velocity"] * velocity_result["score"]
    )
    composite = round(composite, 2)

    # All anomaly signals aggregated
    all_signals = (
        login_result["anomaly_signals"] +
        claim_timing_result["anomaly_signals"] +
        session_result["anomaly_signals"] +
        income_result["anomaly_signals"] +
        velocity_result["anomaly_signals"]
    )

    # Risk level
    if composite >= RISK_THRESHOLDS["low"]:
        risk_level = "low"
    elif composite >= RISK_THRESHOLDS["moderate"]:
        risk_level = "moderate"
    elif composite >= RISK_THRESHOLDS["high"]:
        risk_level = "high"
    else:
        risk_level = "critical"

    return {
        "behavior_score": composite,
        "risk_level": risk_level,
        "dimensions": {
            "login_frequency": login_result,
            "claim_timing": claim_timing_result,
            "session_consistency": session_result,
            "income_consistency": income_result,
            "claim_velocity": velocity_result,
        },
        "all_anomaly_signals": list(set(all_signals)),
        "weights_used": WEIGHTS,
    }


def compute_trust_update(
    current_trust: float,
    behavior_score: float,
    claim_approved: bool,
    fraud_score: float,
) -> Dict[str, Any]:
    """
    Dynamic trust score update after each interaction.
    
    Trust Update Formula:
      delta = alpha * (behavior_score / 100) * direction - beta * fraud_penalty
    
    Where:
      alpha = learning rate = 0.1
      beta  = fraud penalty weight = 0.3
      direction = +1 if approved, -1 if blocked
    """
    ALPHA = 0.10   # learning rate
    BETA = 0.30    # fraud penalty weight
    MIN_TRUST = 10.0
    MAX_TRUST = 100.0

    direction = 1.0 if claim_approved else -1.0
    behavior_factor = behavior_score / 100.0
    fraud_penalty = (fraud_score / 100.0) * BETA

    delta = ALPHA * behavior_factor * direction - fraud_penalty
    new_trust = current_trust + (delta * 10)  # Scale to trust range
    new_trust = round(max(MIN_TRUST, min(MAX_TRUST, new_trust)), 2)

    return {
        "trust_before": round(current_trust, 2),
        "trust_after": new_trust,
        "delta": round(new_trust - current_trust, 2),
        "factors": {
            "behavior_factor": round(behavior_factor, 3),
            "fraud_penalty": round(fraud_penalty, 3),
            "direction": "positive" if claim_approved else "negative",
            "alpha": ALPHA,
            "beta": BETA,
        },
        "interpretation": (
            "Trust improved due to legitimate claim activity"
            if delta > 0
            else "Trust decreased due to fraud indicators or blocked claim"
        )
    }
