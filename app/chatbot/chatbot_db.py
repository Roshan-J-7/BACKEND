"""
Database connection module for the chatbot feature.
Connects to PostgreSQL and manages the chat_sessions table.
"""

import os
import json
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ─────────────────────────────
# Database Configuration
# ─────────────────────────────

# Support both DATABASE_URL (for Docker) and individual env vars (for local)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
    f"{os.getenv('POSTGRES_PASSWORD', '')}@"
    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
    f"{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'DeepBlue')}"
)


def get_connection():
    """Get a new database connection"""
    try:
        # Use DATABASE_URL if available, otherwise fall back to individual params
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.Error as e:
        raise Exception(f"Database connection failed: {str(e)}")


def init_db():
    """
    Initialize the database — create chat_sessions table if it doesn't exist.
    Called once at startup.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY,
                    profile_data JSONB NOT NULL,
                    reports JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    ended_at TIMESTAMP NULL
                );
            """)
        conn.commit()
        print("[DB] chat_sessions table ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to initialize database: {str(e)}")
    finally:
        conn.close()


def create_chat_session(profile_data: list, reports: list) -> str:
    """
    Insert a new chat session into the database.
    Stores profile_data and reports as raw JSONB — no transformation.

    Returns the generated session_id (UUID string).
    """
    session_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, profile_data, reports)
                VALUES (%s, %s, %s)
                """,
                (session_id, Json(profile_data), Json(reports))
            )
        conn.commit()
        print(f"[DB] Session created: {session_id}")
        return session_id
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to create chat session: {str(e)}")
    finally:
        conn.close()


def get_chat_session(session_id: str) -> dict:
    """
    Retrieve a chat session from the database.
    Returns the full row as a dict, or None if not found.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM chat_sessions WHERE id = %s",
                (session_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except psycopg2.Error as e:
        raise Exception(f"Failed to get chat session: {str(e)}")
    finally:
        conn.close()


def end_chat_session(session_id: str) -> bool:
    """
    Soft-end a chat session by setting ended_at timestamp.
    Returns True if session was found and updated.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET ended_at = NOW()
                WHERE id = %s AND ended_at IS NULL
                """,
                (session_id,)
            )
            updated = cur.rowcount > 0
        conn.commit()
        if updated:
            print(f"[DB] Session ended: {session_id}")
        return updated
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to end chat session: {str(e)}")
    finally:
        conn.close()


def delete_chat_session(session_id: str) -> bool:
    """
    Hard-delete a chat session from the database.
    Removes profile_data, reports, everything.
    Called on /chat/end — next chat must be fresh.

    Returns True if session was found and deleted.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE id = %s",
                (session_id,)
            )
            deleted = cur.rowcount > 0
        conn.commit()
        if deleted:
            print(f"[DB] Session deleted: {session_id}")
        return deleted
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to delete chat session: {str(e)}")
    finally:
        conn.close()
