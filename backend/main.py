# BACKEND — Python FastAPI
# File: main.py

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import sqlite3
import hashlib
import math
import statistics

app = FastAPI(title="AI Financial Risk, Portfolio & Fraud Intelligence Platform")
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = "CHANGE_THIS_SECRET_KEY"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB = "/tmp/financial_platform.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            mpin_hash TEXT NOT NULL,
            role TEXT DEFAULT 'CUSTOMER',
            created_at TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            location TEXT,
            transaction_time TEXT,
            device TEXT,
            risk_score REAL,
            fraud_probability REAL,
            decision TEXT,
            created_at TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            invested_value REAL NOT NULL,
            current_value REAL NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    db.commit()
    db.close()


init_db()


class RegisterRequest(BaseModel):
    email: EmailStr
    mpin: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    mpin: str = Field(min_length=6, max_length=6)


class TransactionRequest(BaseModel):
    amount: float
    category: str
    location: str
    transaction_time: str
    device: str


class PortfolioRequest(BaseModel):
    asset: str
    asset_type: str
    invested_value: float
    current_value: float


def create_token(user_id: int, email: str, role: str):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        user_id = payload.get("user_id")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


def audit(user_id, action):
    db = get_db()

    db.execute(
        """
        INSERT INTO audit_logs(user_id, action, timestamp)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            action,
            datetime.utcnow().isoformat()
        )
    )

    db.commit()
    db.close()


@app.get("/")
def home():
    return {
        "project": "AI-Powered Financial Risk, Portfolio & Fraud Intelligence Platform",
        "status": "running"
    }


# =========================
# AUTHENTICATION
# =========================

@app.post("/api/auth/register")
def register(data: RegisterRequest):

    if not data.mpin.isdigit():
        raise HTTPException(
            status_code=400,
            detail="MPIN must contain only numbers"
        )

    db = get_db()

    existing = db.execute(
        "SELECT id FROM users WHERE email=?",
        (data.email,)
    ).fetchone()

    if existing:
        db.close()
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    mpin_hash = pwd_context.hash(data.mpin)

    cursor = db.execute(
        """
        INSERT INTO users(email, mpin_hash, role, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            data.email,
            mpin_hash,
            "CUSTOMER",
            datetime.utcnow().isoformat()
        )
    )

    db.commit()

    user_id = cursor.lastrowid

    db.close()

    return {
        "message": "Registration successful",
        "user_id": user_id
    }


@app.post("/api/auth/login")
def login(data: LoginRequest):

    db = get_db()

    user = db.execute(
        """
        SELECT * FROM users
        WHERE email=?
        """,
        (data.email,)
    ).fetchone()

    db.close()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or MPIN"
        )

    if not pwd_context.verify(
        data.mpin,
        user["mpin_hash"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or MPIN"
        )

    token = create_token(
        user["id"],
        user["email"],
        user["role"]
    )

    audit(
        user["id"],
        "USER_LOGIN"
    )

    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "email": user["email"],
        "role": user["role"]
    }


# =========================
# USER PROFILE
# =========================

@app.get("/api/profile")
def profile(user=Depends(get_current_user)):

    db = get_db()

    result = db.execute(
        """
        SELECT id, email, role, created_at
        FROM users
        WHERE id=?
        """,
        (user["user_id"],)
    ).fetchone()

    db.close()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return dict(result)


# =========================
# TRANSACTION ANALYSIS
# =========================

def analyze_fraud(user_id, amount, location, device):

    db = get_db()

    previous = db.execute(
        """
        SELECT amount, location, device
        FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (user_id,)
    ).fetchall()

    db.close()

    if not previous:

        if amount > 100000:
            return 75, 0.75, [
                "Large first transaction"
            ]

        return 10, 0.05, [
            "Normal transaction"
        ]

    amounts = [row["amount"] for row in previous]

    average_amount = statistics.mean(amounts)

    risk = 0
    reasons = []

    if amount > average_amount * 5:
        risk += 35
        reasons.append(
            "Transaction amount unusually high"
        )

    locations = [row["location"] for row in previous]

    if location not in locations:
        risk += 20
        reasons.append(
            "New geographical location"
        )

    devices = [row["device"] for row in previous]

    if device not in devices:
        risk += 20
        reasons.append(
            "New device detected"
        )

    if amount > 250000:
        risk += 15
        reasons.append(
            "Very large transaction"
        )

    risk = min(risk, 100)

    probability = risk / 100

    if risk >= 70:
        decision = "HIGH RISK"
    elif risk >= 40:
        decision = "SUSPICIOUS"
    else:
        decision = "LEGITIMATE"

    if not reasons:
        reasons.append(
            "No significant abnormal behavior detected"
        )

    return risk, probability, reasons


@app.post("/api/transactions")
def create_transaction(
    data: TransactionRequest,
    user=Depends(get_current_user)
):

    if data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    risk, probability, reasons = analyze_fraud(
        user["user_id"],
        data.amount,
        data.location,
        data.device
    )

    if risk >= 70:
        decision = "HIGH RISK"
    elif risk >= 40:
        decision = "SUSPICIOUS"
    else:
        decision = "LEGITIMATE"

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO transactions(
            user_id,
            amount,
            category,
            location,
            transaction_time,
            device,
            risk_score,
            fraud_probability,
            decision,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["user_id"],
            data.amount,
            data.category,
            data.location,
            data.transaction_time,
            data.device,
            risk,
            probability,
            decision,
            datetime.utcnow().isoformat()
        )
    )

    db.commit()

    transaction_id = cursor.lastrowid

    db.close()

    audit(
        user["user_id"],
        "TRANSACTION_CREATED"
    )

    return {
        "transaction_id": transaction_id,
        "risk_score": risk,
        "fraud_probability": probability,
        "decision": decision,
        "risk_factors": reasons
    }


@app.get("/api/transactions")
def transactions(
    user=Depends(get_current_user)
):

    db = get_db()

    rows = db.execute(
        """
        SELECT *
        FROM transactions
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (user["user_id"],)
    ).fetchall()

    db.close()

    return [dict(row) for row in rows]


