"""
ShieldPay – Database Models & Pydantic Schemas
SQLAlchemy ORM models + request/response validation schemas
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, create_engine
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from pydantic import BaseModel, EmailStr, field_validator
import os

# ──────────────────────────────────────────────
# Database Setup
# ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shieldpay.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────
# SQLAlchemy ORM Models
# ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    city = Column(String(100), default="Mumbai")
    vehicle_type = Column(String(50), default="bike")  # bike, scooter, cycle, car
    declared_weekly_income = Column(Float, default=3000.0)
    last_auto_trigger_at = Column(DateTime, nullable=True)
    last_trigger_type = Column(String(50), nullable=True)
    # JSON-serialized arrays stored as Text
    income_history = Column(Text, default="[]")       # list of floats
    trust_score_history = Column(Text, default="[]")  # list of floats
    payout_history = Column(Text, default="[]")       # list of dicts

    trust_score = Column(Float, default=75.0)         # 0–100
    sessions_count = Column(Integer, default=0)
    login_timestamps = Column(Text, default="[]")     # ISO strings
    claim_timestamps = Column(Text, default="[]")     # ISO strings
    session_durations = Column(Text, default="[]")    # seconds

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    policy = relationship("Policy", back_populates="user", uselist=False)
    claims = relationship("Claim", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    # ── Helpers ──
    def get_income_history(self) -> List[float]:
        return json.loads(self.income_history or "[]")

    def set_income_history(self, data: List[float]):
        self.income_history = json.dumps(data)

    def get_trust_history(self) -> List[float]:
        return json.loads(self.trust_score_history or "[]")

    def set_trust_history(self, data: List[float]):
        self.trust_score_history = json.dumps(data)

    def get_payout_history(self) -> List[dict]:
        return json.loads(self.payout_history or "[]")

    def set_payout_history(self, data: List[dict]):
        self.payout_history = json.dumps(data)

    def get_login_timestamps(self) -> List[str]:
        return json.loads(self.login_timestamps or "[]")

    def append_login_timestamp(self, ts: str):
        arr = self.get_login_timestamps()
        arr.append(ts)
        arr = arr[-50:]  # Keep last 50
        self.login_timestamps = json.dumps(arr)

    def get_claim_timestamps(self) -> List[str]:
        return json.loads(self.claim_timestamps or "[]")

    def append_claim_timestamp(self, ts: str):
        arr = self.get_claim_timestamps()
        arr.append(ts)
        self.claim_timestamps = json.dumps(arr)

    def get_session_durations(self) -> List[float]:
        return json.loads(self.session_durations or "[]")

    def append_session_duration(self, duration: float):
        arr = self.get_session_durations()
        arr.append(duration)
        arr = arr[-30:]  # Keep last 30
        self.session_durations = json.dumps(arr)


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)

    coverage_amount = Column(Float)        # 0.6 * declared_weekly_income
    weekly_premium = Column(Float)         # dynamically computed
    max_claims_week = Column(Integer, default=3)
    max_claims_month = Column(Integer, default=12)
    status = Column(String(50), default="active")

    claims_this_week = Column(Integer, default=0)
    claims_this_month = Column(Integer, default=0)
    week_reset_at = Column(DateTime, default=datetime.utcnow)
    month_reset_at = Column(DateTime, default=datetime.utcnow)

    total_payout = Column(Float, default=0.0)
    wallet_balance = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="policy")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    trigger_type = Column(String(100))     # rain, demand_drop, pollution, traffic
    trigger_severity = Column(String(50))  # low, moderate, high, severe
    income_drop_pct = Column(Float)        # estimated income drop %

    base_payout = Column(Float)
    adjusted_payout = Column(Float)
    fraud_score = Column(Float)
    trust_score_before = Column(Float)
    trust_score_after = Column(Float)

    status = Column(String(50))            # approved, blocked, excluded
    details = Column(Text, default="{}")   # Full JSON breakdown

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="claims")

    def get_details(self) -> dict:
        return json.loads(self.details or "{}")

    def set_details(self, data: dict):
        self.details = json.dumps(data)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100))      # claim_decision, login, fraud_evaluation, trust_update
    summary = Column(Text)
    metadata_ = Column(Text, default="{}")   # Extra JSON
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")

    def get_metadata(self) -> dict:
        return json.loads(self.metadata_ or "{}")


# ──────────────────────────────────────────────
# Pydantic Schemas (Request / Response)
# ──────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    city: str = "Mumbai"
    vehicle_type: str = "bike"
    declared_weekly_income: float = 3000.0

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle(cls, v):
        allowed = {"bike", "scooter", "cycle", "car"}
        if v not in allowed:
            raise ValueError(f"vehicle_type must be one of {allowed}")
        return v

    @field_validator("declared_weekly_income")
    @classmethod
    def validate_income(cls, v):
        if v < 500 or v > 100000:
            raise ValueError("Income must be between 500 and 100000")
        return v


class UserLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    name: str


class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    city: str
    vehicle_type: str
    declared_weekly_income: float
    trust_score: float
    sessions_count: int
    income_history: List[float]
    trust_score_history: List[float]
    payout_history: List[dict]
    created_at: str


class PolicyResponse(BaseModel):
    id: int
    coverage_amount: float
    weekly_premium: float
    max_claims_week: int
    max_claims_month: int
    status: str
    claims_this_week: int
    claims_this_month: int
    total_payout: float
    wallet_balance: float


class TriggerRequest(BaseModel):
    trigger_type: str
    city: Optional[str] = None
    override_severity: Optional[str] = None  # for testing

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger(cls, v):
        allowed = {"rain", "demand_drop", "pollution", "traffic"}
        if v not in allowed:
            raise ValueError(f"trigger_type must be one of {allowed}")
        return v


class ClaimResultResponse(BaseModel):
    claim_id: int
    status: str
    payout_breakdown: dict
    fraud_analysis: dict
    behavioral_analysis: dict
    income_prediction: dict
    trust_update: dict
    explainability: dict
    environment: dict
    timestamp: str


class EnvironmentResponse(BaseModel):
    city: str
    weather: dict
    demand: dict
    aqi: dict
    traffic: dict
    timestamp: str


class AuditLogResponse(BaseModel):
    id: int
    action: str
    summary: str
    timestamp: str


# ──────────────────────────────────────────────
# DB Init
# ──────────────────────────────────────────────

def init_db():
    Base.metadata.create_all(bind=engine)
