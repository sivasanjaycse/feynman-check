import pytest
from slice.store import Store
from slice.records import RunState
from slice.config import settings as load_settings
from slice import runner
from demo.feynman.flow import build_chat_flow
from demo.feynman.schema import CriticVerdict, ProbeMessage

def test_chat_flow_single_step_suspension(tmp_path):
    db_file = str(tmp_path / "test.db")
    store = Store(db_file)
    settings = load_settings()

    # Stub call that returns MISCONCEPTION then probe
    def stub_call(settings, budget, messages, schema, step):
        if schema == CriticVerdict:
            return CriticVerdict(
                verdict="MISCONCEPTION",
                detected_flaw_tag="CLASS_IS_AN_OBJECT",
                flaw_explanation="Student conflates class with object",
                violates_invariant=True,
                confidence=0.9,
            )
        elif schema == ProbeMessage:
            return ProbeMessage(
                probe_id="probe_1",
                counter_example_scenario="Can anyone live in a blueprint?",
                target_invariant="Class vs Object",
            )
        raise ValueError(f"Unknown schema: {schema}")

    flow = build_chat_flow(call=stub_call)

    # 1. Create run
    run_id = store.create_run("feynman_chat", meta={"student_id": "2023101001", "concept_id": "oop_lecture_1"})

    # 2. Append student message 1: "i dont know"
    store.append(run_id, "chat_message", {"text": "i dont know", "student_id": "2023101001"}, produced_by="student:web")

    # 3. Advance runner
    final_state = runner.advance(store, run_id, flow, settings, max_steps=20)

    # Must be suspended (AWAITING_EXPERT), NOT COMPLETE or FAILED
    assert final_state == RunState.AWAITING_EXPERT
    assert final_state.is_suspended is True

    # Must have EXACTLY 1 submission and 1 probe and 1 verdict - NOT 5!
    assert len(store.history(run_id, "submission")) == 1
    assert len(store.history(run_id, "probe")) == 1
    assert len(store.history(run_id, "verdict")) == 1
    assert store.history(run_id, "submission")[0].payload["text"] == "i dont know"

    # 4. If advance() is called again WITHOUT a new message:
    final_state_2 = runner.advance(store, run_id, flow, settings, max_steps=20)
    assert final_state_2 == RunState.AWAITING_EXPERT
    assert len(store.history(run_id, "submission")) == 1

    # 5. Now student sends message 2: "classes are blueprints"
    store.append(run_id, "chat_message", {"text": "classes are blueprints", "student_id": "2023101001"}, produced_by="student:web")
    store.set_state(run_id, RunState.DRAFTING)

    final_state_3 = runner.advance(store, run_id, flow, settings, max_steps=20)
    assert final_state_3 == RunState.AWAITING_EXPERT

    # Now exactly 2 submissions!
    assert len(store.history(run_id, "submission")) == 2
    assert store.history(run_id, "submission")[1].payload["text"] == "classes are blueprints"


def test_chat_flow_multi_fallacy_check(tmp_path):
    """Ensure that answering 1 question correctly does NOT immediately exit;
    it asks a follow-up to test another fallacy/invariant before certifying mastery."""
    db_file = str(tmp_path / "test2.db")
    store = Store(db_file)
    settings = load_settings()

    def stub_call(settings, budget, messages, schema, step):
        if schema == CriticVerdict:
            return CriticVerdict(
                verdict="MASTERED",
                detected_flaw_tag=None,
                flaw_explanation=None,
                violates_invariant=False,
                confidence=0.95,
            )
        elif schema == ProbeMessage:
            return ProbeMessage(
                probe_id="probe_followup",
                counter_example_scenario="Great job on classes vs objects! Now what about constructors — can you call a constructor again on an existing object?",
                target_invariant="Constructor Behavior",
            )
        raise ValueError(f"Unknown schema: {schema}")

    flow = build_chat_flow(call=stub_call)

    run_id = store.create_run("feynman_chat", meta={"student_id": "2023101001", "concept_id": "oop_lecture_1"})

    # Round 1: Student answers Question 1 correctly
    store.append(run_id, "chat_message", {"text": "A class is a blueprint and an object is an instance.", "student_id": "2023101001"}, produced_by="student:web")
    state_1 = runner.advance(store, run_id, flow, settings, max_steps=20)

    # Must NOT be COMPLETE yet! Must be suspended on a follow-up probe testing another concept
    assert state_1 == RunState.AWAITING_EXPERT
    assert len(store.history(run_id, "verdict")) == 1
    assert len(store.history(run_id, "probe")) == 1
    probe_text = store.history(run_id, "probe")[0].payload["counter_example_scenario"]
    assert "constructors" in probe_text

    # Round 2: Student answers Question 2 correctly
    store.append(run_id, "chat_message", {"text": "No, constructors cannot be invoked on existing objects.", "student_id": "2023101001"}, produced_by="student:web")
    store.set_state(run_id, RunState.DRAFTING)
    state_2 = runner.advance(store, run_id, flow, settings, max_steps=20)

    # After answering 2 questions correctly, session immediately terminates with MASTERED!
    assert state_2 == RunState.COMPLETE
    assert len(store.history(run_id, "verdict")) == 2
    session_rec = store.latest(run_id, "session_record")
    assert session_rec["final_verdict"] == "MASTERED"


