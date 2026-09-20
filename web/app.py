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

from fastapi import FastAPI, File, Form, Request, Response, UploadFile
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

# Instructor PIN — set INSTRUCTOR_PIN in .env for production; default is for demo only
INSTRUCTOR_PIN = os.environ.get("INSTRUCTOR_PIN", "feynman2024")

# Lectures registry — dynamic, read from data/lectures_registry.json
LECTURES_REGISTRY = ROOT / "data" / "lectures_registry.json"

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
# Lecture Metadata — dynamic, loaded from data/lectures_registry.json
# ---------------------------------------------------------------------------

def load_lectures() -> list[Dict]:
    """Load lectures from the registry JSON. Falls back to empty list on error."""
    if LECTURES_REGISTRY.exists():
        try:
            return json.loads(LECTURES_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _get_lecture(lecture_id: str) -> Optional[Dict]:
    """Look up a single lecture by id from the registry."""
    return next((l for l in load_lectures() if l["id"] == lecture_id), None)


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


def _get_instructor(request: Request) -> bool:
    """Return True if the request has a valid instructor auth cookie."""
    return request.cookies.get("instructor_auth") == "authenticated"


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
        html = html.replace("<!-- ERROR_MSG_STUDENT -->",
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
# Routes: Instructor Login
# ---------------------------------------------------------------------------

@app.get("/instructor/login", response_class=HTMLResponse)
def instructor_login_page(request: Request):
    """Redirect to root — instructor login is now on the unified login page."""
    if _get_instructor(request):
        return RedirectResponse("/instructor", status_code=303)
    return RedirectResponse("/", status_code=303)


@app.post("/instructor/login")
def instructor_login(pin: str = Form(...)):
    if pin.strip() == INSTRUCTOR_PIN:
        resp = RedirectResponse("/instructor", status_code=303)
        resp.set_cookie("instructor_auth", "authenticated", max_age=3600, httponly=True)
        return resp
    # Wrong PIN — show error on the instructor tab of the unified login page
    html = _read_template("login.html")
    html = html.replace("<!-- ERROR_MSG_INSTRUCTOR -->",
                        '<p class="error">Incorrect PIN. Please try again.</p>')
    return HTMLResponse(html)


@app.get("/instructor/logout")
def instructor_logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie("instructor_auth")
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

    # Build lecture cards from dynamic registry
    cards_html = ""
    for lec in load_lectures():
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

    # Find lecture info from dynamic registry
    lecture = _get_lecture(lecture_id)
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
            opening_q = load_opening_question(lecture_id)
            session_id = store.create_run(
                domain="feynman_chat",
                meta={
                    "student_id": student["roll"],
                    "student_name": student["name"],
                    "concept_id": lecture_id,
                    "lecture_id": lecture_id,
                    "opening_question": opening_q,
                },
            )
            store.append(session_id, "opening_question", {
                "text": opening_q,
                "lecture_id": lecture_id,
            }, produced_by="system:opening")

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
def instructor_page(request: Request):
    """Instructor view — requires instructor PIN authentication."""
    if not _get_instructor(request):
        return RedirectResponse("/instructor/login", status_code=303)
    html = _read_template("instructor.html")
    return HTMLResponse(html)


@app.get("/api/instructor")
def api_instructor(request: Request):
    """Returns JSON of scanned student sessions, clusters, and email escalation status."""
    if not _get_instructor(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
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


@app.post("/api/discover-fallacies")
async def api_discover_fallacies(request: Request):
    """
    Triggers the Fallacy Discovery Agent for a concept markdown file.
    Payload: {"concept_id": "oop_lecture_1", "force": false, "write": true}
    Requires instructor authentication.
    """
    if not _get_instructor(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    concept_id = body.get("concept_id", "").strip()
    force = bool(body.get("force", False))
    write = bool(body.get("write", True))

    if not concept_id:
        return JSONResponse({"error": "concept_id is required"}, status_code=400)

    from demo.feynman.discover import discover_fallacies

    st = load_settings()
    try:
        result = discover_fallacies(
            concept_id,
            settings=st,
            force=force,
            write=write,
            db_path=DB_PATH,
        )
        return JSONResponse({
            "concept_id": result.concept_id,
            "fallacies": [f.model_dump() for f in result.fallacies],
            "opening_question": result.opening_question,
            "status": "success",
        })
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Routes: Lectures & Ingestion
# ---------------------------------------------------------------------------

@app.get("/api/lectures")
def api_get_lectures():
    """Return the list of all registered lectures."""
    return JSONResponse(load_lectures())


@app.post("/instructor/upload-lecture")
@app.post("/api/upload-lecture")
async def upload_lecture(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    concept_id: Optional[str] = Form(None),
    run_discovery: bool = Form(True),
):
    """
    Instructor endpoint: Upload a PDF or PPTX lecture file, extract content,
    generate concept invariants, run the Fallacy Discovery Agent, and register
    the lecture so it's immediately available on student dashboard.
    """
    if not _get_instructor(request):
        return JSONResponse({"error": "Unauthorized. Instructor login required."}, status_code=401)

    title = title.strip()
    if not title:
        return JSONResponse({"error": "Lecture title is required."}, status_code=400)

    filename = file.filename or "lecture.pdf"
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".pptx", ".ppt"):
        return JSONResponse(
            {"error": f"Unsupported file type '{ext}'. Please upload a .pdf or .pptx file."},
            status_code=400,
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            return JSONResponse({"error": "Uploaded file is empty."}, status_code=400)

        import asyncio
        from web.lecture_ingest import ingest_lecture

        result = await asyncio.to_thread(
            ingest_lecture,
            file_bytes=file_bytes,
            filename=filename,
            title=title,
            description=description,
            concept_id=concept_id,
            run_discovery=run_discovery,
            db_path=DB_PATH,
        )

        return JSONResponse({
            "status": "success",
            "concept_id": result.concept_id,
            "lecture_num": result.lecture_num,
            "title": result.title,
            "description": result.description,
            "raw_text_length": result.raw_text_length,
            "fallacies_count": result.fallacies_count,
            "opening_question": result.opening_question,
            "fallacies": result.fallacies,
        })
    except ValueError as ve:
        return JSONResponse({"error": str(ve)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Failed to ingest lecture: {str(e)}"}, status_code=500)


