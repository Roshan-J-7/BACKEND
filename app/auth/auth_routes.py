"""
auth_routes.py
==============
FastAPI router for authentication.

Endpoints:
  POST /auth/signup  — register new user
  POST /auth/login   — login and receive JWT

Isolated from all other routes. Does not import from chatbot/, core/, or vision_model/.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt

from app.auth.auth_config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRY_DAYS
from app.auth.auth_db import email_exists, create_user, get_user_by_email

# ─────────────────────────────
# Router
# ─────────────────────────────
router = APIRouter(prefix="/auth", tags=["Auth"])

# ─────────────────────────────
# Password hashing (bcrypt)
# ─────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─────────────────────────────
# JWT helpers
# ─────────────────────────────

def create_jwt(user_id: str, email: str) -> str:
    """Generate a signed JWT that expires in JWT_EXPIRY_DAYS days."""
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ─────────────────────────────
# Request / Response models
# ─────────────────────────────

class AuthRequest(BaseModel):
    email: str
    password: str


# ─────────────────────────────
# Endpoints
# ─────────────────────────────

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(req: AuthRequest):
    """
    Register a new user.

    - Checks if email already exists → 409 if so
    - Hashes password with bcrypt
    - Stores (email, hashed_password) in `users` table
    """
    if email_exists(req.email):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"success": False, "message": "User already exists"}
        )

    try:
        hashed = hash_password(req.password)
        create_user(email=req.email, hashed_password=hashed)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": f"Internal server error: {str(e)}"}
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"success": True, "message": "User created successfully"}
    )


@router.post("/login", status_code=status.HTTP_200_OK)
def login(req: AuthRequest):
    """
    Authenticate user and return a JWT.

    - Looks up email in `users` table
    - Verifies bcrypt password hash
    - Returns signed JWT (7-day expiry)
    """
    user = get_user_by_email(req.email)

    if not user or not verify_password(req.password, user["hashed_password"]):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "message": "Invalid credentials"}
        )

    token = create_jwt(user_id=str(user["id"]), email=user["email"])

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"success": True, "message": "Login successful", "token": token}
    )
