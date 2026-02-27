"""
Chatbot DB layer — server-authoritative architecture.

Tables:
  chat_sessions   — one per conversation, owned by a user_id.
                    Stores the pre-built system_prompt so profile/medical/
                    reports are only queried once (at /chat/start).
  chat_messages   — full conversation history (user + assistant turns).
                    App never needs to send history back.
"""

import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
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
        raise Exception(f"DB connection failed: {str(e)}")


# ─────────────────────────────────────
# Table initialisation
# ─────────────────────────────────────

def init_chat_db():
    """
    Create chat_sessions + chat_messages tables.

    If the legacy chat_sessions table (profile_data / reports columns) is
    still present it is dropped first — old sessions are stale after the
    server-authoritative architecture change.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # Drop legacy table if it has the old schema
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'chat_sessions'
                          AND column_name = 'profile_data'
                    ) THEN
                        DROP TABLE IF EXISTS chat_sessions CASCADE;
                        RAISE NOTICE 'Dropped legacy chat_sessions table';
                    END IF;
                END $$;
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id        UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    entry_point    VARCHAR(20) NOT NULL DEFAULT 'home',
                    main_report_id VARCHAR(100)         NULL,
                    system_prompt  TEXT        NOT NULL DEFAULT '',
                    status         VARCHAR(10) NOT NULL DEFAULT 'active',
                    started_at     TIMESTAMP   NOT NULL DEFAULT NOW(),
                    ended_at       TIMESTAMP            NULL
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id  UUID        NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                    role        VARCHAR(10) NOT NULL,
                    content     TEXT        NOT NULL,
                    created_at  TIMESTAMP   NOT NULL DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                    ON chat_messages(session_id, created_at);
            """)

        conn.commit()
        print("[DB] chat_sessions + chat_messages tables ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to init chat DB: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────────────
# Session CRUD
# ─────────────────────────────────────

def create_chat_session(
    user_id: str,
    entry_point: str,
    system_prompt: str,
    main_report_id: str = None,
) -> str:
    """Insert a new chat session.  Returns the new session_id (UUID string)."""
    session_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions
                    (session_id, user_id, entry_point, main_report_id, system_prompt)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, user_id, entry_point, main_report_id, system_prompt),
            )
        conn.commit()
        print(f"[DB] Chat session created: {session_id[:8]}…")
        return session_id
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to create chat session: {str(e)}")
    finally:
        conn.close()


def get_chat_session(session_id: str) -> dict:
    """Return the full session row as a dict, or None if not found."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM chat_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except psycopg2.Error as e:
        raise Exception(f"Failed to get chat session: {str(e)}")
    finally:
        conn.close()


def end_chat_session(session_id: str) -> bool:
    """Mark session as ended.  Returns True if a row was updated."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET status = 'ended', ended_at = NOW()
                WHERE session_id = %s AND status = 'active'
                """,
                (session_id,),
            )
            updated = cur.rowcount > 0
        conn.commit()
        if updated:
            print(f"[DB] Chat session ended: {session_id[:8]}…")
        return updated
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to end chat session: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────────────
# Message CRUD
# ─────────────────────────────────────

def save_message(session_id: str, role: str, content: str) -> None:
    """Append a single message (user or assistant) to the session history."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, role, content),
            )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to save message: {str(e)}")
    finally:
        conn.close()


def get_messages(session_id: str) -> list:
    """
    Return full conversation history as [{role, content}, ...] ordered oldest→newest.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT role, content
                FROM   chat_messages
                WHERE  session_id = %s
                ORDER  BY created_at ASC
                """,
                (session_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    except psycopg2.Error as e:
        raise Exception(f"Failed to get messages: {str(e)}")
    finally:
        conn.close()
