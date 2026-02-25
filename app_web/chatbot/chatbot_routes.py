"""
S2 — Web Chatbot API Routes  (/web/chat/*)
Exact duplicate of app/chatbot/chatbot_routes.py but served under /web/chat prefix.
S1 mobile app uses /chat/*  →  this file is unreachable by the app.
S2 kiosk/website uses /web/chat/*  →  only reachable here.

To add web-specific chat logic later, edit ONLY this file.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Reuse S1 chatbot internals (shared for now — diverge here when needed)
from app.chatbot.chatbot_client import chatbot_client
from app.chatbot.chatbot_config import CHATBOT_SYSTEM_PROMPT
from app.chatbot.chatbot_db import create_chat_session, get_chat_session, delete_chat_session

# ─────────────────────────────
# S2 Router — prefix: /web/chat
# ─────────────────────────────
router = APIRouter(prefix="/web/chat", tags=["Web Chat (S2)"])

FALLBACK_MESSAGE = "I'm sorry, something went wrong. Please try again."


# ─────────────────────────────
# Request / Response Models
# ─────────────────────────────

class ProfileEntry(BaseModel):
    question: str
    answer: str


class StartChatRequest(BaseModel):
    profile_data: List[ProfileEntry]
    reports: List[Dict[str, Any]]


class StartChatResponse(BaseModel):
    session_id: str
    message: str
    is_first: bool = True


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ContinueChatRequest(BaseModel):
    session_id: str
    history: List[ChatMessage]


class ContinueChatResponse(BaseModel):
    message: str


class EndChatRequest(BaseModel):
    session_id: str


class EndChatResponse(BaseModel):
    status: str = "ended"


# ─────────────────────────────
# Prompt Helpers (same as S1)
# ─────────────────────────────

def extract_patient_name(profile_data: list) -> str:
    for entry in profile_data:
        q = entry.get("question", "").lower()
        if "name" in q:
            return entry.get("answer", "").strip()
    return "there"


def build_profile_summary(profile_data: list) -> str:
    if not profile_data:
        return ""
    lines = ["Patient Profile:"]
    for entry in profile_data:
        q = entry.get("question", "").replace("?", "").replace("What is your ", "").replace("What is ", "").strip()
        a = entry.get("answer", "")
        lines.append(f"- {q}: {a}")
    return "\n".join(lines)


def build_report_context(reports: list) -> str:
    if not reports:
        return ""

    main_report = None
    other_reports = []
    for r in reports:
        if r.get("is_main", False):
            main_report = r
        else:
            other_reports.append(r)

    sections = []

    if main_report:
        rd = main_report.get("report_data", {})
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
                cause_lines.append(f"  - {title} ({severity}, {int(prob * 100)}% probability): {short}")
                detail = c.get("detail", {})
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
            rd = r.get("report_data", {})
            date = r.get("generated_at", "unknown date")
            summary = rd.get("summary", [])
            urgency = rd.get("urgency_level", "")
            brief = summary[0] if summary else "No summary"
            history_lines.append(f"  - {date}: {brief} (Urgency: {urgency})")
        sections.append("\n".join(history_lines))

    return "\n\n".join(sections)


def build_full_system_prompt(profile_data: list, reports: list) -> str:
    parts = [CHATBOT_SYSTEM_PROMPT.strip()]
    profile_summary = build_profile_summary(profile_data)
    if profile_summary:
        parts.append(profile_summary)
    report_context = build_report_context(reports)
    if report_context:
        parts.append(report_context)
    return "\n\n".join(parts)


# ─────────────────────────────
# S2 Endpoints  /web/chat/*
# ─────────────────────────────

@router.post("/start", response_model=StartChatResponse)
async def web_start_chat(request: StartChatRequest):
    """
    [S2 — Web] Start a new chat session.
    Endpoint: POST /web/chat/start
    Same logic as S1 /chat/start — diverge here when needed.
    """
    try:
        profile_data_raw = [entry.model_dump() for entry in request.profile_data]
        reports_raw = request.reports

        session_id = create_chat_session(
            profile_data=profile_data_raw,
            reports=reports_raw
        )

        full_system_prompt = build_full_system_prompt(profile_data_raw, reports_raw)
        patient_name = extract_patient_name(profile_data_raw)
        has_main_report = any(r.get("is_main", False) for r in reports_raw)

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
            welcome_message = chatbot_client.generate_response(
                user_message=start_instruction,
                system_prompt_override=full_system_prompt
            )
        except Exception:
            if has_main_report:
                welcome_message = f"Hi {patient_name}! I'm Remy. Based on your recent report, how can I help you today?"
            else:
                welcome_message = f"Hi {patient_name}! I'm Remy. How can I help you today?"

        return StartChatResponse(
            session_id=session_id,
            message=welcome_message,
            is_first=True
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start chat: {str(e)}")


@router.post("/message", response_model=ContinueChatResponse)
async def web_continue_chat(request: ContinueChatRequest):
    """
    [S2 — Web] Continue a chat session.
    Endpoint: POST /web/chat/message
    """
    try:
        if not request.history or len(request.history) == 0:
            raise HTTPException(status_code=400, detail="History cannot be empty")

        last_message = request.history[-1]
        if last_message.role != "user":
            raise HTTPException(status_code=400, detail="Last message in history must be from user")

        session = get_chat_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session not found: {request.session_id}")

        profile_data = session.get("profile_data", [])
        reports = session.get("reports", [])
        full_system_prompt = build_full_system_prompt(profile_data, reports)

        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history[:-1]
        ]

        try:
            response_msg = chatbot_client.generate_response(
                user_message=last_message.content,
                conversation_history=conversation_history if conversation_history else None,
                system_prompt_override=full_system_prompt
            )
        except Exception:
            response_msg = FALLBACK_MESSAGE

        return ContinueChatResponse(message=response_msg)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/end", response_model=EndChatResponse)
async def web_end_chat(request: EndChatRequest):
    """
    [S2 — Web] End and delete a chat session.
    Endpoint: POST /web/chat/end
    """
    try:
        deleted = delete_chat_session(request.session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Chat session not found: {request.session_id}")
        return EndChatResponse(status="ended")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end chat: {str(e)}")


@router.get("/health")
async def web_chat_health():
    """[S2 — Web] Health check. Endpoint: GET /web/chat/health"""
    try:
        if not chatbot_client.api_key:
            return {"status": "error", "message": "API key not configured"}
        return {
            "status": "healthy",
            "service": "web-chatbot-s2",
            "model": chatbot_client.model
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
