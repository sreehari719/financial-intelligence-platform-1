import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, validator
import csv, io, re
from passlib.context import CryptContext
from jose import jwt, JWTError

app = FastAPI(title="FinSight Financial Intelligence Platform", version="2.0")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "https://finsight-frontend-tau.vercel.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in frontend_origin.split(",") if origin.strip()] + ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not configured. Add your hosted PostgreSQL connection string in the backend environment variables."
        )
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode="require")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {type(exc).__name__}")


def init_db():
    if not DATABASE_URL:
        return
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email TEXT UNIQUE,
                        phone TEXT UNIQUE,
                        mpin_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'CUSTOMER',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                # Backward-compatible migration for existing email-only accounts.
                cur.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_phone_unique ON users(phone) WHERE phone IS NOT NULL")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
                        category TEXT NOT NULL,
                        location TEXT NOT NULL,
                        transaction_time TIMESTAMPTZ NOT NULL,
                        device TEXT NOT NULL,
                        risk_score NUMERIC(5,2) NOT NULL DEFAULT 0,
                        fraud_probability NUMERIC(5,4) NOT NULL DEFAULT 0,
                        decision TEXT NOT NULL DEFAULT 'LEGITIMATE',
                        risk_factors JSONB NOT NULL DEFAULT '[]'::jsonb,
                        is_demo BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS portfolios (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        asset TEXT NOT NULL,
                        asset_type TEXT NOT NULL,
                        invested_value NUMERIC(14,2) NOT NULL CHECK (invested_value >= 0),
                        current_value NUMERIC(14,2) NOT NULL CHECK (current_value >= 0),
                        is_demo BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        action TEXT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS demo_seeded_users (
                        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        seeded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    init_db()


class AuthRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    mpin: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

    @validator("identifier")
    def normalize_identifier(cls, value):
        value = value.strip()
        if "@" in value:
            value = value.lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                raise ValueError("Enter a valid email address or phone number.")
            return value
        digits = re.sub(r"[^0-9]", "", value)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Enter an email or phone number with country code if needed.")
        return digits


class TransactionRequest(BaseModel):
    amount: float = Field(gt=0, le=1000000000)
    category: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=120)
    transaction_time: Optional[datetime] = None
    device: str = Field(min_length=1, max_length=120)


class PortfolioRequest(BaseModel):
    asset: str = Field(min_length=1, max_length=120)
    asset_type: str = Field(min_length=1, max_length=60)
    invested_value: float = Field(ge=0, le=1000000000)
    current_value: float = Field(ge=0, le=1000000000)


class CreditRiskRequest(BaseModel):
    income: float = Field(gt=0)
    debt: float = Field(ge=0)
    monthly_expenses: float = Field(ge=0)
    credit_utilization: float = Field(ge=0, le=100)
    repayment_score: float = Field(ge=0, le=100)
    savings: float = Field(ge=0)


def create_token(user_id: int, email: str, role: str):
    if not SECRET_KEY:
        raise HTTPException(status_code=503, detail="SECRET_KEY is not configured in backend environment variables.")
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Please log in to access this endpoint.")
    if not SECRET_KEY:
        raise HTTPException(status_code=503, detail="SECRET_KEY is not configured.")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("user_id"):
            raise HTTPException(status_code=401, detail="Invalid token.")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Log in again.")


def audit(user_id: int, action: str):
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO audit_logs(user_id, action) VALUES (%s, %s)", (user_id, action))
    finally:
        conn.close()


def fraud_score(user_id: int, amount: float, location: str, device: str):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT amount, location, device
                FROM transactions
                WHERE user_id = %s AND is_demo = FALSE
                ORDER BY id DESC LIMIT 20
            """, (user_id,))
            history = cur.fetchall()
    finally:
        conn.close()

    score = 0
    reasons = []
    if amount >= 250000:
        score += 35
        reasons.append("Very large transaction amount")
    elif amount >= 100000:
        score += 20
        reasons.append("Large transaction amount")

    if history:
        average = sum(float(row["amount"]) for row in history) / len(history)
        if average > 0 and amount > average * 5:
            score += 30
            reasons.append("Amount is much higher than recent personal average")
        known_locations = {str(row["location"]).casefold() for row in history}
        known_devices = {str(row["device"]).casefold() for row in history}
        if location.casefold() not in known_locations:
            score += 15
            reasons.append("New location compared with recent records")
        if device.casefold() not in known_devices:
            score += 15
            reasons.append("New device compared with recent records")
    elif amount >= 100000:
        reasons.append("Large first recorded transaction")

    score = min(score, 100)
    decision = "HIGH RISK" if score >= 70 else "SUSPICIOUS" if score >= 40 else "LEGITIMATE"
    if not reasons:
        reasons = ["No configured rule was triggered"]
    return score, round(score / 100, 4), decision, reasons


@app.get("/")
def home():
    return {"project": "FinSight Financial Intelligence Platform", "status": "running", "database": "PostgreSQL" if DATABASE_URL else "not configured"}


@app.get("/health")
def health():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        return {"status": "healthy", "database": "connected"}
    finally:
        conn.close()


@app.post("/api/auth/register")
def register(data: AuthRequest):
    identifier = data.identifier
    is_email = "@" in identifier
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                if is_email:
                    cur.execute("SELECT id FROM users WHERE LOWER(email)=LOWER(%s)", (identifier,))
                else:
                    cur.execute("SELECT id FROM users WHERE phone=%s", (identifier,))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="That email or phone number is already registered.")
                if is_email:
                    cur.execute("INSERT INTO users(email, mpin_hash) VALUES (%s,%s) RETURNING id", (identifier, pwd_context.hash(data.mpin)))
                else:
                    cur.execute("INSERT INTO users(phone, mpin_hash) VALUES (%s,%s) RETURNING id", (identifier, pwd_context.hash(data.mpin)))
                user_id = cur.fetchone()["id"]
        audit(user_id, "USER_REGISTERED")
        return {"message": "Registration successful", "user_id": user_id}
    finally:
        conn.close()


@app.post("/api/auth/login")
def login(data: AuthRequest):
    identifier = data.identifier
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if "@" in identifier:
                cur.execute("SELECT * FROM users WHERE LOWER(email)=LOWER(%s)", (identifier,))
            else:
                cur.execute("SELECT * FROM users WHERE phone=%s", (identifier,))
            user = cur.fetchone()
    finally:
        conn.close()
    if not user or not pwd_context.verify(data.mpin, user["mpin_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email/phone or MPIN.")
    login_label = user.get("email") or user.get("phone")
    token = create_token(user["id"], login_label, user["role"])
    audit(user["id"], "USER_LOGIN")
    return {"message": "Login successful", "access_token": token, "token_type": "bearer", "identifier": login_label, "role": user["role"]}


@app.get("/api/profile")
def profile(user=Depends(get_current_user)):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, phone, role, created_at FROM users WHERE id=%s", (user["user_id"],))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found.")
            return dict(row)
    finally:
        conn.close()


# Demo seeding endpoint intentionally omitted: this deployment is real-records-only.

@app.post("/api/transactions")
def create_transaction(data: TransactionRequest, user=Depends(get_current_user)):
    uid = int(user["user_id"])
    event_time = data.transaction_time or datetime.now(timezone.utc)
    score, probability, decision, reasons = fraud_score(uid, data.amount, data.location.strip(), data.device.strip())
    import json
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO transactions
                    (user_id, amount, category, location, transaction_time, device, risk_score, fraud_probability, decision, risk_factors, is_demo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,FALSE)
                    RETURNING id
                """, (uid, data.amount, data.category.strip(), data.location.strip(), event_time, data.device.strip(), score, probability, decision, json.dumps(reasons)))
                transaction_id = cur.fetchone()["id"]
        audit(uid, "TRANSACTION_CREATED")
        return {"transaction_id": transaction_id, "risk_score": score, "fraud_probability": probability, "decision": decision, "risk_factors": reasons, "is_demo": False}
    finally:
        conn.close()


