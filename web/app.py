"""
web/app.py — Main web application for the Feynman Check demo.

Student-facing frontend: login by roll number, select a lecture to revise,
then engage in a Socratic chat that detects misconceptions.

Run:
    uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slice import runner
from slice.config import settings as load_settings
from slice.records import RunState
from slice.store import Store

from demo.feynman.flow import (
    build_chat_flow,
    load_concept_ground_truth,
    load_opening_question,
    log_student_session_state,
)
from demo.feynman.batch import (
    check_and_escalate_batch,
    scan_student_records,
    aggregate_cohort_telemetry,
)

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("FEYNMAN_DB", "demo.db")
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="Feynman Check — OOP Revision Demo")

# Mount static files
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# ---------------------------------------------------------------------------
# Demo Students (hardcoded — this is a hackathon demo)
# ---------------------------------------------------------------------------

DEMO_STUDENTS: Dict[str, str] = {
    "2023101001": "Alice",
    "2023101002": "Bob",
    "2023101003": "Charlie",
    "2023101004": "Diana",
    "2023101005": "Eve",
    "2023101006": "Frank",
}

# ---------------------------------------------------------------------------
# Lecture Metadata
# ---------------------------------------------------------------------------

LECTURES = [
    {"id": "oop_lecture_1", "num": 1, "title": "Classes & Objects", "desc": "Class vs object, constructors, the this/self reference"},
    {"id": "oop_lecture_2", "num": 2, "title": "Encapsulation & Access Modifiers", "desc": "Private, protected, public, getters/setters, information hiding"},
    {"id": "oop_lecture_3", "num": 3, "title": "Inheritance — IS-A vs HAS-A", "desc": "Inheritance, composition, Liskov Substitution, tight vs loose coupling"},
    {"id": "oop_lecture_4", "num": 4, "title": "Polymorphism", "desc": "Overloading vs overriding, dynamic dispatch, reference vs object type"},
    {"id": "oop_lecture_5", "num": 5, "title": "Abstract Classes & Interfaces", "desc": "Abstract classes, interface contracts, multiple inheritance via interfaces"},
    {"id": "oop_lecture_6", "num": 6, "title": "Exception Handling", "desc": "try-catch-finally, checked vs unchecked, throw vs throws"},
    {"id": "oop_lecture_7", "num": 7, "title": "SOLID Principles", "desc": "SRP, OCP, DIP, God class anti-pattern, favour composition"},
]


def _store() -> Store:
    return Store(DB_PATH)


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _get_student(request: Request) -> Optional[Dict[str, str]]:
    """Get current student from cookie."""
    roll = request.cookies.get("student_roll")
    if roll and roll in DEMO_STUDENTS:
        return {"roll": roll, "name": DEMO_STUDENTS[roll]}
    return None


# ---------------------------------------------------------------------------
# Routes: Login
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    student = _get_student(request)
    if student:
        return RedirectResponse("/dashboard", status_code=303)
    html = _read_template("login.html")
    return HTMLResponse(html)


@app.post("/login")
def login(roll_number: str = Form(...)):
    roll = roll_number.strip()
    if roll not in DEMO_STUDENTS:
        html = _read_template("login.html")
        html = html.replace("<!-- ERROR_MSG -->",
                           '<p class="error">Roll number not found. Try one of: ' +
                           ", ".join(DEMO_STUDENTS.keys()) + "</p>")
        return HTMLResponse(html)

    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("student_roll", roll, max_age=86400)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("student_roll")
    return resp


# ---------------------------------------------------------------------------
# Routes: Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    student = _get_student(request)
    if not student:
        return RedirectResponse("/", status_code=303)

    html = _read_template("dashboard.html")
    html = html.replace("{{STUDENT_NAME}}", student["name"])
    html = html.replace("{{STUDENT_ROLL}}", student["roll"])

    # Build lecture cards
    cards_html = ""
    for lec in LECTURES:
        cards_html += f"""
        <a href="/chat/{lec['id']}" class="lecture-card" id="card-{lec['id']}">
            <div class="lecture-num">Lecture {lec['num']}</div>
            <div class="lecture-title">{lec['title']}</div>
            <div class="lecture-desc">{lec['desc']}</div>
            <div class="lecture-action">Start Revision →</div>
        </a>
        """
    html = html.replace("{{LECTURE_CARDS}}", cards_html)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Routes: Chat
# ---------------------------------------------------------------------------

@app.get("/chat/{lecture_id}", response_class=HTMLResponse)
def chat_page(lecture_id: str, request: Request):
    student = _get_student(request)
    if not student:
        return RedirectResponse("/", status_code=303)

    # Find lecture info
    lecture = next((l for l in LECTURES if l["id"] == lecture_id), None)
    if not lecture:
        return RedirectResponse("/dashboard", status_code=303)

    # Load opening question from the concept file (zero LLM calls)
    opening_q = load_opening_question(lecture_id)

    html = _read_template("chat.html")
    html = html.replace("{{STUDENT_NAME}}", student["name"])
    html = html.replace("{{STUDENT_ROLL}}", student["roll"])
    html = html.replace("{{LECTURE_ID}}", lecture_id)
    html = html.replace("{{LECTURE_TITLE}}", lecture["title"])
    html = html.replace("{{LECTURE_NUM}}", str(lecture["num"]))
    html = html.replace("{{OPENING_QUESTION}}", opening_q)

    return HTMLResponse(html)


@app.post("/api/chat")
async def chat_api(request: Request):
    """
    AJAX endpoint for the Socratic chat.

    Receives: {lecture_id, message, session_id (optional)}
    Returns: {response, session_id, status, report (if complete)}
    """
    student = _get_student(request)
    if not student:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    body = await request.json()
    lecture_id = body.get("lecture_id", "")
    message = body.get("message", "").strip()
    session_id = body.get("session_id")

    if not message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    st = load_settings()
    store = _store()
    flow = build_chat_flow()

    try:
        if not session_id:
            # --- First message: create a new run ---
            session_id = store.create_run(
                domain="feynman_chat",
                meta={
                    "student_id": student["roll"],
                    "student_name": student["name"],
                    "concept_id": lecture_id,
                    "lecture_id": lecture_id,
                },
            )

        # Append the student's message to the store
        store.append(session_id, "chat_message", {
            "text": message,
            "student_id": student["roll"],
        }, produced_by="student:web")

        # If the run was suspended waiting for student response, resume it to DRAFTING
        if store.get_state(session_id) == RunState.AWAITING_EXPERT:
            store.set_state(session_id, RunState.DRAFTING)

        # Run the state machine
        final_state = runner.advance(store, session_id, flow, st, max_steps=20)

        # Read what the model produced
        latest_probe = store.latest(session_id, "probe")
        latest_verdict = store.latest(session_id, "verdict")

        if final_state == RunState.COMPLETE:
            # Chat is done — build report
            report = _build_session_report(store, session_id)
            # Check for batch escalation (triggers send_email if threshold met)
            try:
                check_and_escalate_batch()
            except Exception:
                pass

            if latest_verdict and latest_verdict.get("verdict") == "MASTERED":
                return JSONResponse({
                    "response": "🎉 Great job! You've demonstrated a solid understanding of this concept. Your explanation correctly captures the core invariant!",
                    "session_id": session_id,
                    "status": "mastered",
                    "report": report,
                })
            else:
                return JSONResponse({
                    "response": "We've reached the end of this revision session. Check the report below to see what areas need more review.",
                    "session_id": session_id,
                    "status": "unresolved",
                    "report": report,
                })

        elif final_state == RunState.FAILED:
            failure = store.latest(session_id, "failure")
            return JSONResponse({
                "response": f"Something went wrong: {failure.get('detail', 'Unknown error') if failure else 'Unknown error'}",
                "session_id": session_id,
                "status": "error",
            })

        else:
            # Still in progress — return the probe question
            if latest_probe:
                probe_text = latest_probe.get("counter_example_scenario", "")
                return JSONResponse({
                    "response": probe_text,
                    "session_id": session_id,
                    "status": "probing",
                    "verdict_info": {
                        "verdict": latest_verdict.get("verdict", "") if latest_verdict else "",
                        "flaw_tag": latest_verdict.get("detected_flaw_tag", "") if latest_verdict else "",
                    },
                })
            else:
                return JSONResponse({
                    "response": "Hmm, I need a bit more to work with. Could you elaborate on your understanding?",
                    "session_id": session_id,
                    "status": "probing",
                })

    except Exception as e:
        return JSONResponse({
            "error": str(e),
            "session_id": session_id,
            "status": "error",
        }, status_code=500)
    finally:
        store.close()


def _build_session_report(store: Store, session_id: str) -> Dict[str, Any]:
    """Build a structured report from the completed session."""
    verdicts = store.history(session_id, "verdict")
    probes = store.history(session_id, "probe")
    submissions = store.history(session_id, "submission")
    session_record = store.latest(session_id, "session_record")

    rounds = []
    for i, v in enumerate(verdicts):
        round_info: Dict[str, Any] = {
            "round": i + 1,
            "verdict": v.payload.get("verdict", ""),
            "flaw_tag": v.payload.get("detected_flaw_tag"),
            "flaw_explanation": v.payload.get("flaw_explanation"),
            "confidence": v.payload.get("confidence", 0),
        }
        # Student text for this round
        if i < len(submissions):
            round_info["student_text"] = submissions[i].payload.get("text", "")
        # Probe issued for this round
        if i < len(probes):
            round_info["probe_issued"] = probes[i].payload.get("counter_example_scenario", "")

        rounds.append(round_info)

    final_verdict = session_record.get("final_verdict", "UNKNOWN") if session_record else "UNKNOWN"
    tagged_fallacy = session_record.get("tagged_fallacy") if session_record else None

    return {
        "final_verdict": final_verdict,
        "tagged_fallacy": tagged_fallacy,
        "total_rounds": len(verdicts),
        "rounds": rounds,
    }


# ---------------------------------------------------------------------------
# Routes: Report API
# ---------------------------------------------------------------------------

@app.get("/api/report/{session_id}")
def report_api(session_id: str, request: Request):
    student = _get_student(request)
    if not student:
        return JSONResponse({"error": "Not logged in"}, status_code=401)

    store = _store()
    try:
        report = _build_session_report(store, session_id)
        return JSONResponse(report)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Routes: Instructor Dashboard & Telemetry Monitor
# ---------------------------------------------------------------------------

@app.get("/instructor", response_class=HTMLResponse)
def instructor_page():
    """Instructor view showing live cohort misconception clusters and email triggers."""
    html = _read_template("instructor.html")
    return HTMLResponse(html)


@app.get("/api/instructor")
def api_instructor():
    """Returns JSON of scanned student sessions, clusters, and email escalation status."""
    import glob
    students_dir = Path("data/students")
    students = []
    if students_dir.exists():
        for f in sorted(students_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                students.append(data)
            except Exception:
                pass

    # Read batch telemetry
    telemetry_file = Path("data/batch_telemetry.json")
    clusters = {}
    total_scanned = len(students)
    if telemetry_file.exists():
        try:
            t_data = json.loads(telemetry_file.read_text(encoding="utf-8"))
            clusters = t_data.get("clusters", {})
        except Exception:
            pass

    # Count reports in reports/
    reports_dir = Path("reports")
    alerts_count = len(list(reports_dir.glob("*.md"))) if reports_dir.exists() else 0

    return JSONResponse({
        "total_students": total_scanned,
        "cluster_count": len(clusters),
        "clusters": clusters,
        "students": students,
        "alerts_count": alerts_count,
        "threshold": 3,
    })

