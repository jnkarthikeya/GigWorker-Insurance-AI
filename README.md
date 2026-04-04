# ⚡ ShieldPay – AI-Powered Dynamic Income Protection Insurance

> Research-grade parametric insurance system for gig workers.  
> Combines FastAPI + React + ML (fraud detection + income prediction) + behavioral analytics + XAI.

---

## System Architecture

```
shieldpay/
├── backend/
│   ├── main.py            ← FastAPI app + all routes
│   ├── models.py          ← SQLAlchemy ORM + Pydantic schemas
│   ├── auth.py            ← JWT auth (register/login/refresh)
│   ├── claims.py          ← Claim engine + payout formula
│   ├── behavioral.py      ← 5-dimension behavioral analytics
│   ├── ml_engine.py       ← ML inference (fraud + income)
│   ├── data_sources.py    ← Environmental simulation engine
│   ├── requirements.txt
│   └── .env.example
│
├── ml/
│   ├── generate_dataset.py ← Synthetic training data (10k fraud + 5k income)
│   ├── train_fraud.py      ← RandomForest fraud classifier
│   ├── train_income.py     ← GradientBoosting income predictor
│   ├── models/             ← Saved .pkl model files
│   ├── data/               ← CSV datasets
│   └── results/            ← Evaluation plots + metrics JSON
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── api.js          ← Axios client + interceptors
    │   ├── styles.css      ← Global design system
    │   ├── pages/
    │   │   ├── Login.jsx
    │   │   ├── Register.jsx
    │   │   ├── Dashboard.jsx ← Main dashboard with charts
    │   │   └── Policy.jsx    ← Policy + claims + audit
    │   └── components/
    │       ├── ClaimModal.jsx  ← Full XAI claim result modal
    │       ├── TrustGauge.jsx  ← SVG trust ring gauge
    │       ├── EnvPanel.jsx    ← Live environment panel
    │       └── BehavioralPanel.jsx
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## Mathematical Formulations

### Payout Formula
```
Payout = Base × TrustFactor × (1 − FraudScore/100) × EnvFactor

Where:
  Base        = CoverageAmount × (income_drop_pct / 100)
  TrustFactor = trust_score / 100  ∈ [0.10, 1.00]
  FraudScore  = ML fraud probability × 100  ∈ [0, 100]
  EnvFactor   = composite_env_score / 100  ∈ [0.30, 1.00]
```

### Fraud Detection
```
P(fraud | X) = sigmoid(wᵀX + b)

For RandomForest:
  P(fraud | X) = (1/T) Σ_t I(h_t(X) = fraud)

Features X:
  [login_variance, claim_interval_std, session_duration_mean,
   income_deviation, claim_velocity_7d]
```

### Income Prediction
```
ŷ = f(X)  [GradientBoosting ensemble]

Loss: L = Σ(y − ŷ)² / N  [MSE]

Confidence Band:
  lower = ŷ − 1.5σ
  upper = ŷ + 1.5σ

Heuristic fallback:
  ŷ = recent_avg × trend_adj × (1 − env_impact)
  env_impact = 0.40×rain + 0.35×demand + 0.15×aqi + 0.10×traffic
```

### Trust Update
```
Δ = α × (behavior_score/100) × direction − β × fraud_penalty

Where:
  α = 0.10  (learning rate)
  β = 0.30  (fraud penalty weight)
  direction = +1 if approved, −1 if blocked
```

### Behavioral Score (Weighted Composite)
```
behavior_score = Σ_i w_i × score_i

Weights:
  login_frequency:    20%
  claim_timing:       30%   ← highest weight (key fraud signal)
  session_consistency: 15%
  income_consistency:  20%
  claim_velocity:      15%
```

---

## Quick Start

### 1. Clone & Setup Backend

```bash
cd shieldpay/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env to set JWT_SECRET_KEY

# Start API server
uvicorn main:app --reload --port 8000
```

### 2. Train ML Models (Optional but recommended)

```bash
cd shieldpay/ml

# Generate synthetic training datasets
python generate_dataset.py

# Train fraud detection model (RandomForest)
python train_fraud.py

# Train income prediction model (GradientBoosting)
python train_income.py

