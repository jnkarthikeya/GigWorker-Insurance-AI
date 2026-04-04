"""
ShieldPay – Main FastAPI Application (FULL RESTORED + UPGRADED)
"""

import os
from dotenv import load_dotenv
load_dotenv()
import time
from ml_engine import predict_trigger_probability
import logging
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from models import (
    User, Policy, Claim, AuditLog, init_db, get_db,
    UserRegisterRequest, UserLoginRequest, TriggerRequest,
)
from auth import (
    register_user, login_user, refresh_access_token, get_current_user
)
from claims import process_claim, ClaimException
from data_sources import get_full_environment
from ml_engine import reload_models
from behavioral import run_behavioral_analysis
from claims import get_risk_tier  

# ──────────────────────────────────────────────
# LOGGING (PRODUCTION)
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("shieldpay.log")
    ]
)
logger = logging.getLogger("shieldpay")

def log_trigger(db, user, trigger_type, environment):
    log = AuditLog(
        user_id=user.id,
        action="auto_trigger",
        metadata={
            "trigger": trigger_type,
            "env": environment
        }
    )
    db.add(log)
    db.commit()
# ──────────────────────────────────────────────
# APP INIT
# ──────────────────────────────────────────────
app = FastAPI(
    title="ShieldPay API",
    description=(
        "AI-Powered Dynamic Income Protection Insurance for Gig Workers. "
        "Parametric triggers, fraud detection, behavioral analytics, XAI."
    ),
    version="1.0.0",
)

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# auto trigger engine#
from datetime import datetime, timedelta

AUTO_TRIGGER_COOLDOWN_MIN = 10  # 🔥 safe window


def check_auto_trigger(user, environment: dict) -> str | None:
    now = datetime.utcnow()

    # 🔒 Cooldown protection
    if user.last_auto_trigger_at:
        if now - user.last_auto_trigger_at < timedelta(minutes=AUTO_TRIGGER_COOLDOWN_MIN):
            return None

    weather = environment.get("weather", {})
    demand = environment.get("demand", {})
    aqi = environment.get("aqi", {})
    traffic = environment.get("traffic", {})

    trigger = None

    if weather.get("severity") in ["heavy", "severe"]:
        trigger = "rain"

    elif demand.get("index", 100) < 40:
        trigger = "demand_drop"

    elif aqi.get("value", 0) > 250:
        trigger = "pollution"

    elif traffic.get("severity") == "gridlock":
        trigger = "traffic"

    # 🔒 Prevent same trigger spam
    if trigger and user.last_trigger_type == trigger:
        return None

    return trigger
# ──────────────────────────────────────────────
# RATE LIMITING
# ──────────────────────────────────────────────
_rate_limits: dict = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5

logger.warning("Using in-memory rate limiter (NOT production safe)")

def check_rate_limit(user_id: int, endpoint: str = "trigger"):
    key = f"{user_id}:{endpoint}"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    _rate_limits[key] = [ts for ts in _rate_limits[key] if ts > window_start]

    if len(_rate_limits[key]) >= RATE_LIMIT_MAX:
        logger.warning(f"Rate limit exceeded for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {RATE_LIMIT_MAX} per minute"
        )

    _rate_limits[key].append(now)

# ──────────────────────────────────────────────
# SECURITY HEADERS
# ──────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ──────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("ShieldPay API started successfully")

# ──────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "ShieldPay API",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }
from pydantic import BaseModel
class TriggerRequest(BaseModel):
    trigger_type: str
# ──────────────────────────────────────────────
# AUTH ROUTES
# ──────────────────────────────────────────────
@app.post("/auth/register", tags=["Authentication"])
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = register_user(
        payload.name,
        payload.email,
        payload.password,
        payload.city,
        payload.vehicle_type,
        payload.declared_weekly_income,
        db,
    )

    logger.info(f"User registered: {user.id}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "message": "Registration successful",
    }


@app.post("/auth/login", tags=["Authentication"])
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = login_user(
        payload.email,
        payload.password,
        db,
    )

    logger.info(f"User logged in: {user.id}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
    }


