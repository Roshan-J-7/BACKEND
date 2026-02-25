"""
web_server.py — S2 Entry Point
===============================
Run S2 (Web/Kiosk server) with:

    uvicorn web_server:app --reload --port 8001

S1 runs on:  uvicorn app.main:app --reload --port 8000
S2 runs on:  uvicorn web_server:app --reload --port 8001

Both talk to the same PostgreSQL database.
S1 endpoints: /assessment/*, /followup/*, /chat/*, /health
S2 endpoints: /web/assessment/*, /web/followup/*, /web/chat/*, /web/health
"""

from app_web.main import app  # noqa: F401 — import the S2 FastAPI app

# This file exists so S2 can be launched independently:
#   uvicorn web_server:app --reload --port 8001
#
# In Docker or AWS, run both as separate processes:
#   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
#   CMD ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8001"]
