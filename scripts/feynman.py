#!/usr/bin/env python3

"""

scripts/feynman.py - CLI Harness for the Socratic Feynman Check & Batch Gap Ping System.



Member 5: CLI Runner, Test Suite & Live Verification



Usage:

  python scripts/feynman.py run [--concept=<id>] [--stub] [--student-id=<id>]

  python scripts/feynman.py simulate-cohort [--stub]

  python scripts/feynman.py replay <run_id>



Commands:

  run               Run a single student Feynman Check session (interactive or stub).

  simulate-cohort   Automate the Dilshan, Siva, Bakia demo cohort.

  replay            Display the full SQLite audit trail for a run_id.

"""

from __future__ import annotations



import argparse

import json

import sys

import textwrap

from datetime import datetime, timezone

from pathlib import Path



# Ensure project root is on sys.path when run as a script

_ROOT = Path(__file__).resolve().parent.parent

if str(_ROOT) not in sys.path:

    sys.path.insert(0, str(_ROOT))



from slice import runner

from slice.config import settings as load_settings

from slice.records import RunState

from slice.store import Store



from demo.feynman.flow import build_flow

from demo.feynman.batch import run_batch_pipeline as run_batch_aggregation

from demo.feynman.stub import CANNED_STUDENTS, StubCompleter, get_canned_student



# ---------------------------------------------------------------------------

# Shared helpers

# ---------------------------------------------------------------------------



_DB_PATH = _ROOT / "feynman.db"





def _get_store() -> Store:

    return Store(str(_DB_PATH))





def _banner(title: str) -> None:

    width = 70

    print()

    print("=" * width)

    print(f"  {title}")

    print("=" * width)





def _section(title: str) -> None:

    print(f"\n{'-' * 60}")

    print(f"  {title}")

    print("-" * 60)





def _display_run_summary(store: Store, run_id: str) -> None:

    """Pretty-print key events from a finished run."""

    state    = store.get_state(run_id)

    verdicts = store.history(run_id, "verdict")

    probes   = store.history(run_id, "probe")

    subs     = store.history(run_id, "submission")

    rec      = store.latest(run_id, "session_record")



    print(f"\n  Run ID     : {run_id}")

    print(f"  Final State: {state.value.upper()}")



    if subs:

        print(f"\n  ?? Initial Submission:")

        print(textwrap.fill(subs[0].payload.get("text", ""),

                            width=68, initial_indent="    ", subsequent_indent="    "))



    for i, (v, p) in enumerate(zip(verdicts, probes)):

        print(f"\n  ?? Round {i + 1} ? Critic Verdict: {v.payload['verdict']}")

        flaw = v.payload.get("detected_flaw_tag")

        if flaw:

            print(f"     Flaw   : {flaw}")

        expl = v.payload.get("flaw_explanation", "")

        if expl:

            print(textwrap.fill(f"Explanation: {expl}",

                                width=68, initial_indent="     ", subsequent_indent="     "))

        print(f"\n  ?? Socratic Probe:")

        print(textwrap.fill(p.payload.get("counter_example_scenario", ""),

                            width=68, initial_indent="    ", subsequent_indent="    "))

        if i + 1 < len(subs):

            print(f"\n  ??  Student Revision:")

            print(textwrap.fill(subs[i + 1].payload.get("text", ""),

                                width=68, initial_indent="    ", subsequent_indent="    "))



    if verdicts:

        last_v = verdicts[-1].payload

        print(f"\n  ? Final Critic Verdict : {last_v['verdict']}")

        if last_v.get("detected_flaw_tag"):

            print(f"     Remaining Flaw Tag  : {last_v['detected_flaw_tag']}")



    if rec:

        print(f"\n  ?? Session Record:")

        print(f"     student_id     : {rec.get('student_id')}")

        print(f"     concept_id     : {rec.get('concept_id')}")

        print(f"     final_verdict  : {rec.get('final_verdict')}")

        print(f"     iteration_count: {rec.get('iteration_count')}")

        print(f"     tagged_fallacy : {rec.get('tagged_fallacy')}")





# ---------------------------------------------------------------------------

# Command: run

# ---------------------------------------------------------------------------



