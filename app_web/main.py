"""
S2 — Web Server (CURA Kiosk / Website)
=======================================
Exact functional duplicate of app/main.py — ALL endpoints prefixed with /web/

S1 (app/main.py)   → routes: /assessment/*, /followup/*, /chat, /symptom/*, /session/*
S2 (this file)     → routes: /web/assessment/*, /web/followup/*, /web/chat (legacy),
                               /web/symptom/*, /web/session/*

S2 chatbot routes  → /web/chat/* (from app_web/chatbot/chatbot_routes.py)

WHY THIS EXISTS:
- S1 stays frozen for Gowtham's Kotlin app (slow UI iteration)
- S2 is developed freely alongside Roshan's website/kiosk
- Same DB, same core logic — diverge only where web needs differ
- Entry point: web_server.py  →  uvicorn app_web.main:app

TO EDIT S2 ONLY: modify files in app_web/ — never touch app/
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import json
import os

# ─────────────────────────────
# S2 FastAPI App
# ─────────────────────────────
app = FastAPI(
    title="CURA Med Assistant — S2 Web Server",
    version="1.0.0",
    description="Web/Kiosk server. All endpoints are under /web/ prefix."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────
# Include S2 Chatbot Routes  (/web/chat/*)
# ─────────────────────────────
from app_web.chatbot.chatbot_routes import router as web_chatbot_router
from app.chatbot.chatbot_db import init_db   # Shared DB — same PostgreSQL instance

app.include_router(web_chatbot_router)


@app.on_event("startup")
async def startup_event():
    """Initialize shared DB tables on S2 startup"""
    init_db()


# ─────────────────────────────
# Data Loading Helpers
# (Points to app/data/ — single source of truth for data files)
# ─────────────────────────────

def _data_path(filename: str) -> str:
    """Resolve path to shared data files in app/data/"""
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),  # project root
        "app", "data", filename
    )


def load_questionnaire():
    with open(_data_path("questionnaire.json"), "r") as f:
        return json.load(f)


def load_decision_tree():
    with open(_data_path("decision_tree.json"), "r") as f:
        return json.load(f)


# ─────────────────────────────
# DTOs  (identical to S1)
# ─────────────────────────────

class ContextRequest(BaseModel):
    session_id: str
    user_choice: str
    questionnaire_context: Optional[dict] = None
    medical_report: Optional[dict] = None


class AnswerOption(BaseModel):
    id: str
    label: str


class QuestionBlock(BaseModel):
    question_id: str
    text: str
    type: str
    input_mode: Optional[str] = "buttons"
    input_hint: Optional[str] = None


class Progress(BaseModel):
    current: int
    total: int


class AssessmentResponse(BaseModel):
    session_id: str
    phase: str
    request_context: Optional[bool] = None
    request_questionnaire: Optional[bool] = None
    supported_phases: Optional[List[str]] = None
    question: Optional[QuestionBlock] = None
    options: Optional[List[AnswerOption]] = None
    progress: Optional[Progress] = None
    message: Optional[str] = None


class AnswerValue(BaseModel):
    type: str
    value: str


class Question(BaseModel):
    question_id: str
    text: str
    response_type: str
    response_options: Optional[List[Dict[str, str]]] = None
    is_compulsory: bool


class AssessmentStartResponse(BaseModel):
    session_id: str
    question: Question


class AnswerRequest(BaseModel):
    session_id: str
    question: Optional[Question] = None
    answer: Optional[Dict[str, Any]] = None
    phase: Optional[str] = None
    question_id: Optional[str] = None
    answer_value: Optional[AnswerValue] = None
    user_message: Optional[str] = None


class AnswerResponse(BaseModel):
    session_id: str
    status: Optional[str] = None
    question: Optional[Question] = None


class QAPair(BaseModel):
    question: Question
    answer: Dict[str, Any]


class SimpleQA(BaseModel):
    question: str
    answer: str


class ReportRequest(BaseModel):
    session_id: Optional[str] = None
    responses: List[SimpleQA]


class EndSessionRequest(BaseModel):
    session_id: str


class EndSessionResponse(BaseModel):
    status: str


class ReportResponse(BaseModel):
    report_id: str
    summary: str


class CauseDetail(BaseModel):
    about_this: List[str]
    how_common: Dict[str, Any]
    what_you_can_do_now: List[str]
    warning: Optional[str] = None


class PossibleCause(BaseModel):
    id: str
    title: str
    short_description: str
    severity: str
    probability: float
    subtitle: Optional[str] = None
    detail: CauseDetail


class PatientInfo(BaseModel):
    name: str
    age: int
    gender: str


class MedicalReportResponse(BaseModel):
    report_id: str
    assessment_topic: str
    generated_at: str
    patient_info: PatientInfo
    summary: List[str]
    possible_causes: List[PossibleCause]
    advice: List[str]
    urgency_level: str


# ─────────────────────────────
# S2 In-Memory State (isolated from S1)
# ─────────────────────────────
web_sessions = {}
web_session_store = {}
web_followup_sessions = {}
web_followup_store = {}
web_conversation_history = {}
web_current_context = None
web_current_session_id = None


# ─────────────────────────────
# Helpers
# ─────────────────────────────

def detect_symptom(complaint_text: str) -> Optional[Dict[str, Any]]:
    if not complaint_text:
        return None
    complaint_lower = complaint_text.lower().strip()
    decision_tree = load_decision_tree()
    symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
    for symptom in symptoms:
        for keyword in symptom.get("keywords", []):
            if keyword.lower() in complaint_lower:
                return {
                    "symptom_id": symptom["symptom_id"],
                    "label": symptom["label"],
                    "matched_keyword": keyword,
                    "default_urgency": symptom.get("default_urgency", "yellow_doctor_visit")
                }
    return None


def cleanup_session(session_id: str) -> bool:
    found = False
    for store in [web_sessions, web_conversation_history, web_session_store,
                  web_followup_sessions, web_followup_store]:
        if session_id in store:
            del store[session_id]
            found = True
    if found:
        print(f"[S2 CLEANUP] Session {session_id} removed")
    return found


def build_question_response(question_data: dict) -> Question:
    question = Question(
        question_id=question_data["id"],
        text=question_data["text"],
        response_type=question_data["type"],
        response_options=None,
        is_compulsory=question_data.get("is_compulsory", False)
    )
    if question_data["type"] in ["single_choice", "multi_choice"]:
        question.response_options = [
            {"id": opt, "label": opt.replace("_", " ").title()}
            for opt in question_data["options"]
        ]
    return question


# ─────────────────────────────
# S2 PRODUCTION ENDPOINTS   /web/*
# ─────────────────────────────

@app.get("/web/assessment/start", response_model=AssessmentStartResponse)
def web_start_assessment():
    """[S2] Start assessment — GET /web/assessment/start"""
    session_id = str(uuid.uuid4())
    questionnaire = load_questionnaire()
    first_q = questionnaire["questions"][0]

    web_sessions[session_id] = {
        "answers": {},
        "current_index": 0,
        "total_questions": len(questionnaire["questions"]),
        "phase": "questionnaire",
        "followup_questions": None,
        "followup_index": 0,
        "detected_symptom": None
    }

    question = build_question_response(first_q)
    print(f"\n[S2 START] New session: {session_id[:8]}...")
    return AssessmentStartResponse(session_id=session_id, question=question)


@app.post("/web/assessment/answer", response_model=AnswerResponse)
def web_submit_answer(req: AnswerRequest):
    """[S2] Submit answer — POST /web/assessment/answer"""
    session_id = req.session_id

    if session_id not in web_sessions:
        return AnswerResponse(session_id=session_id, status="error")

    answer_data = req.answer or {}
    question_id = req.question.question_id if req.question else req.question_id

    if answer_data.get("type") == "number":
        answer_value = answer_data.get("value")
    elif answer_data.get("type") == "single_choice":
        answer_value = answer_data.get("selected_option_label", answer_data.get("selected_option_id", answer_data.get("value")))
    elif answer_data.get("type") == "multi_choice":
        answer_value = ", ".join(answer_data.get("selected_option_labels", []))
    else:
        answer_value = answer_data.get("value", "")

    web_sessions[session_id]["answers"][question_id] = answer_value
    print(f"[S2 ANSWER] {session_id[:8]}... {question_id}: {answer_value}")

    phase = web_sessions[session_id].get("phase", "questionnaire")

    if phase == "questionnaire":
        questionnaire = load_questionnaire()
        all_questions = questionnaire["questions"].copy()
        answers = web_sessions[session_id]["answers"]

        gender = answers.get("q_gender")
        if gender and gender.lower() == "female":
            conditional = questionnaire.get("conditional", {}).get("q_gender=female", [])
            all_questions.extend(conditional)

        current_index = web_sessions[session_id]["current_index"]
        next_index = current_index + 1

        if next_index >= len(all_questions):
            chief_complaint = answers.get("q_current_ailment", "")
            detected = detect_symptom(chief_complaint) if chief_complaint else None

            if detected:
                symptom_id = detected["symptom_id"]
                decision_tree = load_decision_tree()
                symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
                symptom_data = next((s for s in symptoms if s["symptom_id"] == symptom_id), None)

                if symptom_data and "followup_questions" in symptom_data:
                    followup_qs = symptom_data["followup_questions"]
                    question_keys = list(followup_qs.keys())

                    web_sessions[session_id]["phase"] = "followup"
                    web_sessions[session_id]["followup_questions"] = followup_qs
                    web_sessions[session_id]["followup_keys"] = question_keys
                    web_sessions[session_id]["followup_index"] = 0
                    web_sessions[session_id]["detected_symptom"] = detected

                    first_key = question_keys[0]
                    first_q_data = followup_qs[first_key]

                    question = Question(
                        question_id=first_key,
                        text=first_q_data["question"],
                        response_type=first_q_data["type"],
                        response_options=[
                            {"id": opt, "label": opt.replace("_", " ").title()}
                            for opt in first_q_data.get("options", [])
                        ] if "options" in first_q_data else None,
                        is_compulsory=True
                    )
                    return AnswerResponse(session_id=session_id, question=question)

            return AnswerResponse(session_id=session_id, status="completed")

        web_sessions[session_id]["current_index"] = next_index
        next_q = all_questions[next_index]
        question = build_question_response(next_q)
        return AnswerResponse(session_id=session_id, question=question)

    else:
        # FOLLOW-UP PHASE
        followup_qs = web_sessions[session_id]["followup_questions"]
        question_keys = web_sessions[session_id]["followup_keys"]
        current_index = web_sessions[session_id]["followup_index"]
        next_index = current_index + 1

        if next_index >= len(question_keys):
            return AnswerResponse(session_id=session_id, status="completed")

        web_sessions[session_id]["followup_index"] = next_index
        next_key = question_keys[next_index]
        next_q_data = followup_qs[next_key]

        question = Question(
            question_id=next_key,
            text=next_q_data["question"],
            response_type=next_q_data["type"],
            response_options=[
                {"id": opt, "label": opt.replace("_", " ").title()}
                for opt in next_q_data.get("options", [])
            ] if "options" in next_q_data else None,
            is_compulsory=True
        )
        return AnswerResponse(session_id=session_id, question=question)


@app.post("/web/assessment/report", response_model=MedicalReportResponse)
def web_receive_report(req: ReportRequest):
    """[S2] Generate medical report — POST /web/assessment/report"""
    from app.core.llm_client import generate_medical_report

    session_id = req.session_id or str(uuid.uuid4())
    responses_data = [qa.dict() for qa in req.responses]
    web_session_store[session_id] = responses_data

    chief_complaint = None
    for qa in req.responses:
        if "chief complaint" in qa.question.lower() or "current ailment" in qa.question.lower():
            chief_complaint = qa.answer
            break

    detected_symptom = None
    symptom_data = None
    if chief_complaint:
        detected_symptom = detect_symptom(chief_complaint)
        if detected_symptom:
            decision_tree = load_decision_tree()
            for s in decision_tree["symptom_decision_tree"]["symptoms"]:
                if s["symptom_id"] == detected_symptom["symptom_id"]:
                    symptom_data = s
                    break

    print(f"[S2 REPORT] Generating for session {session_id[:8]}...")
    medical_report = generate_medical_report(responses_data, symptom_data)
    return MedicalReportResponse(**medical_report)


@app.post("/web/assessment/end", response_model=EndSessionResponse)
def web_end_assessment(request: EndSessionRequest):
    """[S2] End assessment session — POST /web/assessment/end"""
    existed = cleanup_session(request.session_id)
    return EndSessionResponse(status="ended" if existed else "not_found")


# ─────────────────────────────
# S2 SYMPTOM / FOLLOWUP ENDPOINTS   /web/symptom/*  /web/followup/*
# ─────────────────────────────

@app.get("/web/symptom/detect")
def web_detect_symptom(complaint: str):
    """[S2] Detect symptom — GET /web/symptom/detect"""
    if not complaint or not complaint.strip():
        return {"error": "Complaint text is required"}
    result = detect_symptom(complaint)
    if result:
        return {
            "detected": True,
            "symptom_id": result["symptom_id"],
            "label": result["label"],
            "matched_keyword": result["matched_keyword"],
            "default_urgency": result["default_urgency"],
            "next_step": f"Call /web/followup/start?symptom={result['symptom_id']}"
        }
    return {"detected": False, "message": "No matching symptom found."}


@app.get("/web/followup/start")
def web_start_followup(symptom: str):
    """[S2] Start follow-up questions — GET /web/followup/start"""
    decision_tree = load_decision_tree()
    symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
    symptom_data = next((s for s in symptoms if s["symptom_id"] == symptom), None)

    if not symptom_data:
        return {"error": f"Symptom '{symptom}' not found."}

    followup_questions = symptom_data["followup_questions"]
    question_keys = list(followup_questions.keys())
    if not question_keys:
        return {"error": "No follow-up questions found for this symptom"}

    session_id = str(uuid.uuid4())
    first_key = question_keys[0]
    first_q_data = followup_questions[first_key]

    web_followup_sessions[session_id] = {
        "symptom": symptom,
        "symptom_label": symptom_data["label"],
        "current_index": 0,
        "question_keys": question_keys,
        "all_questions": followup_questions,
        "responses": []
    }

    response = {
        "session_id": session_id,
        "question": {
            "question_id": first_key,
            "text": first_q_data["question"],
            "response_type": first_q_data["type"]
        },
        "is_last": len(question_keys) == 1
    }
    if "options" in first_q_data:
        response["question"]["response_options"] = [
            {"id": opt, "label": opt.replace("_", " ").title()}
            for opt in first_q_data["options"]
        ]
    return response


@app.post("/web/followup/answer")
def web_answer_followup(req: AnswerRequest):
    """[S2] Answer follow-up question — POST /web/followup/answer"""
    session_id = req.session_id
    if session_id not in web_followup_sessions:
        return {"error": "Session not found"}

    session = web_followup_sessions[session_id]
    question_keys = session["question_keys"]
    all_questions = session["all_questions"]
    current_index = session["current_index"]

    session["responses"].append({"question": req.question, "answer": req.answer})
    current_index += 1
    session["current_index"] = current_index

    if current_index >= len(question_keys):
        return {
            "session_id": session_id,
            "question": {"question_id": "complete", "text": "Follow-up questions completed.", "response_type": "text"},
            "is_last": True
        }

    next_key = question_keys[current_index]
    next_q_data = all_questions[next_key]

    response = {
        "session_id": session_id,
        "question": {
            "question_id": next_key,
            "text": next_q_data["question"],
            "response_type": next_q_data["type"]
        },
        "is_last": (current_index == len(question_keys) - 1)
    }
    if "options" in next_q_data:
        response["question"]["response_options"] = [
            {"id": opt, "label": opt.replace("_", " ").title()}
            for opt in next_q_data["options"]
        ]
    return response


@app.post("/web/followup/report", response_model=ReportResponse)
def web_receive_followup_report(req: ReportRequest):
    """[S2] Submit follow-up report — POST /web/followup/report"""
    session_id = req.session_id or str(uuid.uuid4())
    web_followup_store[session_id] = [qa.dict() for qa in req.responses]
    print(f"[S2 FOLLOWUP REPORT] {len(req.responses)} responses for {session_id[:8]}...")
    return ReportResponse(
        report_id=session_id,
        summary=f"Follow-up assessment completed with {len(req.responses)} responses."
    )


# ─────────────────────────────
# S2 LEGACY ENDPOINTS   /web/session/*  /web/chat (legacy)
# ─────────────────────────────

@app.post("/web/session/context", response_model=AssessmentResponse)
def web_receive_context(req: ContextRequest):
    """[S2 Legacy] Receive context — POST /web/session/context"""
    global web_current_context, web_current_session_id

    if req.questionnaire_context:
        web_current_context = {
            "session_id": req.session_id,
            "user_choice": req.user_choice,
            "answers": req.questionnaire_context
        }
        web_current_session_id = req.session_id
        return AssessmentResponse(
            session_id=req.session_id,
            phase="llm",
            message="Thanks. I'll ask a few questions to better understand your condition."
        )

    web_current_session_id = req.session_id
    web_sessions[req.session_id] = {"answers": {}, "user_choice": req.user_choice}
    questionnaire = load_questionnaire()
    first_question = questionnaire["questions"][0]
    total_questions = len(questionnaire["questions"])

    question_block = QuestionBlock(
        question_id=first_question["id"],
        text=first_question["text"],
        type=first_question["type"]
    )
    options = None
    if first_question["type"] == "single_choice":
        question_block.input_mode = "buttons"
        options = [
            AnswerOption(id=opt, label=opt.replace("_", " ").title())
            for opt in first_question["options"]
        ]
    else:
        question_block.input_hint = first_question.get("hint", "")

    return AssessmentResponse(
        session_id=req.session_id,
        phase="predefined",
        question=question_block,
        options=options,
        progress=Progress(current=1, total=total_questions)
    )


@app.post("/web/session/end")
def web_end_session(request: Dict[str, str]):
    """[S2 Legacy] End session — POST /web/session/end"""
    session_id = request.get("session_id")
    if not session_id:
        return {"status": "error", "message": "session_id required"}
    cleanup_session(session_id)
    return {"status": "ok", "message": f"Session {session_id[:8]}... ended"}


@app.post("/web/chat", response_model=AssessmentResponse)
def web_legacy_chat(req: AnswerRequest):
    """[S2 Legacy] Chat endpoint — POST /web/chat"""
    if req.phase == "predefined":
        if req.session_id not in web_sessions:
            web_sessions[req.session_id] = {"answers": {}}

        if req.question_id:
            web_sessions[req.session_id]["answers"][req.question_id] = req.answer_value.value if req.answer_value else None

        questionnaire = load_questionnaire()
        all_questions = questionnaire["questions"].copy()
        answers = web_sessions[req.session_id]["answers"]

        if "q_gender" in answers and answers["q_gender"] == "female":
            all_questions.extend(questionnaire.get("conditional", {}).get("q_gender=female", []))

        current_index = -1
        for i, q in enumerate(all_questions):
            if q["id"] == req.question_id:
                current_index = i
                break

        next_index = current_index + 1
        if next_index >= len(all_questions):
            return AssessmentResponse(
                session_id=req.session_id,
                phase="predefined",
                request_context=True,
                request_questionnaire=True
            )

        next_question = all_questions[next_index]
        question_block = QuestionBlock(
            question_id=next_question["id"],
            text=next_question["text"],
            type=next_question["type"]
        )
        options = None
        if next_question["type"] == "single_choice":
            question_block.input_mode = "buttons"
            options = [
                AnswerOption(id=opt, label=opt.replace("_", " ").title())
                for opt in next_question["options"]
            ]
        else:
            question_block.input_hint = next_question.get("hint", "")

        return AssessmentResponse(
            session_id=req.session_id,
            phase="predefined",
            question=question_block,
            options=options,
            progress=Progress(current=next_index + 1, total=len(all_questions))
        )

    if req.phase == "llm":
        if not web_current_context:
            return AssessmentResponse(session_id=req.session_id, phase="end", message="Session expired. Please start over.")

        answers = web_current_context["answers"]
        user_msg = req.user_message or ""

        if req.session_id not in web_conversation_history:
            from app.core.medical_schema import build_medical_schema
            from app.core.guidance_engine import load_guidance_rules, match_symptoms, build_guidance_bundle

            schema = build_medical_schema(answers)
            guidance_data = load_guidance_rules()
            current_complaint = schema.get("current_complaint", "")
            matched_symptoms = match_symptoms(current_complaint, guidance_data.get("symptoms", {}))
            guidance_bundle = build_guidance_bundle(matched_symptoms, guidance_data)

            web_conversation_history[req.session_id] = {
                "schema": schema,
                "guidance": guidance_bundle,
                "messages": [],
                "question_count": 0
            }

            follow_up_questions = guidance_bundle.get("follow_up_questions", [])
            if follow_up_questions and current_complaint:
                first_question = follow_up_questions[0]
                first_msg = f"I see you're experiencing {current_complaint}. " + first_question
                web_conversation_history[req.session_id]["messages"].append({"role": "assistant", "content": first_msg})
                web_conversation_history[req.session_id]["question_count"] = 1
                return AssessmentResponse(session_id=req.session_id, phase="llm", message=first_msg)
            else:
                from app.core.llm_client import get_llm_response
                llm_resp = get_llm_response(schema, guidance_bundle, f"Patient's complaint: {current_complaint or 'not specified'}. Ask relevant follow-up question.")
                first_msg = llm_resp.get("text", "Can you describe your symptoms in more detail?")
                web_conversation_history[req.session_id]["messages"].append({"role": "assistant", "content": first_msg})
                return AssessmentResponse(session_id=req.session_id, phase="llm", message=first_msg)

        if user_msg:
            session_data = web_conversation_history[req.session_id]
            session_data["messages"].append({"role": "user", "content": user_msg})

            follow_up_questions = session_data["guidance"].get("follow_up_questions", [])
            current_q_idx = session_data.get("question_count", 0)

            if current_q_idx < len(follow_up_questions):
                next_question = follow_up_questions[current_q_idx]
                session_data["messages"].append({"role": "assistant", "content": next_question})
                session_data["question_count"] = current_q_idx + 1
                return AssessmentResponse(session_id=req.session_id, phase="llm", message=next_question)
            else:
                from app.core.llm_client import get_llm_response
                conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in session_data["messages"][-6:]])
                prompt = (
                    f"Conversation:\n{conv_text}\n\nBased on this info about their "
                    f"{session_data['schema'].get('current_complaint', 'condition')}, "
                    "either ask ONE more relevant clarifying question OR provide analysis with urgency and advice."
                )
                llm_resp = get_llm_response(session_data["schema"], session_data["guidance"], prompt)

                if llm_resp.get("type") == "question":
                    next_q = llm_resp.get("text", "Is there anything else about your symptoms?")
                    session_data["messages"].append({"role": "assistant", "content": next_q})
                    session_data["question_count"] = current_q_idx + 1
                    return AssessmentResponse(session_id=req.session_id, phase="llm", message=next_q)
                else:
                    summary = llm_resp.get("summary", "Based on your symptoms...")
                    advice = llm_resp.get("advice", ["Rest and monitor", "See a doctor if symptoms worsen"])
                    urgency = llm_resp.get("urgency", "self_care")
                    full_msg = f"## Summary\n{summary}\n\n**Urgency:** {urgency.replace('_', ' ').title()}\n\n"
                    full_msg += "## What to do:\n" + "\n".join([f"• {a}" for a in advice])
                    full_msg += "\n\n*This is general guidance. Consult a healthcare provider for personalized advice.*"
                    cleanup_session(req.session_id)
                    return AssessmentResponse(session_id=req.session_id, phase="end", message=full_msg)

        return AssessmentResponse(session_id=req.session_id, phase="end", message="An error occurred. Please restart.")

    return AssessmentResponse(session_id=req.session_id, phase="end", message="Assessment completed. Take care.")


# ─────────────────────────────
# S2 HEALTH & DEBUG   /web/health  /web/debug/*
# ─────────────────────────────

@app.get("/web/health")
def web_health_check():
    """[S2] Health check — GET /web/health"""
    return {"status": "ok", "server": "S2-web"}


@app.get("/web/debug/sessions")
def web_view_all_sessions():
    """[S2] Debug all sessions"""
    return {
        "status": "ok",
        "server": "S2",
        "active_sessions": list(web_session_store.keys()),
        "session_count": len(web_session_store),
        "sessions": web_session_store
    }


@app.get("/web/debug/session/{session_id}")
def web_view_session(session_id: str):
    """[S2] Debug specific session"""
    if session_id not in web_session_store:
        return {"status": "not_found", "session_id": session_id}
    return {
        "status": "ok",
        "server": "S2",
        "session_id": session_id,
        "response_count": len(web_session_store[session_id]),
        "responses": web_session_store[session_id]
    }


@app.get("/web/debug/conversation/{session_id}")
def web_view_conversation(session_id: str):
    """[S2] Debug conversation history"""
    if session_id not in web_conversation_history:
        return {"status": "empty", "session_id": session_id}
    session_data = web_conversation_history[session_id]
    return {
        "status": "ok",
        "server": "S2",
        "session_id": session_id,
        "medical_schema": session_data.get("schema"),
        "matched_symptoms": session_data.get("guidance", {}).get("matched_symptoms", []),
        "conversation": session_data.get("messages", []),
        "turn_count": len(session_data.get("messages", [])) // 2
    }
