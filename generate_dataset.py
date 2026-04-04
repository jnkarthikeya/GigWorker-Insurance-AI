"""
ShieldPay – Synthetic Dataset Generator
Generates training data for:
  A. Fraud Detection Model  (binary classification)
  B. Income Prediction Model (regression)

Dataset Statistics:
  Fraud dataset:  10,000 samples, ~15% fraud rate (realistic imbalance)
  Income dataset: 5,000 samples, continuous target

Usage:
  python generate_dataset.py
  
Outputs:
  ./data/fraud_dataset.csv
  ./data/income_dataset.csv
"""

import os
import math
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

os.makedirs("./data", exist_ok=True)


# ──────────────────────────────────────────────
# A. Fraud Detection Dataset
# ──────────────────────────────────────────────

def generate_fraud_dataset(n_samples: int = 10000) -> pd.DataFrame:
    """
    Generate labeled fraud detection dataset.
    
    Features (X):
      1. login_variance         – std of inter-login intervals (hours)
      2. claim_interval_std     – std of inter-claim intervals (hours)
      3. session_duration_mean  – mean session length (seconds)
      4. income_deviation       – |declared - actual| / declared
      5. claim_velocity_7d      – claims in last 7 days
    
    Label (y): is_fraud (0/1)
    
    Legitimate user profile:
      - Login variance: ~8–72 hours (normal daily variation)
      - Claim intervals: high variance (events are random)
      - Session duration: 120–600 seconds (2–10 min)
      - Income deviation: < 0.2 (slight inflation allowed)
      - Claim velocity: 0–2 per week
    
    Fraud user profile:
      - Login variance: < 1 hour (scripted) OR > 200 hours (dormant then burst)
      - Claim intervals: near-zero std (automated) or exactly 24h
      - Session duration: < 15 seconds (bot) or exactly equal
      - Income deviation: > 0.4 (significant inflation)
      - Claim velocity: 3+ per week (farming)
    """
    records = []
    n_fraud = int(n_samples * 0.15)  # 15% fraud rate
    n_legit = n_samples - n_fraud

    def add_noise(val, scale=0.1):
        return max(0, val + np.random.normal(0, scale * abs(val) + 0.01))

    # ── Legitimate users ──
    for _ in range(n_legit):
        login_variance = add_noise(np.random.uniform(8, 72))
        claim_interval_std = add_noise(np.random.uniform(20, 200))
        session_mean = add_noise(np.random.uniform(120, 600))
        income_deviation = add_noise(np.random.uniform(0.01, 0.20))
        claim_velocity = int(np.random.choice([0, 0, 0, 1, 1, 2], p=[0.30, 0.25, 0.20, 0.15, 0.07, 0.03]))
        records.append({
            "login_variance": round(login_variance, 4),
            "claim_interval_std": round(claim_interval_std, 4),
            "session_duration_mean": round(session_mean, 2),
            "income_deviation": round(income_deviation, 4),
            "claim_velocity_7d": float(claim_velocity),
            "is_fraud": 0,
        })

    # ── Fraud users ──
    fraud_profiles = [
        # Bot: low login variance, zero claim std, very short sessions
        lambda: {
            "login_variance": add_noise(np.random.uniform(0.1, 1.5)),
            "claim_interval_std": add_noise(np.random.uniform(0, 0.5)),
            "session_duration_mean": add_noise(np.random.uniform(2, 15)),
            "income_deviation": add_noise(np.random.uniform(0.05, 0.60)),
            "claim_velocity_7d": float(np.random.randint(3, 7)),
        },
        # Income inflation: high income deviation, moderate everything else
        lambda: {
            "login_variance": add_noise(np.random.uniform(10, 50)),
            "claim_interval_std": add_noise(np.random.uniform(10, 100)),
            "session_duration_mean": add_noise(np.random.uniform(60, 300)),
            "income_deviation": add_noise(np.random.uniform(0.45, 0.90)),
            "claim_velocity_7d": float(np.random.choice([1, 2, 3])),
        },
        # Claim farming: high velocity, 24h interval pattern
        lambda: {
            "login_variance": add_noise(np.random.uniform(20, 100)),
            "claim_interval_std": add_noise(np.random.uniform(0.5, 2.0)),  # ~24h apart
            "session_duration_mean": add_noise(np.random.uniform(100, 400)),
            "income_deviation": add_noise(np.random.uniform(0.1, 0.5)),
            "claim_velocity_7d": float(np.random.randint(3, 6)),
        },
        # Dormant + burst: very high login variance
        lambda: {
            "login_variance": add_noise(np.random.uniform(200, 1000)),
            "claim_interval_std": add_noise(np.random.uniform(0, 3)),
            "session_duration_mean": add_noise(np.random.uniform(30, 200)),
            "income_deviation": add_noise(np.random.uniform(0.2, 0.7)),
            "claim_velocity_7d": float(np.random.randint(2, 5)),
        },
    ]

    for _ in range(n_fraud):
        profile_fn = random.choice(fraud_profiles)
        feat = profile_fn()
        feat["is_fraud"] = 1
        feat = {k: round(v, 4) if isinstance(v, float) else v for k, v in feat.items()}
        records.append(feat)

    df = pd.DataFrame(records)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"Fraud dataset: {len(df)} samples | Fraud rate: {df['is_fraud'].mean():.1%}")
    print(df.describe())

    df.to_csv("./data/fraud_dataset.csv", index=False)
    print("✓ Saved: ./data/fraud_dataset.csv")
    return df