# =========================
# FRAUD ANALYSIS
# =========================

@app.post("/api/fraud/analyze")
def fraud_analysis(
    data: TransactionRequest,
    user=Depends(get_current_user)
):

    risk, probability, reasons = analyze_fraud(
        user["user_id"],
        data.amount,
        data.location,
        data.device
    )

    if risk >= 70:
        decision = "HIGH RISK"
    elif risk >= 40:
        decision = "SUSPICIOUS"
    else:
        decision = "LEGITIMATE"

    return {
        "fraud_probability": round(probability, 4),
        "risk_score": risk,
        "decision": decision,
        "risk_factors": reasons
    }


# =========================
# CREDIT RISK
# =========================

class CreditRiskRequest(BaseModel):
    income: float
    debt: float
    monthly_expenses: float
    credit_utilization: float
    repayment_score: float
    savings: float


@app.post("/api/risk/credit-score")
def credit_score(
    data: CreditRiskRequest,
    user=Depends(get_current_user)
):

    if data.income <= 0:
        raise HTTPException(
            status_code=400,
            detail="Income must be greater than zero"
        )

    debt_ratio = data.debt / data.income

    expense_ratio = (
        data.monthly_expenses / data.income
    )

    savings_ratio = (
        data.savings / data.income
    )

    score = 100

    score -= min(debt_ratio * 40, 40)

    score -= min(expense_ratio * 20, 20)

    score -= min(
        data.credit_utilization * 0.20,
        20
    )

    score += min(
        savings_ratio * 10,
        10
    )

    score += min(
        data.repayment_score * 0.30,
        30
    )

    score = max(
        0,
        min(100, score)
    )

    if score >= 70:
        category = "LOW RISK"
    elif score >= 40:
        category = "MEDIUM RISK"
    else:
        category = "HIGH RISK"

    audit(
        user["user_id"],
        "CREDIT_RISK_ANALYSIS"
    )

    return {
        "risk_score": round(score, 2),
        "risk_category": category,
        "debt_to_income": round(
            debt_ratio,
            4
        ),
        "expense_to_income": round(
            expense_ratio,
            4
        ),
        "savings_ratio": round(
            savings_ratio,
            4
        )
    }


# =========================
# PORTFOLIO
# =========================

@app.post("/api/portfolio/assets")
def add_asset(
    data: PortfolioRequest,
    user=Depends(get_current_user)
):

    if (
        data.invested_value < 0
        or data.current_value < 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Values cannot be negative"
        )

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO portfolios(
            user_id,
            asset,
            asset_type,
            invested_value,
            current_value
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user["user_id"],
            data.asset,
            data.asset_type,
            data.invested_value,
            data.current_value
        )
    )

    db.commit()

    asset_id = cursor.lastrowid

    db.close()

    audit(
        user["user_id"],
        "PORTFOLIO_ASSET_ADDED"
    )

    return {
        "asset_id": asset_id,
        "message": "Asset added successfully"
    }


