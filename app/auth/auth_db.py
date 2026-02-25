"""
auth_db.py
==========
Database layer for user authentication.

Uses the SAME PostgreSQL instance as the rest of the project (DeepBlue DB)
but a completely SEPARATE table: `users`

Tables managed here:
  - users  (id, email, hashed_password, created_at)

NOT related to chat_sessions — never read or write that table here.
"""

import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────
# Reuse the same DATABASE_URL from .env
# (Same Postgres instance, same DeepBlue DB — new table only)
# ─────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
    f"{os.getenv('POSTGRES_PASSWORD', '')}@"
    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
    f"{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'DeepBlue')}"
)


def _get_conn():
    """Open and return a raw psycopg2 connection."""
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as e:
        raise Exception(f"Auth DB connection failed: {str(e)}")


# ─────────────────────────────
# Init
# ─────────────────────────────

def init_auth_db() -> None:
    """
    Create the `users` table if it does not already exist.
    Called once at server startup — safe to call multiple times.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email         VARCHAR(320) UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at    TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
        print("[AUTH DB] users table ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to initialise auth DB: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Read
# ─────────────────────────────

def get_user_by_email(email: str) -> dict | None:
    """
    Fetch a user row by email.
    Returns a dict with keys {id, email, hashed_password, created_at}
    or None if not found.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, hashed_password, created_at FROM users WHERE email = %s;",
                (email.lower().strip(),)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def email_exists(email: str) -> bool:
    """Return True if the email is already registered."""
    return get_user_by_email(email) is not None


# ─────────────────────────────
# Write
# ─────────────────────────────

def create_user(email: str, hashed_password: str) -> str:
    """
    Insert a new user into the `users` table.
    Returns the new user's UUID as a string.
    """
    user_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, email, hashed_password)
                VALUES (%s, %s, %s);
                """,
                (user_id, email.lower().strip(), hashed_password)
            )
        conn.commit()
        return user_id
    except psycopg2.IntegrityError:
        conn.rollback()
        raise Exception("Email already exists")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to create user: {str(e)}")
    finally:
        conn.close()
