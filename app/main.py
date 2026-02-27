from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import json
import os
from jose import jwt, JWTError

app = FastAPI(title="Healthcare Chatbot", version="0.2.0")

# ─────────────────────────────
# CORS Configuration
# ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (ngrok, localhost, etc.)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# ─────────────────────────────
# Include Chatbot Routes
# ─────────────────────────────
from app.chatbot.chatbot_routes import router as chatbot_router
from app.chatbot.chatbot_db import init_chat_db
app.include_router(chatbot_router)

# ─────────────────────────────
# Include Auth Routes  (/auth/signup  /auth/login)
# ─────────────────────────────
from app.auth.auth_routes import router as auth_router
from app.auth.auth_db import init_auth_db
app.include_router(auth_router)

# ─────────────────────────────
# Include Profile Routes  (/user/profile/onboarding  /user/profile)
# ─────────────────────────────
from app.auth.profile_routes import router as profile_router
from app.auth.profile_db import init_profile_db
from app.auth.medical_db import init_medical_db
from app.auth.reports_db import init_reports_db, save_report
app.include_router(profile_router)

# ─────────────────────────────
# Vision Model Routes (PAUSED - Isolated)
# ─────────────────────────────
# Vision module is paused and isolated
# Uncomment below to re-enable when resuming project
# from app.vision_model.vision_routes import router as vision_router
# app.include_router(vision_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    # Initialize chatbot DB (chat_sessions + chat_messages tables)
    init_chat_db()
    # Initialize auth DB (users table — separate from chat_sessions)
    init_auth_db()
    # Initialize profile DB (user_profiles table — linked to users via FK)
    init_profile_db()
    # Initialize medical DB (user_medical_data table — linked to users via FK)
    init_medical_db()
    # Initialize reports DB (reports table — stores all generated assessment reports)
    init_reports_db()
    
    # Vision model loading paused - see app/vision_model/ for details
    # To resume: uncomment vision imports above and the vision loading code below
    # 
    # from app.vision_model.vision_config import VISION_LOAD_ON_STARTUP
    # if VISION_LOAD_ON_STARTUP:
    #     import asyncio
    #     from concurrent.futures import ThreadPoolExecutor
    #     from app.vision_model.vision_client import vision_client
    #     ... (rest of vision loading code)


# ─────────────────────────────
# DTOs
# ─────────────────────────────

class ContextRequest(BaseModel):
    session_id: str
    user_choice: str  # "new_user" | "existing_user"
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

    # INIT
    request_context: Optional[bool] = None
    request_questionnaire: Optional[bool] = None
    supported_phases: Optional[List[str]] = None

    # predefined
    question: Optional[QuestionBlock] = None
    options: Optional[List[AnswerOption]] = None
    progress: Optional[Progress] = None

    # llm
    message: Optional[str] = None


class AnswerValue(BaseModel):
    type: str
    value: str


class AnswerRequest(BaseModel):
    session_id: str
    phase: str
    question_id: Optional[str] = None
    answer: Optional[AnswerValue] = None
    user_message: Optional[str] = None  # For LLM phase


# ─────────────────────────────
# PRODUCTION API MODELS
# ─────────────────────────────

class Question(BaseModel):
    question_id: str
    text: str
    response_type: str  # "text", "number", "single_choice", "multi_choice"
    response_options: Optional[List[Dict[str, str]]] = None
    is_compulsory: bool  # True = user must manually enter; False = app can auto-populate from profile


class StoredAnswer(BaseModel):
    question_id: str
    question_text: str
    answer_json: Dict[str, Any]


class AssessmentStartResponse(BaseModel):
    session_id: str
    question: Question
    stored_answers: List[StoredAnswer] = []


class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    question_text: str
    answer_json: Dict[str, Any]  # {type, value} | {type, selected_option_label} | etc.


class AnswerResponse(BaseModel):
    session_id: str
    status: str = "next"  # "next" | "completed" | "error" — never null
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
    status: str  # "ended" or "not_found"


class ReportResponse(BaseModel):
    report_id: str
    summary: str


class CauseDetail(BaseModel):
    about_this: List[str]
    how_common: Dict[str, Any]  # {percentage: 60, description: "..."}
    what_you_can_do_now: List[str]
    warning: Optional[str] = None


class PossibleCause(BaseModel):
    id: str  # unique stable ID like "tension_headache"
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
# HELPER FUNCTIONS
# ─────────────────────────────

def load_questionnaire():
    """Load questionnaire from JSON file"""
    json_path = os.path.join(os.path.dirname(__file__), "data", "questionnaire.json")
    with open(json_path, "r") as f:
        return json.load(f)


def load_decision_tree():
    """Load decision tree from JSON file"""
    json_path = os.path.join(os.path.dirname(__file__), "data", "decision_tree.json")
    with open(json_path, "r") as f:
        return json.load(f)


