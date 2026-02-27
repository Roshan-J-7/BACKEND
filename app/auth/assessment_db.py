"""
assessment_db.py
================
Database layer for session-based assessment flow.

Tables:
  assessment_sessions
    session_id       UUID PK
    user_id          UUID FK → users(id) CASCADE
    status           VARCHAR(20)   -- active | completed | expired
    phase            VARCHAR(20)   -- questionnaire | followup
    detected_symptom VARCHAR(100)  -- null until chief complaint matched
    started_at       TIMESTAMP
    completed_at     TIMESTAMP NULL

  assessment_session_answers
    id               UUID PK
    session_id       UUID FK → assessment_sessions CASCADE
    question_id      VARCHAR(100)
    question_text    TEXT
    answer_json      JSONB
    created_at       TIMESTAMP

Partial unique index: only one active session per user at a time.
Unique constraint on (session_id, question_id): safe to call save_answer multiple times.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
from typing import Optional

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
        raise Exception(f"Assessment DB connection failed: {str(e)}")


# ─────────────────────────────
# Init
# ─────────────────────────────

def init_assessment_db() -> None:
    """Create assessment_sessions and assessment_session_answers tables."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assessment_sessions (
                    session_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    status            VARCHAR(20) NOT NULL DEFAULT 'active',
                    phase             VARCHAR(20) NOT NULL DEFAULT 'questionnaire',
                    detected_symptom  VARCHAR(100),
                    started_at        TIMESTAMP DEFAULT NOW(),
                    completed_at      TIMESTAMP
                );
            """)
            # Only one active session per user (partial unique index)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_assessment_sessions_user_active
                ON assessment_sessions(user_id)
                WHERE status = 'active';
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assessment_session_answers (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id    UUID NOT NULL
                                  REFERENCES assessment_sessions(session_id)
                                  ON DELETE CASCADE,
                    question_id   VARCHAR(100) NOT NULL,
                    question_text TEXT NOT NULL,
                    answer_json   JSONB NOT NULL,
                    created_at    TIMESTAMP DEFAULT NOW(),
                    UNIQUE (session_id, question_id)
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_answers_session_id
                ON assessment_session_answers(session_id);
            """)
        conn.commit()
        print("[ASSESSMENT DB] assessment_sessions + assessment_session_answers tables ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to initialise assessment DB: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Sessions
# ─────────────────────────────

def get_active_session(user_id: str) -> Optional[dict]:
    """Return the user's current active session, or None."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT session_id, user_id, status, phase, detected_symptom,
                       started_at
                FROM assessment_sessions
                WHERE user_id = %s AND status = 'active'
                LIMIT 1
                """,
                (user_id,)
            )
            row = cur.fetchone()
        return dict(row) if row else None
    except psycopg2.Error as e:
        raise Exception(f"Failed to fetch active session: {str(e)}")
    finally:
        conn.close()


def create_session(user_id: str) -> dict:
    """
    Create a new active session for the user.
    Any previously active session for this user is expired first.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Expire any stale active sessions for this user
            cur.execute(
                """
                UPDATE assessment_sessions
                SET status = 'expired'
                WHERE user_id = %s AND status = 'active'
                """,
                (user_id,)
            )
            # Create the new session
            cur.execute(
                """
                INSERT INTO assessment_sessions (user_id, status, phase)
                VALUES (%s, 'active', 'questionnaire')
                RETURNING session_id, user_id, status, phase, detected_symptom, started_at
                """,
                (user_id,)
            )
            row = cur.fetchone()
        conn.commit()
        return dict(row)
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to create session: {str(e)}")
    finally:
        conn.close()


def get_session_by_id(session_id: str) -> Optional[dict]:
    """Fetch a session by its ID."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT session_id, user_id, status, phase, detected_symptom, started_at
                FROM assessment_sessions WHERE session_id = %s
                """,
                (session_id,)
            )
            row = cur.fetchone()
        return dict(row) if row else None
    except psycopg2.Error as e:
        raise Exception(f"Failed to fetch session: {str(e)}")
    finally:
        conn.close()


def update_session_phase(session_id: str, phase: str, detected_symptom: Optional[str] = None) -> None:
    """Update phase and/or detected_symptom for a session."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE assessment_sessions
                SET phase = %s, detected_symptom = COALESCE(%s, detected_symptom)
                WHERE session_id = %s
                """,
                (phase, detected_symptom, session_id)
            )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to update session phase: {str(e)}")
    finally:
        conn.close()


def complete_session(session_id: str) -> None:
    """Mark session as completed."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE assessment_sessions
                SET status = 'completed', completed_at = NOW()
                WHERE session_id = %s
                """,
                (session_id,)
            )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to complete session: {str(e)}")
    finally:
        conn.close()


def expire_session(session_id: str) -> None:
    """Mark session as expired (manual end)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE assessment_sessions SET status = 'expired' WHERE session_id = %s",
                (session_id,)
            )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to expire session: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Session Answers
# ─────────────────────────────

def save_session_answer(session_id: str, question_id: str,
                        question_text: str, answer_json: dict) -> None:
    """
    Upsert an answer for a session question.
    If the question was already answered, updates it.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO assessment_session_answers
                    (session_id, question_id, question_text, answer_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id, question_id)
                DO UPDATE SET answer_json = EXCLUDED.answer_json,
                              question_text = EXCLUDED.question_text,
                              created_at = NOW()
                """,
                (session_id, question_id, question_text, Json(answer_json))
            )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to save session answer: {str(e)}")
    finally:
        conn.close()


def get_session_answers(session_id: str) -> dict:
    """
    Fetch all answers for a session as a dict.

    Returns:
        { question_id: answer_json_dict, ... }
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT question_id, question_text, answer_json
                FROM assessment_session_answers
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,)
            )
            rows = cur.fetchall()
        return {row["question_id"]: row["answer_json"] for row in rows}
    except psycopg2.Error as e:
        raise Exception(f"Failed to fetch session answers: {str(e)}")
    finally:
        conn.close()


def get_session_answers_full(session_id: str) -> list:
    """
    Fetch all answers as a list with question_text included.

    Returns:
        [{ question_id, question_text, answer_json }, ...]
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT question_id, question_text, answer_json
                FROM assessment_session_answers
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,)
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    except psycopg2.Error as e:
        raise Exception(f"Failed to fetch full session answers: {str(e)}")
    finally:
        conn.close()
