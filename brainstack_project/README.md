# BrainStack E-Library

A fresh integrated web + Android digital library project using FastAPI, SQLite, Brevo transactional email, and ElevenLabs Conversational AI. The web theme follows the supplied reference project's maroon, warm-white, and gold palette, rounded cards, pill navigation, and clean catalog layout. This is a new project; no original application source files are used as the application foundation.

## Project structure

- `web/` responsive web UI
- `backend/` FastAPI REST API and SQLite database
- `backend/data/books.json` catalog seed (215 unique public-domain/openly licensed records from the supplied project data; check the license/source for each title before redistribution)
- `android/` Kotlin + Jetpack Compose Android client starter
- `app.yaml` Wasmer Edge configuration template
- `.github/workflows/backend-tests.yml` CI tests

## Local setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set a long JWT_SECRET, Brevo sender/API key, and admin credentials.
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` for the website and `http://localhost:8000/docs` for API docs. The first run creates `backend/data/brainstack.db` and seeds the catalog.

## Brevo setup

Create a Brevo API key, verify a sender email/domain, then set `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, and `BREVO_SENDER_NAME` in the backend environment. Registration sends a six-digit code that expires in five minutes. Never put the API key in browser or Android code.

## ElevenLabs setup

Create an ElevenLabs Conversational AI agent and set `ELEVENLABS_API_KEY` and `ELEVENLABS_AGENT_ID` in the backend environment. The web AI page loads the official ElevenLabs widget when an agent ID is configured. Configure the agent's webhook tools to call:

- `GET https://YOUR_HOST/api/ai/tools/search_books?q={query}`
- `GET https://YOUR_HOST/api/ai/tools/book_details/{book_id}`

The authenticated save operation is `POST /api/ai/tools/save_favorite` with `{ "book_id": 123, "confirmed": true }` and a user's Bearer token. The agent must ask the user to confirm before invoking it. Do not expose user tokens or service secrets to public agent configuration. Tool authentication and ownership should be configured in the ElevenLabs tool settings before public deployment.

## Android

Open the `android/` folder in Android Studio. The default emulator API base URL is `http://10.0.2.2:8000/`. Change `API_BASE_URL` in `android/app/build.gradle.kts` to your HTTPS Wasmer URL for a production build. The current Android module provides the branded Compose navigation and live catalog retrieval foundation; authentication, download/favorites flows, and the ElevenLabs native voice SDK/widget bridge remain to be completed before claiming full Phase 3 compliance.

## Tests

```powershell
cd backend
pytest -q
```

## Docker

From project root:

```bash
docker build -t brainstack-api ./backend
docker run --env-file backend/.env -p 8000:8000 -v brainstack-data:/data -e DATABASE_PATH=/data/brainstack.db brainstack-api
```

## Wasmer

Wasmer's current `app.yaml` requires a published Wasmer package name. Update `owner` and `package` in the root `app.yaml`, publish the backend package using the current Wasmer Python/WASI packaging workflow, then deploy with `wasmer deploy`. Set secrets in the Wasmer dashboard. The SQLite volume template is included, but Wasmer documentation warns that Edge volumes currently have read-write-many semantics and are not suitable for databases requiring a single writer. Use this SQLite setup only for a carefully tested single-instance/demo deployment; do not scale multiple app instances against one SQLite volume.

## Important completion notes

The web/API foundation implements account verification, login, guest session IDs, catalog search, favorites, download caps, admin summary, and catalog tools. Before final examination, finish the remaining items documented in `docs/PHASE3-CHECKLIST.md`, test all flows on real devices, and validate book-specific download licensing. The seed records are not a blanket license to redistribute full book files; the app links to their source editions.
