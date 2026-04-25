# Pitch and Demo Video Link
https://drive.google.com/file/d/1LWx-VOci3QK8h5G5Bf9ALMDn-3wifm_h/view?usp=sharing

# FoodRescue (UM Hackathon)

FoodRescue is a lightweight web app that helps restaurants donate surplus food to nearby NGOs.
Donors submit pickup requests through an LLM-powered chatbot, and NGOs receive assigned requests in a dashboard where they can accept or reject.

## Key Features

- **LLM Chatbot Pickup Assistant**
  - Collects donation details in natural language (food type/items, quantity, pickup time, expiry time, location, contact).
  - Asks follow-up questions when required fields are missing.
  - Produces structured data for downstream matching + notification creation.

- **NGO Matching + Dispatch**
  - Matches eligible NGOs by **food preference**, **capacity**, and **distance**.
  - Dispatches a pickup request to the **top 3 NGO candidates**.
  - Each candidate receives its own record with `ngo_status = pending`.

- **NGO Dashboard Workflow**
  - NGO logs in and sees only requests assigned to their `ngo_id`.
  - NGO can **Accept** or **Reject**.
  - On first acceptance, the other two candidate rows are automatically set to `reject` to prevent duplicates.

- **PostgreSQL + PostgREST Persistence**
  - NGO data stored in `ngos`.
  - Requests stored in `notifications`.
  - FastAPI uses PostgREST to read/write DB rows via HTTP.

## Tech Stack

- **Backend**: Python, FastAPI
- **LLM Orchestration**: Custom orchestrator (`app\llm_tools\orchestrator.py`) + LLM handler (`app\llm_tools\llm_handler.py`)
- **Database**: PostgreSQL
- **DB API Layer**: PostgREST (HTTP interface to PostgreSQL)
- **Backend → DB Client**: `requests`, `python-dotenv`
- **Frontend**: Vanilla HTML, CSS, JavaScript (Fetch API, LocalStorage)
- **Containerization**: Docker, Docker Compose

## Project Structure

- `app\main.py` — FastAPI backend endpoints (chat + NGO polling/decision).
- `app\llm_tools\orchestrator.py` — Conversation/session logic + NGO matching + notification creation.
- `app\llm_tools\knowledge_base.py` — NGO retrieval + capacity updates (via PostgREST).
- `app\database\database.sql` — PostgreSQL schema (tables: `ngos`, `notifications`).
- `app\database\db_crud.py` — PostgREST CRUD helpers.
- `app\frontend\html\` — Pages: `index.html`, `chatbot.html`, `login.html`, `ngo.html`, etc.
- `app\frontend\js\` — Frontend logic for chat and NGO dashboard.
- `app\frontend\css\` — Styling.


## Backend API (FastAPI)

Base URL (local): `http://localhost:8000`

- `GET /health`
- `POST /api/chat` (also mounted at `/api/chat/stream` for compatibility)
  - Body: `{ "message": "...", "session_id": "optional" }`
  - Returns: `{ status, session_id, message, ... }`

- `GET /api/ngo/requests?ngo_id=NGO_006`
  - Returns pending requests assigned to that NGO.

- `POST /api/ngo/requests/decision`
  - Body: `{ "request_id": "...", "ngo_id": "...", "decision": "accept|reject" }`
  - Accepting updates the chosen row to `accept` and sets the other two candidate rows to `reject`.

## Database

Schema file:
- `app\database\database.sql`

Tables:
- `um_hackathon.ngos`
- `um_hackathon.notifications`

## Running Locally (Windows)

### 1) Start Backend (FastAPI)
If you run FastAPI directly (example):

```powershell
cd c:\Users\Hp\Desktop\UM_Hackathon
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2) Open Frontend
Open the HTML files directly (no build step):
- `app\frontend\html\index.html`

### 3) Database + PostgREST
This project expects PostgREST reachable from `app\database\db_crud.py` via environment variables:
- `POSTGREST_IP`
- `POSTGREST_PORT`
- `POSTGREST_TOKEN`

Make sure PostgREST is configured to expose:
- `um_hackathon.ngos`
- `um_hackathon.notifications`

## Typical Demo Flow (Under 5 Minutes)

1. Open `index.html` → click **Request Pickup**
2. In chatbot, enter a natural donation message (food + quantity + pickup time + expiry + location + contact).
3. Chatbot confirms top NGO candidates and dispatches to possible NGOs.
4. Open **NGO Login** and log in as a demo NGO.
5. Go to **NGO Dashboard** → see assigned request → click **Accept**
6. Confirm request is no longer pending for other NGOs (de-duplication via reject updates).

## Troubleshooting

- **NGO dashboard shows no requests**
  - Ensure the backend `/api/ngo/requests` is reading from Postgres/PostgREST (not old txt/csv logic).
  - Confirm `notifications` rows exist and have `ngo_status = 'pending'` for the logged-in `ngo_id`.
  - Check `API_BASE_URL` in `app\frontend\js\ngo.js` and `chatbot.js` points to `http://localhost:8000`.

- **Favicon or logo not updating**
  - Hard refresh the browser (Ctrl+F5) to bypass cache.

- **Chatbot errors**
  - The UI shows a red error panel when the backend response is missing or errors.
  - Verify FastAPI is running on port 8000 and CORS is enabled.

---