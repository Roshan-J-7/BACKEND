"""
medical_db.py
=============
Database layer for user medical data onboarding.

Table: user_medical_data
  - id            UUID PRIMARY KEY
  - user_id       UUID NOT NULL  →  foreign key → users(id)
  - question_id   VARCHAR NOT NULL
  - question_text TEXT NOT NULL
  - answer_json   JSONB NOT NULL
  - created_at    TIMESTAMP DEFAULT NOW()

Each answered question is stored as a separate row, all linked to the same user_id.
user_id is extracted from the JWT token — never passed in request body.

Separate from user_profiles — profile holds personal data, this holds health history.
"""

import os
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
        raise Exception(f"Medical DB connection failed: {str(e)}")


# ─────────────────────────────
# Init
# ─────────────────────────────

def init_medical_db() -> None:
    """
    Create the `user_medical_data` table if it doesn't exist.
    Linked to `users` table via user_id (foreign key).
    Called once at server startup.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_medical_data (
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
                CREATE INDEX IF NOT EXISTS idx_user_medical_data_user_id
                ON user_medical_data(user_id);
            """)
        conn.commit()
        print("[MEDICAL DB] user_medical_data table ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to initialise medical DB: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Write
# ─────────────────────────────

def save_medical_answers(user_id: str, answers: list) -> None:
    """
    Replace all medical data for a user with new answers.

    - Deletes existing rows for user_id (idempotent — re-submission safe)
    - Inserts each answer as a fresh row

    Args:
        user_id: UUID string extracted from JWT
        answers: list of dicts with keys: question_id, question_text, answer_json
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # Delete previous medical data for this user (upsert pattern)
            cur.execute(
                "DELETE FROM user_medical_data WHERE user_id = %s",
                (user_id,)
            )

            # Insert each Q&A row
            for item in answers:
                cur.execute(
                    """
                    INSERT INTO user_medical_data
                        (user_id, question_id, question_text, answer_json)
                    VALUES (%s, %s, %s, %s)
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
        raise Exception(f"Failed to save medical answers: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Read
# ─────────────────────────────

def get_medical_by_user_id(user_id: str) -> list:
    """
    Fetch all medical data rows stored for a user.

    Returns:
        List of dicts: [{ question_id, question_text, answer_json }, ...]
        Empty list if no data found.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT question_id, question_text, answer_json
                FROM user_medical_data
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (user_id,)
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except psycopg2.Error as e:
        raise Exception(f"Failed to fetch medical data: {str(e)}")
    finally:
        conn.close()