# ──────────────────────────────────────────────
# B. Income Prediction Dataset
# ──────────────────────────────────────────────

def generate_income_dataset(n_samples: int = 5000) -> pd.DataFrame:
    """
    Generate income prediction dataset.
    
    Features (X):
      1. recent_avg_4w    – mean income last 4 weeks
      2. income_trend     – slope of income trend
      3. income_std       – income volatility
      4. rain_impact      – rain disruption factor (0–1)
      5. demand_impact    – demand drop factor (0–1)
      6. aqi_impact       – pollution factor (0–1)
      7. traffic_impact   – traffic factor (0–1)
      8. declared_income  – declared weekly income
    
    Target (y): actual_income_this_week
    
    Ground truth formula:
      y = recent_avg × (1 - env_impact) × trend_adj + noise
      where env_impact = 0.4×rain + 0.35×demand + 0.15×aqi + 0.1×traffic
    """
    records = []
    declared_options = [1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000]

    for _ in range(n_samples):
        declared = random.choice(declared_options)
        base = declared * random.uniform(0.7, 1.1)  # Some under/over-declare

        # Historical average
        recent_avg = base * random.uniform(0.85, 1.15)
        income_trend = random.uniform(-0.05, 0.08)
        income_std = recent_avg * random.uniform(0.05, 0.25)

        # Environmental conditions (simulate realistic distributions)
        rain_impact = max(0, min(0.65, np.random.beta(1.5, 8)))
        demand_impact = max(0, min(0.40, np.random.beta(1.2, 7)))
        aqi_impact = max(0, min(0.50, np.random.beta(2, 8)))
        traffic_impact = max(0, min(0.55, np.random.beta(1.8, 6)))

        # Ground truth income
        env_impact = (
            0.40 * rain_impact +
            0.35 * demand_impact +
            0.15 * aqi_impact +
            0.10 * traffic_impact
        )
        trend_adj = 1 + income_trend
        noise = np.random.normal(0, income_std * 0.3)
        actual_income = max(0, recent_avg * trend_adj * (1 - env_impact) + noise)

        records.append({
            "recent_avg_4w": round(recent_avg, 2),
            "income_trend": round(income_trend, 4),
            "income_std": round(income_std, 2),
            "rain_impact": round(rain_impact, 4),
            "demand_impact": round(demand_impact, 4),
            "aqi_impact": round(aqi_impact, 4),
            "traffic_impact": round(traffic_impact, 4),
            "declared_income": float(declared),
            "actual_income": round(actual_income, 2),
        })

    df = pd.DataFrame(records)

    print(f"\nIncome dataset: {len(df)} samples")
    print(f"Target range: ₹{df['actual_income'].min():.0f} – ₹{df['actual_income'].max():.0f}")
    print(df.describe())

    df.to_csv("./data/income_dataset.csv", index=False)
    print("✓ Saved: ./data/income_dataset.csv")
    return df


if __name__ == "__main__":
    print("=" * 60)
    print("ShieldPay – Dataset Generator")
    print("=" * 60)
    df_fraud = generate_fraud_dataset(10000)
    df_income = generate_income_dataset(5000)
    print("\n✓ All datasets generated successfully")
