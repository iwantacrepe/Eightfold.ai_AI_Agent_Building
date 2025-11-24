# Account Plan Research Assistant

> **One chat-driven orchestrator that clarifies a sales brief, runs multi-channel research, drafts an enterprise account plan, lets you regenerate any section, exports everything to PDF, and even accepts microphone audio as chat input.**

This document explains the project in depth: backend stack, agent design, state transitions, search adapters, UI behavior, PDF/export flow, and the technical decisions that keep the experience coherent.

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [End-to-End Workflow](#end-to-end-workflow)
4. [Backend Architecture](#backend-architecture)
5. [Conversation State Machine](#conversation-state-machine)
6. [Agent Lineup & Responsibilities](#agent-lineup--responsibilities)
7. [Research & Tooling Layer](#research--tooling-layer)
8. [LLM Strategy & Prompting](#llm-strategy--prompting)
9. [Frontend Experience](#frontend-experience)
10. [API Surface](#api-surface)
11. [Audio Capture & Gemini Integration](#audio-capture--gemini-integration)
12. [PDF / Markdown Export Pipeline](#pdf--markdown-export-pipeline)
13. [Data Models](#data-models)
14. [Setup & Local Development](#setup--local-development)
15. [Configuration Matrix](#configuration-matrix)
16. [Troubleshooting](#troubleshooting)
17. [Extending the System](#extending-the-system)

---

## System Overview

The assistant combines a Flask backend, a vanilla JS frontend, and a set of LLM-driven agents. The UX mirrors a sales strategist: gather the brief, confirm a workplan, run targeted research across the web, synthesize insights into a structured account plan, and let users regenerate specific sections. The UI keeps the chat and plan in sync, shows what each agent is doing, and can export the final plan as HTML/PDF.

Key characteristics:
- **Multi-agent orchestration:** Distinct agents own planning, research, analysis, and selective updates.
- **Structured prompts:** Every agent uses a dedicated prompt (see `llm/prompts.py`) to keep outputs predictable.
- **Tool transparency:** Every fetch/search is logged to the Research Feed and Agent Console so users trust the output.
- **Live editing:** Regenerate buttons open a modal where users describe refinements; edits flow back into the account plan without restarting the entire workflow.
- **Audio-enabled chat:** Users can send recorded mic input; the backend transcribes audio via Google Gemini (inline for small files, Files API for larger blobs) and feeds the transcript into the state machine.

---

## Technology Stack

| Layer | Technology | Rationale |
| --- | --- | --- |
| Web server | Flask 3 + Werkzeug | Simple routing, easy session handling, minimal overhead. |
| Frontend | HTML (Jinja templates), vanilla JS (`static/app.js`), CSS (`static/styles.css`) | Keeps bundle lightweight, no build tooling required. |
| State & models | Python dataclasses (`core/models.py`) | Serializes cleanly, easy to mutate across agents. |
| LLM integration | LangChain wrappers for OpenAI + Google Gemini, plus native `google.genai` client | Provides streaming + JSON responses while supporting the latest Gemini audio APIs. |
| Research tooling | Custom adapters under `tools/` (DuckDuckGo, RSS, Yahoo Finance, etc.) | Keeps each channel isolated and testable. |
| PDF export | pdfkit/wkhtmltopdf primary, WeasyPrint fallback (`pdf/generator.py`) | Produces pixel-accurate PDFs without shipping binaries. |
| Audio capture | MediaRecorder API + `/api/chat-audio` endpoint | Enables voice-first workflows. |
| Styling/UI | Modern CSS (Inter font, gradients, sticky tab controls) | Mirrors premium SaaS aesthetics while remaining pure CSS. |

---

## End-to-End Workflow

1. **Clarification chat** – User describes their need; the Clarification agent only asks for missing items (company, region, persona, product, voice, depth). Once complete, it signals readiness.
2. **Workplan drafting** – Planner agent generates a Markdown workplan summarizing phases. User confirms (or requests tweaks). Confirmation flips the state machine into execution mode.
3. **Search task generation** – Search Router agent reads the workplan and emits 6–12 concrete search tasks, ensuring coverage across web/news/finance/leadership/talent/competitors.
4. **Research sweep (Group 1)** – Channel-specific collectors (DuckDuckGo, RSS, Yahoo Finance, etc.) run in sequence, populating a `ResearchBundle` and streaming progress logs + research cards to the UI.
5. **Analysis & plan drafting (Group 2)** – For each `PlanSection` (overview, industry, SWOT, etc.), the system feeds the bundle and a tailored prompt to the Analysis agent, producing an `AccountPlan` dataclass.
6. **Review mode** – UI switches to the Account Plan tab; user can download, request another section, or refine. Regeneration requests reuse the same prompts with the user’s guidance.
7. **Export** – Using the PDF button, the server renders the plan to HTML and prints to PDF via pdfkit (wkhtmltopdf) or WeasyPrint fallback.

Audio input, progress overlays, and the Research Feed run concurrently so the user always knows which agent is working.

---

## Backend Architecture

### Flask Entrypoint (`app.py`)
- Registers routes for chat (`/api/chat`), audio chat (`/api/chat-audio`), progress polling, section regeneration, PDF export, and report fetching.
- Stores per-session state in memory via `SESSION_STORE` (dict of `SessionState`). The `flask_session` cookie holds a UUID key.
- `_build_chat_response()` packages replies with stage info, progress logs, agent activity, and `has_account_plan` booleans for the UI.

### Session Management
- `SessionState` tracks: `chat_history`, `stage`, `workplan`, `search_tasks`, `research_activity`, `research_bundle`, `account_plan`, `plan_version`, etc.
- `core/state_machine.handle_user_message()` mutates the session while routing the message to the correct agent flow.
- Stages guard heavy work (research + analysis) so the backend never triggers duplicate runs.

### Threading & Long Tasks
- Research and analysis are executed synchronously per request to keep the implementation deterministic. In production, these could move to task queues.

---

## Conversation State Machine

States (see `core/models.ConversationStage`):
1. `PLANNING` – Clarification agent gathers scope.
2. `CONFIRMING_PLAN` – Planner shares the workplan; user must confirm/adjust.
3. `RESEARCHING` – Search tasks fan out; Research Feed streams updates.
4. `ANALYZING` – Strategy agents synthesize sections, then mark plan ready.
5. `REVIEWING` – User reads plan, regenerates sections, or exports.
6. `EDITING` – Temporary state while a selective update runs.

State transitions trigger UI cues (tabs, overlays, status banners) via payload fields.

---

## Agent Lineup & Responsibilities

| Agent | File | Purpose | Key Prompt |
| --- | --- | --- | --- |
| Clarification Strategist | `agents/planner_agent.py` (clarification branch) | Collect missing scope inputs adaptively. | `CLARIFICATION_SYSTEM_PROMPT` |
| Workplan Architect | `agents/planner_agent.py` (plan branch) | Converts finalized scope into a Markdown workplan with phases. | `WORKPLAN_SYSTEM_PROMPT` |
| Search Router | `agents/search_planner.py` | Breaks workplan into concrete search tasks with channel metadata. | `SEARCH_ROUTER_SYSTEM_PROMPT` |
| Group 1 Research Agents | `agents/group1_research.py` | Run queries per channel, store normalized results, log activities. | Hard-coded logic blending LLM + tools |
| Group 2 Analysis Agents | `agents/group2_analysis.py` | Draft each plan section using research bundle + targeted prompts. | `SECTION_PROMPTS[...]` |
| Selective Update Agent | `agents/selective_update.py` | Reruns prompts for a single section using user guidance. | Same section prompt + regen instructions |

Each agent writes structured output (dicts/dataclasses) so downstream logic never parses raw text.

---

## Research & Tooling Layer

All tooling lives in `tools/`:

| Module | Data Source | Notes |
| --- | --- | --- |
| `duckduckgo_search.py` | DuckDuckGo + Tavily (if configured) | General web results with snippets and URLs. |
| `community_watch.py` | Reddit/Hacker News (via APIs) | Detects community sentiment or product chatter. |
| `news_search.py` / `rss_news.py` | Google News / RSS feeds | Time-bounded breaking news. |
| `social_listening.py` | Twitter/X placeholder or LinkedIn scrape | Hooks ready for paid APIs. |
| `wiki_fetch.py` | Wikipedia summary | Quick baseline context. |
| `yahoo_finance.py` | Yahoo Finance | Pulls revenue, valuation, key ratios. |

Each tool returns normalized dicts so `group1_research` can aggregate them into `ResearchBundle` objects. The bundle includes raw hits + derived metadata used later by analysis prompts.

---

## LLM Strategy & Prompting

### Client Abstraction (`llm/client.py`)
- **Providers:** Supports OpenAI (ChatGPT), Google Gemini, or a Dummy fallback for offline dev.
- **Configuration:** `LLM_PROVIDER`, `OPENAI_API_KEY`, `GEMINI_API_KEY` env variables, plus optional `temperature` and model names.
- **Structured outputs:** For JSON-heavy tasks (clarification, search router) the client requests JSON or `response_mime_type="application/json"` (Gemini) so parsing is reliable.
- **Audio transcription:** Uses the latest `google.genai` SDK. Small blobs go inline via `types.Part.from_bytes`. Larger blobs auto-save to a temp file, upload through Gemini Files API, and then call `models.generate_content`. This matches Google’s guidance (under 20 MB inline; otherwise always upload).

### Prompt Design (`llm/prompts.py`)
- Clarification prompt is intentionally adaptive: it keeps the tone warm, infers context, and stops once the scope is complete.
- Workplan prompt outputs Markdown phases with Inputs/Actions/Outputs, always ending with a confirmation question.
- Section prompts each highlight different research angles (financials, leadership, SWOT, etc.) while referencing the shared bundle.

---

## Frontend Experience

### Templates & Layout
- `templates/base.html` loads Inter fonts, JS, and CSS.
- `templates/index.html` defines the shell: tab controls (Conversation / Research Feed / Account Plan), hero message, agent console, plan actions, regen modal, and progress overlay.

### Static Assets
- `static/styles.css` implements the modern SaaS aesthetic (radial gradients, glassmorphism, sticky agent console, blue regen buttons, red recording state for mic).
- `static/app.js` handles chat submission, tab switching, plan rendering, research feed updates, regen modal orchestration, microphone recording, and fetch abstractions.

### UX Highlights
- **Mic button:** Blue idle state; red pulsing while recording. Uses MediaRecorder, toggles `aria-pressed`, and sends the blob to `/api/chat-audio`.
- **Research Feed:** Every research task renders as a card with agent name, objective, channel badge, and bullet results. Empty states and spinners are included.
- **Plan view:** Each section has a top-right Regenerate button. Clicking opens the blue modal asking “How should I improve this part of the account plan?”. When regenerating, the section dims and displays “Refreshing…”.
- **Progress overlay:** During Researching/Analyzing stages the chat area blurs and an overlay lists in-flight tasks.
- **PDF/Markdown:** Download buttons call `/api/export-pdf` and the plan HTML rendering, respectively.

---

## API Surface

| Endpoint | Method | Purpose | Important Payload Fields |
| --- | --- | --- | --- |
| `/` | GET | Serve main UI | Creates/loads session. |
| `/api/chat` | POST | Primary text chat | `{ message }` → returns reply, stage, progress, plan flag. |
| `/api/chat-audio` | POST | Voice input | `FormData` with `audio` + `mime_type`. Transcribes then feeds transcript through state machine. |
| `/api/report` | GET | Current plan & sources | Returns `sections`, `company_name`, `scope`, `version`, `sources`. |
| `/api/progress` | GET | Polling for stage/progress | UI uses it to refresh research feed/status banner. |
| `/api/regenerate-section` | POST | Selective update | `{ section, instruction }`. Regeneration increments plan version. |
| `/api/export-pdf` | GET | Export PDF | Streams binary PDF; uses wkhtmltopdf when available. |

All responses include error handling with descriptive messages so the frontend can surface issues.

---

## Audio Capture & Gemini Integration

1. **Frontend recording:** `static/app.js` requests mic permission, records via `MediaRecorder`, and builds a Blob using the best supported mime type (prefers `audio/webm;codecs=opus`).
2. **Upload:** Blob + mime type posted to `/api/chat-audio` as `FormData`.
3. **Backend transcription:** `llm_client.transcribe_audio()` chooses inline vs Files API depending on byte size (threshold 18 MB to stay below Gemini’s 20 MB limit). Temp files are auto-deleted.
4. **Result handling:** Transcript feeds back into `handle_user_message`, and the assistant reply flows just like typed input. The UI keeps a placeholder “Voice note (transcribing…)” message until the final transcript lands.

---

## PDF / Markdown Export Pipeline

The Account Plan tab is rendered as HTML using Markdown output from the analysis agent. Export steps:
1. `pdf/generator.py` receives the `AccountPlan` dataclass.
2. HTML template assembled with all sections + metadata.
3. Try `pdfkit.from_string()` (requires wkhtmltopdf). If it raises, fall back to WeasyPrint.
4. `/api/export-pdf` streams the PDF with `Content-Disposition: attachment`.
5. The UI’s Download button simply opens the endpoint in a new tab.

Because sections already render as Markdown in the browser, “copy markdown” functionality is trivial—users can copy straight from the DOM.

---

## Data Models

Defined in `core/models.py`:
- `PlanSection` enum – names of every section (overview, industry, etc.).
- `ConversationStage` enum – planning, confirming, researching, analyzing, reviewing, editing.
- `AccountPlan` dataclass – `company_name`, `scope`, each section string, `version`.
- `ResearchBundle` – normalized hits per channel, metadata for prompts.
- `SessionState` – overarching container for chat history, stage, tasks, bundle, plan, plan version, research feed.

These models are JSON-serializable so we can send them to the frontend or persist later.

---

## Setup & Local Development

### Prerequisites
- Python 3.11+
- pip
- Optional: wkhtmltopdf binary (for best PDF quality)

### 1. Create & activate a venv
```cmd
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install dependencies
```cmd
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment
Create `.env` or export variables:
```
FLASK_SECRET_KEY=replace-me
LLM_PROVIDER=gemini
OPENAI_API_KEY=...
GEMINI_API_KEY=...
TAVILY_API_KEY=...
FLASK_DEBUG=true
```

### 4. Run the server
```cmd
set FLASK_APP=app
set FLASK_ENV=development
flask run
```

Or use the VS Code task **Run Flask Server** (invokes Conda command configured in `.vscode/tasks.json`).

### 5. Open the UI
Visit `http://127.0.0.1:5000`, interact with the Conversation tab, and monitor Research Feed / Account Plan as the state machine progresses.

---

## Configuration Matrix

| Variable | Description | Default |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | Session signing key | required |
| `LLM_PROVIDER` | `gemini` or `openai` | `gemini` |
| `OPENAI_API_KEY` | OpenAI credential | optional |
| `GEMINI_API_KEY` | Google Gemini credential | optional but required for audio |
| `TAVILY_API_KEY` | Access to Tavily search | optional |
| `PDF_ENGINE` | Force `wkhtmltopdf` or `weasyprint` | auto-detect |
| `GOOGLE_APPLICATION_CREDENTIALS` | If using GCP libraries | optional |

Setting `LLM_PROVIDER=dummy` (or leaving API keys unset) activates the `DummyLLM`, useful for UI testing without spending tokens.

---

## Troubleshooting

- **`wkhtmltopdf` missing:** Install the binary or let the app fall back to WeasyPrint (slower). Logs indicate which engine was used.
- **`newspaper` build errors (Windows):** Install Microsoft C++ Build Tools and retry `pip install -r requirements.txt`.
- **Audio permission denied:** Browser will notify; the UI posts “Microphone permission is required…” and leaves mic disabled.
- **LLM/API keys absent:** The backend prints a warning and falls back to DummyLLM + DuckDuckGo, which is fine for demos but not production.
- **Session reset:** Delete `.flask_session` cookie or restart Flask to clear in-memory `SESSION_STORE`.

---
