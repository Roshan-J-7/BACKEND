# 🩺 CURA - Med Assistant | Backend Server

> ⚠️ **This README is temporary and will be removed later.**

## Tech Stack

| Component | Technology |
|---|---|
| Server | FastAPI (Python) |
| Database | PostgreSQL (JSONB) |
| AI Engine | Google Gemini API |
| IoT Sync | Firebase Realtime DB |
| Containerization | Docker |
| Deployment | Cloud (AWS/GCP/Render) |

## Project Structure

```
healthcare-chatbot/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── chatbot/
│   │   ├── chatbot_db.py       # PostgreSQL connection & session CRUD
│   │   ├── chatbot_routes.py   # Chat endpoints (/chat/start, /chat/message, /chat/end)
│   │   ├── chatbot_client.py   # Gemini AI integration
│   │   └── chatbot_config.py   # Chatbot configuration
│   ├── core/
│   │   ├── llm_client.py       # LLM client abstraction
│   │   ├── llm_prompt.py       # Prompt engineering
│   │   ├── medical_schema.py   # Medical data schemas
│   │   └── guidance_engine.py  # Clinical guidance logic
│   └── vision_model/
│       ├── vision_routes.py    # Vision API endpoints
│       └── vision_client.py    # Image analysis via Gemini
├── config/
│   └── settings.py             # App settings
├── Dockerfile                  # Container config
├── docker-compose.yml          # Multi-service orchestration
├── requirements.txt            # Python dependencies
└── README.md                   # Main README
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat/start` | Start a new session with profile data |
| `POST` | `/chat/message` | Send a symptom message, get AI response |
| `POST` | `/chat/end` | End session, get report, delete data |

## Environment Variables

```env
DATABASE_URL=postgresql://user:password@host:5432/DeepBlue
GEMINI_API_KEY=your_gemini_api_key
FIREBASE_URL=your_firebase_realtime_db_url
```

## Run Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Team

**Deep Blue** — CURA Med Assistant Backend