def detect_symptom(complaint_text: str) -> Optional[Dict[str, Any]]:
    """Match chief complaint text against symptom keywords in decision tree"""
    if not complaint_text:
        return None
    
    complaint_lower = complaint_text.lower().strip()
    decision_tree = load_decision_tree()
    symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
    
    # Try to match against keywords
    for symptom in symptoms:
        keywords = symptom.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in complaint_lower:
                print(f"\n🔍 SYMPTOM DETECTED: '{keyword}' matched to {symptom['symptom_id']}")
                return {
                    "symptom_id": symptom["symptom_id"],
                    "label": symptom["label"],
                    "matched_keyword": keyword,
                    "default_urgency": symptom.get("default_urgency", "yellow_doctor_visit")
                }
    
    print(f"\n⚠️  NO SYMPTOM MATCH: Could not match '{complaint_text}' to any symptom")
    return None


# In-memory session storage - stores questionnaire responses
session_store = {}  # {session_id: [{"question": "...", "answer": "..."}, ...]}

# Follow-up question responses storage
followup_store = {}  # {session_id: [{"question": "...", "answer": "..."}, ...]}

# Conversation history for LLM phase (stores all chat turns)
conversation_history = {}

# Session storage for questionnaire flow
sessions = {}

# Session storage for follow-up questions flow
followup_sessions = {}  # {session_id: {"symptom": "...", "current_index": 0, "questions": [...]}}


def cleanup_session(session_id: str) -> bool:
    """Remove session data when chat is complete. Returns True if session existed."""
    found = False
    
    if session_id in sessions:
        del sessions[session_id]
        found = True
    
    if session_id in conversation_history:
        del conversation_history[session_id]
        found = True
    
    if session_id in session_store:
        del session_store[session_id]
        found = True
    
    if session_id in followup_sessions:
        del followup_sessions[session_id]
        found = True
    
    if session_id in followup_store:
        del followup_store[session_id]
        found = True
    
    if found:
        print(f"[CLEANUP] Session {session_id} removed from all stores")
    
    return found


def build_question_response(question_data: dict) -> Question:
    """Convert questionnaire format to app's expected format"""
    response_type_map = {
        "text": "text",
        "number": "number",
        "single_choice": "single_choice",
        "multi_choice": "multi_choice"
    }
    
    question = Question(
        question_id=question_data["id"],
        text=question_data["text"],
        response_type=response_type_map.get(question_data["type"], "text"),
        response_options=None,
        is_compulsory=question_data.get("is_compulsory", False)  # Default to False if not specified
    )
    
    # Add options if single_choice or multi_choice
    if question_data["type"] in ["single_choice", "multi_choice"]:
        question.response_options = [
            {"id": opt, "label": opt.replace("_", " ").title()}
            for opt in question_data["options"]
        ]
    
    return question


def extract_assessment_topic(answers: dict) -> str:
    """Extract assessment topic from user's chief complaint"""
    chief_complaint = answers.get("q_current_ailment", "")
    if chief_complaint:
        # Simple extraction - use the complaint as topic
        return chief_complaint.lower().strip()
    return "general_health"


# ─────────────────────────────
# PRODUCTION ENDPOINTS
# ─────────────────────────────

@app.get("/assessment/start", response_model=AssessmentStartResponse)
def start_assessment(request: Request):
    """
    Start assessment and return:
      - session_id
      - first question
      - stored_answers: all Q&A previously saved for this user
        (merged from user_profiles + user_medical_data tables)

    JWT is optional — if valid, stored answers are returned so the app
    can auto-populate answers from local cache without extra API calls.
    If no/invalid JWT, stored_answers is empty and app collects everything fresh.
    """
    from app.auth.auth_config import JWT_SECRET_KEY, JWT_ALGORITHM
    from app.auth.profile_db import get_profile_by_user_id
    from app.auth.medical_db import get_medical_by_user_id

    session_id = str(uuid.uuid4())
    questionnaire = load_questionnaire()
    first_q = questionnaire["questions"][0]

    # Initialize session
    sessions[session_id] = {
        "answers": {},
        "current_index": 0,
        "total_questions": len(questionnaire["questions"]),
        "phase": "questionnaire",  # "questionnaire" or "followup"
        "followup_questions": None,  # Will be populated after questionnaire
        "followup_index": 0,
        "detected_symptom": None
    }

    # Build question response
    question = build_question_response(first_q)

    # ── Fetch stored answers from JWT (optional) ──────────────────────
    stored_answers = []
    auth_header = request.headers.get("Authorization", "")

    print(f"[START] Auth header present: {bool(auth_header)}")

    if not auth_header.startswith("Bearer "):
        print("[START] WARNING: No Bearer token in Authorization header — stored_answers will be empty")
    else:
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            print(f"[START] JWT decoded OK — user_id: {user_id}")

            if not user_id:
                print("[START] WARNING: JWT has no 'sub' field — stored_answers will be empty")
            else:
                profile_rows = get_profile_by_user_id(user_id)
                medical_rows = get_medical_by_user_id(user_id)
                print(f"[START] Profile rows: {len(profile_rows)} | Medical rows: {len(medical_rows)}")

                for row in profile_rows + medical_rows:
                    stored_answers.append(StoredAnswer(
                        question_id=row["question_id"],
                        question_text=row["question_text"],
                        answer_json=row["answer_json"]
                    ))
        except JWTError as e:
            print(f"[START] JWT decode error: {e} — stored_answers will be empty")
        except Exception as e:
            print(f"[START] DB fetch error: {e} — stored_answers will be empty")

    print(f"\n[START] New session: {session_id[:8]}...")
    print(f"[START] First question: {first_q['id']}")
    print(f"[START] Stored answers returned: {len(stored_answers)}\n")

    return AssessmentStartResponse(
        session_id=session_id,
        question=question,
        stored_answers=stored_answers
    )


