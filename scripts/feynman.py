#!/usr/bin/env python3
"""
scripts/feynman.py - Interactive CLI Runner & Test Harness for Socratic Feynman Check.

Usage:
    # 1. Test offline with canned responses (zero tokens, no API key required):
    python scripts/feynman.py run --stub

    # 2. Test live with OpenRouter LLM (enter your own explanation interactively):
    python scripts/feynman.py run --concept=virtual_memory

    # 3. Test another topic (proving topic-agnostic design):
    python scripts/feynman.py run --concept=deadlocks

    # 4. Simulate the cohort (Dilshan, Siva, Bakia) to trigger batch telemetry:
    python scripts/feynman.py simulate-cohort

    # 5. Replay an entire session's audit trail:
    python scripts/feynman.py replay <run_id>
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from slice import runner
from slice.config import settings as load_settings
from slice.records import RunState
from slice.store import Store

from demo.feynman.flow import (
    AWAIT_EXPLANATION,
    CRITIC_EVALUATE,
    SOCRATIC_PROBE,
    COMPLETE,
    FAILED,
    build_flow,
    load_concept_ground_truth,
)
from demo.feynman.stub import CANNED_STUDENTS, StubCompleter, stub_complete

# Terminal ANSI formatting
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
RED = "\033[31m"
AMBER = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"


def _c(s: str, colour: str) -> str:
    return f"{colour}{s}{RESET}" if sys.stdout.isatty() else str(s)


def cmd_run(args: argparse.Namespace) -> int:
    st = load_settings()
    store = Store(args.db)

    # ------------------------------------------------------------- Setup Mode & Caller
    if args.stub:
        mode_label = "STUB (Offline / Canned)"
        call = StubCompleter()
    else:
        if not st.api_key:
            print(_c("Error: No OPENROUTER_API_KEY found in .env.", RED))
            print("Run with --stub to test without an API key, or add your key to .env.")
            return 1
        from slice.llm import complete as call
        mode_label = f"LIVE ({st.model})"

    concept_id = args.concept
    student_id = args.student_id

    print(f"\n{_c('=== Socratic Feynman Check ===', BOLD)}")
    print(f"{_c('Mode:', DIM)} {mode_label}")
    print(f"{_c('Concept:', DIM)} {BOLD}{concept_id}{RESET}   {_c('Student ID:', DIM)} {student_id}")

    # Display ground truth preview
    ground_truth = load_concept_ground_truth(concept_id)
    first_few_lines = "\n".join(ground_truth.strip().splitlines()[:6])
    print(f"\n{_c('Target Invariants Preview:', CYAN)}\n{_c(first_few_lines, DIM)}\n...")

    # ------------------------------------------------------------- Acquire Initial Explanation
    initial_text = args.text
    if not initial_text:
        if args.stub:
            # Pick Dilshan by default in stub mode
            canned = CANNED_STUDENTS.get(args.canned, CANNED_STUDENTS["dilshan"])
            initial_text = canned["initial_text"]
            print(f"\n{_c('[Stub Input for ' + args.canned + ']:', AMBER)}")
            print(f"\"{initial_text}\"")
        else:
            print(f"\n{_c('Explain this concept in your own words (with a concrete example):', BOLD)}")
            try:
                initial_text = input(_c("> ", CYAN)).strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                return 0

    if not initial_text:
        print(_c("No explanation provided. Exiting.", RED))
        return 1

    meta = {
        "student_id": student_id,
        "concept_id": concept_id,
        "student_name": args.canned if args.stub else student_id,
        "text": initial_text,
        "interactive": True if (not args.stub and args.text is None) else False,
    }
    run_id = store.create_run("feynman", meta=meta)
    store.append(
        run_id,
        "input",
        {"student_id": student_id, "concept_id": concept_id, "text": initial_text},
        produced_by="user:cli"
    )

    flow = build_flow(call=call)

    # ------------------------------------------------------------- Execute Run
    print(f"\n{_c('Evaluating submission with Socratic agent...', DIM)}")

    state = runner.advance(store, run_id, flow, st, max_steps=20)

    # Display dialogue history in order
    verdicts = store.history(run_id, "verdict")
    probes = store.history(run_id, "probe")
    submissions = store.history(run_id, "submission")

    if verdicts:
        first_v = verdicts[0].payload
        v_type = first_v.get("verdict")
        v_color = GREEN if v_type == "MASTERED" else RED if v_type == "MISCONCEPTION" else AMBER
        flaw = f" ({first_v.get('detected_flaw_tag')})" if first_v.get('detected_flaw_tag') else ""
        print(f"\n  {_c('Critic Verdict (Initial):', BOLD)} {_c(v_type + flaw, v_color)}")
        if first_v.get("flaw_explanation"):
            print(f"  {_c('Diagnosis:', DIM)} {first_v['flaw_explanation']}")

    if probes:
        latest_p = probes[0].payload
        print(f"\n{_c('+--- Socratic Counter-Probe -------------------------------------------+', MAGENTA)}")
        for line in textwrap.wrap(latest_p.get("counter_example_scenario", ""), width=76):
            print(f"{_c('|', MAGENTA)} {line}")
        print(f"{_c('+---------------------------------------------------------------------+', MAGENTA)}")

    if len(submissions) > 1:
        print(f"\n  {_c('[Student Revision Submitted]:', CYAN)}")
        print(f"  \"{submissions[1].payload.get('text')}\"")

    if len(verdicts) > 1:
        second_v = verdicts[1].payload
        v_type2 = second_v.get("verdict")
        v_color2 = GREEN if v_type2 == "MASTERED" else RED if v_type2 == "MISCONCEPTION" else AMBER
        flaw2 = f" ({second_v.get('detected_flaw_tag')})" if second_v.get('detected_flaw_tag') else ""
        print(f"\n  {_c('Critic Verdict (After Revision):', BOLD)} {_c(v_type2 + flaw2, v_color2)}")
        if second_v.get("flaw_explanation"):
            print(f"  {_c('Diagnosis:', DIM)} {second_v['flaw_explanation']}")

    if state is RunState.FAILED:
        failures = store.history(run_id, "failure")
        detail = failures[-1].payload if failures else "Unknown error"
        print(f"\n{_c('Run Terminated:', RED)} {detail}")


    # ------------------------------------------------------------- Summary
    tokens = store.counter(run_id, "tokens")
    session_records = store.history(run_id, "session_record")
    final_verdict = session_records[-1].payload.get("final_verdict") if session_records else state.value

    is_ok = final_verdict == "MASTERED"
    outcome_color = GREEN if is_ok else RED
    print(f"\n{_c('=== Session Outcome ===', BOLD)}")
    print(f"Final State: {_c(str(final_verdict).upper(), outcome_color)} | Total Tokens: {int(tokens):,}")

    probes_issued = len(store.history(run_id, "probe"))
    if probes_issued > 0:
        print(f"{_c('Agentic Back-Edge Proven:', GREEN)} Resolved across {probes_issued} counter-probe iteration(s).")
    else:
        print(f"{_c('Mastered on first attempt.', GREEN)} No back-edge was required.")

    print(f"\nReplay full audit trail with: {_c(f'python scripts/feynman.py replay {run_id}', CYAN)}\n")
    return 0 if is_ok else 1


def cmd_replay(args: argparse.Namespace) -> int:
    store = Store(args.db)
    records = store.replay(args.run_id)
    if not records:
        print(_c(f"No run found with ID: {args.run_id}", RED))
        return 1

    print(f"\n{_c('=== Audit Replay for Run:', BOLD)} {args.run_id} ===")
    for v in records:
        header = f"#{v.seq} [{v.kind.upper()}] from {v.produced_by} (+{v.age_seconds:.2f}s)"
        print(f"\n{_c(header, CYAN)}")
        body = json.dumps(v.payload, indent=2)
        for line in body.splitlines():
            print(f"    {line}")
    print()
    return 0


def cmd_simulate_cohort(args: argparse.Namespace) -> int:
    """Simulates 3 cohort members (Dilshan, Siva, Bakia) demonstrating batch accumulation."""
    print(f"\n{_c('=== Simulating Cohort Submissions (Dilshan, Siva, Bakia) ===', BOLD)}")
    store = Store(args.db)
    st = load_settings()

    students = ["dilshan", "siva", "bakia"]
    for name in students:
        canned = CANNED_STUDENTS[name]
        sid = canned["student_id"]
        print(f"\n---> Ingesting student: {_c(name.upper(), BOLD)} ({sid})")

        run_id = store.create_run("feynman", meta={"student_id": sid, "student_name": name})
        store.append(
            run_id,
            "input",
            {"student_id": sid, "concept_id": "virtual_memory", "text": canned["initial_text"]},
            produced_by="test",
        )

        flow = build_flow(call=StubCompleter())
        state = runner.advance(store, run_id, flow, st)

        session_rec = store.history(run_id, "session_record")[-1].payload
        print(f"     Status: {_c(session_rec['final_verdict'], GREEN)} | Flaw: {_c(str(session_rec['tagged_fallacy']), AMBER)}")

    # Check student JSON files
    students_dir = Path("data/students")
    json_files = list(students_dir.glob("*.json"))
    print(f"\n{_c('Batch State:', GREEN)} {len(json_files)} student telemetry files stored under data/students/.")
    print(f"Run {_c('pytest tests/test_feynman_flow.py', CYAN)} to verify all test invariants.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Socratic Feynman Check CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default="run.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run command
    r = sub.add_parser("run", help="Run a Feynman Check session (live or stub)")
    r.add_argument("--stub", action="store_true", help="Use deterministic stubs (0 tokens, no key needed)")
    r.add_argument("--concept", default="virtual_memory", help="Concept ID (e.g. virtual_memory, deadlocks)")
    r.add_argument("--student-id", default="20231035053", help="Student registration ID")
    r.add_argument("--text", default=None, help="Initial explanation text (skips interactive prompt)")
    r.add_argument("--canned", choices=list(CANNED_STUDENTS.keys()), default="dilshan", help="Profile to use in stub mode")
    r.set_defaults(fn=cmd_run)

    # replay command
    rp = sub.add_parser("replay", help="Replay a past session's step-by-step history")
    rp.add_argument("run_id", help="The run_id to inspect")
    rp.set_defaults(fn=cmd_replay)

    # simulate-cohort command
    sc = sub.add_parser("simulate-cohort", help="Simulate Dilshan, Siva, and Bakia submissions")
    sc.set_defaults(fn=cmd_simulate_cohort)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