# Models saved to: ml/models/fraud_model.pkl, income_model.pkl
# Evaluation plots: ml/results/*.png
# Metrics: ml/results/*.json
```

> Without training, the system uses high-quality rule-based fallbacks.

### 3. Start Frontend

```bash
cd shieldpay/frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/auth/register` | Register gig worker + create policy |
| POST | `/auth/login` | Authenticate → JWT tokens |
| POST | `/auth/refresh` | Refresh access token |
| GET  | `/users/me` | User profile + history |
| PUT  | `/users/me` | Update profile |
| GET  | `/policies/me` | Policy details |
| GET  | `/environment` | Live env data |
| POST | `/claims/trigger` | File parametric claim |
| GET  | `/claims/history` | Claim history |
| GET  | `/claims/{id}` | Claim detail + XAI |
| GET  | `/dashboard/data` | All dashboard data |
| POST | `/ml/reload` | Reload ML models |
| GET  | `/audit/logs` | Audit trail |
| GET  | `/health` | Health check |
| GET  | `/docs` | Interactive API docs (Swagger) |
| GET  | `/redoc` | API docs (ReDoc) |

---

## Features

### Auth System
- JWT access token (30min) + refresh token (7 days)
- bcrypt password hashing
- Auto-refresh on 401 via Axios interceptor
- Login timestamp tracking for behavioral analytics

### Policy System
- Coverage = 60% × declared weekly income
- Premium = 2.5% × income × vehicle risk multiplier
- Vehicle risk: cycle(0.9×), bike(1.0×), scooter(1.05×), car(1.15×)
- Max 3 claims/week, 12 claims/month

### Parametric Triggers
| Trigger | Max Income Impact | Severity Levels |
|---------|------------------|-----------------|
| Rain Storm | 65% | light, moderate, heavy, severe |
| Demand Drop | 40% | light, moderate, heavy, severe |
| Pollution Spike | 50% | light, moderate, heavy, severe |
| Traffic Jam | 55% | light, moderate, heavy, severe |

### ML Models
| Model | Algorithm | Features | Metrics |
|-------|-----------|---------|---------|
| Fraud Detection | RandomForest | 5 behavioral | Accuracy, AUC-ROC, F1 |
| Income Prediction | GradientBoosting | 8 env+history | MAE, RMSE, R² |

### Dashboard Charts
- Income trend: actual + declared + confidence band (AreaChart)
- Trust score history (LineChart)
- Payout history (BarChart)
- Behavioral breakdown (progress bars)
- Live environment panel (weather/demand/AQI/traffic)

### Claim Result Modal (XAI)
Full explainability breakdown:
1. Status + payout breakdown with formula
2. Fraud analysis: score, signals, feature importances
3. Behavioral analysis: all 5 dimensions
4. Income prediction: predicted, confidence band, feature importance
5. Trust update: before → after with delta and formula
6. Decision explanation: factors, fairness note, appeal eligibility

---

## Security

- JWT with separate access/refresh secrets
- bcrypt password hashing (cost factor 12)
- Rate limiting: 5 trigger requests/minute per user
- Security headers: X-Frame-Options, X-XSS-Protection, HSTS
- Input sanitization + Pydantic validation
- Parameterized queries via SQLAlchemy ORM (injection-safe)
- Audit logging for all claim decisions and fraud evaluations

---

## Edge Deployment Note

For lightweight ESP32 deployment, replace GradientBoosting with:
```python
# Quantized decision tree (depth 4)
from sklearn.tree import DecisionTreeClassifier
model = DecisionTreeClassifier(max_depth=4)

# Export as C header with sklearn-porter
# Latency: ~0.1ms vs ~15ms for full GBM
```

Tradeoff: F1 ~0.78 vs ~0.91, but 150× faster inference.

---

## Feedback Loop (Retraining)

After each claim, data is stored and can be used to retrain:
```bash
# Add new labeled data
# Then retrain:
python ml/train_fraud.py
python ml/train_income.py

# Reload models in running API (no restart needed):
curl -X POST http://localhost:8000/ml/reload \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## License

MIT – Built as a research-grade demonstration system.
