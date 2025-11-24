"""Flask entry point for the multi-agent account plan assistant."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_file, session as flask_session

from agents.selective_update import regenerate_section
from config import Settings, get_settings
from core.models import ConversationStage, PlanSection, SessionState
from core.progress import get_progress_log
from core.state_machine import handle_user_message
from llm.client import LLMClient
from pdf.generator import generate_pdf_from_account_plan

settings: Settings = get_settings()
app = Flask(__name__)
app.secret_key = settings.secret_key

llm_client = LLMClient(provider=settings.llm_provider)
SESSION_STORE: dict[str, SessionState] = {}


def _get_or_create_session() -> SessionState:
    session_id = flask_session.get("session_id")
    if not session_id or session_id not in SESSION_STORE:
        session_id = str(uuid4())
        flask_session["session_id"] = session_id
        SESSION_STORE[session_id] = SessionState(session_id=session_id)
    return SESSION_STORE[session_id]


def _build_chat_response(session_state: SessionState, reply: str, extra: dict | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "reply": reply,
        "stage": session_state.stage.value,
        "progress_log": get_progress_log(session_state),
        "has_account_plan": session_state.account_plan is not None,
        "research_activity": session_state.research_activity,
    }
    if extra:
        payload.update(extra)
    return payload


@app.route("/")
def index() -> str:
    _get_or_create_session()
    return render_template("index.html")


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(force=True)
    message = payload.get("message", "").strip()
    if not message:
        return jsonify({"reply": "Please enter a message."}), 400

    session_state = _get_or_create_session()
    session_state, reply = handle_user_message(session_state, llm_client, message)
    return jsonify(_build_chat_response(session_state, reply))


@app.post("/api/chat-audio")
def api_chat_audio():
    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "Audio file missing."}), 400

    audio_bytes = audio_file.read()
    mime_type = request.form.get("mime_type") or audio_file.mimetype or "audio/webm"
    if not audio_bytes:
        return jsonify({"error": "Empty audio payload."}), 400

    transcript = llm_client.transcribe_audio(audio_bytes, mime_type)
    if not transcript:
        return jsonify({"error": "Unable to transcribe audio."}), 400

    session_state = _get_or_create_session()
    session_state, reply = handle_user_message(session_state, llm_client, transcript)
    extra = {"transcript": transcript}
    return jsonify(_build_chat_response(session_state, reply, extra))


@app.get("/api/report")
def api_report():
    session_state = _get_or_create_session()
    plan = session_state.account_plan
    bundle = session_state.research_bundle
    if not plan:
        return jsonify({"sections": {}, "sources": []})

    sections = {section.value: getattr(plan, section.value) for section in PlanSection}
    return jsonify(
        {
            "company_name": plan.company_name,
            "scope": plan.scope,
            "sections": sections,
            "version": plan.version,
            "sources": bundle.sources if bundle else [],
        }
    )


@app.post("/api/regenerate-section")
def api_regenerate_section():
    payload = request.get_json(force=True)
    section_key = payload.get("section")
    instruction = payload.get("instruction")
    if not section_key:
        return jsonify({"error": "Section is required."}), 400

    try:
        section = PlanSection(section_key)
    except ValueError:
        return jsonify({"error": f"Unknown section: {section_key}"}), 400

    session_state = _get_or_create_session()
    if not session_state.account_plan or not session_state.research_bundle:
        return jsonify({"error": "No plan available to regenerate."}), 400

    regenerate_section(llm_client, session_state, section, instruction)
    plan = session_state.account_plan
    version = plan.version if plan else 1
    return jsonify({"section": section.value, "version": version})


@app.get("/api/progress")
def api_progress():
    session_state = _get_or_create_session()
    return jsonify(
        {
            "stage": session_state.stage.value,
            "progress_log": get_progress_log(session_state),
            "research_activity": session_state.research_activity,
        }
    )


@app.get("/api/export-pdf")
def api_export_pdf():
    session_state = _get_or_create_session()
    if not session_state.account_plan:
        return jsonify({"error": "No account plan available"}), 400

    pdf_bytes = generate_pdf_from_account_plan(session_state.account_plan)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{session_state.account_plan.company_name}_account_plan.pdf",
    )


if __name__ == "__main__":
    app.run(debug=settings.debug)
