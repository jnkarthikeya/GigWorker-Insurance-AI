import asyncio
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import get_current_user, login_user, refresh_access_token, register_user
from .behavioral import run_behavioral_analysis
from .claims import ClaimException, get_risk_tier, process_claim
from .data_sources import get_full_environment
from .ml_engine import predict_trigger_probability, reload_models
from .models import (
    AuditLog,
    Claim,
    Policy,
    User,
    UserLoginRequest,
    UserRegisterRequest,
    TriggerRequest,
    get_db,
    init_db,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("shieldpay.log")],
)
logger = logging.getLogger("shieldpay")

app = FastAPI(
    title="ShieldPay API",
    description="AI-powered income protection platform for gig workers.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_connections: Dict[int, set[WebSocket]] = defaultdict(set)
dashboard_connections: set[WebSocket] = set()
_rate_limits: dict[str, list[float]] = defaultdict(list)

AUTO_TRIGGER_INTERVAL = int(os.getenv("AUTO_TRIGGER_INTERVAL", "12"))
AUTO_TRIGGER_COOLDOWN_MIN = int(os.getenv("AUTO_TRIGGER_COOLDOWN_MIN", "10"))
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5


def _check_rate_limit(user_id: int, endpoint: str = "trigger") -> None:
    key = f"{user_id}:{endpoint}"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    _rate_limits[key] = [ts for ts in _rate_limits[key] if ts > window_start]
    if len(_rate_limits[key]) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {RATE_LIMIT_MAX} per minute",
        )
    _rate_limits[key].append(now)


def _can_auto_trigger(user: User) -> bool:
    if not user.last_auto_trigger_at:
        return True
    return datetime.utcnow() - user.last_auto_trigger_at >= timedelta(minutes=AUTO_TRIGGER_COOLDOWN_MIN)


async def _send_json_safe(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except Exception:
        return False


async def send_user_update(user_id: int, payload: dict) -> None:
    stale = []
    for websocket in list(user_connections[user_id]):
        ok = await _send_json_safe(websocket, payload)
        if not ok:
            stale.append(websocket)
    for websocket in stale:
        user_connections[user_id].discard(websocket)


async def broadcast_dashboard(payload: dict) -> None:
    stale = []
    for websocket in list(dashboard_connections):
        ok = await _send_json_safe(websocket, payload)
        if not ok:
            stale.append(websocket)
    for websocket in stale:
        dashboard_connections.discard(websocket)


async def push_claim_progress(user_id: int, result: dict) -> None:
    base = {"timestamp": datetime.utcnow().isoformat()}
    await send_user_update(user_id, {**base, "step": "trigger_detected", "data": {"status": "started"}})
    await send_user_update(user_id, {**base, "step": "environment_fetch", "data": result.get("environment", {})})
    await send_user_update(
        user_id,
        {
            **base,
            "step": "ml_analysis",
            "data": {
                "fraud_analysis": result.get("fraud_analysis", {}),
                "income_prediction": result.get("income_prediction", {}),
                "trust_update": result.get("trust_update", {}),
            },
        },
    )
    await send_user_update(user_id, {**base, "step": "decision", "data": result})
    if result.get("status") in {"APPROVED", "PAYMENT_REVIEW"}:
        await send_user_update(user_id, {**base, "step": "payment_processing", "data": {}})
        await send_user_update(user_id, {**base, "step": "payment_success", "data": result, "payment": result.get("payment")})


def _serialize_dashboard(user: User, db: Session) -> dict:
    policy = db.query(Policy).filter(Policy.user_id == user.id).first()
    environment = get_full_environment(user.city)
    behavioral = run_behavioral_analysis(user)

    claims = (
        db.query(Claim)
        .filter(Claim.user_id == user.id)
        .order_by(Claim.created_at.desc())
        .limit(5)
        .all()
    )

    recent_claims = [
        {
            "id": claim.id,
            "trigger_type": claim.trigger_type,
            "status": claim.status,
            "amount": claim.adjusted_payout or 0,
            "fraud_score": claim.fraud_score or 0,
            "created_at": claim.created_at.isoformat(),
        }
        for claim in claims
    ]

    income_history = user.get_income_history()
    chart = []
    for idx, amount in enumerate(income_history[-8:]):
        chart.append(
            {
                "month": f"W{idx + 1}",
                "actual": round(amount, 2),
                "predicted": round(user.declared_weekly_income, 2),
            }
        )

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "city": user.city,
            "vehicle_type": user.vehicle_type,
            "declared_weekly_income": user.declared_weekly_income,
            "trust_score": user.trust_score,
            "risk_tier": get_risk_tier(user.trust_score or 0),
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
            "total_payout": policy.total_payout if policy else 0,
        },
        "environment": environment,
        "behavioral": behavioral,
        "income_chart": chart,
        "trust_history": user.get_trust_history(),
        "payout_history": user.get_payout_history(),
        "recent_claims": recent_claims,
    }