@app.post("/assessment/answer", response_model=AnswerResponse)
def submit_answer(req: AnswerRequest):
    """Handle answer and return next question"""
    session_id = req.session_id
    
    # Validate session exists
    if session_id not in sessions:
        print(f"[ERROR] Session {session_id[:8]}... not found")
        return AnswerResponse(
            session_id=session_id,
            status="error"
        )
    
    # Store answer based on type
    answer_data = req.answer_json
    question_id = req.question_id
    
    # Extract answer value based on type
    if answer_data.get("type") == "number":
        answer_value = answer_data.get("value")
    elif answer_data.get("type") == "single_choice":
        answer_value = answer_data.get("selected_option_label", answer_data.get("selected_option_id", answer_data.get("value")))
    elif answer_data.get("type") == "multi_choice":
        answer_value = ", ".join(answer_data.get("selected_option_labels", []))
    else:
        answer_value = answer_data.get("value", "")
    
    sessions[session_id]["answers"][question_id] = answer_value
    
    print(f"[ANSWER] Session {session_id[:8]}... answered {question_id}: {answer_value}")
    
    # Get session phase
    phase = sessions[session_id].get("phase", "questionnaire")
    
    if phase == "questionnaire":
        # QUESTIONNAIRE PHASE
        questionnaire = load_questionnaire()
        all_questions = questionnaire["questions"].copy()
        
        # Check for conditional questions (female → pregnancy/menstrual)
        answers = sessions[session_id]["answers"]
        gender = answers.get("q_gender")
        if gender and gender.lower() == "female":
            conditional = questionnaire.get("conditional", {}).get("q_gender=female", [])
            all_questions.extend(conditional)
        
        # Find next question
        current_index = sessions[session_id]["current_index"]
        next_index = current_index + 1
        
        # Check if questionnaire is complete
        if next_index >= len(all_questions):
            print(f"\n{'='*60}")
            print(f"✅ QUESTIONNAIRE COMPLETE")
            print(f"{'='*60}")
            
            # Detect symptom from chief complaint
            chief_complaint = answers.get("q_current_ailment", "")
            detected = detect_symptom(chief_complaint) if chief_complaint else None
            
            if detected:
                symptom_id = detected["symptom_id"]
                print(f"🔍 Detected symptom: {detected['label']} ({symptom_id})")
                print(f"🔄 Transitioning to FOLLOW-UP questions...\n")
                
                # Load follow-up questions for detected symptom
                decision_tree = load_decision_tree()
                symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
                symptom_data = next((s for s in symptoms if s["symptom_id"] == symptom_id), None)
                
                if symptom_data and "followup_questions" in symptom_data:
                    followup_qs = symptom_data["followup_questions"]
                    question_keys = list(followup_qs.keys())
                    
                    # Update session to follow-up phase
                    sessions[session_id]["phase"] = "followup"
                    sessions[session_id]["followup_questions"] = followup_qs
                    sessions[session_id]["followup_keys"] = question_keys
                    sessions[session_id]["followup_index"] = 0
                    sessions[session_id]["detected_symptom"] = detected
                    
                    # Return first follow-up question
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
                        is_compulsory=True  # Follow-up questions are always compulsory
                    )
                    
                    print(f"[FOLLOWUP] Question 1/{len(question_keys)}: {first_key}\n")
                    
                    return AnswerResponse(
                        session_id=session_id,
                        question=question
                    )
            
            # No symptom detected or no follow-up questions - end here
            print(f"⚠️  No symptom detected or no follow-up questions available")
            print(f"📊 Ready for final report\n")
            
            return AnswerResponse(
                session_id=session_id,
                status="completed"
            )
        
        # Return next questionnaire question
        sessions[session_id]["current_index"] = next_index
        next_q = all_questions[next_index]
        question = build_question_response(next_q)
        
        print(f"[NEXT] Session {session_id[:8]}... question {next_index + 1}/{len(all_questions)}: {next_q['id']}")
        
        return AnswerResponse(
            session_id=session_id,
            question=question
        )
    
    else:
        # FOLLOW-UP PHASE
        followup_qs = sessions[session_id]["followup_questions"]
        question_keys = sessions[session_id]["followup_keys"]
        current_index = sessions[session_id]["followup_index"]
        
        # Move to next follow-up question
        next_index = current_index + 1
        
        # Check if follow-ups are complete
        if next_index >= len(question_keys):
            print(f"\n{'='*60}")
            print(f"✅ FOLLOW-UP QUESTIONS COMPLETE")
            print(f"📊 Ready for final report with ALL questions\n")
            print(f"{'='*60}\n")
            
            return AnswerResponse(
                session_id=session_id,
                status="completed"
            )
        
        # Return next follow-up question
        sessions[session_id]["followup_index"] = next_index
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
            is_compulsory=True  # Follow-up questions are always compulsory
        )
        
        print(f"[FOLLOWUP] Session {session_id[:8]}... question {next_index + 1}/{len(question_keys)}: {next_key}\n")
        
        return AnswerResponse(
            session_id=session_id,
            question=question
        )


