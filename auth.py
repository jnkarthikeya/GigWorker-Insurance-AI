"""
ShieldPay – Authentication System
JWT-based auth with access + refresh tokens, bcrypt password hashing,
login tracking for behavioral analytics
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from models import User, AuditLog, get_db

# ──────────────────────────────────────────────
# Logging Setup
# ──────────────────────────────────────────────
logger = logging.getLogger("shieldpay.auth")

# ──────────────────────────────────────────────
# Config (PRODUCTION SAFE)
# ──────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY")

if not SECRET_KEY or not REFRESH_SECRET_KEY:
    logger.critical("JWT secrets not set in environment variables")
    raise RuntimeError("JWT secrets not set in environment variables")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ──────────────────────────────────────────────
# Password Hashing
# ──────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ──────────────────────────────────────────────
# Token Generation
# ──────────────────────────────────────────────
def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


# ──────────────────────────────────────────────
# Dependency: Get Current User
# ──────────────────────────────────────────────
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        logger.warning("Invalid access token used")
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()

    if user is None or not user.is_active:
        logger.warning(f"Unauthorized access attempt for user_id={user_id}")
        raise credentials_exception

    return user


# ──────────────────────────────────────────────
# Auth Service Functions
# ──────────────────────────────────────────────
def register_user(
    name: str,
    email: str,
    password: str,
    city: str,
    vehicle_type: str,
    declared_weekly_income: float,
    db: Session,
) -> Tuple[User, str, str]:

    email = email.strip().lower()
    name = name.strip()

    # Password validation
    if len(password) < 8 or password.isdigit() or password.isalpha():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 chars and include letters & numbers"
        )

    # Check duplicate
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        city=city,
        vehicle_type=vehicle_type,
        declared_weekly_income=declared_weekly_income,
        trust_score=75.0,
        sessions_count=0,
    )

    # Seed income history
    import random
    base = declared_weekly_income
    history = [round(base * random.uniform(0.85, 1.15), 2) for _ in range(8)]
    user.set_income_history(history)
    user.set_trust_history([75.0])

    db.add(user)
    db.flush()

    # Create policy
    from models import Policy
    coverage = round(0.6 * declared_weekly_income, 2)

    vehicle_risk = {"bike": 1.0, "scooter": 1.05, "cycle": 0.9, "car": 1.15}
    risk_mult = vehicle_risk.get(vehicle_type, 1.0)

    premium = round(0.025 * declared_weekly_income * risk_mult, 2)

    policy = Policy(
        user_id=user.id,
        coverage_amount=coverage,
        weekly_premium=premium,
        wallet_balance=0.0,
        total_payout=0.0,
    )
    db.add(policy)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="user_register",
        summary=f"User {name} registered from {city}",
    )
    db.add(audit)

    db.commit()
    db.refresh(user)

    logger.info(f"New user registered: {email}")

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    return user, access_token, refresh_token


def login_user(
    email: str,
    password: str,
    db: Session,
) -> Tuple[User, str, str]:

    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        logger.warning(f"Failed login attempt: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended"
        )

    # Track login
    ts = datetime.utcnow().isoformat()
    user.append_login_timestamp(ts)
    user.sessions_count += 1

    logger.info(f"User login: {user.id} | session #{user.sessions_count}")

    audit = AuditLog(
        user_id=user.id,
        action="user_login",
        summary=f"User {user.name} logged in",
    )
    db.add(audit)

    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    return user, access_token, refresh_token


def refresh_access_token(refresh_token: str, db: Session) -> str:

    payload = decode_refresh_token(refresh_token)

    if not payload:
        logger.warning("Invalid refresh token used")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    logger.info(f"Access token refreshed for user {user.id}")

    return create_access_token(user.id, user.email)