@app.post("/api/transactions/import-csv")
async def import_transactions_csv(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Import user-authorized CSV records. Required columns: amount and category/description."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    raw = await file.read(2_000_000 + 1)
    if len(raw) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV must be 2 MB or smaller.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames: raise ValueError("CSV header row is missing.")
        headers = {h.strip().lower(): h for h in reader.fieldnames if h}
        def col(*names): return next((headers[n] for n in names if n in headers), None)
        amount_key = col("amount", "transaction amount", "debit", "value")
        category_key = col("category", "description", "merchant", "narration", "name")
        date_key = col("date", "datetime", "transaction_time", "transaction date", "timestamp")
        location_key = col("location", "city", "merchant location")
        device_key = col("device", "channel", "payment method", "mode")
        if not amount_key or not category_key: raise ValueError("CSV needs amount and category/description columns.")
        parsed = []
        for rownum, row in enumerate(reader, start=2):
            if not row or not row.get(amount_key): continue
            try:
                amount = abs(float(str(row[amount_key]).replace(",", "").replace("₹", "").strip()))
                if amount <= 0: continue
                raw_date = (row.get(date_key) or "").strip() if date_key else ""
                event_time = datetime.fromisoformat(raw_date.replace("Z", "+00:00")) if raw_date else datetime.now(timezone.utc)
                if event_time.tzinfo is None: event_time = event_time.replace(tzinfo=timezone.utc)
                category = (row.get(category_key) or "Imported transaction").strip()[:80] or "Imported transaction"
                location = ((row.get(location_key) or "Imported") if location_key else "Imported").strip()[:120] or "Imported"
                device = ((row.get(device_key) or "CSV import") if device_key else "CSV import").strip()[:120] or "CSV import"
                parsed.append((amount, category, location, event_time, device))
            except Exception: raise ValueError(f"Invalid amount or date on CSV row {rownum}.")
        if not parsed: raise ValueError("No valid transaction rows found.")
        if len(parsed) > 5000: raise ValueError("A maximum of 5,000 transactions can be imported at once.")
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    uid = int(user["user_id"])
    import json
    inserted, flagged = 0, 0
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                for amount, category, location, event_time, device in parsed:
                    score, probability, decision, reasons = fraud_score(uid, amount, location, device)
                    cur.execute("""INSERT INTO transactions
                        (user_id, amount, category, location, transaction_time, device, risk_score, fraud_probability, decision, risk_factors, is_demo)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,FALSE)""",
                        (uid, amount, category, location, event_time, device, score, probability, decision, json.dumps(reasons)))
                    inserted += 1
                    if decision in ("SUSPICIOUS", "HIGH RISK"): flagged += 1
        audit(uid, f"CSV_IMPORT:{inserted}")
    finally: conn.close()
    return {"imported": inserted, "flagged": flagged, "message": f"Imported {inserted} transactions and flagged {flagged} for review."}


@app.get("/api/transactions")
def list_transactions(user=Depends(get_current_user)):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            query = "SELECT * FROM transactions WHERE user_id=%s AND is_demo=FALSE ORDER BY transaction_time DESC, id DESC"
            cur.execute(query, (int(user["user_id"]),))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@app.post("/api/fraud/analyze")
def analyze_transaction(data: TransactionRequest, user=Depends(get_current_user)):
    score, probability, decision, reasons = fraud_score(int(user["user_id"]), data.amount, data.location, data.device)
    return {"risk_score": score, "fraud_probability": probability, "decision": decision, "risk_factors": reasons, "note": "Rule-based educational screening; not a definitive fraud determination."}


@app.get("/api/fraud/alerts")
def fraud_alerts(user=Depends(get_current_user)):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM transactions
                WHERE user_id=%s AND is_demo=FALSE AND decision IN ('SUSPICIOUS','HIGH RISK')
                ORDER BY transaction_time DESC
            """, (int(user["user_id"]),))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@app.post("/api/risk/credit-score")
def credit_score(data: CreditRiskRequest, user=Depends(get_current_user)):
    debt_ratio = data.debt / data.income
    expense_ratio = data.monthly_expenses / data.income
    savings_ratio = data.savings / data.income
    # credit_utilization is a percentage from 0 to 100
    score = 100 - min(debt_ratio * 40, 40) - min(expense_ratio * 20, 20)
    score -= min(data.credit_utilization * 0.2, 20)
    score += min(savings_ratio * 10, 10)
    score += min(data.repayment_score * 0.3, 30)
    score = round(max(0, min(100, score)), 2)
    category = "LOW RISK" if score >= 70 else "MEDIUM RISK" if score >= 40 else "HIGH RISK"
    audit(int(user["user_id"]), "CREDIT_RISK_ANALYSIS")
    return {"risk_score": score, "risk_category": category, "debt_to_income": round(debt_ratio, 4),