@app.post("/auth/refresh", tags=["Authentication"])
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    access_token = refresh_access_token(refresh_token, db)
    return {"access_token": access_token, "token_type": "bearer"}

# ──────────────────────────────────────────────
# USER ROUTES
# ──────────────────────────────────────────────
@app.get("/users/me", tags=["Users"])
def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "city": user.city,
        "vehicle_type": user.vehicle_type,
        "declared_weekly_income": user.declared_weekly_income,
        "trust_score": user.trust_score,
        "sessions_count": user.sessions_count,
        "income_history": user.get_income_history(),
        "trust_score_history": user.get_trust_history(),
        "payout_history": user.get_payout_history(),
        "created_at": user.created_at.isoformat(),
    }


@app.put("/users/me", tags=["Users"])
def update_profile(
    declared_weekly_income: Optional[float] = None,
    city: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if declared_weekly_income and 500 <= declared_weekly_income <= 100000:
        user.declared_weekly_income = declared_weekly_income

        policy = db.query(Policy).filter(Policy.user_id == user.id).first()
        if policy:
            policy.coverage_amount = round(0.6 * declared_weekly_income, 2)
            vehicle_risk = {"bike": 1.0, "scooter": 1.05, "cycle": 0.9, "car": 1.15}
            risk_mult = vehicle_risk.get(user.vehicle_type, 1.0)
            policy.weekly_premium = round(0.025 * declared_weekly_income * risk_mult, 2)

    if city:
        user.city = city.strip()

    if vehicle_type and vehicle_type in {"bike", "scooter", "cycle", "car"}:
        user.vehicle_type = vehicle_type

    audit = AuditLog(
        user_id=user.id,
        action="profile_update",
        summary=f"Profile updated"
    )
    db.add(audit)

    db.commit()
    db.refresh(user)

    logger.info(f"User profile updated: {user.id}")

    return {"message": "Profile updated", "user_id": user.id}

# ──────────────────────────────────────────────
# POLICY ROUTES
# ──────────────────────────────────────────────
@app.get("/policies/me", tags=["Policy"])
def get_policy(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.user_id == user.id).first()

    if not policy:
        raise HTTPException(status_code=404, detail="No policy found")

    return {
        "id": policy.id,
        "coverage_amount": policy.coverage_amount,
        "weekly_premium": policy.weekly_premium,
        "max_claims_week": policy.max_claims_week,
        "max_claims_month": policy.max_claims_month,
        "status": policy.status,
        "claims_this_week": policy.claims_this_week,
        "claims_this_month": policy.claims_this_month,
        "total_payout": policy.total_payout,
        "wallet_balance": policy.wallet_balance,
    }

# ──────────────────────────────────────────────
# ENVIRONMENT
# ──────────────────────────────────────────────
@app.get("/environment", tags=["Environment"])
def get_environment(city: Optional[str] = None, user: User = Depends(get_current_user)):
    target_city = city or user.city
    return get_full_environment(target_city)

# ──────────────────────────────────────────────
# CLAIMS
# ──────────────────────────────────────────────
@app.post("/claims/trigger", tags=["Claims"])
def trigger_claim(
    payload: TriggerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(f"User {user.id} triggered claim: {payload.trigger_type}")

    check_rate_limit(user.id)

    try:
        # 🔥 FIX: ensure trigger_type is always string
        trigger_type = payload.trigger_type

        if isinstance(trigger_type, dict):
            logger.warning(f"⚠️ trigger_type received as dict: {trigger_type}")
            trigger_type = trigger_type.get("type") or trigger_type.get("trigger_type") or "traffic"

        logger.info(f"✅ Final trigger_type used: {trigger_type}")

        # 🔥 GET REAL ENVIRONMENT (ADDED)
        try:
            env = get_full_environment(user.city)
        except Exception as e:
            logger.error(f"Env fetch failed: {e}")
            env = {}

        # 🔥 ML PREDICTION (ADDED — REAL INTEGRATION)
        ml_result = None
        try:
            ml_result = predict_trigger_probability(env, user)

            logger.info({
                "ml_result": ml_result
            })

        except Exception as e:
            logger.warning(f"ML failed: {e}")
            ml_result = {}

        # 🔥 PROCESS CLAIM (EXISTING — KEPT)
        result = process_claim(
            user=user,
            trigger_type=trigger_type,   # ✅ FIXED HERE
            db=db,
        )

        # 🔥 EXTRACT ML VALUES (ADDED)
        ml_prob = ml_result.get("probability", 0)
        income_drop = ml_result.get("income_drop_pct", 0)
        ml_trigger = ml_result.get("trigger_type", None)

        # 🔥 COMPUTE REAL PREDICTED INCOME (ADDED)
        declared_income = user.declared_weekly_income or 0

        if declared_income > 0:
            predicted_income = declared_income * (1 - income_drop / 100)
        else:
            predicted_income = declared_income

        # 🔥 EXISTING LINES (KEPT — BUT ENHANCED)
        result["new_trust_score"] = user.trust_score

        # 🔥 REPLACED FAKE VALUE WITH REAL ML
        result["predicted_income"] = predicted_income

        # 🔥 KEEP ORIGINAL BUT ENHANCE WITH ML
        result["trigger_type"] = ml_trigger or trigger_type

        # 🔥 ADD EXTRA ML SIGNALS (NEW — DOES NOT REMOVE ANYTHING)
        result["ml_probability"] = ml_prob
        result["income_drop_pct"] = income_drop

        logger.info({
            "final_claim_response": result
        })

        return result

    except Exception as e:
        logger.error(f"Claim trigger failed: {e}")
        raise HTTPException(status_code=500, detail="Claim processing failed")

        # 🔥 EVENT PUSH AFTER CLAIM
        try:
            if result.get("status") == "approved":
                asyncio.create_task(
                    push_event_alert(f"✅ Claim approved for user {user.id}")
                )
            else:
                asyncio.create_task(
                    push_event_alert(f"⚠️ Claim {result.get('status')}")
                )
        except Exception as e:
            logger.error(f"Event push failed: {e}")

        #  FRAUD DETECTION ALERT
        try:
            fraud_score = result.get("fraud_analysis", {}).get("fraud_score", 0)  

            if fraud_score > 0.75:
                asyncio.create_task(
                    push_event_alert(f"🚨 High fraud risk detected (score={fraud_score:.2f})")
                )
        except Exception as e:
            logger.error(f"Fraud alert failed: {e}")

        return result

    except ClaimException as e:
        logger.error(f"Claim failed: {e.reason}")
        raise HTTPException(status_code=422, detail={"status": e.status, "reason": e.reason})


@app.get("/claims/history", tags=["Claims"])
def claim_history(limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    claims = (
        db.query(Claim)
        .filter(Claim.user_id == user.id)
        .order_by(Claim.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )

    return {
        "claims": [
            {
                "id": c.id,
                "trigger_type": c.trigger_type,
                "adjusted_payout": c.adjusted_payout,
                "fraud_score": c.fraud_score,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
            }
            for c in claims
        ]
    }

# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────
@app.get("/dashboard/data", tags=["Dashboard"])
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.user_id == user.id).first()
    env = get_full_environment(user.city)
    behavior = run_behavioral_analysis(user)

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "city": user.city,
            "vehicle_type": user.vehicle_type,
            "declared_weekly_income": user.declared_weekly_income,
            "trust_score": user.trust_score,
            "risk_tier": get_risk_tier(user.trust_score),  # 🔥 IMPORTANT
            "sessions_count": user.sessions_count,
        },

        "policy": {
            "coverage_amount": policy.coverage_amount if policy else 0,
            "weekly_premium": policy.weekly_premium if policy else 0,
            "wallet_balance": policy.wallet_balance if policy else 0,
            "claims_this_week": policy.claims_this_week if policy else 0,
            "claims_this_month": policy.claims_this_month if policy else 0,
            "max_claims_week": policy.max_claims_week if policy else 0,
            "max_claims_month": policy.max_claims_month if policy else 0,
            "status": policy.status if policy else "inactive",
        },

        "environment": env,
        "behavioral": behavior,

        # 🔥 Charts
        "income_chart": user.get_income_history(),
        "trust_history": user.get_trust_history(),
        "payout_history": user.get_payout_history(),

        # 🔥 Recent claims (safe slice)
        "recent_claims": user.get_payout_history()[-5:] if user.get_payout_history() else [],
    }

# ──────────────────────────────────────────────
# ML ROUTES
# ──────────────────────────────────────────────
@app.post("/ml/reload", tags=["ML"])
def reload_ml_models_route(user: User = Depends(get_current_user)):
    result = reload_models()
    logger.info(f"ML models reloaded by user {user.id}")
    return result

# ──────────────────────────────────────────────
# AUDIT
# ──────────────────────────────────────────────
@app.get("/audit/logs", tags=["Audit"])
def get_audit_logs(limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(min(limit, 200))
        .all()
    )

    return {
        "logs": [
            {
                "action": l.action,
                "summary": l.summary,
                "timestamp": l.timestamp.isoformat(),
            }
            for l in logs
        ]
    }

def validate_claim(user, trigger_type: str, environment: dict) -> bool:
    """
    Validate whether a claim should be processed.

    Prevents:
    - Duplicate triggers
    - Invalid environment conditions
    - Low severity noise
    """

    try:
        # 🔒 Prevent duplicate trigger spam
        if user.last_trigger_type == trigger_type:
            return False

        # 🌍 Basic environment validation
        if not environment:
            return False

        # 🧠 Optional severity check (light filter)
        env_score = environment.get("composite_env_score", 50)

        if env_score < 30:
            return False

        return True

    except Exception as e:
        print("❌ validate_claim error:", e)
        return False
# ──────────────────────────────────────────────
# 🔥 REAL-TIME WEBSOCKET STREAMING
# ──────────────────────────────────────────────

connected_clients = set()
MAX_CLIENTS = 100


# 🔥 EVENT BROADCAST SYSTEM
async def broadcast_event(message: dict):
    disconnected = set()

    for client in list(connected_clients):
        try:
            if client.client_state.name == "CONNECTED":
                await client.send_json(message)
            else:
                disconnected.add(client)
        except Exception:
            disconnected.add(client)

    # cleanup dead clients safely
    for dc in disconnected:
        connected_clients.discard(dc)


# 🔥 PUSH ALERT EVENT
async def push_event_alert(text: str):
    payload = {
        "type": "event_alert",
        "message": text,
        "timestamp": datetime.utcnow().isoformat()
    }
    await broadcast_event(payload)


# ──────────────────────────────────────────────
# 🔥 DASHBOARD STREAM
# ──────────────────────────────────────────────
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):

    if len(connected_clients) >= MAX_CLIENTS:
        await websocket.close()
        logger.warning("Too many dashboard WS connections")
        return

    await websocket.accept()
    connected_clients.add(websocket)

    logger.info("Client connected to dashboard stream")

    last_alert_time = 0

    try:
        while True:

            # ✅ SAFE CONNECTION CHECK
            if websocket.client_state.name != "CONNECTED":
                break

            # 🔥 SAFE ENV FETCH (FIXED INDENT)
            try:
                env = get_full_environment("bangalore")
            except Exception as e:
                logger.error(f"Dashboard env error: {e}")
                await asyncio.sleep(3)
                continue

            # 🔥 SEND DATA
            try:
                await websocket.send_json({
                    "type": "environment_update",
                    "environment": env,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.warning(f"Dashboard WS send failed: {e}")
                break

            # 🔥 ALERT SYSTEM
            now = time.time()
            if env and env.get("composite_env_score", 100) < 40 and (now - last_alert_time > 15):
                asyncio.create_task(
                    push_event_alert("🌧 Severe environment conditions detected")
                )
                last_alert_time = now

            await asyncio.sleep(3)

    except WebSocketDisconnect:
        logger.info("Client disconnected")

    except Exception as e:
        logger.error(f"Dashboard WS crashed: {e}")

    finally:
        connected_clients.discard(websocket)
        logger.info("Dashboard WS cleaned up")


# ──────────────────────────────────────────────
# 🔥 USER STREAM (FINAL FIXED)
# ──────────────────────────────────────────────
@app.websocket("/ws/user/{user_id}")
async def websocket_user(websocket: WebSocket, user_id: int):

    if len(connected_clients) >= MAX_CLIENTS:
        await websocket.close()
        return

    await websocket.accept()
    connected_clients.add(websocket)

    db_gen = get_db()
    db = next(db_gen)

    logger.info(f"User {user_id} connected to user stream")

    try:
        while True:

            # ✅ CONNECTION CHECK
            if websocket.client_state.name != "CONNECTED":
                break

            await asyncio.sleep(3)

            # 🔥 Prevent stale ORM cache
            db.expire_all()

            user = db.query(User).filter(User.id == user_id).first()

            if not user:
                logger.warning("User not found, closing WS")
                await websocket.close()
                break

            # 🌍 Get environment
            try:
                env = get_full_environment(user.city)
            except Exception as e:
                logger.error(f"User env error: {e}")
                continue

            # 🔥 ML RESULT (FIXED POSITION + INDENT)
            ml_payload = None
            try:
                ml_result = predict_trigger_probability(env, user)
                ml_payload = {
                    "probability": ml_result.get("probability", 0),
                    "should_trigger": ml_result.get("should_trigger", False),
                    "trigger_type": ml_result.get("trigger_type", None)
                }
                logger.info(f"ML PAYLOAD: {ml_payload}")
            except Exception as e:
                logger.warning(f"ML packaging failed: {e}")

            # 🔥 SINGLE CLEAN SEND (REMOVED DUPLICATE)
            try:
                await websocket.send_json({
                    "type": "environment_update",
                    "environment": env,
                    "ml": ml_payload
                })
            except Exception as e:
                logger.warning(f"WS send failed: {e}")
                break

            # 🚀 AUTO-TRIGGER ENGINE
            try:
                trigger_type = None

                # 🔒 HARD COOLDOWN
                if user.last_auto_trigger_at:
                    delta = datetime.utcnow() - user.last_auto_trigger_at
                    if delta.total_seconds() < 120:
                        continue

                # 🧠 ML TRIGGER
                try:
                    ml_result = predict_trigger_probability(env, user)
                    prob = ml_result.get("probability", 0)

                    if ml_result.get("should_trigger") and prob > 0.7:
                        trigger_type = ml_result.get("trigger_type", "ml_auto")

                        logger.info({
                            "event": "ml_trigger",
                            "user": user.id,
                            "prob": prob
                        })

                except Exception as e:
                    logger.warning(f"ML trigger failed: {e}")

                # 🔁 RULE FALLBACK
                if not trigger_type:
                    trigger_type = check_auto_trigger(user, env)

                # 🚨 EXECUTION
                if trigger_type:

                    # 🔒 SECOND CHECK (ANTI-RACE)
                    if user.last_auto_trigger_at:
                        delta = datetime.utcnow() - user.last_auto_trigger_at
                        if delta.total_seconds() < 120:
                            continue

                    if not validate_claim(user, trigger_type, env):
                        logger.warning("Claim validation failed")
                        continue

                    log_trigger(db, user, trigger_type, env)

                    result = process_claim(user, trigger_type, db)

                    # ✅ Update tracking
                    user.last_auto_trigger_at = datetime.utcnow()
                    user.last_trigger_type = trigger_type
                    db.commit()

                    # 🔥 USER ALERT
                    try:
                        await websocket.send_json({
                            "type": "event_alert",
                            "message": f"⚡ AUTO CLAIM: {trigger_type.upper()}",
                            "claim": result
                        })
                    except Exception as e:
                        logger.warning(f"Auto alert failed: {e}")

                    # 🌐 BROADCAST
                    asyncio.create_task(
                        broadcast_event({
                            "type": "event_alert",
                            "message": f"⚡ SYSTEM ALERT: {trigger_type}",
                            "claim": result
                        })
                    )

            except Exception as e:
                logger.warning(f"Auto-trigger failed: {str(e)}")

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        try:
            connected_clients.discard(websocket)
            db.close()
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")