@app.get("/api/portfolio")
def portfolio(
    user=Depends(get_current_user)
):

    db = get_db()

    assets = db.execute(
        """
        SELECT *
        FROM portfolios
        WHERE user_id=?
        """,
        (user["user_id"],)
    ).fetchall()

    db.close()

    total_invested = sum(
        a["invested_value"]
        for a in assets
    )

    total_current = sum(
        a["current_value"]
        for a in assets
    )

    profit_loss = (
        total_current -
        total_invested
    )

    return_percentage = (
        (profit_loss / total_invested) * 100
        if total_invested > 0
        else 0
    )

    allocation = {}

    for asset in assets:

        asset_type = asset["asset_type"]

        allocation.setdefault(
            asset_type,
            0
        )

        allocation[asset_type] += (
            asset["current_value"]
        )

    allocation_percentage = {}

    for asset_type, value in allocation.items():

        allocation_percentage[asset_type] = (
            value / total_current * 100
            if total_current > 0
            else 0
        )

    warnings = []

    for asset_type, percentage in allocation_percentage.items():

        if percentage > 60:
            warnings.append(
                f"HIGH CONCENTRATION RISK: "
                f"{asset_type} = {percentage:.2f}%"
            )

    return {
        "assets": [dict(a) for a in assets],
        "total_invested": total_invested,
        "current_value": total_current,
        "profit_loss": profit_loss,
        "return_percentage": round(
            return_percentage,
            2
        ),
        "allocation": allocation_percentage,
        "risk_warnings": warnings
    }


# =========================
# FINANCIAL HEALTH
# =========================

class FinancialHealthRequest(BaseModel):
    income: float
    expenses: float
    assets: float
    liabilities: float
    savings: float
    liquidity: float


@app.post("/api/customers/financial-health")
def financial_health(
    data: FinancialHealthRequest,
    user=Depends(get_current_user)
):

    if data.income <= 0:
        raise HTTPException(
            status_code=400,
            detail="Income must be greater than zero"
        )

    savings_ratio = (
        data.savings /
        data.income
    )

    expense_ratio = (
        data.expenses /
        data.income
    )

    debt_ratio = (
        data.liabilities /
        data.income
    )

    net_worth = (
        data.assets -
        data.liabilities
    )

    score = 100

    score -= min(
        expense_ratio * 30,
        30
    )

    score -= min(
        debt_ratio * 30,
        30
    )

    score += min(
        savings_ratio * 25,
        25
    )

    score += min(
        data.liquidity * 15,
        15
    )

    score = max(
        0,
        min(100, score)
    )

    if score >= 70:
        category = "HEALTHY"
    elif score >= 40:
        category = "MODERATE"
    else:
        category = "NEEDS ATTENTION"

    return {
        "financial_health_score": round(
            score,
            2
        ),
        "category": category,
        "net_worth": net_worth,
        "savings_ratio": round(
            savings_ratio,
            4
        ),
        "expense_to_income_ratio": round(
            expense_ratio,
            4
        ),
        "debt_to_income_ratio": round(
            debt_ratio,
            4
        )
    }


# =========================
# AI FINANCIAL ASSISTANT
# =========================

class AIRequest(BaseModel):
    question: str


@app.post("/api/ai/advice")
def ai_advice(
    data: AIRequest,
    user=Depends(get_current_user)
):

    question = data.question.lower()

    if "fraud" in question:
        advice = (
            "Review transaction amount, location, "
            "device, transaction frequency and "
            "historical behavior before classifying "
            "a transaction as suspicious."
        )

    elif "portfolio" in question:
        advice = (
            "Review asset allocation, concentration, "
            "volatility, drawdown and diversification. "
            "This system provides educational analysis, "
            "not guaranteed investment advice."
        )

    elif "debt" in question:
        advice = (
            "Calculate debt-to-income ratio, "
            "review repayment history and compare "
            "monthly debt obligations with income."
        )

    elif "saving" in question:
        advice = (
            "Compare savings with income and expenses "
            "and monitor your liquidity position."
        )

    elif "risk" in question:
        advice = (
            "Risk should be evaluated using multiple "
            "indicators rather than one variable."
        )

    else:
        advice = (
            "Use the Financial Health, Fraud, "
            "Credit Risk and Portfolio modules "
            "to analyze the relevant financial data."
        )

    return {
        "answer": advice,
        "disclaimer": (
            "This is educational analytical guidance "
            "and is not guaranteed financial advice."
        )
    }


# =========================
# AUDIT LOGS
# =========================

@app.get("/api/audit")
def audit_logs(
    user=Depends(get_current_user)
):

    if user["role"] not in [
        "ADMIN",
        "RISK_ANALYST"
    ]:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    db = get_db()

    logs = db.execute(
        """
        SELECT *
        FROM audit_logs
        ORDER BY id DESC
        """
    ).fetchall()

    db.close()

    return [dict(log) for log in logs]


# =========================
# DASHBOARD
# =========================


@app.get("/api/dashboard")
def dashboard(user=Depends(get_current_user)):
    db = get_db()

    transaction_count = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM transactions
        WHERE user_id = ?
        """,
        (user["user_id"],)
    ).fetchone()["count"]

    transaction_value = db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
        """,
        (user["user_id"],)
    ).fetchone()["total"]

    return {
        "transaction_count": transaction_count,
        "transaction_value": transaction_value,
        "suspicious_transactions": 0,
        "risk_score": 0,
        "portfolio_value": 0
    }