@app.post("/assessment/report", response_model=MedicalReportResponse)
def receive_report(req: ReportRequest, request: Request):
    """Receive completed assessment responses, generate medical report using LLM.
    If JWT is present in Authorization header, the report is also persisted to
    the `reports` table linked to that user."""
    from app.core.llm_client import generate_medical_report
    
    # Generate session_id if not provided
    session_id = req.session_id or str(uuid.uuid4())
    
    print(f"\n{'='*60}")
    print(f"📊 ASSESSMENT REPORT RECEIVED")
    print(f"{'='*60}")
    print(f"Session ID: {session_id}")
    print(f"Total Responses: {len(req.responses)}")
    print(f"{'='*60}\n")
    
    # Store responses in-memory session store
    responses_data = [qa.dict() for qa in req.responses]
    session_store[session_id] = responses_data
    
    # Extract chief complaint and detect symptom
    chief_complaint = None
    for qa in req.responses:
        if "chief complaint" in qa.question.lower() or "current ailment" in qa.question.lower():
            chief_complaint = qa.answer
            break
    
    # Try to detect symptom from chief complaint
    detected_symptom = None
    symptom_data = None
    
    if chief_complaint:
        print(f"\n🔍 Analyzing chief complaint: '{chief_complaint}'")
        detected_symptom = detect_symptom(chief_complaint)
        if detected_symptom:
            print(f"✅ Matched to: {detected_symptom['label']} ({detected_symptom['symptom_id']})")
            
            # Load full symptom data from decision tree
            decision_tree = load_decision_tree()
            symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
            for s in symptoms:
                if s["symptom_id"] == detected_symptom["symptom_id"]:
                    symptom_data = s
                    break
    
    # Print all responses for verification
    print(f"\n{'='*60}")
    print(f"PATIENT RESPONSES:")
    print(f"{'='*60}")
    for i, qa in enumerate(req.responses, 1):
        print(f"  {i}. Q: {qa.question}")
        print(f"     A: {qa.answer}")
    
    print(f"\n{'='*60}")
    print(f"✅ Stored {len(req.responses)} responses for session {session_id[:8]}...")
    print(f"📦 Storage: session_store['{session_id[:8]}...']")
    if detected_symptom:
        print(f"🎯 Detected Symptom: {detected_symptom['label']}")
    print(f"{'='*60}\n")
    
    # Generate medical report using LLM
    print(f"🤖 Generating medical report using LLM...")
    medical_report = generate_medical_report(responses_data, symptom_data)
    
    print(f"\n{'='*60}")
    print(f"✅ MEDICAL REPORT GENERATED")
    print(f"{'='*60}")
    print(f"Topic: {medical_report.get('assessment_topic', 'N/A')}")
    print(f"Urgency: {medical_report.get('urgency_level', 'N/A')}")
    print(f"Summary points: {len(medical_report.get('summary', []))}")
    print(f"Possible causes: {len(medical_report.get('possible_causes', []))}")
    print(f"Advice items: {len(medical_report.get('advice', []))}")
    print(f"{'='*60}\n")
    
    # Build the final response object — Pydantic validates and normalises all fields.
    # This is the EXACT JSON the app will receive.
    report_response = MedicalReportResponse(**medical_report)

    # ── Persist report to DB if JWT present ──────────────────────────────
    # Save report_response.dict() — identical to what FastAPI serialises to the app,
    # so GET /user/reports always returns the same JSON shape.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from jose import jwt as _jwt, JWTError as _JWTError
        from app.auth.auth_config import JWT_SECRET_KEY, JWT_ALGORITHM
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = _jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                save_report(user_id=user_id, report=report_response.dict())
                print(f"[REPORT] Persisted to DB for user {user_id[:8]}...")
            else:
                print("[REPORT] JWT has no 'sub' — report not persisted")
        except _JWTError as e:
            print(f"[REPORT] JWT decode error: {e} — report not persisted")
        except Exception as e:
            print(f"[REPORT] DB save error: {e} — report not persisted (still returned to app)")
    else:
        print("[REPORT] No JWT — report generated but not persisted")

    return report_response