def cmd_run(args: argparse.Namespace) -> int:

    """Run a single student Feynman Check session."""

    concept_id = args.concept or "virtual_memory"

    use_stub   = args.stub

    student_id = args.student_id or "student_001"



    _banner(f"Feynman Check ? Concept: {concept_id}")



    settings = load_settings()

    store    = _get_store()



    if use_stub:

        profile = get_canned_student(student_id) or get_canned_student("dilshan")

        text              = profile["initial_text"]

        student_name      = profile["name"]

        actual_student_id = profile["student_id"]

        print(f"\n  [STUB MODE] Student: {student_name} ({actual_student_id})")

        print(f"  Concept  : {concept_id}")

        print(f"\n  ?? Pre-loaded submission:")

        print(textwrap.fill(text, width=68, initial_indent="    ", subsequent_indent="    "))

    else:

        actual_student_id = student_id

        student_name      = student_id

        print(f"\n  Student ID : {student_id}  |  Concept: {concept_id}")

        print("\n  Enter your explanation (press Enter twice to submit):")

        lines: list[str] = []

        try:

            while True:

                line = input()

                if line == "" and lines and lines[-1] == "":

                    break

                lines.append(line)

        except (KeyboardInterrupt, EOFError):

            print("\n  [Aborted]")

            return 1

        text = "\n".join(lines).strip()

        if not text:

            print("  ? No explanation provided.")

            return 1



    run_id = store.create_run(

        "feynman",

        meta={"student_id": str(actual_student_id),

              "student_name": student_name,

              "concept_id": concept_id},

    )

    store.append(run_id, "input",

                 {"student_id": str(actual_student_id), "concept_id": concept_id, "text": text},

                 produced_by="cli:run")



    flow        = build_flow(call=StubCompleter()) if use_stub else build_flow()

    print(f"\n  ?? Advancing state machine (run_id: {run_id}) ...")

    final_state = runner.advance(store, run_id, flow, settings)



    _section("Results")

    _display_run_summary(store, run_id)

    print(f"\n  Run complete ? {final_state.value.upper()}")

    print(f"  Replay: python scripts/feynman.py replay {run_id}\n")



    try:

        run_batch_aggregation()

    except Exception:

        pass



    return 0 if final_state is RunState.COMPLETE else 1





# ---------------------------------------------------------------------------

# Command: simulate-cohort

# ---------------------------------------------------------------------------



def cmd_simulate_cohort(args: argparse.Namespace) -> int:

    """Automate the Dilshan, Siva, Bakia demo cohort and trigger batch escalation."""

    _banner("Simulate Cohort ? Dilshan ? Siva ? Bakia")



    settings = load_settings()

    store    = _get_store()

    cohort   = ["dilshan", "siva", "bakia"]

    run_ids: list[str] = []



    for name in cohort:

        profile = CANNED_STUDENTS[name]

        _section(f"Student: {profile['name']} ({profile['student_id']})")



        run_id = store.create_run(

            "feynman",

            meta={"student_id": profile["student_id"],

                  "student_name": name,

                  "concept_id": profile["concept_id"]},

        )

        store.append(run_id, "input",

                     {"student_id": profile["student_id"],

                      "concept_id": profile["concept_id"],

                      "text": profile["initial_text"]},

                     produced_by="cli:simulate-cohort")



        final_state = runner.advance(store, run_id, build_flow(call=StubCompleter()), settings)

        rec = store.latest(run_id, "session_record")

        verdict = rec.get("final_verdict", "?") if rec else "?"

        fallacy = rec.get("tagged_fallacy", "none") if rec else "none"

        print(f"\n  ? State: {final_state.value.upper():12s}  verdict={verdict}  fallacy={fallacy}")

        run_ids.append(run_id)



    _section("Batch Aggregation & Escalation")

    try:

        result = run_batch_aggregation()

        if result:

            print("  ??  Escalation triggered ? check reports/ for INSTRUCTOR_ALERT_*.md")

        else:

            print("  ? No escalation threshold reached.")

    except Exception as exc:

        print(f"  ??  Batch error: {exc}")



    _section("Cohort Summary")

    for name, run_id in zip(cohort, run_ids):

        state   = store.get_state(run_id)

        rec     = store.latest(run_id, "session_record")

        verdict = rec.get("final_verdict", "?") if rec else "?"

        print(f"  {CANNED_STUDENTS[name]['name']:12s} ? {state.value:10s}  verdict={verdict}")



    print(f"\n  Database : {_DB_PATH}")

    print(f"  Replay   : python scripts/feynman.py replay <run_id>\n")

    return 0