async def auto_trigger_engine() -> None:
    await asyncio.sleep(2)
    while True:
        db = next(get_db())
        try:
            users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
            for user in users:
                if not _can_auto_trigger(user):
                    continue
                environment = get_full_environment(user.city)
                trigger = predict_trigger_probability(environment, user)
                if not trigger.get("should_trigger"):
                    continue

                try:
                    result = process_claim(
                        user=user,
                        trigger_type=trigger.get("trigger_type") or "rain",
                        db=db,
                        environment_override=environment,
                    )
                except ClaimException:
                    continue

                user.last_auto_trigger_at = datetime.utcnow()
                user.last_trigger_type = result["trigger_type"]
                db.add(
                    AuditLog(
                        user_id=user.id,
                        action="auto_trigger",
                        summary=f"Auto-triggered {result['trigger_type']}",
                    )
                )
                db.commit()

                await push_claim_progress(user.id, result)
                await broadcast_dashboard(
                    {
                        "type": "claim_update",
                        "user_id": user.id,
                        "claim": {
                            "status": result["status"],
                            "trigger_type": result["trigger_type"],
                            "amount": result["payout"]["final"],
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
        except Exception as exc:
            logger.error("Auto trigger engine failure: %s", exc)
        finally:
            db.close()
        await asyncio.sleep(AUTO_TRIGGER_INTERVAL)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(auto_trigger_engine())
    logger.info("ShieldPay API started")


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "ShieldPay API",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
    }


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
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "role": user.role,
        "message": "Registration successful",
    }


@app.post("/auth/login", tags=["Authentication"])
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user, access_token, refresh_token = login_user(payload.email, payload.password, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "role": user.role,
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/auth/refresh", tags=["Authentication"])
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    access_token = refresh_access_token(payload.refresh_token, db)
    return {"access_token": access_token, "token_type": "bearer"}


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
        "risk_tier": get_risk_tier(user.trust_score or 0),
        "sessions_count": user.sessions_count,
        "income_history": user.get_income_history(),
        "trust_score_history": user.get_trust_history(),
        "payout_history": user.get_payout_history(),
        "created_at": user.created_at.isoformat(),
    }


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


@app.get("/environment", tags=["Environment"])
def get_environment(city: Optional[str] = None, user: User = Depends(get_current_user)):
    return get_full_environment(city or user.city)


@app.post("/claims/trigger", tags=["Claims"])
async def trigger_claim(
    payload: TriggerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_rate_limit(user.id, "trigger")
    environment = get_full_environment(payload.city or user.city)

    try:
        result = process_claim(
            user=user,
            trigger_type=payload.trigger_type,
            db=db,
            environment_override=environment,
        )
    except ClaimException as exc:
        raise HTTPException(status_code=422, detail={"status": exc.status, "reason": exc.reason}) from exc

    user.last_auto_trigger_at = datetime.utcnow()
    user.last_trigger_type = result["trigger_type"]
    db.commit()

    await push_claim_progress(user.id, result)
    return result


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
                "id": claim.id,
                "trigger_type": claim.trigger_type,
                "status": claim.status,
                "adjusted_payout": claim.adjusted_payout,
                "fraud_score": claim.fraud_score,
                "created_at": claim.created_at.isoformat(),
                "details": claim.get_details(),
            }
            for claim in claims
        ]
    }


@app.get("/dashboard/data", tags=["Dashboard"])
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize_dashboard(user, db)


@app.post("/ml/reload", tags=["ML"])
def reload_ml_models_route(user: User = Depends(get_current_user)):
    result = reload_models()
    logger.info("ML models reloaded by user %s", user.id)
    return result


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
                "action": log.action,
                "summary": log.summary,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in logs
        ]
    }


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    dashboard_connections.add(websocket)
    try:
        while True:
            payload = {
                "type": "environment_update",
                "environment": get_full_environment("Bangalore"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            ok = await _send_json_safe(websocket, payload)
            if not ok:
                break
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    finally:
        dashboard_connections.discard(websocket)


@app.websocket("/ws/{user_id}")
async def websocket_user(websocket: WebSocket, user_id: int):
    await websocket.accept()
    user_connections[user_id].add(websocket)
    db = next(get_db())
    try:
        while True:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await websocket.close(code=1008)
                break

            environment = get_full_environment(user.city)
            ml_result = predict_trigger_probability(environment, user)
            payload = {
                "type": "environment_update",
                "step": "environment_update",
                "environment": environment,
                "ml": ml_result,
                "timestamp": datetime.utcnow().isoformat(),
            }
            ok = await _send_json_safe(websocket, payload)
            if not ok:
                break
            await asyncio.sleep(4)
    except WebSocketDisconnect:
        pass
    finally:
        user_connections[user_id].discard(websocket)
        db.close()