# ═════════════════════════════════════════════════════════════
# SYMPTOM DETECTION & FOLLOW-UP QUESTIONS
# ═════════════════════════════════════════════════════════════

@app.get("/symptom/detect")
def detect_symptom_endpoint(complaint: str):
    """Detect symptom from chief complaint text using keyword matching"""
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
            "next_step": f"Call /followup/start?symptom={result['symptom_id']}"
        }
    else:
        return {
            "detected": False,
            "message": "No matching symptom found. Available symptoms: chest_pain, fever, headache",
            "suggestion": "User may need general medical consultation without symptom-specific questions"
        }


@app.get("/followup/start")
def start_followup(symptom: str):
    """Start symptom-specific follow-up questions from decision tree"""
    decision_tree = load_decision_tree()
    symptoms = decision_tree["symptom_decision_tree"]["symptoms"]
    
    # Find the matching symptom
    symptom_data = None
    for s in symptoms:
        if s["symptom_id"] == symptom:
            symptom_data = s
            break
    
    if not symptom_data:
        return {"error": f"Symptom '{symptom}' not found. Valid options: chest_pain, fever, headache"}
    
    # Extract follow-up questions
    followup_questions = symptom_data["followup_questions"]
    question_keys = list(followup_questions.keys())
    
    if not question_keys:
        return {"error": "No follow-up questions found for this symptom"}
    
    # Create session
    session_id = str(uuid.uuid4())
    first_question_key = question_keys[0]
    first_question_data = followup_questions[first_question_key]
    
    # Store session state
    followup_sessions[session_id] = {
        "symptom": symptom,
        "symptom_label": symptom_data["label"],
        "current_index": 0,
        "question_keys": question_keys,
        "all_questions": followup_questions,
        "responses": []
    }
    
    print(f"\n[FOLLOWUP START] Session: {session_id[:8]}... | Symptom: {symptom}")
    print(f"[FOLLOWUP START] First question: {first_question_key}\n")
    
    # Build response in EXACT same format as /assessment/start
    response = {
        "session_id": session_id,
        "question": {
            "question_id": first_question_key,
            "text": first_question_data["question"],
            "response_type": first_question_data["type"]
        },
        "is_last": len(question_keys) == 1
    }
    
    # Add response_options if present
    if "options" in first_question_data:
        options = []
        for opt in first_question_data["options"]:
            options.append({
                "id": opt,
                "label": opt.replace("_", " ").title()
            })
        response["question"]["response_options"] = options
    
    return response


@app.post("/followup/answer")
def answer_followup(req: AnswerRequest):
    """Submit answer to follow-up question and get next question"""
    session_id = req.session_id
    
    if session_id not in followup_sessions:
        print(f"[ERROR] Follow-up session {session_id[:8]}... not found")
        return {"error": "Session not found"}
    
    session = followup_sessions[session_id]
    current_index = session["current_index"]
    question_keys = session["question_keys"]
    all_questions = session["all_questions"]
    
    # Store the answer
    current_question_key = question_keys[current_index]
    session["responses"].append({
        "question": req.question,
        "answer": req.answer
    })
    
    print(f"[FOLLOWUP ANSWER] Session {session_id[:8]}... answered {current_question_key}: {req.answer}")
    
    # Move to next question
    current_index += 1
    session["current_index"] = current_index
    
    # Check if we're done
    if current_index >= len(question_keys):
        print(f"[FOLLOWUP COMPLETE] Session {session_id[:8]}... finished all {len(question_keys)} questions")
        return {
            "session_id": session_id,
            "question": {
                "question_id": "complete",
                "text": "Follow-up questions completed. Please submit your report.",
                "response_type": "text"
            },
            "is_last": True
        }
    
    # Get next question
    next_question_key = question_keys[current_index]
    next_question_data = all_questions[next_question_key]
    
    print(f"[FOLLOWUP NEXT] Session {session_id[:8]}... question {current_index + 1}/{len(question_keys)}: {next_question_key}")
    
    # Build response
    response = {
        "session_id": session_id,
        "question": {
            "question_id": next_question_key,
            "text": next_question_data["question"],
            "response_type": next_question_data["type"]
        },
        "is_last": (current_index == len(question_keys) - 1)
    }
    
    # Add response_options if present
    if "options" in next_question_data:
        options = []
        for opt in next_question_data["options"]:
            options.append({
                "id": opt,
                "label": opt.replace("_", " ").title()
            })
        response["question"]["response_options"] = options
    
    return response