# ---------------------------------------------------------------------------

# Command: replay

# ---------------------------------------------------------------------------



def cmd_replay(args: argparse.Namespace) -> int:

    """Display the full SQLite audit trail for a run_id."""

    run_id = args.run_id

    store  = _get_store()



    try:

        state = store.get_state(run_id)

    except KeyError:

        print(f"\n  ? Run not found: {run_id}  (db: {_DB_PATH})")

        return 1



    _banner(f"Replay Audit Trail ? {run_id}")

    print(f"  Final state: {state.value.upper()}")



    versions = store.replay(run_id)

    if not versions:

        print("  (no events recorded)")

        return 0



    print(f"\n  {'SEQ':>4}  {'KIND':<20}  {'PRODUCED_BY':<28}  PAYLOAD SUMMARY")

    print(f"  {'-'*4}  {'-'*20}  {'-'*28}  {'-'*34}")



    for v in versions:

        p = v.payload

        if v.kind == "submission":

            summary = f"sid={p.get('student_id')} iter={p.get('iteration')} text={p.get('text','')[:38]!r}"

        elif v.kind == "verdict":

            summary = f"verdict={p.get('verdict')} flaw={p.get('detected_flaw_tag')}"

        elif v.kind == "probe":

            summary = f"probe_id={p.get('probe_id')} scenario={p.get('counter_example_scenario','')[:30]!r}"

        elif v.kind == "session_record":

            summary = f"final={p.get('final_verdict')} iters={p.get('iteration_count')} fallacy={p.get('tagged_fallacy')}"

        elif v.kind == "failure":

            summary = f"kind={p.get('kind')} detail={p.get('detail','')[:45]!r}"

        elif v.kind == "input":

            summary = f"concept={p.get('concept_id')} text={p.get('text','')[:38]!r}"

        else:

            summary = str(p)[:60]

        print(f"  {v.seq:>4}  {v.kind:<20}  {v.produced_by:<28}  {summary}")



    if getattr(args, "verbose", False):

        print("\n  -- Full payloads --")

        for v in versions:

            print(f"\n  [{v.seq}] {v.kind} (by {v.produced_by})")

            print(json.dumps(v.payload, indent=4))



    print()

    return 0





# ---------------------------------------------------------------------------

# Argument parser & entry point

# ---------------------------------------------------------------------------



def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(

        prog="feynman",

        description="Socratic Feynman Check & Batch Gap Ping ? CLI",

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog=textwrap.dedent("""\

            Examples:

              python scripts/feynman.py run --stub --student-id=dilshan

              python scripts/feynman.py run --concept=deadlocks --stub

              python scripts/feynman.py simulate-cohort

              python scripts/feynman.py replay run_abc123def456

        """),

    )

    sub = parser.add_subparsers(dest="command", required=True)



    p_run = sub.add_parser("run", help="Run a single student session.")

    p_run.add_argument("--concept", default="virtual_memory",

                       help="Concept ID (virtual_memory | deadlocks). Default: virtual_memory")

    p_run.add_argument("--stub", action="store_true",

                       help="Deterministic stub ? no API key required.")

    p_run.add_argument("--student-id", dest="student_id", default=None,

                       help="Student ID or canned name (dilshan | siva | bakia | mastered | adversarial).")



    p_cohort = sub.add_parser("simulate-cohort", help="Automate the Dilshan/Siva/Bakia demo.")

    p_cohort.add_argument("--stub", action="store_true", default=True)



    p_replay = sub.add_parser("replay", help="Show full audit trail for a run.")

    p_replay.add_argument("run_id", help="Run ID to replay.")

    p_replay.add_argument("--verbose", "-v", action="store_true",

                          help="Also print full JSON payloads.")



    return parser





def main() -> int:

    parser = build_parser()

    args   = parser.parse_args()

    dispatch = {"run": cmd_run, "simulate-cohort": cmd_simulate_cohort, "replay": cmd_replay}

    try:

        return dispatch[args.command](args)

    except KeyboardInterrupt:

        print("\n  [Interrupted]")

        return 130





if __name__ == "__main__":

    sys.exit(main())

