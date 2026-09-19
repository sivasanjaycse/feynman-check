#!/usr/bin/env python3
"""
scripts/feynman.py - Interactive CLI Runner & Test Harness for Socratic Feynman Check.

Usage:
    # 1. Test offline with canned responses (zero tokens, no API key required):
    python scripts/feynman.py run --stub

    # 2. Test live with OpenRouter LLM (enter your own explanation interactively):
    python scripts/feynman.py run --concept=virtual_memory

    # 3. Test any other concept (proving topic-agnostic design):
    python scripts/feynman.py run --concept=deadlocks

    # 4. Test a brand-new concept (just drop a .md in data/concepts/ first):
    python scripts/feynman.py run --stub --concept=cpu_scheduling

    # 5. Simulate the cohort (Dilshan, Siva, Bakia) for virtual_memory:
    python scripts/feynman.py simulate-cohort

    # 6. Simulate cohort for any other concept:
    python scripts/feynman.py simulate-cohort --concept=deadlocks

    # 7. Replay an entire session's audit trail:
    python scripts/feynman.py replay <run_id>

    # 8. List all available concept files:
    python scripts/feynman.py list-concepts
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
from demo.feynman.stub import CANNED_STUDENTS, StubCompleter, stub_complete, get_canned_cohort_for_concept

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
    try:
        ground_truth = load_concept_ground_truth(concept_id)
    except FileNotFoundError as e:
        print(_c(f"\nError: {e}", RED))
        return 1
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
        "interactive": True if (not args.stub or getattr(args, "interactive", False)) else False,
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
    """Simulates 3 cohort members demonstrating batch accumulation for any concept."""
    concept_id = getattr(args, "concept", "virtual_memory") or "virtual_memory"
    print(f"\n{_c('=== Simulating Cohort Submissions ===', BOLD)}")
    print(f"{_c('Concept:', DIM)} {BOLD}{concept_id}{RESET}")
    store = Store(args.db)
    st = load_settings()

    cohort_profiles = get_canned_cohort_for_concept(concept_id)
    if not cohort_profiles:
        print(_c(f"No canned cohort profiles found for concept '{concept_id}'.", RED))
        print("Tip: ensure data/concepts/{concept_id}.md exists with fallacy tags defined.")
        return 1

    for profile in cohort_profiles:
        sid = profile["student_id"]
        name = profile.get("name", sid)
        initial_text = profile["initial_text"]
        print(f"\n---> Ingesting student: {_c(name.upper(), BOLD)} ({sid})")

        run_id = store.create_run("feynman", meta={"student_id": sid, "student_name": name.lower()})
        store.append(
            run_id,
            "input",
            {"student_id": sid, "concept_id": concept_id, "text": initial_text},
            produced_by="test",
        )

        flow = build_flow(call=StubCompleter())
        state = runner.advance(store, run_id, flow, st)

        session_recs = store.history(run_id, "session_record")
        if session_recs:
            session_rec = session_recs[-1].payload
            print(f"     Status: {_c(session_rec['final_verdict'], GREEN)} | Flaw: {_c(str(session_rec['tagged_fallacy']), AMBER)}")
        else:
            print(f"     State: {_c(str(state), AMBER)}")

    # Check student JSON files
    students_dir = Path("data/students")
    json_files = list(students_dir.glob("*.json")) if students_dir.exists() else []
    print(f"\n{_c('Batch State:', GREEN)} {len(json_files)} student telemetry file(s) stored under data/students/.")
    print(f"Run {_c('pytest tests/test_feynman_flow.py', CYAN)} to verify all test invariants.")
    return 0


def cmd_list_concepts(args: argparse.Namespace) -> int:
    """Lists all available concept files in data/concepts/."""
    concepts_dir = Path("data/concepts")
    if not concepts_dir.exists():
        print(_c("data/concepts/ directory not found.", RED))
        return 1
    md_files = sorted(concepts_dir.glob("*.md"))
    if not md_files:
        print(_c("No concept files found in data/concepts/.", AMBER))
        print("Create a .md file there (e.g., data/concepts/cpu_scheduling.md) to add a new concept.")
        return 0
    print(f"\n{_c('=== Available Concepts ===', BOLD)}")
    for f in md_files:
        concept_id = f.stem
        print(f"  {_c(concept_id, CYAN):40s}  {_c(f'python scripts/feynman.py run --concept={concept_id}', DIM)}")
    print(f"\n{_c('To add a new concept:', DIM)} drop a .md file with fallacy tags into data/concepts/")
    print(f"{_c('No Python source changes required.', GREEN)}\n")
    return 0


def cmd_discover_fallacies(args: argparse.Namespace) -> int:
    """Runs the Fallacy Discovery Agent on a concept file."""
    from demo.feynman.discover import discover_fallacies

    concept_id = args.concept
    print(f"\n{_c('=== Fallacy Discovery Agent ===', BOLD)}")
    print(f"{_c('Concept:', DIM)} {BOLD}{concept_id}{RESET}")

    if args.stub:
        from demo.feynman.stub import StubCompleter
        call = StubCompleter()
        print(f"{_c('Mode:', DIM)} STUB (Offline, 0 tokens)")
    else:
        st = load_settings()
        if not st.api_key:
            print(_c("Error: No OPENROUTER_API_KEY found in .env.", RED))
            print("Run with --stub to test without an API key.")
            return 1
        from slice.llm import complete as call
        print(f"{_c('Mode:', DIM)} LIVE ({st.model})")

    try:
        result = discover_fallacies(
            concept_id,
            call=call,
            force=args.force,
            write=not args.dry_run,
            db_path=args.db,
        )
    except FileNotFoundError as e:
        print(_c(f"\nError: {e}", RED))
        return 1
    except Exception as e:
        print(_c(f"\nError discovering fallacies: {e}", RED))
        return 1

    print(f"\n{_c('Discovered Fallacy Patterns:', GREEN)}")
    for i, f in enumerate(result.fallacies, start=1):
        print(f"\n  {_c(f'{i}. [{f.tag}]', AMBER)}")
        print(f"     {_c('Description:', DIM)} {f.description}")
        print(f"     {_c('Flawed claim:', DIM)} \"{f.example_claim}\"")
        print(f"     {_c('Counter:', DIM)} {f.pedagogical_counter}")

    if result.opening_question:
        print(f"\n  {_c('Diagnostic Opening Question:', CYAN)} {result.opening_question}")

    if args.dry_run:
        print(f"\n{_c('[Dry Run] No files modified.', AMBER)}\n")
    else:
        print(f"\n{_c('[Saved] Fallacies successfully written to data/concepts/' + concept_id + '.md', GREEN)}\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Socratic Feynman Check CLI — Concept-Agnostic Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default="run.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # run command
    r = sub.add_parser("run", help="Run a Feynman Check session (live or stub) for any concept")
    r.add_argument("--stub", action="store_true", help="Use deterministic stubs (0 tokens, no key needed)")
    r.add_argument("--interactive", "-i", action="store_true", help="Prompt interactively for revisions even in stub mode")
    r.add_argument("--concept", default="virtual_memory",
                   help="Concept ID matching a file in data/concepts/ (e.g. virtual_memory, deadlocks, cpu_scheduling)")
    r.add_argument("--student-id", default="20231035053", help="Student registration ID")
    r.add_argument("--text", default=None, help="Initial explanation text (skips interactive prompt)")
    r.add_argument("--canned", choices=list(CANNED_STUDENTS.keys()), default="dilshan",
                   help="Canned student profile to use in stub mode (plain names default to virtual_memory; use e.g. dilshan_deadlocks for deadlocks)")
    r.set_defaults(fn=cmd_run)

    # replay command
    rp = sub.add_parser("replay", help="Replay a past session's step-by-step history")
    rp.add_argument("run_id", help="The run_id to inspect")
    rp.set_defaults(fn=cmd_replay)

    # simulate-cohort command
    sc = sub.add_parser("simulate-cohort",
                        help="Simulate Dilshan, Siva, and Bakia for any concept (triggers batch escalation)")
    sc.add_argument("--concept", default="virtual_memory",
                    help="Concept ID to simulate cohort for (e.g. virtual_memory, deadlocks, or any new concept in data/concepts/)")
    sc.set_defaults(fn=cmd_simulate_cohort)

    # list-concepts command
    lc = sub.add_parser("list-concepts", help="List all available concept files in data/concepts/")
    lc.set_defaults(fn=cmd_list_concepts)

    # discover-fallacies command (Fallacy Discovery Agent)
    df = sub.add_parser("discover-fallacies", help="Run the Fallacy Discovery Agent on a concept file")
    df.add_argument("--concept", required=True,
                    help="Concept ID (e.g., oop_lecture_1)")
    df.add_argument("--stub", action="store_true",
                    help="Use stub (offline, 0 tokens, no API call)")
    df.add_argument("--force", action="store_true",
                    help="Force re-discovery and overwrite existing Section 2")
    df.add_argument("--dry-run", action="store_true",
                    help="Show discovered fallacies without modifying the file")
    df.set_defaults(fn=cmd_discover_fallacies)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