@app.post("/followup/report", response_model=ReportResponse)
def receive_followup_report(req: ReportRequest):
    """Receive completed follow-up question responses"""
    # Generate session_id if not provided
    session_id = req.session_id or str(uuid.uuid4())
    
    print(f"\n{'='*60}")
    print(f"📊 FOLLOW-UP REPORT RECEIVED")
    print(f"{'='*60}")
    print(f"Session ID: {session_id}")
    print(f"Total Responses: {len(req.responses)}")
    print(f"{'='*60}\n")
    
    # Store responses in follow-up store
    followup_store[session_id] = [qa.dict() for qa in req.responses]
    
    # Print all responses for verification
    for i, qa in enumerate(req.responses, 1):
        print(f"  {i}. Q: {qa.question}")
        print(f"     A: {qa.answer}")
    
    print(f"\n{'='*60}")
    print(f"✅ Stored {len(req.responses)} follow-up responses for session {session_id[:8]}...")
    print(f"📦 Storage: followup_store['{session_id[:8]}...']")
    print(f"{'='*60}\n")
    
    return ReportResponse(
        report_id=session_id,
        summary=f"Follow-up assessment completed with {len(req.responses)} responses. Ready for analysis."
    )


# LEGACY ENDPOINT (kept for backward compatibility)
@app.post("/session/context", response_model=AssessmentResponse)
def receive_context(req: ContextRequest):
    """Receive context and start questionnaire or handle completed questionnaire"""
    global current_context, current_session_id
    
    # If questionnaire_context is provided, it means questionnaire is complete
    if req.questionnaire_context:
        print("\n" + "="*60)
        print("📋 QUESTIONNAIRE ANSWERS RECEIVED:")
        print("="*60)
        print(f"Session ID: {req.session_id}")
        print(f"User Choice: {req.user_choice}")
        print("\nAnswers:")
        for q_id, answer in req.questionnaire_context.items():
            print(f"  {q_id}: {answer}")
        print("="*60 + "\n")
        
        # TESTING MODE: Store only latest context (overwrites previous)
        current_context = {
            "session_id": req.session_id,
            "user_choice": req.user_choice,
            "answers": req.questionnaire_context
        }
        current_session_id = req.session_id
        
        print(f"✅ Context stored in RAM at: current_context variable")
        print(f"   Access via GET /debug/context to view\n")
        print(f"📊 Parsed Answers:")
        for k, v in req.questionnaire_context.items():
            print(f"   {k} = {v}")
        print()
        
        # Transition to LLM phase
        return AssessmentResponse(
            session_id=req.session_id,
            phase="llm",
            message="Thanks. I'll ask a few questions to better understand your condition."
        )
    
    # Initialize session storage for new user
    current_session_id = req.session_id
    sessions[req.session_id] = {
        "answers": {},
        "user_choice": req.user_choice
    }
    
    # Load questionnaire
    questionnaire = load_questionnaire()
    first_question = questionnaire["questions"][0]
    
    # Calculate total questions (base questions only for now)
    total_questions = len(questionnaire["questions"])
    
    # Build response
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


# ─────────────────────────────
# ANSWER HANDLING
# ─────────────────────────────

