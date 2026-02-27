"""
Chatbot API Routes — server-authoritative architecture.

Philosophy:
  - JWT identifies the user on every call.
  - /chat/start fetches all context (profile, medical, reports) from DB,
    builds the full system prompt once, stores it in chat_sessions.
  - /chat/message loads the stored system_prompt + full history from DB.
    The app sends ONLY the new user message — no history, no profile data.
  - /chat/end marks the session as ended.

Tables written to: chat_sessions, chat_messages
DB tables read:    user_profiles, user_medical_data, reports
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from jose import jwt, JWTError

from app.chatbot.chatbot_client import chatbot_client
from app.chatbot.chatbot_config import CHATBOT_SYSTEM_PROMPT
from app.chatbot.chatbot_db import (
    create_chat_session,
    get_chat_session,
    end_chat_session,
    save_message,
    get_messages,
)
from app.auth.profile_db import get_profile_by_user_id
from app.auth.medical_db import get_medical_by_user_id
from app.auth.reports_db import get_reports_by_user_id
from app.auth.auth_config import JWT_SECRET_KEY, JWT_ALGORITHM

router = APIRouter(prefix="/chat", tags=["Chat"])

FALLBACK_MESSAGE = "I'm sorry, something went wrong. Please try again."


# ─────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────

class StartChatRequest(BaseModel):
    entry_point: str = "home"          # "home" | "assessment"
    main_report_id: Optional[str] = None


class StartChatResponse(BaseModel):
    session_id: str
    message: str


class SendMessageRequest(BaseModel):
    session_id: str
    message: str


class SendMessageResponse(BaseModel):
    message: str


class EndChatRequest(BaseModel):
    session_id: str


class EndChatResponse(BaseModel):
    status: str = "ended"


# ─────────────────────────────────────
# Auth helper
# ─────────────────────────────────────

def _require_user_id(request: Request) -> str:
    """
    Decode the JWT from the Authorization header.
    Raises HTTP 401 if the token is missing or invalid.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no subject")
        return user_id
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ─────────────────────────────────────
# Context / prompt helpers
# ─────────────────────────────────────

def _answer_to_text(answer_json: dict) -> str:
    """Normalise the polymorphic answer_json shape to a plain string."""
    if not answer_json:
        return ""
    t = answer_json.get("type", "")
    if t == "text":
        return str(answer_json.get("value", ""))
    if t == "number":
        return str(answer_json.get("number_value", ""))
    if t == "single_choice":
        return answer_json.get("selected_option_label", "")
    if t == "multi_choice":
        options = answer_json.get("selected_options", [])
        return ", ".join(o.get("label", "") for o in options)
    # Fallback
    return str(answer_json.get("value", ""))


def _build_profile_summary(rows: list) -> str:
    """
    rows: [{question_text, answer_json}, ...] from user_profiles /
          user_medical_data tables.
    """
    if not rows:
        return ""
    lines = ["Patient Profile:"]
    for row in rows:
        label = row.get("question_text", "").replace("?", "").strip()
        answer = _answer_to_text(row.get("answer_json") or {})
        if answer:
            lines.append(f"  - {label}: {answer}")
    return "\n".join(lines)


def _extract_patient_name(profile_rows: list) -> str:
    for row in profile_rows:
        if "name" in (row.get("question_text") or "").lower():
            return _answer_to_text(row.get("answer_json") or {}).strip()
    return "there"


def _build_report_context(reports: list, main_report_id: Optional[str]) -> str:
    """
    reports: list from get_reports_by_user_id.
    The report whose report_id == main_report_id is treated as the focal point.
    """
    if not reports:
        return ""

    main_report = None
    other_reports = []
    for r in reports:
        if main_report_id and r.get("report_id") == main_report_id:
            main_report = r
        else:
            other_reports.append(r)

    sections = []

    if main_report:
        rd = main_report.get("report_data") or {}
        sections.append(
            "── CURRENT ASSESSMENT REPORT (Primary Topic) ──\n"
            "This conversation is a continuation of a medical assessment report.\n"
            "The user may ask clarifications, question accuracy, or seek explanation.\n"
            "Treat this report as the primary topic unless the user shifts topic.\n"
        )
        urgency = rd.get("urgency_level", "unknown")
        sections.append(f"Urgency Level: {urgency}")

        summary = rd.get("summary", [])
        if summary:
            sections.append("Summary: " + " ".join(summary))

        causes = rd.get("possible_causes", [])
        if causes:
            cause_lines = []
            for c in causes:
                title = c.get("title", "Unknown")
                severity = c.get("severity", "unknown")
                prob = c.get("probability", 0)
                short = c.get("short_description", "")
                cause_lines.append(
                    f"  - {title} ({severity}, {int(prob * 100)}%): {short}"
                )
                detail = c.get("detail") or {}
                what_to_do = detail.get("what_you_can_do_now", [])
                if what_to_do:
                    cause_lines.append("    What patient can do: " + "; ".join(what_to_do))
                warning = detail.get("warning", "")
                if warning:
                    cause_lines.append(f"    ⚠ Warning: {warning}")
            sections.append("Possible Causes:\n" + "\n".join(cause_lines))

        advice = rd.get("advice", [])
        if advice:
            sections.append("Advice: " + "; ".join(advice))

    if other_reports:
        history_lines = ["Past Medical Reports:"]
        for r in other_reports:
            rd = r.get("report_data") or {}
            date = str(r.get("created_at", "unknown date"))[:10]
            summary = rd.get("summary", [])
            urgency = rd.get("urgency_level", "")
            brief = summary[0] if summary else "No summary"
            history_lines.append(f"  - {date}: {brief} (Urgency: {urgency})")
        sections.append("\n".join(history_lines))

    return "\n\n".join(sections)


