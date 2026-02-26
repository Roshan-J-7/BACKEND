"""
profile_db.py
=============
Database layer for user profile onboarding.

Table: user_profiles
  - id            UUID PRIMARY KEY
  - user_id       UUID NOT NULL  →  foreign key → users(id)
  - question_id   VARCHAR NOT NULL
  - question_text TEXT NOT NULL
  - answer_json   JSONB NOT NULL
  - created_at    TIMESTAMP DEFAULT NOW()

Each answered question is stored as a separate row, all linked to the same user_id.
user_id is extracted from the JWT token — never passed in request body.
"""

import os
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
    f"{os.getenv('POSTGRES_PASSWORD', '')}@"
    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
    f"{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'DeepBlue')}"
)


def _get_conn():
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as e:
        raise Exception(f"Profile DB connection failed: {str(e)}")


# ─────────────────────────────
# Init
# ─────────────────────────────

def init_profile_db() -> None:
    """
    Create the `user_profiles` table if it doesn't exist.
    Linked to `users` table via user_id (foreign key).
    Called once at server startup.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    question_id   VARCHAR(100) NOT NULL,
                    question_text TEXT NOT NULL,
                    answer_json   JSONB NOT NULL,
                    created_at    TIMESTAMP DEFAULT NOW()
                );
            """)
            # Index on user_id for fast lookups
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id
                ON user_profiles(user_id);
            """)
        conn.commit()
        print("[PROFILE DB] user_profiles table ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to initialise profile DB: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Write
# ─────────────────────────────

def save_profile_answers(user_id: str, answers: list) -> None:
    """
    Insert profile answers for a given user.
    Each item in `answers` is a dict with:
      - question_id   (str)
      - question_text (str)
      - answer_json   (dict)

    Deletes any previous profile answers for this user before inserting new ones.
    (Re-onboarding replaces old data cleanly.)
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # Clear existing profile for this user (idempotent re-onboarding)
            cur.execute("DELETE FROM user_profiles WHERE user_id = %s;", (user_id,))

            # Insert each Q&A as a separate row
            for item in answers:
                cur.execute(
                    """
                    INSERT INTO user_profiles (user_id, question_id, question_text, answer_json)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (
                        user_id,
                        item["question_id"],
                        item["question_text"],
                        Json(item["answer_json"])
                    )
                )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to save profile: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Read
# ─────────────────────────────

def get_profile_by_user_id(user_id: str) -> list:
    """
    Fetch all profile answers for a user.
    Returns list of dicts: [{question_id, question_text, answer_json}, ...]
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT question_id, question_text, answer_json
                FROM user_profiles
                WHERE user_id = %s
                ORDER BY created_at ASC;
                """,
                (user_id,)
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()