@app.post("/chat", response_model=AssessmentResponse)
def submit_answer(req: AnswerRequest):
    """Handle questionnaire answers"""
    print("CHAT:", req.dict())
    
    # ─── PREDEFINED PHASE
    if req.phase == "predefined":
        
        # Get or initialize session
        if req.session_id not in sessions:
            sessions[req.session_id] = {"answers": {}}
        
        # Store the answer
        if req.question_id:
            sessions[req.session_id]["answers"][req.question_id] = req.answer.value
        
        # Load questionnaire
        questionnaire = load_questionnaire()
        all_questions = questionnaire["questions"].copy()
        answers = sessions[req.session_id]["answers"]
        
        # Check if we need to add conditional questions
        if "q_gender" in answers and answers["q_gender"] == "female":
            conditional_questions = questionnaire.get("conditional", {}).get("q_gender=female", [])
            all_questions.extend(conditional_questions)
        
        # Find current question index
        current_index = -1
        for i, q in enumerate(all_questions):
            if q["id"] == req.question_id:
                current_index = i
                break
        
        # Get next question
        next_index = current_index + 1
        
        # Check if questionnaire is complete
        if next_index >= len(all_questions):
            # Request questionnaire context from app
            return AssessmentResponse(
                session_id=req.session_id,
                phase="predefined",
                request_context=True,
                request_questionnaire=True
            )
        
        # Get next question
        next_question = all_questions[next_index]
        
        # Build question block
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
    
    # ─── LLM PHASE - Conversational Medical Guidance
    if req.phase == "llm":
        print(f"\n[LLM] Request received: user_message='{req.user_message}'")
        
        # Access stored context
        if not current_context:
            return AssessmentResponse(
                session_id=req.session_id,
                phase="end",
                message="Session expired. Please start over."
            )
        
        answers = current_context["answers"]
        user_msg = req.user_message or ""
        
        print(f"[LLM] Session {req.session_id[:8]}... has history: {req.session_id in conversation_history}")
        
        # Initialize conversation history for this session (FIRST TIME ONLY)
        if req.session_id not in conversation_history:
            # Build medical schema from questionnaire
            from app.core.medical_schema import build_medical_schema
            from app.core.guidance_engine import load_guidance_rules, match_symptoms, build_guidance_bundle
            
            schema = build_medical_schema(answers)
            guidance_data = load_guidance_rules()
            
            # Match symptoms
            current_complaint = schema.get("current_complaint", "")
            matched_symptoms = match_symptoms(current_complaint, guidance_data.get("symptoms", {}))
            guidance_bundle = build_guidance_bundle(matched_symptoms, guidance_data)
            
            print(f"\n{'='*60}")
            print(f"[LLM INIT] Current complaint: '{current_complaint}'")
            print(f"[LLM INIT] Matched symptoms: {matched_symptoms}")
            print(f"[LLM INIT] Guidance questions available: {len(guidance_bundle.get('follow_up_questions', []))}")
            if guidance_bundle.get('follow_up_questions'):
                for i, q in enumerate(guidance_bundle['follow_up_questions'][:3], 1):
                    print(f"[LLM INIT]   Q{i}: {q}")
            print(f"{'='*60}\n")
            
            # Store for this session
            conversation_history[req.session_id] = {
                "schema": schema,
                "guidance": guidance_bundle,
                "messages": [],
                "question_count": 0
            }
            
            # Get first question from guidance rules or LLM
            follow_up_questions = guidance_bundle.get("follow_up_questions", [])
            
            if follow_up_questions and current_complaint:
                # Use first follow-up question from guidance rules
                first_question = follow_up_questions[0]
                intro = f"I see you're experiencing {current_complaint}. "
                first_msg = intro + first_question
                
                conversation_history[req.session_id]["messages"].append({
                    "role": "assistant",
                    "content": first_msg
                })
                conversation_history[req.session_id]["question_count"] = 1
                
                print(f"[LLM] Asking question 1: {first_question}")
                
                return AssessmentResponse(
                    session_id=req.session_id,
                    phase="llm",
                    message=first_msg
                )
            else:
                # No matched symptoms - ask LLM to generate question
                from app.core.llm_client import get_llm_response
                
                context_prompt = f"Patient's complaint: {current_complaint or 'not specified'}. Ask relevant follow-up question."
                llm_resp = get_llm_response(schema, guidance_bundle, context_prompt)
                
                first_msg = llm_resp.get("text", "Can you describe your symptoms in more detail?")
                
                conversation_history[req.session_id]["messages"].append({
                    "role": "assistant",
                    "content": first_msg
                })
                
                return AssessmentResponse(
                    session_id=req.session_id,
                    phase="llm",
                    message=first_msg
                )
        
        # Subsequent LLM turns - user has sent an answer
        if user_msg:
            session_data = conversation_history[req.session_id]
            
            # Store user message
            session_data["messages"].append({
                "role": "user",
                "content": user_msg
            })
            
            print(f"\n[LLM] Turn #{(len(session_data['messages']) + 1)//2}")
            print(f"[LLM] User: {user_msg}")
            
            # Continue asking questions
            follow_up_questions = session_data["guidance"].get("follow_up_questions", [])
            current_q_idx = session_data.get("question_count", 0)
            
            print(f"[LLM] Question count: {current_q_idx}, Available guidance questions: {len(follow_up_questions)}")
            
            # Check if we have more predefined questions from guidance rules
            if current_q_idx < len(follow_up_questions):
                next_question = follow_up_questions[current_q_idx]
                
                session_data["messages"].append({
                    "role": "assistant",
                    "content": next_question
                })
                session_data["question_count"] = current_q_idx + 1
                
                print(f"[LLM] Asking guidance question #{current_q_idx + 1}: {next_question}")
                
                return AssessmentResponse(
                    session_id=req.session_id,
                    phase="llm",
                    message=next_question
                )
            else:
                # No more predefined questions - use LLM to either ask more or analyze
                from app.core.llm_client import get_llm_response
                
                # Build conversation context
                conv_text = "\n".join([
                    f"{msg['role']}: {msg['content']}" 
                    for msg in session_data["messages"][-6:]  # Last 6 messages
                ])
                
                prompt = f"Conversation:\n{conv_text}\n\nBased on this info about their {session_data['schema'].get('current_complaint', 'condition')}, either ask ONE more relevant clarifying question OR provide analysis with urgency and advice if you have enough information."
                
                print(f"[LLM] No more guidance questions. Calling LLM for next step...")
                
                llm_resp = get_llm_response(
                    session_data["schema"],
                    session_data["guidance"],
                    prompt
                )
                
                if llm_resp.get("type") == "question":
                    next_question = llm_resp.get("text", "Is there anything else about your symptoms?")
                    
                    session_data["messages"].append({
                        "role": "assistant",
                        "content": next_question
                    })
                    session_data["question_count"] = current_q_idx + 1
                    
                    print(f"[LLM] LLM-generated question: {next_question}")
                    
                    return AssessmentResponse(
                        session_id=req.session_id,
                        phase="llm",
                        message=next_question
                    )
                else:
                    # LLM wants to provide analysis
                    summary = llm_resp.get("summary", "Based on your symptoms...")
                    advice = llm_resp.get("advice", ["Rest and monitor", "See a doctor if symptoms worsen"])
                    urgency = llm_resp.get("urgency", "self_care")
                    
                    full_msg = f"## Summary\n{summary}\n\n"
                    full_msg += f"**Urgency:** {urgency.replace('_', ' ').title()}\n\n"
                    full_msg += "## What to do:\n" + "\n".join([f"• {a}" for a in advice])
                    full_msg += "\n\n*This is general guidance. Consult a healthcare provider for personalized advice.*"
                    
                    print(f"[LLM] Analysis complete. Ending session.")
                    
                    cleanup_session(req.session_id)
                    
                    return AssessmentResponse(
                        session_id=req.session_id,
                        phase="end",
                        message=full_msg
                    )
        
        # Shouldn't reach here - initialization should have returned OR user should have sent message
        print(f"[LLM] WARNING: Reached unexpected fallback!")
        print(f"[LLM] user_msg: '{user_msg}', session in history: {req.session_id in conversation_history}")
        return AssessmentResponse(
            session_id=req.session_id,
            phase="end",
            message="An error occurred. Please restart the conversation."
        )
    
    # ─── END
    return AssessmentResponse(
        session_id=req.session_id,
        phase="end",
        message="Assessment completed. Take care."
    )


