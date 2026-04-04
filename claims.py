import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session

from models import User, Policy, Claim, AuditLog
from behavioral import run_behavioral_analysis, compute_trust_update
from ml_engine import predict_fraud, predict_income
from data_sources import simulate_trigger_environment, get_full_environment

CLAIM_COOLDOWN_SECONDS = 120  # 2 minutes
logger = logging.getLogger("shieldpay.claims")

# RISK SCORE #
def get_risk_tier(trust_score):
    if trust_score >= 80:
        return "premium"
    elif trust_score >= 50:
        return "standard"
    elif trust_score >= 30:
        return "risky"
    return "high_risk"

# ──────────────────────────────────────────────
# Exception
# ──────────────────────────────────────────────
class ClaimException(Exception):
    def __init__(self, status: str, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(reason)


# ──────────────────────────────────────────────
# POLICY EXCLUSIONS
# ──────────────────────────────────────────────
def _check_policy_exclusions(trigger_type: str, environment: dict):
    return False, ""


# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────
def _validate_policy_limits(policy: Policy, db: Session):
    now = datetime.utcnow()

    if now - policy.week_reset_at >= timedelta(days=7):
        policy.claims_this_week = 0
        policy.week_reset_at = now

    if now - policy.month_reset_at >= timedelta(days=30):
        policy.claims_this_month = 0
        policy.month_reset_at = now

    if policy.status != "active":
        raise ClaimException("excluded", f"Policy is {policy.status}")

    if policy.claims_this_week >= policy.max_claims_week:
        raise ClaimException("excluded", "Weekly claim limit reached")

    if policy.claims_this_month >= policy.max_claims_month:
        raise ClaimException("excluded", "Monthly claim limit reached")


# ──────────────────────────────────────────────
# BASE PAYOUT
# ──────────────────────────────────────────────
def _compute_base_payout(coverage_amount: float, income_drop_pct: float) -> float:
    return round(min(coverage_amount, coverage_amount * (income_drop_pct / 100)), 2)


# ──────────────────────────────────────────────
# ADJUSTED PAYOUT
# ──────────────────────────────────────────────
def _compute_adjusted_payout(
    base_payout: float,
    trust_score: float,
    fraud_score: float,
    env_score: float,
) -> Dict[str, Any]:

    trust_factor = max(0.15, min(1.0, trust_score / 100))
    fraud_penalty = max(0.0, min(1.0, fraud_score / 100))
    env_factor = max(0.30, min(1.0, env_score / 100))

    fraud_multiplier = (1 - fraud_penalty) ** 1.3

    weighted = (
        0.5 * trust_factor +
        0.3 * fraud_multiplier +
        0.2 * env_factor
    )

    adjusted = base_payout * weighted
    adjusted = max(0.05 * base_payout, adjusted)
    adjusted = round(adjusted, 2)

    return {
        "base_payout": base_payout,
        "adjusted_payout": adjusted,
        "trust_factor": round(trust_factor, 4),
        "fraud_multiplier": round(fraud_multiplier, 4),
        "env_factor": round(env_factor, 4),
        "formula": "Payout = Weighted(Trust, Fraud, Env)",
    }

# ──────────────────────────────────────────────
# COOLDOWN CHECK
# ──────────────────────────────────────────────
def _check_cooldown(user: User):
    try:
        timestamps = user.get_claim_timestamps()

        if not timestamps:
            return

        last_time = datetime.fromisoformat(timestamps[-1])
        delta = datetime.utcnow() - last_time

        if delta.total_seconds() < CLAIM_COOLDOWN_SECONDS:
            raise ClaimException(
                "cooldown",
                f"Cooldown active. Try again in {int(CLAIM_COOLDOWN_SECONDS - delta.total_seconds())} sec"
            )

    except Exception as e:
        # Don't break system for parsing issues
        logger.warning(f"Cooldown check failed: {e}")
# ──────────────────────────────────────────────
# MAIN CLAIM PROCESSOR
# ──────────────────────────────────────────────
def process_claim(user: User, trigger_type: str, db: Session):
    print("🚀 Processing claim:", trigger_type)

    # 🔥 FIX 1: ensure trigger_type is string
    if isinstance(trigger_type, dict):
        print("⚠️ FIXING TRIGGER TYPE:", trigger_type)
        trigger_type = trigger_type.get("type", "traffic")

    # 🔥 EXTRA VALIDATION
    if not isinstance(trigger_type, str):
        raise ValueError(f"Invalid trigger_type format: {trigger_type}")

    print("🔥 TRIGGER RECEIVED:", trigger_type)

    policy = user.policy

    # 🔒 COOLDOWN CHECK
    _check_cooldown(user)

    # 1. Validate
    _validate_policy_limits(policy, db)

    # 2. Environment
    environment = get_full_environment(user.city)
    print("🌍 ENV BEFORE:", environment)

    # 3. Exclusions
    is_excluded, exclusion_reason = _check_policy_exclusions(trigger_type, environment)

    if is_excluded:
        logger.warning(f"Claim excluded: {exclusion_reason}")

        claim = Claim(
            user_id=user.id,
            policy_id=policy.id,
            trigger_type=trigger_type,
            status="excluded",
            payout_amount=0.0,
            metadata={"reason": exclusion_reason},
        )
        db.add(claim)

        audit = AuditLog(
            user_id=user.id,
            action="claim_excluded",
            details={"reason": exclusion_reason},
        )
        db.add(audit)

        db.commit()

        raise ClaimException("excluded", exclusion_reason)

    # 4. Simulate environment
    try:
        env_after = simulate_trigger_environment(environment, trigger_type)
    except Exception as e:
        print("❌ ENV SIMULATION FAILED:", e)
        env_after = environment

    print("🌪 ENV AFTER:", env_after)

    # 5. Income prediction
    income_pred = predict_income(
        user.get_income_history(),
        user.declared_weekly_income,
        env_after,
    )

    predicted_income = income_pred.get(
        "predicted_income",
        user.declared_weekly_income
    )

    declared_income = user.declared_weekly_income
    print("Income predicted:", predicted_income)

    income_drop_pct = max(
        0,
        (declared_income - predicted_income) / declared_income * 100
    )

    # ──────────────────────────────────────────────
    # 🔥 FRAUD DETECTION
    # ──────────────────────────────────────────────
    fraud = predict_fraud(
        user.get_login_timestamps(),
        user.get_claim_timestamps(),
        user.get_session_durations(),
        user.get_income_history(),
        user.declared_weekly_income,
    )

    fraud_score = fraud.get("fraud_score", 0)
    fraud_prob = fraud.get("probability", 0)
    features = fraud.get("features_used", {})

    print("Fraud score:", fraud_score)

    fraud_flags = []

    if fraud_prob > 0.7:
        fraud_flags.append("High fraud probability")

    if features.get("claim_velocity_7d", 0) >= 3:
        fraud_flags.append("Excessive claim frequency")

    if features.get("income_deviation", 0) > 0.4:
        fraud_flags.append("Suspicious income inflation")

    if not fraud_flags:
        fraud_flags.append("No anomalies detected")

    # 🔥 BEHAVIORAL ANALYSIS
    behavioral = run_behavioral_analysis(user)

    # 🔥 BASE PAYOUT
    base_payout = _compute_base_payout(
        policy.coverage_amount,
        income_drop_pct
    )

    # 🔥 ADJUSTED PAYOUT
    payout = _compute_adjusted_payout(
        base_payout,
        user.trust_score,
        fraud_score,
        env_after.get("composite_env_score", 50),
    )

    adjusted_payout = payout.get("adjusted_payout", 0)

    # 🔥 TRUST UPDATE
    behavior_score = behavioral.get("behavior_score", 50)

    trust_update = compute_trust_update(
        user.trust_score,
        behavior_score,
        fraud_score,
    )

    if isinstance(trust_update, dict) and "new_score" in trust_update:
        logger.info({
            "trust_update": {
                "old": user.trust_score,
                "new": trust_update["new_score"],
                "behavior": behavior_score,
                "fraud": fraud_score
            }
        })
        user.trust_score = trust_update["new_score"]
    else:
        logger.warning("Trust update failed, keeping previous score")

    # 🔥 SAVE CLAIM
    claim = Claim(
        user_id=user.id,
        policy_id=policy.id,
        trigger_type=trigger_type,
        status="approved",
        payout_amount=adjusted_payout,
    )

    db.add(claim)

    # 🔥 POLICY LIMIT UPDATE
    policy.claims_this_week = (policy.claims_this_week or 0) + 1
    policy.claims_this_month = (policy.claims_this_month or 0) + 1

    # 🔥 COOLDOWN TRACKING
    user.append_claim_timestamp(datetime.utcnow().isoformat())

    # 🔥 PAYOUT HISTORY
    history = user.get_payout_history() or []

    history.append({
        "amount": adjusted_payout,
        "trigger": trigger_type,
        "date": datetime.utcnow().isoformat(),
    })

    user.set_payout_history(history[-50:])

    # 🔥 FINAL COMMIT
    db.commit()

    # ──────────────────────────────────────────────
    # 🔥 DECISION CONFIDENCE
    # ──────────────────────────────────────────────
    decision_confidence = (
        0.4 * fraud.get("confidence", 0.7) +
        0.3 * (behavioral.get("behavior_score", 70) / 100) +
        0.3 * env_after.get("confidence", 0.7)
    )

    # ──────────────────────────────────────────────
    # FINAL RESPONSE
    # ──────────────────────────────────────────────
    return {
        "status": "approved",
        "claim_id": claim.id,
        "payout_breakdown": payout,

        "fraud_analysis": {
            "fraud_score": fraud_score,
            "probability": fraud_prob,
            "confidence": fraud.get("confidence", 0.7),
            "model_type": fraud.get("model_type", "hybrid"),
            "signals": fraud_flags,
            "explainability_summary": (
                "⚠ Claim flagged due to suspicious behavioral patterns"
                if fraud_prob > 0.7 else
                "No suspicious behavior detected"
            )
        },

        "behavioral_analysis": behavioral,
        "income_prediction": income_pred,
        "trust_update": trust_update,
        "environment": env_after,

        "decision_confidence": round(decision_confidence, 2),
        "risk_tier": get_risk_tier(user.trust_score),
    }