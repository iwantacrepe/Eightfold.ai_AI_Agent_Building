# Account Plan Research Assistant

Multi-agent research workflow that gathers public intel, summarizes it with LLM prompts, and returns an editable enterprise account plan via a lightweight Flask UI.

## Setup Instructions

### Prerequisites
- Python 3.11+ and pip
- wkhtmltopdf installed (optional but recommended for highest-quality PDFs)
- API keys for whichever LLM provider(s) and search services you intend to use (OpenAI, Google Gemini, Tavily, etc.)

### 1. Create a virtual environment
```cmd
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install dependencies
```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

If you skipped wkhtmltopdf, PDF export falls back to WeasyPrint but will take slightly longer.

### 3. Configure environment variables
Create a `.env` file in the project root or export variables in your shell. At minimum, set a secret key and the LLM/search credentials you plan to use.

```
FLASK_SECRET_KEY=replace-me
LLM_PROVIDER=gemini   # or openai
OPENAI_API_KEY=...
GEMINI_API_KEY=...
TAVILY_API_KEY=...
FLASK_DEBUG=true
```

### 4. Run the Flask server
```cmd
set FLASK_APP=app
set FLASK_ENV=development
flask run
```

The existing VS Code task "Run Flask Server" calls the same command via Conda if you prefer using the Tasks panel.

### 5. Interact with the UI
Open `http://127.0.0.1:5000` in a browser, start a chat in the Conversation tab, then switch to Account Plan or Research Feed as the workflow progresses.

## Architecture Notes
- **Flask entrypoint (`app.py`)** wires HTTP routes for chat, report export, PDF generation, and section regeneration while storing session state in-memory.
- **State machine (`core/state_machine.py`)** steps through planning → confirmation → research → analysis → review/editing and guards long-running phases so the UI receives deterministic progress updates.
- **Planner + search planner agents (`agents/planner_agent.py`, `agents/search_planner.py`)** clarify scope, build an approved workplan, then fan out structured search tasks for downstream tools.
- **Group 1 research (`agents/group1_research.py`)** executes mandatory data channels (web, news, finance, leadership, talent, competitors, Wikipedia) via adapters under `tools/`, merges results into a `ResearchBundle`, and logs activities for the UI feed.
- **Group 2 analysis (`agents/group2_analysis.py`)** transforms the bundle into each `PlanSection` using targeted prompts defined in `llm/prompts.py`, writing a structured `AccountPlan` object.
- **Selective updates (`agents/selective_update.py`)** regenerate individual sections on demand while bumping the plan version counter so edits stay auditable.
- **LLM abstraction (`llm/client.py`)** provides a single interface to OpenAI, Gemini, or a Dummy fallback, including structured JSON responses for planners/search routing.
- **Presentation layer (`templates/`, `static/`, `pdf/`)** renders the chat UI, shows research progress, and exports the final `AccountPlan` to HTML/PDF via pdfkit with a WeasyPrint fallback.

## Design Decisions
- **In-memory session store** keeps per-user `SessionState` simple for local demos; swap in Redis or a database if you need persistence or horizontal scaling.
- **Explicit conversation stages** minimize accidental parallel LLM calls, ensure user confirmation before spending tokens, and make progress logs deterministic for the frontend.
- **Mandatory research channels** guarantee a baseline dataset even if the LLM returns sparse or biased search tasks, improving coverage for SWOT/opportunity sections.
- **Search task normalization** caps the task list, deduplicates channels, and annotates each task with agent/source metadata so the UI can render consistent activity cards.
- **Provider-agnostic LLM client** lets you flip between OpenAI and Gemini through configuration without touching calling code, and gracefully degrades to a dummy offline model.
- **Section regeneration pipeline** reuses the same prompt path as first-pass analysis to keep tone/structure consistent while incrementing plan versions for auditability.
- **Dual PDF engines** try pdfkit/wkhtmltopdf first for pixel-accurate output, then fall back to WeasyPrint so export still works when native binaries are missing.

## Troubleshooting & Development Tips
- The `pip install newspaper` step in `requirements.txt` can fail on Windows without Visual C++ build tools; install the dependency manually if you see compile errors.
- If Tavily or Gemini keys are absent, the app automatically falls back to DuckDuckGo search and the `DummyLLM`, which is useful for UI smoke tests but not production-quality plans.
- Delete the `.flask_session` cookie or restart the server to reset conversations; `SESSION_STORE` is process-bound.
- Use `flask --app app --debug run` to enable hot reloads while editing templates or static assets.