@app.post("/assessment/end", response_model=EndSessionResponse)
def end_assessment(request: EndSessionRequest):
    """
    End assessment session and cleanup all related data.
    
    Removes session from:
    - In-memory session stores (sessions, session_store)
    - Follow-up question stores (followup_sessions, followup_store)
    - LLM conversation history (conversation_history)
    
    Returns:
    - {"status": "ended"} if session was found and cleaned
    - {"status": "not_found"} if session didn't exist
    """
    session_existed = cleanup_session(request.session_id)
    
    if session_existed:
        return EndSessionResponse(status="ended")
    else:
        return EndSessionResponse(status="not_found")


@app.post("/session/end")
def end_session(request: Dict[str, str]):
    """Cleanup session when user closes or completes chat (legacy endpoint)"""
    session_id = request.get("session_id")
    if not session_id:
        return {"status": "error", "message": "session_id required"}
    
    cleanup_session(session_id)
    return {"status": "ok", "message": f"Session {session_id[:8]}... ended and cleaned up"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/debug/sessions")
def view_all_sessions():
    """View all stored sessions"""
    return {
        "status": "ok",
        "active_sessions": list(session_store.keys()),
        "session_count": len(session_store),
        "sessions": session_store
    }


@app.get("/debug/session/{session_id}")
def view_session_data(session_id: str):
    """View specific session data"""
    if session_id not in session_store:
        return {
            "status": "not_found",
            "message": f"Session {session_id} not found in storage",
            "session_id": session_id
        }
    
    return {
        "status": "ok",
        "session_id": session_id,
        "response_count": len(session_store[session_id]),
        "responses": session_store[session_id]
    }


@app.get("/debug/conversation/{session_id}")
def view_conversation(session_id: str):
    """View conversation history for a session (TESTING MODE)"""
    if session_id not in conversation_history:
        return {
            "status": "empty",
            "message": "No conversation found for this session",
            "session_id": session_id
        }
    
    session_data = conversation_history[session_id]
    return {
        "status": "ok",
        "session_id": session_id,
        "medical_schema": session_data.get("schema"),
        "matched_symptoms": session_data.get("guidance", {}).get("matched_symptoms", []),
        "conversation": session_data.get("messages", []),
        "turn_count": len(session_data.get("messages", [])) // 2
    }