def _build_system_prompt(
    profile_rows: list,
    medical_rows: list,
    reports: list,
    main_report_id: Optional[str],
) -> str:
    parts = [CHATBOT_SYSTEM_PROMPT.strip()]

    profile_summary = _build_profile_summary(profile_rows + medical_rows)
    if profile_summary:
        parts.append(profile_summary)

    report_context = _build_report_context(reports, main_report_id)
    if report_context:
        parts.append(report_context)

    return "\n\n".join(parts)


# ─────────────────────────────────────
# Endpoints
# ─────────────────────────────────────

@router.post("/start", response_model=StartChatResponse)
async def start_chat(request: Request, body: StartChatRequest):
    """
    Start a new chat session.

    1. Verify JWT → user_id
    2. Fetch profile + medical + reports from DB
    3. Build full system prompt (stored in chat_sessions — never rebuilt again)
    4. Generate personalized welcome message via LLM
    5. Persist welcome message to chat_messages
    6. Return {session_id, message}
    """
    user_id = _require_user_id(request)

    try:
        # Fetch user context from DB
        profile_rows = get_profile_by_user_id(user_id) or []
        medical_rows = get_medical_by_user_id(user_id) or []
        reports = get_reports_by_user_id(user_id) or []

        system_prompt = _build_system_prompt(
            profile_rows, medical_rows, reports, body.main_report_id
        )

        session_id = create_chat_session(
            user_id=user_id,
            entry_point=body.entry_point,
            system_prompt=system_prompt,
            main_report_id=body.main_report_id,
        )

        # Build welcome instruction for LLM
        patient_name = _extract_patient_name(profile_rows)
        has_main_report = body.main_report_id is not None

        if has_main_report:
            start_instruction = (
                f"Start the conversation. Greet the patient by their name ({patient_name}). "
                f"Introduce yourself as Remy. Reference their recent assessment report briefly "
                f"and ask how you can help them understand or follow up on it. "
                f"Keep it warm, concise — 2-3 sentences max."
            )
        else:
            start_instruction = (
                f"Start the conversation. Greet the patient by their name ({patient_name}). "
                f"Introduce yourself as Remy. Ask how you can help them today. "
                f"Keep it warm, concise — 2-3 sentences max."
            )

        try:
            welcome = chatbot_client.generate_response(
                user_message=start_instruction,
                system_prompt_override=system_prompt,
            )
        except Exception:
            welcome = (
                f"Hi {patient_name}! I'm Remy. Based on your recent report, how can I help?"
                if has_main_report
                else f"Hi {patient_name}! I'm Remy. How can I help you today?"
            )

        # Persist the opening assistant message
        save_message(session_id, "assistant", welcome)

        return StartChatResponse(session_id=session_id, message=welcome)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start chat: {e}")


@router.post("/message", response_model=SendMessageResponse)
async def send_message(request: Request, body: SendMessageRequest):
    """
    Send a user message and get an assistant reply.

    1. Verify JWT → user_id
    2. Validate session ownership and active status
    3. Save user message to chat_messages
    4. Load full history from chat_messages
    5. Call LLM with stored system_prompt + history
    6. Save assistant reply to chat_messages
    7. Return {message}

    App sends ONLY {session_id, message} — no history, no profile data.
    """
    user_id = _require_user_id(request)

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        session = get_chat_session(body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        if str(session["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to this user")
        if session["status"] != "active":
            raise HTTPException(status_code=400, detail="Chat session has already ended")

        # Persist the incoming user message
        save_message(body.session_id, "user", body.message)

        # Load full conversation history from DB (includes the message we just saved)
        history = get_messages(body.session_id)

        # history[-1] is the user message we just saved — pass it as user_message,
        # everything before it as conversation_history
        conversation_history = history[:-1] if len(history) > 1 else None

        try:
            reply = chatbot_client.generate_response(
                user_message=body.message,
                conversation_history=conversation_history,
                system_prompt_override=session["system_prompt"],
            )
        except Exception:
            reply = FALLBACK_MESSAGE

        # Persist assistant reply
        save_message(body.session_id, "assistant", reply)

        return SendMessageResponse(message=reply)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")


@router.post("/end", response_model=EndChatResponse)
async def end_chat(request: Request, body: EndChatRequest):
    """
    End a chat session.

    Marks status = 'ended' in chat_sessions.
    History remains in chat_messages (soft end — data preserved for cloud history).
    """
    user_id = _require_user_id(request)

    try:
        session = get_chat_session(body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        if str(session["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="Session does not belong to this user")

        end_chat_session(body.session_id)
        return EndChatResponse(status="ended")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end chat: {e}")


@router.get("/health")
async def health_check():
    try:
        if not chatbot_client.api_key:
            return {"status": "error", "message": "API key not configured"}
        return {"status": "healthy", "service": "chatbot", "model": chatbot_client.model}
    except Exception as e:
        return {"status": "error", "message": str(e)}