def test_chat_flow_advances_after_resolving_earlier_misconception(tmp_path):
    """Models user scenario:
    Round 1: Misconception on Class vs Object
    Round 2: Ambiguous on Class vs Object
    Round 3: Mastered on Class vs Object
    Verifies that it does NOT terminate! It must advance to CONSTRUCTOR_IS_A_METHOD."""
    db_file = str(tmp_path / "test3.db")
    store = Store(db_file)
    settings = load_settings()

    verdicts_queue = [
        CriticVerdict(verdict="MISCONCEPTION", detected_flaw_tag="CLASS_IS_AN_OBJECT", violates_invariant=True),
        CriticVerdict(verdict="AMBIGUOUS", detected_flaw_tag="CLASS_IS_AN_OBJECT", violates_invariant=False),
        CriticVerdict(verdict="MASTERED", detected_flaw_tag=None, violates_invariant=False),
    ]

    def stub_call(settings, budget, messages, schema, step):
        if schema == CriticVerdict:
            return verdicts_queue.pop(0)
        elif schema == ProbeMessage:
            return ProbeMessage(
                probe_id="probe_test",
                counter_example_scenario="Next probe scenario",
                target_invariant="Test",
            )
        raise ValueError(f"Unknown schema: {schema}")

    flow = build_chat_flow(call=stub_call)
    run_id = store.create_run("feynman_chat", meta={"student_id": "2023101001", "concept_id": "oop_lecture_1"})

    # Round 1: Misconception
    store.append(run_id, "chat_message", {"text": "Class is memory object is functionality", "student_id": "2023101001"}, produced_by="student:web")
    s1 = runner.advance(store, run_id, flow, settings, max_steps=20)
    assert s1 == RunState.AWAITING_EXPERT

    # Round 2: Ambiguous
    store.append(run_id, "chat_message", {"text": "Oh. YEs, object is allocation of memory...", "student_id": "2023101001"}, produced_by="student:web")
    store.set_state(run_id, RunState.DRAFTING)
    s2 = runner.advance(store, run_id, flow, settings, max_steps=20)
    assert s2 == RunState.AWAITING_EXPERT

    # Round 3: Mastered on Fallacy 1!
    store.append(run_id, "chat_message", {"text": "new Car() is never called right.. So no object is created.", "student_id": "2023101001"}, produced_by="student:web")
    store.set_state(run_id, RunState.DRAFTING)
    s3 = runner.advance(store, run_id, flow, settings, max_steps=20)

    # CRITICAL: Must NOT be COMPLETE! It MUST advance to CONSTRUCTOR_IS_A_METHOD!
    assert s3 == RunState.AWAITING_EXPERT
    assert s3 != RunState.COMPLETE

    latest_probe = store.latest(run_id, "probe")
    assert latest_probe["target_fallacy"] == "CONSTRUCTOR_IS_A_METHOD"


def test_reset_demo_cohort_api():
    """Verify that /api/reset-demo-cohort cleanly resets Alice & Bob."""
    from fastapi.testclient import TestClient
    from web.app import app
    client = TestClient(app)

    resp = client.post("/api/reset-demo-cohort")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"

    from pathlib import Path
    students_dir = Path("data/students")
    assert (students_dir / "2023101001.json").exists()
    assert (students_dir / "2023101002.json").exists()


def test_chat_api_with_inspector_telemetry(monkeypatch):
    """Verify that /api/chat returns rich inspector cognitive telemetry."""
    monkeypatch.setenv("FEYNMAN_USE_STUB", "1")
    from fastapi.testclient import TestClient
    from web.app import app
    client = TestClient(app)

    # Set student cookie
    client.cookies.set("student_roll", "2023101001")

    resp = client.post("/api/chat", json={
        "lecture_id": "oop_lecture_1",
        "message": "A class is a blueprint and an object is a runtime instance.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "inspector" in data
    inspector = data["inspector"]
    assert "current_state" in inspector
    assert "back_edge_triggered" in inspector
    assert "confidence" in inspector
    assert "turn_count" in inspector
    assert "mastered_count" in inspector
    assert "cluster_count" in inspector


