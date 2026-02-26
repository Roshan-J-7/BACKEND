"""
reports_db.py
=============
Database layer for storing generated assessment reports.

Table: reports
  - id               UUID PRIMARY KEY
  - user_id          UUID NOT NULL  →  foreign key → users(id)
  - report_id        VARCHAR(100)   (the report_id from the generated report JSON)
  - assessment_topic VARCHAR(255)
  - urgency_level    VARCHAR(100)
  - report_data      JSONB          (full report JSON exactly as generated)
  - created_at       TIMESTAMP DEFAULT NOW()

Reports are stored automatically when POST /assessment/report is called with a JWT.
If no JWT is provided the report is still generated and returned — just not persisted.

Linked to users via user_id so:
  - cross-device sync works (same user_id regardless of device)
  - reports are never lost even if app local storage is cleared
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
        raise Exception(f"Reports DB connection failed: {str(e)}")


# ─────────────────────────────
# Init
# ─────────────────────────────

def init_reports_db() -> None:
    """
    Create the `reports` table if it doesn't exist.
    Linked to `users` table via user_id (foreign key, cascade on delete).
    Called once at server startup.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    report_id        VARCHAR(100) NOT NULL,
                    assessment_topic VARCHAR(255),
                    urgency_level    VARCHAR(100),
                    report_data      JSONB NOT NULL,
                    created_at       TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_user_id
                ON reports(user_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_report_id
                ON reports(report_id);
            """)
        conn.commit()
        print("[REPORTS DB] reports table ready")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to initialise reports DB: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Write
# ─────────────────────────────

def save_report(user_id: str, report: dict) -> None:
    """
    Persist a generated report for a user.

    Args:
        user_id: UUID string extracted from JWT
        report:  Full report dict as returned by generate_medical_report()
                 Must contain at minimum: report_id, assessment_topic, urgency_level

    Stores the full report_data as JSONB — identical format to what is returned
    to the app, so the chat context can be reconstructed server-side.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reports
                    (user_id, report_id, assessment_topic, urgency_level, report_data)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    report.get("report_id", ""),
                    report.get("assessment_topic", ""),
                    report.get("urgency_level", ""),
                    Json(report)
                )
            )
        conn.commit()
        print(f"[REPORTS DB] Saved report {report.get('report_id', '?')} for user {user_id[:8]}...")
    except psycopg2.Error as e:
        conn.rollback()
        raise Exception(f"Failed to save report: {str(e)}")
    finally:
        conn.close()


# ─────────────────────────────
# Read
# ─────────────────────────────

def get_reports_by_user_id(user_id: str) -> list:
    """
    Fetch all reports for a user, newest first.

    Returns:
        List of dicts:
        [
          {
            "report_id": "...",
            "assessment_topic": "...",
            "urgency_level": "...",
            "report_data": { full report JSON },
            "created_at": "2026-02-26T..."
          },
          ...
        ]
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT report_id, assessment_topic, urgency_level, report_data,
                       created_at AT TIME ZONE 'UTC' AS created_at
                FROM reports
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            rows = cur.fetchall()
        return [
            {
                **dict(row),
                "created_at": row["created_at"].isoformat() + "Z" if row["created_at"] else None
            }
            for row in rows
        ]
    except psycopg2.Error as e:
        raise Exception(f"Failed to fetch reports: {str(e)}")
    finally:
        conn.close()
